from __future__ import annotations

from typing import Any, Dict, List, Optional

import asyncpg

from domain.entities import AgentConnection
from domain.access import Principal
from domain.errors import Conflict, NotFound
from repositories.agents import AgentRepository
from repositories.connections import ConnectionRepository
from repositories.unit_of_work import UnitOfWork
from .versions import VersionRecorder


class ConnectionService:
    """Who may call whom. A connection is part of the calling agent's behaviour, so each change is a version of it."""

    def __init__(self, connections: ConnectionRepository, agents: AgentRepository, recorder: VersionRecorder, uow: UnitOfWork):
        self.connections, self.agents, self.recorder, self.uow = connections, agents, recorder, uow

    async def list(self, agent_id: Optional[int] = None) -> List[AgentConnection]:
        return await self.connections.list(agent_id)

    async def _existing(self, connection_id: int) -> AgentConnection:
        connection = await self.connections.get(connection_id)
        if not connection:
            raise NotFound("Agent connection not found")
        return connection

    async def get(self, connection_id: int) -> AgentConnection:
        return await self._existing(connection_id)

    async def create(self, principal: Principal, data) -> AgentConnection:
        if data.agent1_id == data.agent2_id:
            raise Conflict("An agent cannot be connected to itself")
        for agent_id in (data.agent1_id, data.agent2_id):
            if not await self.agents.get(agent_id):
                raise NotFound(f"Agent {agent_id} not found")
        try:
            async with self.uow.transaction():
                connection = await self.connections.insert(data.agent1_id, data.agent2_id, data.description)
                await self.recorder.record(data.agent1_id, f"may call agent {data.agent2_id}", principal.token.id)
        except asyncpg.UniqueViolationError:
            raise Conflict(f"Agent {data.agent1_id} is already connected to agent {data.agent2_id}")
        except asyncpg.ForeignKeyViolationError:  # an agent deleted meanwhile
            raise NotFound("Agent not found")
        return connection

    async def update(self, principal: Principal, connection_id: int, data) -> AgentConnection:
        connection = await self._existing(connection_id)
        async with self.uow.transaction():
            updated = await self.connections.update(connection_id, data.description)
            await self.recorder.record(connection.agent1_id, f"description of agent {connection.agent2_id} changed", principal.token.id)
        if not updated:
            raise NotFound("Agent connection not found")
        return updated

    async def delete(self, principal: Principal, connection_id: int) -> AgentConnection:
        connection = await self._existing(connection_id)
        async with self.uow.transaction():
            deleted = await self.connections.delete(connection_id)
            await self.recorder.record(connection.agent1_id, f"may no longer call agent {connection.agent2_id}", principal.token.id)
        if not deleted:
            raise NotFound("Agent connection not found")
        return deleted

    async def connected_agents(self, agent_id: int) -> List[Dict[str, Any]]:
        """The agents `agent_id` may call: id, name and what the connection says about each."""
        found = []
        for connection in await self.connections.list(agent_id):
            agent = await self.agents.get(connection.agent2_id)
            if agent is not None:
                found.append({"id": agent.id, "name": agent.name, "description": connection.description})
        return found

    async def has_connection(self, caller_id: int, target_id: int) -> bool:
        return await self.connections.find(caller_id, target_id) is not None
