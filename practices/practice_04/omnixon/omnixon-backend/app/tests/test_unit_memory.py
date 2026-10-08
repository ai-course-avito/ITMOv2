"""unit memory tests"""

import asyncio
import math
import uuid
import pytest
from pydantic_ai import Agent
from ai.capabilities import Memory
from ai.deps import Dependencies
from ai import memory as memory_module
from core import DATABASE_CONFIG, DEFAULT_TOOLS

from shared import (
    FakeDB,
    agent_row,
    memory,
    scratch_pool,
)


def vec(angle_degrees: float):
    """A 2-d unit vector; the cosine distance of two of them is 1 - cos(angle between)."""
    radians = math.radians(angle_degrees)
    return [math.cos(radians), math.sin(radians)]


def angle_for(distance: float) -> float:
    return math.degrees(math.acos(1 - distance))


def embeddings(monkeypatch, texts: dict):
    """embed() answers with the angle given for the text (None for unknown texts)."""

    async def fake(text):
        return vec(texts[text]) if text in texts else None

    monkeypatch.setattr(memory_module, "embed", fake)


SCOPE = (7, 3)


@pytest.mark.asyncio
async def test_a_fact_that_is_already_remembered_is_not_saved_again(monkeypatch):
    db = FakeDB(memories=[memory(1, "The user's dog is called Rex.")])

    saved, is_new, similar = await memory_module.save_memory(
        db, SCOPE, "the user's DOG is called rex."
    )
    assert (saved.id, is_new, similar) == (1, False, [])  # the same words
    assert not any(call[0] == "create_memory" for call in db.calls)


@pytest.mark.asyncio
async def test_a_fact_restated_in_other_words_is_recognised_by_meaning(monkeypatch):
    db = FakeDB(
        memories=[memory(1, "The user's dog is called Rex.")],
        vectors={1: vec(0)},
    )
    embeddings(
        monkeypatch,
        {
            "The user has a dog named Rex.": angle_for(0.05),  # near-verbatim
            "The user is the owner of a dog, Rex.": angle_for(0.15),  # reworded
        },
    )

    saved, is_new, _ = await memory_module.save_memory(
        db, SCOPE, "The user has a dog named Rex."
    )
    assert (saved.id, is_new) == (1, False)  # dropped: it says the same

    # 0.15 away could also be "no longer has a dog": saved, and the similar one is shown
    saved, is_new, similar = await memory_module.save_memory(
        db, SCOPE, "The user is the owner of a dog, Rex."
    )
    assert is_new and [m.id for m in similar] == [1]


@pytest.mark.asyncio
async def test_unrelated_facts_are_saved_without_a_similar_hint(monkeypatch):
    db = FakeDB(memories=[memory(1, "The user lives in Prague.")], vectors={1: vec(0)})
    embeddings(monkeypatch, {"The user likes tea.": angle_for(0.6)})

    saved, is_new, similar = await memory_module.save_memory(
        db, SCOPE, "The user likes tea."
    )
    assert (
        is_new
        and similar == []
        and ("create_memory", 7, 3, "The user likes tea.") in db.calls
    )
    assert db.vectors[saved.id] == pytest.approx(
        vec(angle_for(0.6))
    )  # stored with its embedding


@pytest.mark.asyncio
async def test_memory_works_without_the_embedding_service():
    db = FakeDB(memories=[memory(1, "The user lives in Prague.")], vectors={1: vec(0)})
    saved, is_new, similar = await memory_module.save_memory(
        db, SCOPE, "The user likes tea."
    )
    assert (
        is_new and similar == [] and saved.id not in db.vectors
    )  # no embedding to store


@pytest.mark.asyncio
async def test_recall_finds_by_meaning_then_by_words(monkeypatch):
    memories = [
        memory(4, "Works at the harbour office"),  # no embedding yet (an old memory)
        memory(3, "The user has a dog named Rex."),
        memory(2, "The user lives in Prague."),
        memory(1, "The user's favourite food is pizza."),
    ]
    # the question is 0.5 away from the dog; Prague and the pizza are on other sides
    third = angle_for(0.5)
    vectors = {3: vec(0), 2: vec(-third), 1: vec(180)}
    db = FakeDB(memories=memories, vectors=vectors)

    async def fake_embed(text):
        return vec(third) if text == "my pet" else None

    monkeypatch.setattr(memory_module, "embed", fake_embed)
    found = await memory_module.recall_memories(db, SCOPE, "my pet", limit=5)
    assert [m.id for m in found] == [3]  # by meaning; the others are beyond the cut-off

    # words are matched too, and also find memories that have no embedding
    found = await memory_module.recall_memories(db, SCOPE, "harbour", limit=5)
    assert [m.id for m in found] == [4]

    # meaning first, then words, each memory once
    async def both(text):
        return vec(third) if text == "dog" else None

    monkeypatch.setattr(memory_module, "embed", both)
    found = await memory_module.recall_memories(db, SCOPE, "dog", limit=5)
    assert [m.id for m in found] == [3]  # found by meaning and by the word "dog": once


@pytest.mark.asyncio
async def test_recall_without_a_query_lists_the_newest_and_respects_the_limit(
    monkeypatch,
):
    db = FakeDB(memories=[memory(i, f"fact {i}") for i in (5, 4, 3, 2, 1)])
    found = await memory_module.recall_memories(db, SCOPE, "  ", limit=2)
    assert [m.id for m in found] == [5, 4]

    embeddings(monkeypatch, {"fact": 0.0})
    db.vectors = {i: vec(i) for i in (1, 2, 3, 4, 5)}  # all close to "fact"
    assert len(await memory_module.recall_memories(db, SCOPE, "fact", limit=3)) == 3


def test_auto_memory_needs_the_flag_the_memory_tool_and_a_user():
    assert memory_module.wants_auto_memory(FakeDB(auto_memory=True))
    assert not memory_module.wants_auto_memory(FakeDB(auto_memory=False))
    assert not memory_module.wants_auto_memory(FakeDB(auto_memory=True, tools=("rag",)))
    assert not memory_module.wants_auto_memory(FakeDB(auto_memory=True, user=False))
    assert not memory_module.wants_auto_memory(FakeDB(auto_memory=True, agent=False))


def extractor(facts, prompts=None):
    """A pydantic-ai model that answers the memory extraction with `facts`."""
    from pydantic_ai.messages import ModelResponse, ToolCallPart
    from pydantic_ai.models.function import FunctionModel

    def answer(messages, info):
        if prompts is not None:
            prompts.append(messages[-1].parts[0].content)
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, {"response": facts})]
        )

    return FunctionModel(answer)


@pytest.mark.asyncio
async def test_facts_are_extracted_from_an_exchange_and_remembered():
    db = FakeDB(memories=[memory(1, "The user lives in Prague.")], auto_memory=True)
    prompts = []
    created = await memory_module.extract_memories(
        db,
        SCOPE,
        extractor(
            [
                "The user is called Ivan.",
                "  ",
                "The user lives in Prague.",
                "The user has a cat.",
            ],
            prompts,
        ),
        "I'm Ivan, I live in Prague and have a cat.",
        "Nice to meet you, Ivan!",
    )
    # blanks and what is remembered already are skipped
    assert [m.content for m in created] == [
        "The user is called Ivan.",
        "The user has a cat.",
    ]
    # the model is told what is known, and what was said
    assert "- The user lives in Prague." in prompts[0]
    assert "I'm Ivan" in prompts[0] and "Nice to meet you" in prompts[0]


@pytest.mark.asyncio
async def test_at_most_a_few_facts_are_taken_from_one_exchange():
    db = FakeDB(auto_memory=True)
    facts = [f"Fact number {i}." for i in range(12)]
    created = await memory_module.extract_memories(
        db, SCOPE, extractor(facts), "x", "y"
    )
    assert len(created) == memory_module.MAX_FACTS_PER_EXCHANGE
    assert (
        await memory_module.extract_memories(db, SCOPE, extractor([]), "x", "y") == []
    )


@pytest.mark.asyncio
async def test_extraction_runs_in_the_background_and_never_raises(monkeypatch):
    db = FakeDB(auto_memory=True)
    monkeypatch.setattr(
        memory_module,
        "generate_model",
        lambda request_json: extractor(["The user is called Ivan."]),
    )

    memory_module.schedule_extraction(db, {"model": "a/b"}, "I'm Ivan", "Hello Ivan")
    await asyncio.gather(*memory_module._background)
    assert [m.content for m in db.memories] == ["The user is called Ivan."]

    # a failing model costs only the extraction
    def broken(request_json, **kw):
        raise RuntimeError("model is down")

    monkeypatch.setattr(memory_module, "generate_model", broken)
    memory_module.schedule_extraction(db, {"model": "a/b"}, "x", "y")
    await asyncio.gather(*memory_module._background)  # no exception


@pytest.mark.asyncio
async def test_extraction_is_not_scheduled_without_auto_memory(monkeypatch):
    monkeypatch.setattr(
        memory_module, "generate_model", lambda r, **kw: extractor(["x"])
    )
    for db in (FakeDB(auto_memory=False), FakeDB(auto_memory=True, tools=("rag",))):
        memory_module.schedule_extraction(db, {"model": "a/b"}, "x", "y")
        assert not memory_module._background
        assert db.memories == []


@pytest.mark.asyncio
async def test_remember_tool_tells_the_model_about_similar_memories(monkeypatch):
    db = FakeDB(memories=[memory(1, "The user likes tea.")], vectors={1: vec(0)})
    embeddings(monkeypatch, {"a": angle_for(0.15)})  # TestModel remembers "a"

    from pydantic_ai.models.test import TestModel

    model = TestModel(call_tools=["remember"])
    agent = Agent(model, deps_type=Dependencies, capabilities=[Memory()])
    result = await agent.run("hi", deps=Dependencies(db=db))
    returned = [
        part.content
        for message in result.all_messages()
        for part in message.parts
        if part.part_kind == "tool-return"
    ]
    assert (
        "Saved as memory" in returned[0]
        and "forget" in returned[0]
        and "[1] The user likes tea." in returned[0]
    )


@pytest.mark.asyncio
async def test_old_memories_get_embeddings_and_a_failing_service_stops_it(monkeypatch):
    class Db(FakeDB):
        def __init__(self):
            super().__init__(memories=[memory(i, f"fact {i}") for i in (1, 2, 3)])
            self.stored = {}

        async def memories_without_embedding(self, limit):
            return [m for m in self.memories if m.id not in self.stored][:limit]

        async def set_memory_embedding(self, memory_id, embedding):
            self.stored[memory_id] = embedding

    db = Db()
    embeddings(monkeypatch, {"fact 1": 10, "fact 2": 20, "fact 3": 30})
    assert await memory_module.backfill_embeddings(db, batch=2) == 3 and set(
        db.stored
    ) == {1, 2, 3}

    db = Db()
    embeddings(monkeypatch, {"fact 1": 10})  # the service fails for the others
    assert await memory_module.backfill_embeddings(db) == 1 and set(db.stored) == {1}


@pytest.mark.asyncio
async def test_memory_embeddings_are_stored_searched_and_follow_the_content():
    from core import INITIAL_API_KEY
    from database import Context, PostgresDB, PostgresPool

    def axis(k):  # unit vectors along different axes are 1.0 apart (cosine distance)
        return [1.0 if i == k else 0.0 for i in range(1536)]

    name = f"memvec_test_{uuid.uuid4().hex[:8]}"
    admin = await scratch_pool(name)
    try:
        async with PostgresPool({**DATABASE_CONFIG, "database": name}) as pool:
            db = PostgresDB(pool, Context(agent=None, token=None, user=None))
            db.context.token = await db.ensure_initial_token(INITIAL_API_KEY)
            agent = await db.create_agent("x", 0, name="a")
            db.context.agent = agent
            user = await db.create_user("memvec_user")
            scope = (user.id, agent.id)

            dog = await db.create_memory(*scope, "dog", axis(0))
            await db.create_memory(*scope, "cat", axis(1))
            old = await db.create_memory(
                *scope, "no embedding yet"
            )  # made before embeddings

            assert not hasattr(dog, "embedding") and "embedding" not in dog.model_dump()

            hits = await db.search_memories(*scope, axis(0), limit=5)
            assert [(m.content, round(d, 3)) for m, d in hits] == [
                ("dog", 0.0),
                ("cat", 1.0),
            ]
            assert [
                m.content
                for m, _ in await db.search_memories(
                    *scope, axis(0), 5, max_distance=0.5
                )
            ] == ["dog"]
            assert len(await db.search_memories(*scope, axis(0), limit=1)) == 1

            # other users and agents are not searched
            other = await db.create_user("memvec_other")
            assert await db.search_memories(other.id, agent.id, axis(0), 5) == []

            # an edit without a new embedding clears the old one: it must not match the old words
            await db.update_memory(dog.id, "a different fact")
            assert "a different fact" not in [
                m.content for m, _ in await db.search_memories(*scope, axis(0), 5)
            ]
            assert [m.id for m in await db.memories_without_embedding(10)] == [
                dog.id,
                old.id,
            ]

            await db.set_memory_embedding(old.id, axis(2))
            await db.update_memory(dog.id, "dog again", axis(0))
            assert await db.memories_without_embedding(10) == []
            assert [
                m.content for m, _ in await db.search_memories(*scope, axis(0), 1)
            ] == ["dog again"]
    finally:
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()


def test_auto_memory_is_on_by_default_and_can_be_switched_off(monkeypatch):
    from database import models

    assert agent_row({}).auto_memory is True
    assert agent_row({"auto_memory": False}).auto_memory is False
    assert agent_row({"auto_memory": True}).auto_memory is True
    assert agent_row({}).model_dump()["config"] == {
        "tools": DEFAULT_TOOLS
    }  # stored as set: nothing

    monkeypatch.setattr(
        models, "DEFAULT_AUTO_MEMORY", False
    )  # DEFAULT_AUTO_MEMORY=false
    assert agent_row({}).auto_memory is False
    assert (
        agent_row({"auto_memory": True}).auto_memory is True
    )  # an agent can still turn it on


def test_default_auto_memory_reads_the_environment(monkeypatch):
    import importlib

    from core import config

    try:
        for raw, expected in (
            ("true", True),
            ("1", True),
            ("false", False),
            ("0", False),
            ("OFF", False),
            ("", False),
        ):
            monkeypatch.setenv("DEFAULT_AUTO_MEMORY", raw)
            importlib.reload(config)
            assert config.DEFAULT_AUTO_MEMORY is expected, raw
        monkeypatch.delenv("DEFAULT_AUTO_MEMORY")
        importlib.reload(config)
        assert config.DEFAULT_AUTO_MEMORY is True
    finally:
        monkeypatch.undo()
        importlib.reload(config)
