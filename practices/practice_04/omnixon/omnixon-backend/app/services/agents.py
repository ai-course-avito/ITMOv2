from __future__ import annotations

from typing import List

import asyncpg

from config import AgentDefaults
from database.models import Agent, MCPServer
from domain.access import AccessPolicy, Principal
from domain.errors import Conflict, NotFound
from repositories.agents import AgentRepository
from repositories.connections import ConnectionRepository
from repositories.models import McpServerRepository
from repositories.unit_of_work import UnitOfWork
from repositories.versions import VersionRepository
from .versions import VersionRecorder


class AgentService:
    def __init__(
        self,
        agents: AgentRepository,
        versions: VersionRepository,
        servers: McpServerRepository,
        connections: ConnectionRepository,
        recorder: VersionRecorder,
        policy: AccessPolicy,
        uow: UnitOfWork,
        defaults: AgentDefaults,
    ):
        self.agents, self.versions, self.servers, self.connections = agents, versions, servers, connections
        self.recorder, self.policy, self.uow, self.defaults = recorder, policy, uow, defaults

    async def list(self) -> List[Agent]:
        return await self.agents.list()

    async def _own_or_any(self, principal: Principal, agent_id: int) -> Agent:
        self.policy.ensure_agent(principal, agent_id)
        agent = await self.agents.get(agent_id)
        if not agent:
            raise NotFound("Agent not found")
        return agent

    async def get(self, principal: Principal, agent_id: int) -> Agent:
        return await self._own_or_any(principal, agent_id)

    async def create(self, principal: Principal, data) -> Agent:
        """`config` is merged over the default {"tools": [...]}; version 1 is recorded."""
        settings = {"tools": list(self.defaults.tools)}
        settings.update({k: v for k, v in (data.config.changes() if data.config else {}).items() if v is not None})
        try:
            async with self.uow.transaction():  # the agent and its first version
                agent = await self.agents.insert(data.name, data.prompt, data.model_id, settings)
                await self.recorder.record(agent.id, data.comment or "created", principal.token.id)
        except asyncpg.ForeignKeyViolationError:
            raise NotFound("Model not found")
        return agent

    async def update(self, principal: Principal, agent_id: int, data) -> Agent:
        self.policy.ensure_agent(principal, agent_id)
        try:
            async with self.uow.transaction():  # the change and its version stand or fall together
                await self.uow.lock(f"agent-versions:{agent_id}")  # so the version check holds
                if data.expected_version is not None:
                    latest = await self.versions.latest_number(agent_id)
                    if latest is not None and latest != data.expected_version:
                        raise Conflict(f"The agent is at version {latest}, not {data.expected_version}")
                agent = await self.agents.update(
                    agent_id,
                    name=data.name,
                    prompt=data.prompt,
                    model_id=data.model_id,
                    config_changes=data.config.changes() if data.config is not None else None,
                )
                if not agent:
                    raise NotFound("Agent not found")
                await self.recorder.record(agent_id, data.comment or "updated", principal.token.id)
        except asyncpg.ForeignKeyViolationError:
            raise NotFound("Model not found")
        return agent

    async def delete(self, principal: Principal, agent_id: int) -> Agent:
        try:
            async with self.uow.transaction():
                # the agents that could call it lose that: a change of their behaviour, so a version of each
                callers = await self.connections.callers_of(agent_id)
                agent = await self.agents.delete(agent_id)
                if agent:
                    await self.recorder.record_many(callers, f"agent {agent_id} deleted: may no longer call it", principal.token.id)
        except asyncpg.ForeignKeyViolationError:
            raise Conflict("Agent still has tokens")
        if not agent:
            raise NotFound("Agent not found")
        return agent

    async def mcp_servers(self, principal: Principal, agent_id: int) -> List[MCPServer]:
        await self._own_or_any(principal, agent_id)
        return await self.servers.of_agent(agent_id)

    async def attach(self, principal: Principal, agent_id: int, server_id: int) -> List[MCPServer]:
        if not await self.agents.get(agent_id):
            raise NotFound("Agent not found")
        if not await self.servers.get(server_id):
            raise NotFound("MCP server not found")
        async with self.uow.transaction():
            await self.servers.attach(agent_id, server_id)
            await self.recorder.record(agent_id, f"MCP server {server_id} attached", principal.token.id)
        return await self.servers.of_agent(agent_id)

    async def detach(self, principal: Principal, agent_id: int, server_id: int) -> List[MCPServer]:
        await self._own_or_any(principal, agent_id)
        async with self.uow.transaction():
            await self.servers.detach(agent_id, server_id)
            await self.recorder.record(agent_id, f"MCP server {server_id} detached", principal.token.id)
        return await self.servers.of_agent(agent_id)
