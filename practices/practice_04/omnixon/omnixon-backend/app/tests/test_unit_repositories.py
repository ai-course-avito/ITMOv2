"""unit repository tests: the SQL of every aggregate, on a scratch database, with every id explicit"""

import asyncpg
import pytest
import pytest_asyncio

from database.models import RAG
from domain.agents import AgentSnapshot
from repositories.agents import AgentRepository
from repositories.connections import ConnectionRepository
from repositories.data import KnowledgeRepository, MemoryRepository, UsageRepository
from repositories.database import Database
from repositories.models import McpServerRepository, ModelRepository
from repositories.people import ChatRepository, MessageRepository, TokenRepository, UserRepository
from repositories.versions import VersionRepository
from shared import scratch_database


@pytest_asyncio.fixture
async def database():
    async with scratch_database("repos") as (pool, _):
        yield Database(pool.pool)


async def agent(database, name="a"):
    return await AgentRepository(database).insert(name, "p", 0, {"tools": ["rag"]})


@pytest.mark.asyncio
async def test_agents_models_and_servers_round_trip(database):
    agents, models, servers = AgentRepository(database), ModelRepository(database), McpServerRepository(database)
    a = await agent(database)
    assert (await agents.get(a.id)).config.tools == ["rag"] and [x.id for x in await agents.list()][-1] == a.id
    updated = await agents.update(a.id, prompt="q", config_changes={"memo_limit": 3, "tools": None})
    assert updated.prompt == "q" and updated.config.memo_limit == 3 and updated.config.tools != ["rag"]  # a null removes a key
    model = await models.insert({"model": "x/y"}, name="m", base_url="http://llm/v1", use_proxy=False, api_token="secret")
    assert model.base_url == "http://llm/v1" and model.use_proxy is False and model.has_api_token
    assert (await models.update(model.id, base_url="")).base_url.startswith("https://openrouter")
    assert (await models.update(model.id, api_token="")).has_api_token is False
    server = await servers.insert({"url": "http://m/mcp"}, "s")
    await servers.attach(a.id, server.id)
    await servers.attach(a.id, server.id)  # twice is once
    assert [s.id for s in await servers.of_agent(a.id)] == [server.id] and await servers.agents_using(server.id) == [a.id]
    await servers.detach(a.id, server.id)
    assert await servers.of_agent(a.id) == []
    assert a.id in await agents.ids_using_model(0)
    assert (await agents.delete(a.id)).id == a.id and await agents.get(a.id) is None


@pytest.mark.asyncio
async def test_an_unknown_model_is_a_foreign_key_violation(database):
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await AgentRepository(database).insert("a", "p", 99999, {})


@pytest.mark.asyncio
async def test_deleting_an_agent_drops_its_knowledge_partition(database):
    a = await agent(database)
    knowledge = KnowledgeRepository(database)
    await knowledge.insert(a.id, "text", [0.1] * 1536)
    assert await database.fetch_one("SELECT to_regclass($1) AS t", (f"rag_{a.id}",))
    await AgentRepository(database).delete(a.id)
    assert (await database.fetch_one("SELECT to_regclass($1) AS t", (f"rag_{a.id}",)))["t"] is None


@pytest.mark.asyncio
async def test_a_snapshot_has_copies_and_a_fingerprint_and_versions_are_numbered(database):
    a = await agent(database)
    versions = VersionRepository(database)
    snapshot = await versions.snapshot_of(a.id)
    assert isinstance(snapshot, AgentSnapshot) and snapshot.raw["prompt"] == "p" and snapshot.raw["connections"] == []
    first = await versions.insert(a.id, snapshot, "created", None)
    second = await versions.insert(a.id, snapshot, "again", None)
    assert (first.number, second.number) == (1, 2) and await versions.latest_number(a.id) == 2
    assert [v.number for v in await versions.list(a.id)] == [2, 1] and (await versions.get(a.id, 1)).comment == "created"
    assert AgentSnapshot.from_raw((await versions.latest(a.id)).snapshot) == snapshot
    assert await versions.snapshot_of(99999) is None


@pytest.mark.asyncio
async def test_connections_are_found_listed_and_replaced(database):
    a, b, c = await agent(database, "a"), await agent(database, "b"), await agent(database, "c")
    connections = ConnectionRepository(database)
    link = await connections.insert(a.id, b.id, "b")
    with pytest.raises(asyncpg.UniqueViolationError):
        await connections.insert(a.id, b.id, "again")
    assert (await connections.find(a.id, b.id)).id == link.id and await connections.callers_of(b.id) == [a.id]
    await connections.replace_of(a.id, [{"agent2_id": c.id, "description": "c"}, {"agent2_id": 99999, "description": "gone"}])
    assert [x.agent2_id for x in await connections.list(a.id)] == [c.id]  # one to an agent that is gone is left out


@pytest.mark.asyncio
async def test_a_token_read_knows_if_it_is_the_initial_one(database):
    a = await agent(database)
    tokens = TokenRepository(database)
    made = await tokens.insert("t", a.id, "user")
    assert (await tokens.by_secret(made.token)).id == made.id and made.token_sha256
    assert (await tokens.update(made.id, name="u", role="admin")).role == "admin"
    assert [t.id for t in await tokens.list(a.id)] == [made.id]
    assert (await tokens.delete(made.id)).id == made.id and await tokens.by_secret(made.token) is None


@pytest.mark.asyncio
async def test_users_are_found_by_prefix_literally_and_two_inserts_make_one_row(database):
    a, b = await agent(database, "a"), await agent(database, "b")
    users = UserRepository(database)
    first, second = await users.insert(a.id, "alice_1"), await users.insert(a.id, "alice_1")
    assert first is not None and second is None
    await users.insert(a.id, "alicex"), await users.insert(b.id, "alice_1")
    assert [u.external_id for u in await users.search(a.id, "alice_")] == ["alice_1"]  # `_` is not a wildcard
    assert [u.external_id for u in await users.search(a.id, "ali")] == ["alice_1", "alicex"]
    assert await users.rename(first.id, a.id, "alicex") is None  # taken
    assert (await users.rename(first.id, a.id, "zed")).external_id == "zed"


@pytest.mark.asyncio
async def test_chats_and_messages(database):
    a = await agent(database)
    users, chats, messages = UserRepository(database), ChatRepository(database, ttl_days=7), MessageRepository(database, ttl_days=7)
    user = await users.insert(a.id, "u")
    default = await chats.ensure_default(user.id)
    assert default.is_default and (await chats.ensure_default(user.id)).id == default.id
    other = await chats.insert(user.id)
    for i in range(3):
        await messages.append(user.id, other.id, a.id, {"type": "user", "content": f"m{i}"})
    await chats.touch(other.id, "hello there")
    assert [m.content["content"] for m in await messages.window_of(other.id, 2)] == ["m1", "m2"]  # the latest two, oldest first
    assert (await chats.get(user.id, other.id)).title == "hello there" and (await chats.get(user.id, other.id)).messages == 3
    assert await chats.get(user.id + 1, other.id) is None  # not another user's
    assert (await chats.rename(user.id, other.id, "new")).title == "new"
    await messages.clear(other.id)
    assert await messages.window_of(other.id, 10) == []
    assert (await chats.delete(user.id, other.id)).id == other.id and await chats.get(user.id, other.id) is None


@pytest.mark.asyncio
async def test_memories_and_knowledge_of_two_agents_stay_apart(database):
    a, b = await agent(database, "a"), await agent(database, "b")
    user = await UserRepository(database).insert(a.id, "u")
    memories, knowledge = MemoryRepository(database), KnowledgeRepository(database)
    first = await memories.insert(user.id, a.id, "likes tea", [1.0] + [0.0] * 1535)
    await memories.insert(user.id, a.id, "has a cat")
    assert [m.content for m in await memories.newest(user.id, a.id, 5)] == ["has a cat", "likes tea"]
    assert [m.content for m in await memories.newest(user.id, a.id, 5, "TEA")] == ["likes tea"]
    near = await memories.nearest(user.id, a.id, [1.0] + [0.0] * 1535, 5, 0.1)
    assert [(m.content, round(d, 3)) for m, d in near] == [("likes tea", 0.0)]
    assert await memories.count(user.id, a.id) == 2 and len(await memories.without_embedding(10)) == 1
    assert (await memories.update(first.id, "likes coffee")).content == "likes coffee" and len(await memories.without_embedding(10)) == 2
    assert await memories.delete(first.id, agent_id=b.id) is None and (await memories.delete(first.id, user_id=user.id)).id == first.id

    entry = await knowledge.insert(a.id, "alpha", [0.5] * 1536, {"k": 1})
    assert await knowledge.list(b.id) == [] and [r.id for r in await knowledge.list(a.id)] == [entry.id]
    assert (await knowledge.get(a.id, entry.id)).embedding is None  # not unless asked for
    assert (await knowledge.nearest(a.id, [0.5] * 1536, 3))[0].content == "alpha"
    assert (await knowledge.update(a.id, RAG(id=entry.id, agent_id=a.id, content="beta", timestamp=entry.timestamp))).content == "beta"
    assert await knowledge.delete(b.id, entry.id) is None and (await knowledge.delete(a.id, entry.id)).id == entry.id


@pytest.mark.asyncio
async def test_usage_is_written_and_summed_by_day(database):
    from datetime import date

    a = await agent(database)
    token = await TokenRepository(database).insert("t", a.id, "user")
    usage = UsageRepository(database)
    for status in ("ok", "502"):
        await usage.record(token_id=token.id, token_name="t", agent_id=a.id, kind="request", model="m", status=status, duration_ms=5, input_tokens=3, output_tokens=2, cost=0.5)
    rows = await usage.daily(date.today(), date.today(), token_id=token.id)
    assert rows[0]["requests"] == 2 and rows[0]["errors"] == 1 and rows[0]["input_tokens"] == 6 and rows[0]["cost"] == 1.0
    assert await usage.daily(date.today(), date.today(), own_agent_id=a.id + 1) == []
    assert await usage.monthly(token_id=token.id) == []


@pytest.mark.asyncio
async def test_memory_embeddings_are_stored_searched_and_follow_the_content(database):
    def axis(k):  # unit vectors along different axes are 1.0 apart (cosine distance)
        return [1.0 if i == k else 0.0 for i in range(1536)]

    a = await agent(database)
    user, other = await UserRepository(database).insert(a.id, "memvec_user"), await UserRepository(database).insert(a.id, "memvec_other")
    memories = MemoryRepository(database)
    scope = (user.id, a.id)
    dog = await memories.insert(*scope, "dog", axis(0))
    await memories.insert(*scope, "cat", axis(1))
    old = await memories.insert(*scope, "no embedding yet")  # made before embeddings
    assert "embedding" not in dog.model_dump()
    assert [(m.content, round(d, 3)) for m, d in await memories.nearest(*scope, axis(0), limit=5)] == [("dog", 0.0), ("cat", 1.0)]
    assert [m.content for m, _ in await memories.nearest(*scope, axis(0), 5, max_distance=0.5)] == ["dog"]
    assert await memories.nearest(other.id, a.id, axis(0), 5) == []  # other users are not searched
    # an edit without a new embedding clears the old one: it must not match the old words
    await memories.update(dog.id, "a different fact")
    assert "a different fact" not in [m.content for m, _ in await memories.nearest(*scope, axis(0), 5)]
    assert [m.id for m in await memories.without_embedding(10)] == [dog.id, old.id]
    await memories.set_embedding(old.id, axis(2))
    await memories.update(dog.id, "dog again", axis(0))
    assert await memories.without_embedding(10) == []
    assert [m.content for m, _ in await memories.nearest(*scope, axis(0), 1)] == ["dog again"]
