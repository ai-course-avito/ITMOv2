from typing import Optional, Sequence

from fastapi import Body, Depends, Query

from api.controller import Controller, current_principal, endpoint
from api.schemas.agents import AgentCreate, AgentUpdate
from api.schemas.connections import AgentConnectionCreate, AgentConnectionUpdate
from api.schemas.versions import RollbackRequest, VersionDiff
from domain.entities import Agent, AgentConnection, AgentVersion, MCPServer
from domain.access import Principal
from services.agents import AgentService
from services.connections import ConnectionService
from services.versions import VersionService


class AgentController(Controller):
    prefix = "/api/v1/admin"
    tags = ["Admin API"]
    default_role = "user"

    def __init__(self, agents: AgentService):
        self.agents = agents
        super().__init__()

    @endpoint.get("/agents", summary="List all agents", min_role="admin")
    async def get_agents(self) -> Sequence[Agent]:
        return await self.agents.list()

    @endpoint.post("/agents", summary="Create a new agent", status_code=201, min_role="admin")
    async def create_agent(self, data: AgentCreate = Body(...), principal: Principal = Depends(current_principal)) -> Agent:
        return await self.agents.create(principal, data)

    @endpoint.get("/agents/{agent_id}", summary="Get an agent by ID")
    async def get_agent(self, agent_id: int, principal: Principal = Depends(current_principal)) -> Agent:
        return await self.agents.get(principal, agent_id)

    @endpoint.patch("/agents/{agent_id}", summary="Update an agent")
    async def update_agent(self, agent_id: int, data: AgentUpdate = Body(...), principal: Principal = Depends(current_principal)) -> Agent:
        return await self.agents.update(principal, agent_id, data)

    @endpoint.delete("/agents/{agent_id}", summary="Delete an agent", min_role="admin")
    async def delete_agent(self, agent_id: int, principal: Principal = Depends(current_principal)) -> Agent:
        return await self.agents.delete(principal, agent_id)

    # Agent <-> MCP server associations

    @endpoint.get("/agents/{agent_id}/mcp-servers", summary="List MCP servers attached to an agent")
    async def get_agent_mcp_servers(self, agent_id: int, principal: Principal = Depends(current_principal)) -> Sequence[MCPServer]:
        return await self.agents.mcp_servers(principal, agent_id)

    @endpoint.post(
        "/agents/{agent_id}/mcp-servers/{mcp_server_id}",
        summary="Attach an existing MCP server to an agent",
        status_code=201,
        min_role="admin",
    )
    async def add_agent_mcp_server(self, agent_id: int, mcp_server_id: int, principal: Principal = Depends(current_principal)) -> Sequence[MCPServer]:
        return await self.agents.attach(principal, agent_id, mcp_server_id)

    @endpoint.delete("/agents/{agent_id}/mcp-servers/{mcp_server_id}", summary="Detach an MCP server from an agent")
    async def remove_agent_mcp_server(self, agent_id: int, mcp_server_id: int, principal: Principal = Depends(current_principal)) -> Sequence[MCPServer]:
        return await self.agents.detach(principal, agent_id, mcp_server_id)


class VersionController(Controller):
    prefix = "/api/v1/admin"
    tags = ["Admin API"]
    default_role = "user"

    def __init__(self, versions: VersionService):
        self.versions = versions
        super().__init__()

    @endpoint.get("/agents/{agent_id}/versions", summary="History of an agent (newest first)")
    async def get_agent_versions(self, agent_id: int, principal: Principal = Depends(current_principal)) -> Sequence[AgentVersion]:
        return await self.versions.list(principal, agent_id)

    @endpoint.get("/agents/{agent_id}/versions/{number}", summary="One version of an agent")
    async def get_agent_version(self, agent_id: int, number: int, principal: Principal = Depends(current_principal)) -> AgentVersion:
        return await self.versions.get(principal, agent_id, number)

    @endpoint.get("/agents/{agent_id}/versions/{number}/diff", summary="What changed between two versions of an agent")
    async def diff_agent_versions(
        self,
        agent_id: int,
        number: int,
        to: Optional[int] = Query(None, ge=1, description="Default: the latest version"),
        principal: Principal = Depends(current_principal),
    ) -> VersionDiff:
        return VersionDiff(**await self.versions.diff(principal, agent_id, number, to))

    @endpoint.post("/agents/{agent_id}/rollback", summary="Make an agent what one of its versions was (recorded as a new version)")
    async def rollback_agent(self, agent_id: int, data: RollbackRequest = Body(...), principal: Principal = Depends(current_principal)) -> AgentVersion:
        return await self.versions.rollback(principal, agent_id, data.to, data.comment)


class ConnectionController(Controller):
    """Connections between agents: agent1 may call agent2 (the tools list_agents and ask_agent), and the description tells agent1 what
    agent2 is for. Only admins see and change them (they are the ones who see every agent)."""

    prefix = "/api/v1/admin"
    tags = ["Admin API"]
    default_role = "admin"

    def __init__(self, connections: ConnectionService):
        self.connections = connections
        super().__init__()

    @endpoint.get("/agent-connections", summary="List the connections between agents (or those going out of one agent)")
    async def get_agent_connections(self, agent_id: Optional[int] = None) -> Sequence[AgentConnection]:
        return await self.connections.list(agent_id)

    @endpoint.post("/agent-connections", summary="Let one agent call another", status_code=201)
    async def create_agent_connection(self, data: AgentConnectionCreate, principal: Principal = Depends(current_principal)) -> AgentConnection:
        return await self.connections.create(principal, data)

    @endpoint.get("/agent-connections/{connection_id}", summary="Get a connection between agents")
    async def get_agent_connection(self, connection_id: int) -> AgentConnection:
        return await self.connections.get(connection_id)

    @endpoint.patch("/agent-connections/{connection_id}", summary="Change what a connection tells the calling agent")
    async def update_agent_connection(
        self, connection_id: int, data: AgentConnectionUpdate, principal: Principal = Depends(current_principal)
    ) -> AgentConnection:
        return await self.connections.update(principal, connection_id, data)

    @endpoint.delete("/agent-connections/{connection_id}", summary="Stop one agent from calling another")
    async def delete_agent_connection(self, connection_id: int, principal: Principal = Depends(current_principal)) -> AgentConnection:
        return await self.connections.delete(principal, connection_id)
