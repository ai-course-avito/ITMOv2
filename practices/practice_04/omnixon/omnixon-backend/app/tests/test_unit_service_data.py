"""unit memory, knowledge and usage service tests"""

import math

import pytest

from api.schemas.knowledge import RAGCreate, RAGUpdate
from api.schemas.memories import MemoryCreate
from domain.access import Conversation
from domain.errors import Forbidden, Invalid, NotFound
from repositories.data import UsageRepository
from services.knowledge import KnowledgeService
from services.memories import MemoryService
from services.usage import UsageService
from services.users import ChatService, UserService
from world import FakeEmbedder, world


async def conversation(w, role="user", **memory_limits):
    p = await w.principal(role)
    user = await w.get(UserService).create(p, "u")
    chat = await w.get(ChatService).resolve(user, None)
    return p, Conversation(p, user, chat, p.agent.settings(w.container.settings.agent_defaults))


@pytest.mark.asyncio
async def test_memories_are_listed_found_by_meaning_and_by_the_words_and_scoped_to_the_agent():
    embedder = FakeEmbedder({"likes tea": 0.0, "tea": 0.1, "has a cat": 1.2})
    async with world(embedder=embedder) as w:
        memories = w.get(MemoryService)
        p, c = await conversation(w)
        await memories.create(p, MemoryCreate(user_id="u", content="likes tea"))
        await memories.create(p, MemoryCreate(user_id="u", content="has a cat"))
        assert [m.content for m in await memories.list(p, "u", None, 10, None)] == ["has a cat", "likes tea"]
        assert [m.content for m in await memories.list(p, "u", None, 10, "tea")][0] == "likes tea"  # by meaning first
        other = await w.principal("user")
        with pytest.raises(NotFound, match="^User not found$"):
            await memories.list(other, "u", None, 10, None)
        with pytest.raises(Forbidden, match="only use its own agent"):
            await memories.list(other, "u", p.agent.id, 10, None)


@pytest.mark.asyncio
async def test_memory_still_works_without_the_embedding_service_by_the_words():
    embedder = FakeEmbedder()
    async with world(embedder=embedder) as w:
        memories = w.get(MemoryService)
        p, c = await conversation(w)
        embedder.fail = True
        made = await memories.create(p, MemoryCreate(user_id="u", content="likes green tea"))
        assert [m.id for m in await memories.recall((c.user.id, p.agent.id), "green", 5)] == [made.id]
        assert await memories.backfill() == 0  # still down: stops at the first failure
        embedder.fail = False
        assert await memories.backfill() == 1


@pytest.mark.asyncio
async def test_remember_drops_a_restatement_but_keeps_a_similar_fact_and_names_it():
    embedder = FakeEmbedder({"The user likes tea.": 0.0, "the user likes tea.": 0.0, "The user likes tea a lot.": 0.55, "Lives in Prague": 2.0})
    async with world(embedder=embedder) as w:
        memories = w.get(MemoryService)
        p, c = await conversation(w)
        first = await memories.remember(c, "The user likes tea.")
        assert first.startswith("Saved as memory [")
        assert (await memories.remember(c, "the user likes tea.")).startswith("Already remembered as memory [")
        similar = await memories.remember(c, "The user likes tea a lot.")
        assert similar.startswith("Saved as memory [") and "Similar memories exist" in similar and "The user likes tea." in similar
        assert (await memories.remember(c, "x" * 2001)).startswith("Not saved: a fact must be 1-2000")
        assert (await memories.remember(c, "Lives in Prague")).count("Similar") == 0


@pytest.mark.asyncio
async def test_two_requests_that_learn_the_same_fact_at_once_save_it_once():
    import asyncio

    async with world(embedder=FakeEmbedder({"same": 0.0})) as w:
        memories = w.get(MemoryService)
        p, c = await conversation(w)
        results = await asyncio.gather(*[memories.remember(c, "same") for _ in range(4)])
        assert sum(r.startswith("Saved") for r in results) == 1


@pytest.mark.asyncio
async def test_the_memory_block_shows_the_newest_and_says_how_many_are_hidden():
    async with world(default_memo_limit=2, embedder=FakeEmbedder({"a": 0.0, "b": 1.0, "c": 2.0})) as w:
        memories = w.get(MemoryService)
        p, c = await conversation(w)
        assert "Nothing is remembered about this user yet." in await memories.block(c)
        for fact in ("a", "b", "c"):
            await memories.remember(c, fact)
        block = await memories.block(c)
        assert block.startswith("<Memory>") and block.endswith("</Memory>")
        assert "] c" in block and "] b" in block and "] a" not in block and "1 older memories are not shown" in block
        assert (await memories.recall_text(c, "")).count("[") == 2
        first_id = (await memories.recall((c.user.id, p.agent.id), "a", 5))[0].id
        assert await memories.forget(c, first_id) == f"Forgot memory [{first_id}]." and await memories.forget(c, first_id) == "No such memory."


@pytest.mark.asyncio
async def test_knowledge_is_created_listed_found_updated_and_deleted_on_the_agents_own_base():
    async with world(embedder=FakeEmbedder({"alpha": 0.0, "beta": 1.5, "query": 0.05})) as w:
        knowledge = w.get(KnowledgeService)
        p = await w.principal("user")
        a = await knowledge.create(p, None, RAGCreate(content="alpha"))
        b = await knowledge.create(p, None, RAGCreate(content="beta", embedding_content="beta"))
        assert [r.id for r in await knowledge.search(p, None, None, 10, 0, False)] == [a.id, b.id]
        assert (await knowledge.search(p, "query", None, 1, 0, False))[0].content == "alpha"
        assert (await knowledge.update(p, a.id, None, RAGUpdate(content="alpha2", metadata={"k": 1}))).metadata == {"k": 1}
        with pytest.raises(Invalid, match="^limit above 100 is allowed without a query only$"):
            await knowledge.search(p, "query", None, 101, 0, False)
        with pytest.raises(NotFound, match="^RAG entry not found$"):
            await knowledge.get(p, 99999, None, False)
        assert (await knowledge.delete(p, b.id, None)).id == b.id
        other = await w.principal("user")
        with pytest.raises(NotFound):
            await knowledge.get(other, a.id, None, False)  # another agent's base is empty for it
        with pytest.raises(Forbidden):
            await knowledge.search(other, None, p.agent.id, 10, 0, False)


@pytest.mark.asyncio
async def test_the_retrieve_tool_answers_with_rag_limit_records():
    async with world(embedder=FakeEmbedder({"q": 0.0}), default_rag_limit=1) as w:
        knowledge = w.get(KnowledgeService)
        p, c = await conversation(w)
        await knowledge.create(p, None, RAGCreate(content="first", embedding_content="q"))
        await knowledge.create(p, None, RAGCreate(content="second", embedding_content="q"))
        answer = await knowledge.retrieve(c, "q")
        assert answer.count("<record") == 1 and "first" in answer


@pytest.mark.asyncio
async def test_usage_below_admin_is_that_of_the_own_agent_and_an_admin_sees_all():
    async with world() as w:
        usage, repo = w.get(UsageService), w.get(UsageRepository)
        user, other, admin = await w.principal("user"), await w.principal("user"), await w.principal("admin")
        for p in (user, other):
            await repo.record(token_id=p.token.id, token_name="t", agent_id=p.agent.id, kind="request", model="m", status="ok", duration_ms=5)
        assert {r["token_id"] for r in await usage.daily(user, 30, None, None)} == {user.token.id}
        assert {user.token.id, other.token.id} <= {r["token_id"] for r in await usage.daily(admin, 30, None, None)}
        assert {r["token_id"] for r in await usage.daily(admin, 30, None, other.agent.id)} == {other.token.id}
        with pytest.raises(Forbidden):
            await usage.daily(user, 30, None, other.agent.id)
        assert await usage.monthly(user, None, None) == []


@pytest.mark.asyncio
async def test_a_memory_can_be_made_for_another_agent_about_a_user_of_the_agent_in_context():
    """A user belongs to the agent in context; the memory to the agent that is asked for (an admin keeps what another agent knows of a person)."""
    async with world(embedder=FakeEmbedder()) as w:
        memories = w.get(MemoryService)
        admin = await w.principal("admin")
        await w.get(UserService).create(admin, "person")
        other = await w.agent("other")
        made = await memories.create(admin, MemoryCreate(user_id="person", content="knows Python", agent_id=other.id))
        assert made.agent_id == other.id
        assert [m.id for m in await memories.list(admin, "person", other.id, 10, None)] == [made.id]
        assert await memories.list(admin, "person", None, 10, None) == []  # none for the own agent
