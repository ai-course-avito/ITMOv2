from __future__ import annotations

from typing import List

from database.models import MCPServer
from domain.access import AccessPolicy, Principal
from domain.errors import NotFound
from repositories.agents import AgentRepository
from repositories.models import McpServerRepository
from repositories.unit_of_work import UnitOfWork
from .versions import VersionRecorder


class McpServerService:
    def __init__(self, servers: McpServerRepository, agents: AgentRepository, recorder: VersionRecorder, policy: AccessPolicy, uow: UnitOfWork):
        self.servers, self.agents, self.recorder, self.policy, self.uow = servers, agents, recorder, policy, uow

    async def list(self) -> List[MCPServer]:
        return await self.servers.list()

    async def _existing(self, server_id: int) -> MCPServer:
        server = await self.servers.get(server_id)
        if not server:
            raise NotFound("MCP server not found")
        return server

    async def create(self, principal: Principal, data) -> MCPServer:
        agent_id = data.agent_id
        if not principal.is_admin:
            agent_id = self.policy.agent_scope(principal, agent_id)  # a user token always gives it to its own agent
        elif agent_id is not None and not await self.agents.get(agent_id):
            raise NotFound("Agent not found")
        async with self.uow.transaction():
            created = await self.servers.insert(data.config, data.name)
            if agent_id is not None:
                await self.servers.attach(agent_id, created.id)
                await self.recorder.record(agent_id, f"MCP server {created.id} created", principal.token.id)
        return created

    async def get(self, principal: Principal, server_id: int) -> MCPServer:
        server = await self._existing(server_id)
        self.policy.ensure_mcp_use(principal, await self.servers.agents_using(server_id), change=False)
        return server

    async def update(self, principal: Principal, server_id: int, data) -> MCPServer:
        await self._existing(server_id)
        self.policy.ensure_mcp_use(principal, await self.servers.agents_using(server_id), change=True)
        async with self.uow.transaction():
            server = await self.servers.update(server_id, data.config, data.name)
            if not server:
                raise NotFound("MCP server not found")
            await self.recorder.record_many(await self.servers.agents_using(server_id), f"MCP server {server_id} updated", principal.token.id)
        return server

    async def delete(self, principal: Principal, server_id: int) -> MCPServer:
        await self._existing(server_id)
        self.policy.ensure_mcp_use(principal, await self.servers.agents_using(server_id), change=True)
        async with self.uow.transaction():
            agent_ids = await self.servers.agents_using(server_id)  # detached by the delete
            server = await self.servers.delete(server_id)
            if not server:
                raise NotFound("MCP server not found")
            await self.recorder.record_many(agent_ids, f"MCP server {server_id} deleted", principal.token.id)
        return server
