from __future__ import annotations

import json
from typing import List, Optional

from domain.entities import AgentVersion
from domain.agents import AgentSnapshot
from domain.models import DEFAULT_BASE_URL, ModelConnection
from .base import Repository

_SNAPSHOT = """
    SELECT
        a.prompt,
        a.model_id,
        m.request_json AS model,
        m.base_url AS _base_url,
        m.use_proxy AS _use_proxy,
        m.api_token AS _api_token,
        a.config,
        COALESCE((
            SELECT jsonb_agg(jsonb_build_object('id', s.id, 'config', s.config) ORDER BY s.id)
            FROM agent_mcp_servers x JOIN mcp_servers s ON s.id = x.mcp_server_id
            WHERE x.agent_id = a.id
        ), '[]'::jsonb) AS mcp_servers,
        COALESCE((
            SELECT jsonb_agg(jsonb_build_object('agent2_id', c.agent2_id, 'description', c.description) ORDER BY c.agent2_id)
            FROM agent_connections c
            WHERE c.agent1_id = a.id
        ), '[]'::jsonb) AS connections
    FROM agents a JOIN models m ON m.id = a.model_id
    WHERE a.id = $1
"""


class VersionRepository(Repository):
    """The history of an agent. A version holds a snapshot with copies (not references) of its model and MCP server configs."""

    async def snapshot_of(self, agent_id: int) -> Optional[AgentSnapshot]:
        """What the agent is now, as a snapshot (None: no such agent)."""
        row = await self.db.fetch_one(_SNAPSHOT, (agent_id,))
        if row is None:
            return None
        connection = ModelConnection(row.pop("_base_url") or DEFAULT_BASE_URL, row.pop("_use_proxy"), row.pop("_api_token"))
        snapshot = {key: json.loads(value) if isinstance(value, str) and key != "prompt" else value for key, value in row.items()}
        # the key itself is not copied into a version: only a mark of it, so that a change of key shows as a change
        snapshot["model_connection"] = {"base_url": connection.base_url, "use_proxy": connection.use_proxy, "own_api_token": connection.fingerprint()}
        return AgentSnapshot.from_raw(snapshot)

    async def latest(self, agent_id: int) -> Optional[AgentVersion]:
        return await self.db.fetch_one(
            "SELECT * FROM agent_versions WHERE agent_id=$1 ORDER BY number DESC LIMIT 1", (agent_id,), AgentVersion
        )

    async def latest_number(self, agent_id: int) -> Optional[int]:
        row = await self.db.fetch_one("SELECT max(number) AS n FROM agent_versions WHERE agent_id=$1", (agent_id,))
        return row["n"] if row else None

    async def list(self, agent_id: int) -> List[AgentVersion]:
        """Newest first."""
        return await self.db.fetch_all("SELECT * FROM agent_versions WHERE agent_id=$1 ORDER BY number DESC", (agent_id,), AgentVersion)

    async def get(self, agent_id: int, number: int) -> Optional[AgentVersion]:
        return await self.db.fetch_one("SELECT * FROM agent_versions WHERE agent_id=$1 AND number=$2", (agent_id, number), AgentVersion)

    async def insert(self, agent_id: int, snapshot: AgentSnapshot, comment: Optional[str], token_id: Optional[int]) -> AgentVersion:
        """The next number of the agent (call it under the agent's lock, in the transaction that changed the agent)."""
        return await self.db.fetch_one(
            """
            INSERT INTO agent_versions (agent_id, number, snapshot, comment, created_by_token_id)
            VALUES ($1, (SELECT COALESCE(max(number), 0) + 1 FROM agent_versions WHERE agent_id=$1), $2, $3, $4)
            RETURNING *
            """,
            (agent_id, snapshot.raw, comment, token_id),
            AgentVersion,
        )
