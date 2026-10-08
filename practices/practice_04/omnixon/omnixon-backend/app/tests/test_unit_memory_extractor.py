"""unit memory extractor tests: what the model is asked after an exchange, what is kept of the answer, and that a failure costs only the extraction"""

import asyncio

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from ai.memory_extractor import MAX_FACTS_PER_EXCHANGE, MemoryExtractor
from infrastructure.jobs import TaskSupervisor
from repositories.data import MemoryRepository
from repositories.models import ModelRepository
from world import FakeEmbedder, world


def extractor_model(facts, prompts=None):
    """A pydantic-ai model that answers the memory extraction with `facts`."""

    def answer(messages, info):
        if prompts is not None:
            prompts.append(messages[-1].parts[0].content)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"response": facts})])

    return FunctionModel(answer)


def distinct(*facts):
    return FakeEmbedder({fact: float(i) * 0.7 for i, fact in enumerate(facts)})


@pytest.mark.asyncio
async def test_facts_are_extracted_from_an_exchange_and_remembered():
    facts = ["The user is called Ivan.", "  ", "The user lives in Prague.", "The user has a cat."]
    prompts = []
    async with world(model=extractor_model(facts, prompts), embedder=distinct(*facts)) as w:
        c = await w.conversation()
        await w.get(MemoryRepository).insert(c.user.id, c.agent.id, "The user lives in Prague.")
        model = await w.get(ModelRepository).get(0)
        created = await w.get(MemoryExtractor).extract(c, model, "I'm Ivan, I live in Prague and have a cat.", "Nice to meet you, Ivan!")
        # blanks and what is remembered already are skipped
        assert [m.content for m in created] == ["The user is called Ivan.", "The user has a cat."]
        # the model is told what is known, and what was said
        assert "- The user lives in Prague." in prompts[0]
        assert "I'm Ivan" in prompts[0] and "Nice to meet you" in prompts[0]
        rows = await w.get(MemoryRepository).db.fetch_all("SELECT kind, model FROM usage_logs")
        assert [r["kind"] for r in rows] == ["auto_memory"]


@pytest.mark.asyncio
async def test_at_most_a_few_facts_are_taken_from_one_exchange():
    facts = [f"Fact number {i}." for i in range(12)]
    async with world(model=extractor_model(facts), embedder=distinct(*facts)) as w:
        c = await w.conversation()
        model = await w.get(ModelRepository).get(0)
        assert len(await w.get(MemoryExtractor).extract(c, model, "x", "y")) == MAX_FACTS_PER_EXCHANGE
    async with world(model=extractor_model([])) as w:
        c = await w.conversation()
        assert await w.get(MemoryExtractor).extract(c, await w.get(ModelRepository).get(0), "x", "y") == []


@pytest.mark.asyncio
async def test_extraction_runs_in_the_background_and_never_raises():
    async with world(model=extractor_model(["The user is called Ivan."])) as w:
        c = await w.conversation(agent=await w.agent("a", auto_memory=True))
        model = await w.get(ModelRepository).get(0)
        extractor = w.get(MemoryExtractor)
        extractor.schedule(c, model, "I'm Ivan", "Hello Ivan")
        await asyncio.gather(*extractor.supervisor._tasks)
        assert [m.content for m in await w.get(MemoryRepository).newest(c.user.id, c.agent.id, 5)] == ["The user is called Ivan."]

        async def broken(*args, **kwargs):
            raise RuntimeError("model is down")

        extractor.extract = broken  # a failing model costs only the extraction
        extractor.schedule(c, model, "x", "y")
        await asyncio.gather(*extractor.supervisor._tasks)  # no exception


@pytest.mark.asyncio
async def test_extraction_is_not_scheduled_without_auto_memory_or_the_memory_tool():
    async with world(model=extractor_model(["x"])) as w:
        extractor = w.get(MemoryExtractor)
        model = await w.get(ModelRepository).get(0)
        for config in ({"auto_memory": False}, {"auto_memory": True, "tools": ["rag"]}):
            c = await w.conversation(agent=await w.agent("a", **config))
            assert extractor.wanted(c) is False
            extractor.schedule(c, model, "x", "y")
            assert extractor.supervisor.running == 0
        assert extractor.wanted(await w.conversation(agent=await w.agent("on", auto_memory=True))) is True


@pytest.mark.asyncio
async def test_the_supervisor_cancels_what_is_still_being_learned_at_close():
    started = asyncio.Event()

    def never(messages, info):
        raise AssertionError("not reached")

    async with world(model=extractor_model([])) as w:
        supervisor = w.get(TaskSupervisor)

        async def slow():
            started.set()
            await asyncio.sleep(30)

        supervisor.spawn(slow(), "slow")
        await started.wait()
        await supervisor.aclose()
        assert supervisor.running == 0
