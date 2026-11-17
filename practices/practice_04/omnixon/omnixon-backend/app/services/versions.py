from __future__ import annotations

from typing import Optional, Sequence

from domain.entities import AgentVersion
from repositories.unit_of_work import UnitOfWork
from repositories.versions import VersionRepository


class VersionRecorder:
    """Writes down what an agent has become: a version is added only when its snapshot differs from the latest one.

    Versions of one agent are numbered one at a time (under a lock). Call it in the transaction that changed the agent, so that a change
    and its version stand or fall together."""

    def __init__(self, versions: VersionRepository, uow: UnitOfWork):
        self.versions, self.uow = versions, uow

    async def record(self, agent_id: int, comment: Optional[str], token_id: Optional[int]) -> Optional[AgentVersion]:
        from domain.agents import AgentSnapshot

        async with self.uow.transaction():
            await self.uow.lock(f"agent-versions:{agent_id}")
            snapshot = await self.versions.snapshot_of(agent_id)
            if snapshot is None:
                return None
            latest = await self.versions.latest(agent_id)
            if latest is not None and AgentSnapshot.from_raw(latest.snapshot) == snapshot:
                return None
            return await self.versions.insert(agent_id, snapshot, comment, token_id)

    async def record_many(self, agent_ids: Sequence[int], comment: str, token_id: Optional[int]) -> None:
        for agent_id in agent_ids:
            await self.record(agent_id, comment, token_id)


class VersionService:
    """Reading the history of an agent, comparing versions, and going back to one."""

    def __init__(self, versions, agents, models, servers, connections, recorder: VersionRecorder, policy, uow):
        self.versions, self.agents, self.models, self.servers = versions, agents, models, servers
        self.connections, self.recorder, self.policy, self.uow = connections, recorder, policy, uow

    async def _agent(self, principal, agent_id: int) -> None:
        from domain.errors import NotFound

        self.policy.ensure_agent(principal, agent_id)
        if not await self.agents.get(agent_id):
            raise NotFound("Agent not found")

    async def _version(self, principal, agent_id: int, number: int) -> AgentVersion:
        from domain.errors import NotFound

        await self._agent(principal, agent_id)
        version = await self.versions.get(agent_id, number)
        if not version:
            raise NotFound("Version not found")
        return version

    async def list(self, principal, agent_id: int):
        await self._agent(principal, agent_id)
        return await self.versions.list(agent_id)

    async def get(self, principal, agent_id: int, number: int) -> AgentVersion:
        return await self._version(principal, agent_id, number)

    async def diff(self, principal, agent_id: int, number: int, to: Optional[int]) -> dict:
        from domain.agents import AgentSnapshot

        old = await self._version(principal, agent_id, number)
        target = to if to is not None else await self.versions.latest_number(agent_id)
        new = await self._version(principal, agent_id, target)
        return {
            "agent_id": agent_id,
            "from_version": old.number,
            "to_version": new.number,
            "changes": AgentSnapshot.from_raw(old.snapshot).diff(AgentSnapshot.from_raw(new.snapshot)),
        }

    async def rollback(self, principal, agent_id: int, to: int, comment: Optional[str]) -> AgentVersion:
        """Make the agent what version `to` was; the result is a new version (or the latest one, if the agent already is that)."""
        await self._version(principal, agent_id, to)
        async with self.uow.transaction():  # a rollback that fails halfway undoes itself
            version = await self._restore(agent_id, to, comment, principal.token.id)
        if version is None:
            version = await self.versions.get(agent_id, await self.versions.latest_number(agent_id))
        return version

    async def _restore(self, agent_id: int, number: int, comment: Optional[str], token_id: int) -> Optional[AgentVersion]:
        from domain.agents import AgentSnapshot
        from domain.models import DEFAULT_BASE_URL

        snapshot = AgentSnapshot.from_raw((await self.versions.get(agent_id, number)).snapshot).raw
        model = await self.models.get(snapshot["model_id"])
        wanted_connection = snapshot["model_connection"]
        if (
            model is None
            or model.request_json != snapshot["model"]
            or model.base_url != (wanted_connection["base_url"] or DEFAULT_BASE_URL)
            or model.use_proxy != wanted_connection["use_proxy"]
        ):
            # the key is not in a version: a copy of the model keeps the key of the record it replaces (if there is one)
            model = await self.models.insert(
                snapshot["model"],
                base_url=wanted_connection["base_url"],
                use_proxy=wanted_connection["use_proxy"],
                api_token=model.api_token if model else None,
            )

        wanted = []
        for saved in snapshot.get("mcp_servers", []):
            server = await self.servers.get(saved["id"])
            if server is None or server.config != saved["config"]:
                server = await self.servers.insert(saved["config"])
            wanted.append(server.id)

        attached = {s.id for s in await self.servers.of_agent(agent_id)}
        for server_id in attached - set(wanted):
            await self.servers.detach(agent_id, server_id)
        for server_id in wanted:
            await self.servers.attach(agent_id, server_id)

        # the agents it could call then (none for a version made before there were connections)
        await self.connections.replace_of(agent_id, snapshot["connections"])
        await self.agents.set_behaviour(agent_id, snapshot["prompt"], model.id, snapshot["config"])
        return await self.recorder.record(agent_id, comment or f"rolled back to version {number}", token_id)
