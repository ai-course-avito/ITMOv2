from typing import Optional, Sequence
from ..context import PostgresConnectionWithContext
from ..models import MCPServer


class MCPServerMethods(PostgresConnectionWithContext):
    async def get_mcp_server(self, mcp_server_id: int) -> Optional[MCPServer]:
        query = "SELECT * FROM mcp_servers WHERE id=$1"
        return await self.fetch_one(query, (mcp_server_id,), MCPServer)

    async def get_all_mcp_servers(self) -> Sequence[MCPServer]:
        query = "SELECT * FROM mcp_servers ORDER BY id ASC"
        return (await self.fetch_all(query, (), MCPServer)) or []

    async def create_mcp_server(
        self, config: dict, name: Optional[str] = None
    ) -> MCPServer:
        query = """
            INSERT INTO mcp_servers (config, name)
            VALUES ($1, $2)
            RETURNING *
        """
        return await self.fetch_one(query, (config, name), MCPServer)

    async def update_mcp_server(
        self,
        mcp_server_id: int,
        config: Optional[dict] = None,
        name: Optional[str] = None,
    ) -> Optional[MCPServer]:
        query = """
            UPDATE mcp_servers
            SET config=COALESCE($1, config), name=COALESCE($2, name)
            WHERE id=$3
            RETURNING *
        """
        return await self.fetch_one(query, (config, name, mcp_server_id), MCPServer)

    async def delete_mcp_server(self, mcp_server_id: int) -> Optional[MCPServer]:
        query = "DELETE FROM mcp_servers WHERE id=$1 RETURNING *"
        return await self.fetch_one(query, (mcp_server_id,), MCPServer)

    async def get_agent_mcp_servers(self, agent_id: int) -> Sequence[MCPServer]:
        query = """
            SELECT m.*
            FROM mcp_servers m
            JOIN agent_mcp_servers ams ON ams.mcp_server_id = m.id
            WHERE ams.agent_id = $1
            ORDER BY m.id ASC
        """
        return (await self.fetch_all(query, (agent_id,), MCPServer)) or []

    async def add_agent_mcp_server(self, agent_id: int, mcp_server_id: int) -> None:
        query = """
            INSERT INTO agent_mcp_servers (agent_id, mcp_server_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
        """
        await self.execute(query, (agent_id, mcp_server_id))

    async def remove_agent_mcp_server(self, agent_id: int, mcp_server_id: int) -> None:
        query = """
            DELETE FROM agent_mcp_servers
            WHERE agent_id=$1 AND mcp_server_id=$2
        """
        await self.execute(query, (agent_id, mcp_server_id))
