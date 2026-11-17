"""unit agent service tests: create, change under a lock, delete, MCP attachments, versions, rollback and connections"""

import pytest

from api.schemas.agents import AgentCreate, AgentUpdate
from api.schemas.connections import AgentConnectionCreate, AgentConnectionUpdate
from domain.errors import Conflict, Forbidden, NotFound
from repositories.connections import ConnectionRepository
from repositories.models import McpServerRepository, ModelRepository
from repositories.people import TokenRepository
from repositories.versions import VersionRepository
from services.agents import AgentService
from services.connections import ConnectionService
from services.versions import VersionService
from world import world


def new(name="a", **config):
    return AgentCreate(name=name, prompt="p", model_id=0, config=config or None, comment=None)


@pytest.mark.asyncio
async def test_an_agent_is_made_with_the_default_tools_and_a_first_version():
    async with world() as w:
        agents, versions = w.get(AgentService), w.get(VersionRepository)
        admin = await w.principal("admin")
        agent = await agents.create(admin, new(memo_limit=3))
        assert agent.config.tools == ["rag", "memory"] and agent.config.memo_limit == 3
        assert [(v.number, v.comment) for v in await versions.list(agent.id)] == [(1, "created")]
        with pytest.raises(NotFound, match="^Model not found$"):
            await agents.create(admin, AgentCreate(name="x", prompt="p", model_id=99999))


@pytest.mark.asyncio
async def test_an_expected_version_that_is_behind_changes_nothing_and_a_null_resets_a_key():
    async with world() as w:
        agents = w.get(AgentService)
        admin = await w.principal("admin")
        agent = await agents.create(admin, new(rag_limit=5))
        await agents.update(admin, agent.id, AgentUpdate(prompt="v2"))
        with pytest.raises(Conflict, match="^The agent is at version 2, not 1$"):
            await agents.update(admin, agent.id, AgentUpdate(prompt="v3", expected_version=1))
        assert (await agents.get(admin, agent.id)).prompt == "v2"
        reset = await agents.update(admin, agent.id, AgentUpdate.model_validate({"config": {"rag_limit": None}, "expected_version": 2}))
        assert reset.config.rag_limit is None


@pytest.mark.asyncio
async def test_a_user_token_reads_and_changes_only_its_own_agent():
    async with world() as w:
        agents = w.get(AgentService)
        user = await w.principal("user")
        other = await w.agent("other")
        assert (await agents.get(user, user.agent.id)).id == user.agent.id
        with pytest.raises(Forbidden, match="only use its own agent"):
            await agents.get(user, other.id)
        with pytest.raises(Forbidden):
            await agents.update(user, other.id, AgentUpdate(prompt="x"))
        with pytest.raises(NotFound, match="^Agent not found$"):
            await agents.get(await w.principal("admin"), 99999)


@pytest.mark.asyncio
async def test_an_agent_with_tokens_cannot_be_deleted_and_callers_get_a_version():
    async with world() as w:
        agents, connections, versions = w.get(AgentService), w.get(ConnectionService), w.get(VersionRepository)
        admin = await w.principal("admin")
        caller, target = await agents.create(admin, new("caller")), await agents.create(admin, new("target"))
        await connections.create(admin, AgentConnectionCreate(agent1_id=caller.id, agent2_id=target.id, description="d"))
        await w.get(TokenRepository).insert("t", target.id, "regular")
        with pytest.raises(Conflict, match="^Agent still has tokens$"):
            await agents.delete(admin, target.id)
        for token in await w.get(TokenRepository).list(target.id):
            await w.get(TokenRepository).delete(token.id)
        await agents.delete(admin, target.id)
        assert (await versions.latest(caller.id)).comment == f"agent {target.id} deleted: may no longer call it"
        with pytest.raises(NotFound):
            await agents.delete(admin, target.id)


@pytest.mark.asyncio
async def test_attaching_and_detaching_an_mcp_server_are_versions():
    async with world() as w:
        agents, servers, versions = w.get(AgentService), w.get(McpServerRepository), w.get(VersionRepository)
        admin = await w.principal("admin")
        agent = await agents.create(admin, new())
        server = await servers.insert({"url": "http://m/mcp"}, "s")
        assert [s.id for s in await agents.attach(admin, agent.id, server.id)] == [server.id]
        assert [s.id for s in await agents.mcp_servers(admin, agent.id)] == [server.id]
        assert await agents.detach(admin, agent.id, server.id) == []
        assert [v.comment for v in await versions.list(agent.id)][:2] == [f"MCP server {server.id} detached", f"MCP server {server.id} attached"]
        with pytest.raises(NotFound, match="^MCP server not found$"):
            await agents.attach(admin, agent.id, 99999)


@pytest.mark.asyncio
async def test_connections_are_part_of_the_callers_versions_and_come_back_with_a_rollback():
    async with world() as w:
        agents, connections, versions = w.get(AgentService), w.get(ConnectionService), w.get(VersionService)
        admin = await w.principal("admin")
        a, b = await agents.create(admin, new("a")), await agents.create(admin, new("b"))
        before = len(await versions.list(admin, a.id))
        link = await connections.create(admin, AgentConnectionCreate(agent1_id=a.id, agent2_id=b.id, description="knows prices"))
        snapshots = await versions.list(admin, a.id)
        assert len(snapshots) == before + 1 and snapshots[0].snapshot["connections"] == [{"agent2_id": b.id, "description": "knows prices"}]
        await connections.update(admin, link.id, AgentConnectionUpdate(description="knows prices and stock"))
        await connections.delete(admin, link.id)
        assert await connections.connected_agents(a.id) == []
        restored = await versions.rollback(admin, a.id, snapshots[0].number, None)
        assert restored.comment == f"rolled back to version {snapshots[0].number}"
        assert await connections.connected_agents(a.id) == [{"id": b.id, "name": "b", "description": "knows prices"}]


@pytest.mark.asyncio
async def test_a_rollback_skips_a_connection_to_an_agent_that_is_gone_and_to_the_version_it_already_is():
    async with world() as w:
        agents, connections, versions = w.get(AgentService), w.get(ConnectionService), w.get(VersionService)
        admin = await w.principal("admin")
        a, b = await agents.create(admin, new("a")), await agents.create(admin, new("b"))
        await connections.create(admin, AgentConnectionCreate(agent1_id=a.id, agent2_id=b.id, description="b"))
        number = (await versions.list(admin, a.id))[0].number
        await agents.delete(admin, b.id)
        assert await connections.connected_agents(a.id) == []
        await versions.rollback(admin, a.id, number, None)
        assert await connections.connected_agents(a.id) == []  # the agent is gone: the connection is left out
        latest = (await versions.list(admin, a.id))[0]
        assert (await versions.rollback(admin, a.id, latest.number, None)).number == latest.number  # already that version: no new one


@pytest.mark.asyncio
async def test_a_rollback_copies_a_model_that_changed_and_keeps_the_key_of_the_record_it_replaces():
    async with world() as w:
        agents, models, versions = w.get(AgentService), w.get(ModelRepository), w.get(VersionService)
        admin = await w.principal("admin")
        model = await models.insert({"model": "a/b"}, "m", api_token="own-key")
        agent = await agents.create(admin, AgentCreate(name="x", prompt="p", model_id=model.id))
        await models.update(model.id, request_json={"model": "a/c"})
        await agents.update(admin, agent.id, AgentUpdate(prompt="p2"))  # version 2 sees the changed model
        restored = await versions.rollback(admin, agent.id, 1, None)
        back = await agents.get(admin, agent.id)
        assert back.model_id != model.id and restored.number == 3
        copy = await models.get(back.model_id)
        assert copy.request_json == {"model": "a/b"} and copy.api_token == "own-key"


@pytest.mark.asyncio
async def test_connection_rules_have_the_texts_of_the_api():
    async with world() as w:
        agents, connections = w.get(AgentService), w.get(ConnectionService)
        admin = await w.principal("admin")
        a, b = await agents.create(admin, new("a")), await agents.create(admin, new("b"))
        with pytest.raises(Conflict, match="^An agent cannot be connected to itself$"):
            await connections.create(admin, AgentConnectionCreate(agent1_id=a.id, agent2_id=a.id, description="d"))
        with pytest.raises(NotFound, match="^Agent 99999 not found$"):
            await connections.create(admin, AgentConnectionCreate(agent1_id=a.id, agent2_id=99999, description="d"))
        await connections.create(admin, AgentConnectionCreate(agent1_id=a.id, agent2_id=b.id, description="d"))
        with pytest.raises(Conflict, match=f"^Agent {a.id} is already connected to agent {b.id}$"):
            await connections.create(admin, AgentConnectionCreate(agent1_id=a.id, agent2_id=b.id, description="d"))
        with pytest.raises(NotFound, match="^Agent connection not found$"):
            await connections.get(99999)
        assert await connections.has_connection(a.id, b.id) and not await connections.has_connection(b.id, a.id)
