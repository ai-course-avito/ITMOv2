import json
from typing import Optional, Sequence

from ..context import PostgresConnectionWithContext
from ..models import DEFAULT_BASE_URL, AgentVersion, fingerprint


def normal(snapshot: dict) -> dict:
    """What a snapshot made before a key existed meant: a model with no connection of its own (base_url, use_proxy,
    a key) had the default one, and an agent with no connections to other agents called none. Without this an old
    latest version would differ from every new snapshot, and the next change would record a needless version."""
    defaults = {
        "model_connection": {
            "base_url": DEFAULT_BASE_URL,
            "use_proxy": True,
            "own_api_token": None,
        },
        "connections": [],
    }
    missing = {key: value for key, value in defaults.items() if key not in snapshot}
    return {**snapshot, **missing} if missing else snapshot


def diff_snapshots(old: dict, new: dict) -> dict:
    """What differs between two snapshots: {key: {"from": ..., "to": ...}}."""
    old, new = normal(old), normal(new)
    return {
        key: {"from": old.get(key), "to": new.get(key)}
        for key in sorted(set(old) | set(new))
        if old.get(key) != new.get(key)
    }


class AgentVersionMethods(PostgresConnectionWithContext):
    """The history of an agent. A version is a snapshot of everything that decides
    how the agent behaves, with copies (not references) of its model and MCP server
    configs: those records can be edited later, and a rollback must bring back the
    behaviour of that time."""

    async def build_agent_snapshot(self, agent_id: int) -> Optional[dict]:
        query = """
            SELECT
                a.prompt,
                a.model_id,
                m.request_json AS model,
                m.base_url AS _base_url,
                m.use_proxy AS _use_proxy,
                m.api_token AS _api_token,
                a.config,
                COALESCE((
                    SELECT jsonb_agg(
                        jsonb_build_object('id', s.id, 'config', s.config) ORDER BY s.id
                    )
                    FROM agent_mcp_servers x JOIN mcp_servers s ON s.id = x.mcp_server_id
                    WHERE x.agent_id = a.id
                ), '[]'::jsonb) AS mcp_servers,
                COALESCE((
                    SELECT jsonb_agg(
                        jsonb_build_object('agent2_id', c.agent2_id, 'description', c.description)
                        ORDER BY c.agent2_id
                    )
                    FROM agent_connections c
                    WHERE c.agent1_id = a.id
                ), '[]'::jsonb) AS connections
            FROM agents a JOIN models m ON m.id = a.model_id
            WHERE a.id = $1
        """
        row = await self.fetch_one(query, (agent_id,))
        if row is None:
            return None
        connection = {
            "base_url": row.pop("_base_url") or DEFAULT_BASE_URL,
            "use_proxy": row.pop("_use_proxy"),
            # the key itself is not copied into a version: only a mark of it, so that a change of key shows as a change
            "own_api_token": fingerprint(row.pop("_api_token")),
        }
        snapshot = {
            key: json.loads(value)
            if isinstance(value, str) and key != "prompt"
            else value
            for key, value in row.items()
        }
        snapshot["model_connection"] = connection
        return snapshot

    async def get_agent_versions(self, agent_id: int) -> Sequence[AgentVersion]:
        """Newest first."""
        query = "SELECT * FROM agent_versions WHERE agent_id=$1 ORDER BY number DESC"
        return (await self.fetch_all(query, (agent_id,), AgentVersion)) or []

    async def get_agent_version(
        self, agent_id: int, number: int
    ) -> Optional[AgentVersion]:
        query = "SELECT * FROM agent_versions WHERE agent_id=$1 AND number=$2"
        return await self.fetch_one(query, (agent_id, number), AgentVersion)

    async def get_latest_version_number(self, agent_id: int) -> Optional[int]:
        row = await self.fetch_one(
            "SELECT max(number) AS n FROM agent_versions WHERE agent_id=$1", (agent_id,)
        )
        return row["n"] if row else None

    async def record_agent_version(
        self,
        agent_id: int,
        comment: Optional[str] = None,
        token_id: Optional[int] = None,
    ) -> Optional[AgentVersion]:
        """Add a version if the agent differs from its latest one (None otherwise).

        Versions of one agent are numbered one at a time. Call this in the transaction
        that changed the agent, so a change and its version stand or fall together."""
        async with self.transaction():
            await self.lock(f"agent-versions:{agent_id}")

            snapshot = await self.build_agent_snapshot(agent_id)
            if snapshot is None:
                return None

            latest = await self.fetch_one(
                "SELECT * FROM agent_versions WHERE agent_id=$1 ORDER BY number DESC LIMIT 1",
                (agent_id,),
                AgentVersion,
            )
            if latest is not None and normal(latest.snapshot) == snapshot:
                return None

            query = """
                INSERT INTO agent_versions (agent_id, number, snapshot, comment, created_by_token_id)
                VALUES (
                    $1,
                    (SELECT COALESCE(max(number), 0) + 1 FROM agent_versions WHERE agent_id=$1),
                    $2, $3, $4
                )
                RETURNING *
            """
            return await self.fetch_one(
                query, (agent_id, snapshot, comment, token_id), AgentVersion
            )

    async def agent_ids_using_model(self, model_id: int) -> Sequence[int]:
        rows = await self.fetch_all(
            "SELECT id FROM agents WHERE model_id=$1", (model_id,)
        )
        return [row["id"] for row in rows or []]

    async def agent_ids_using_mcp_server(self, mcp_server_id: int) -> Sequence[int]:
        rows = await self.fetch_all(
            "SELECT agent_id FROM agent_mcp_servers WHERE mcp_server_id=$1",
            (mcp_server_id,),
        )
        return [row["agent_id"] for row in rows or []]

    async def record_versions_of(
        self, agent_ids: Sequence[int], comment: str, token_id: Optional[int] = None
    ) -> None:
        for agent_id in agent_ids:
            await self.record_agent_version(agent_id, comment, token_id)

    async def rollback_agent(
        self,
        agent_id: int,
        number: int,
        comment: Optional[str] = None,
        token_id: Optional[int] = None,
    ) -> Optional[AgentVersion]:
        """Make the agent what version `number` was; the result is a new version.

        The model and MCP servers of that time are used again when they still are what
        they were; otherwise new records with the old content are created, so the
        records that other agents use are left alone."""
        async with self.transaction():  # a rollback that fails halfway undoes itself
            return await self._rollback(agent_id, number, comment, token_id)

    async def _rollback(
        self,
        agent_id: int,
        number: int,
        comment: Optional[str],
        token_id: Optional[int],
    ) -> Optional[AgentVersion]:
        version = await self.get_agent_version(agent_id, number)
        if version is None:
            return None
        snapshot = version.snapshot

        model = await self.get_model(snapshot["model_id"])
        # versions made before connections existed were made with the defaults
        wanted_connection = snapshot.get("model_connection") or {"base_url": DEFAULT_BASE_URL, "use_proxy": True}
        if (
            model is None
            or model.request_json != snapshot["model"]
            or model.base_url != wanted_connection["base_url"]
            or model.use_proxy != wanted_connection["use_proxy"]
        ):
            # the key is not in a version: a copy of the model keeps the key of the record it replaces (if there is one)
            model = await self.create_model(
                snapshot["model"],
                base_url=wanted_connection["base_url"],
                use_proxy=wanted_connection["use_proxy"],
                api_token=model.api_token if model else None,
            )

        wanted = []
        for saved in snapshot.get("mcp_servers", []):
            server = await self.get_mcp_server(saved["id"])
            if server is None or server.config != saved["config"]:
                server = await self.create_mcp_server(saved["config"])
            wanted.append(server.id)

        attached = {s.id for s in await self.get_agent_mcp_servers(agent_id)}
        for mcp_server_id in attached - set(wanted):
            await self.remove_agent_mcp_server(agent_id, mcp_server_id)
        for mcp_server_id in wanted:
            await self.add_agent_mcp_server(agent_id, mcp_server_id)

        # the agents it could call then (none for a version made before there were connections)
        await self.set_agent_connections(agent_id, normal(snapshot)["connections"])

        await self.fetch_one(
            "UPDATE agents SET prompt=$1, model_id=$2, config=$3 WHERE id=$4 RETURNING id",
            (snapshot["prompt"], model.id, snapshot["config"], agent_id),
        )
        return await self.record_agent_version(
            agent_id, comment or f"rolled back to version {number}", token_id
        )
