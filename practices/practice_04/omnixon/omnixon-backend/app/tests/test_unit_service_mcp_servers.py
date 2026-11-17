"""unit MCP server service tests: who sees and changes a server, and the versions its change leaves"""

import pytest

from api.schemas.mcp_servers import MCPServerCreate, MCPServerUpdate
from domain.errors import Forbidden, NotFound
from repositories.versions import VersionRepository
from services.mcp_servers import McpServerService
from world import world

CONFIG = {"url": "http://mcp/mcp"}


@pytest.mark.asyncio
async def test_a_user_token_creates_a_server_for_its_own_agent_and_it_is_a_version():
    async with world() as w:
        servers, versions = w.get(McpServerService), w.get(VersionRepository)
        user = await w.principal("user")
        made = await servers.create(user, MCPServerCreate(name="s", config=CONFIG))
        assert (await servers.get(user, made.id)).id == made.id
        assert [v.comment for v in await versions.list(user.agent.id)] == [f"MCP server {made.id} created"]
        other = await w.principal("user")
        with pytest.raises(Forbidden, match="not attached to the token's agent"):
            await servers.get(other, made.id)


@pytest.mark.asyncio
async def test_an_admin_may_make_a_server_of_nobodys_but_not_for_an_unknown_agent():
    async with world() as w:
        servers = w.get(McpServerService)
        admin = await w.principal("admin")
        assert (await servers.create(admin, MCPServerCreate(name="s", config=CONFIG))).id
        with pytest.raises(NotFound, match="^Agent not found$"):
            await servers.create(admin, MCPServerCreate(name="s", config=CONFIG, agent_id=99999))


@pytest.mark.asyncio
async def test_a_shared_server_cannot_be_changed_by_a_user_token_but_by_an_admin():
    async with world() as w:
        servers = w.get(McpServerService)
        user, admin = await w.principal("user"), await w.principal("admin")
        made = await servers.create(user, MCPServerCreate(name="s", config=CONFIG))
        from repositories.models import McpServerRepository

        other = await w.agent("other")
        await w.get(McpServerRepository).attach(other.id, made.id)
        with pytest.raises(Forbidden, match="shared with another agent"):
            await servers.update(user, made.id, MCPServerUpdate(name="x"))
        assert (await servers.update(admin, made.id, MCPServerUpdate(name="x"))).name == "x"
        versions = w.get(VersionRepository)
        assert (await versions.latest(other.id)).comment == f"MCP server {made.id} updated"


@pytest.mark.asyncio
async def test_deleting_a_server_is_a_version_of_the_agents_that_used_it():
    async with world() as w:
        servers, versions = w.get(McpServerService), w.get(VersionRepository)
        user = await w.principal("user")
        made = await servers.create(user, MCPServerCreate(name="s", config=CONFIG))
        await servers.delete(user, made.id)
        assert (await versions.latest(user.agent.id)).comment == f"MCP server {made.id} deleted"
        with pytest.raises(NotFound, match="^MCP server not found$"):
            await servers.delete(user, made.id)
