from __future__ import annotations

from typing import List, Optional

from database.models import DEFAULT_BASE_URL, MCPServer, Model
from .base import Repository


class ModelRepository(Repository):
    async def get(self, model_id: int) -> Optional[Model]:
        return await self.db.fetch_one("SELECT * FROM models WHERE id=$1", (model_id,), Model)

    async def list(self) -> List[Model]:
        return await self.db.fetch_all("SELECT * FROM models ORDER BY id ASC", (), Model)

    async def insert(
        self,
        request_json: dict,
        name: Optional[str] = None,
        base_url: Optional[str] = None,
        use_proxy: bool = True,
        api_token: Optional[str] = None,
    ) -> Model:
        """`base_url` None (or OpenRouter's own address) is stored as NULL; `api_token` None: the key of the deployment."""
        return await self.db.fetch_one(
            "INSERT INTO models (request_json, name, base_url, use_proxy, api_token) VALUES ($1, $2, $3, $4, $5) RETURNING *",
            (request_json, name, None if base_url in (None, "", DEFAULT_BASE_URL) else base_url, use_proxy, api_token or None),
            Model,
        )

    async def update(
        self,
        model_id: int,
        request_json: Optional[dict] = None,
        name: Optional[str] = None,
        base_url: Optional[str] = None,
        use_proxy: Optional[bool] = None,
        api_token: Optional[str] = None,
    ) -> Optional[Model]:
        """Only what is given changes. For `base_url` and `api_token` an empty string goes back to the default; None keeps what there is."""
        if base_url == DEFAULT_BASE_URL:
            base_url = ""
        return await self.db.fetch_one(
            """
            UPDATE models
            SET request_json=COALESCE($1, request_json),
                name=COALESCE($2, name),
                base_url=CASE WHEN $3::text IS NULL THEN base_url WHEN $3 = '' THEN NULL ELSE $3 END,
                use_proxy=COALESCE($4, use_proxy),
                api_token=CASE WHEN $5::text IS NULL THEN api_token WHEN $5 = '' THEN NULL ELSE $5 END
            WHERE id=$6
            RETURNING *
            """,
            (request_json, name, base_url, use_proxy, api_token, model_id),
            Model,
        )

    async def delete(self, model_id: int) -> Optional[Model]:
        return await self.db.fetch_one("DELETE FROM models WHERE id=$1 RETURNING *", (model_id,), Model)


class McpServerRepository(Repository):
    async def get(self, server_id: int) -> Optional[MCPServer]:
        return await self.db.fetch_one("SELECT * FROM mcp_servers WHERE id=$1", (server_id,), MCPServer)

    async def list(self) -> List[MCPServer]:
        return await self.db.fetch_all("SELECT * FROM mcp_servers ORDER BY id ASC", (), MCPServer)

    async def insert(self, config: dict, name: Optional[str] = None) -> MCPServer:
        return await self.db.fetch_one("INSERT INTO mcp_servers (config, name) VALUES ($1, $2) RETURNING *", (config, name), MCPServer)

    async def update(self, server_id: int, config: Optional[dict] = None, name: Optional[str] = None) -> Optional[MCPServer]:
        return await self.db.fetch_one(
            "UPDATE mcp_servers SET config=COALESCE($1, config), name=COALESCE($2, name) WHERE id=$3 RETURNING *",
            (config, name, server_id),
            MCPServer,
        )

    async def delete(self, server_id: int) -> Optional[MCPServer]:
        return await self.db.fetch_one("DELETE FROM mcp_servers WHERE id=$1 RETURNING *", (server_id,), MCPServer)

    async def of_agent(self, agent_id: int) -> List[MCPServer]:
        return await self.db.fetch_all(
            """
            SELECT m.* FROM mcp_servers m JOIN agent_mcp_servers ams ON ams.mcp_server_id = m.id
            WHERE ams.agent_id = $1 ORDER BY m.id ASC
            """,
            (agent_id,),
            MCPServer,
        )

    async def attach(self, agent_id: int, server_id: int) -> None:
        await self.db.execute(
            "INSERT INTO agent_mcp_servers (agent_id, mcp_server_id) VALUES ($1, $2) ON CONFLICT DO NOTHING", (agent_id, server_id)
        )

    async def detach(self, agent_id: int, server_id: int) -> None:
        await self.db.execute("DELETE FROM agent_mcp_servers WHERE agent_id=$1 AND mcp_server_id=$2", (agent_id, server_id))

    async def agents_using(self, server_id: int) -> List[int]:
        rows = await self.db.fetch_all("SELECT agent_id FROM agent_mcp_servers WHERE mcp_server_id=$1", (server_id,))
        return [row["agent_id"] for row in rows]
