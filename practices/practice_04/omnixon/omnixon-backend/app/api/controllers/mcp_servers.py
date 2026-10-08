from typing import Sequence

from fastapi import Body, Depends

from api.controller import Controller, current_principal, endpoint
from api.schemas.mcp_servers import MCPServerCreate, MCPServerUpdate
from database.models import MCPServer
from domain.access import Principal
from services.mcp_servers import McpServerService


class McpServerController(Controller):
    prefix = "/api/v1/admin"
    tags = ["Admin API"]
    default_role = "user"

    def __init__(self, servers: McpServerService):
        self.servers = servers
        super().__init__()

    @endpoint.get("/mcp-servers", summary="List all MCP servers", min_role="admin")
    async def get_mcp_servers(self) -> Sequence[MCPServer]:
        return await self.servers.list()

    @endpoint.post("/mcp-servers", summary="Create a new MCP server", status_code=201)
    async def create_mcp_server(self, data: MCPServerCreate = Body(...), principal: Principal = Depends(current_principal)) -> MCPServer:
        return await self.servers.create(principal, data)

    @endpoint.get("/mcp-servers/{mcp_server_id}", summary="Get an MCP server by ID")
    async def get_mcp_server(self, mcp_server_id: int, principal: Principal = Depends(current_principal)) -> MCPServer:
        return await self.servers.get(principal, mcp_server_id)

    @endpoint.patch("/mcp-servers/{mcp_server_id}", summary="Update an MCP server")
    async def update_mcp_server(
        self, mcp_server_id: int, data: MCPServerUpdate = Body(...), principal: Principal = Depends(current_principal)
    ) -> MCPServer:
        return await self.servers.update(principal, mcp_server_id, data)

    @endpoint.delete("/mcp-servers/{mcp_server_id}", summary="Delete an MCP server")
    async def delete_mcp_server(self, mcp_server_id: int, principal: Principal = Depends(current_principal)) -> MCPServer:
        return await self.servers.delete(principal, mcp_server_id)
