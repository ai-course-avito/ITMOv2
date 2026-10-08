"""unit parallel tests: the tools a model calls in one turn run together, unless the agent says no (ai/runner.py, capabilities/parallel.py)"""

import asyncio
import time

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import DeltaToolCall, FunctionModel

from ai import runner
from ai.capabilities import ParallelCalls, build_capabilities
from ai.capabilities.parallel import PARALLEL_INSTRUCTIONS
from database import AgentConfig
from routers.agent import AgentConfigInput

from shared import FakeDB, agent_row

PAUSE = 0.3
CALLS = 4


class SlowDB(FakeDB):
    """Every `recall` takes a moment, so whether the calls overlap shows in the time."""

    async def get_memories(self, user_id, agent_id, limit=None, query=None):
        await asyncio.sleep(PAUSE)
        return []


def four_recalls(seen=None):
    """A model that asks for `recall` four times in its first turn, then answers."""

    def respond(messages, info):
        if seen is not None:
            seen.append(info)
        if len(messages) == 1:
            return ModelResponse(parts=[ToolCallPart("recall", {}, tool_call_id=f"c{i}") for i in range(CALLS)])
        return ModelResponse(parts=[TextPart("done")])

    async def stream(messages, info):
        if seen is not None:
            seen.append(info)
        if len(messages) == 1:
            yield {i: DeltaToolCall(name="recall", json_args="{}", tool_call_id=f"c{i}") for i in range(CALLS)}
        else:
            yield "done"

    return FunctionModel(respond, stream_function=stream)


async def timed(monkeypatch, db, seen=None, **options):
    monkeypatch.setattr(runner, "generate_model", lambda j, **kw: four_recalls(seen))
    started = time.monotonic()
    run = await runner.agent_run(db, "go", **options)
    assert run.output == "done"
    return time.monotonic() - started


@pytest.mark.asyncio
async def test_the_calls_of_one_turn_run_at_the_same_time(monkeypatch):
    elapsed = await timed(monkeypatch, SlowDB(tools=("memory",)))
    assert elapsed < PAUSE * 3  # the memory block (one pause) and then four calls of 0.3 s together, not 1.2 s one by one


@pytest.mark.asyncio
async def test_with_parallel_tool_calls_off_they_run_one_after_another_and_the_provider_is_told(monkeypatch):
    seen = []
    db = SlowDB(tools=("memory",))
    db.context.agent.parallel_tool_calls = False
    elapsed = await timed(monkeypatch, db, seen)
    assert elapsed >= PAUSE * CALLS
    assert seen[0].model_settings["parallel_tool_calls"] is False  # the provider is asked for one call per turn too
    assert PARALLEL_INSTRUCTIONS not in (seen[0].instructions or "")


@pytest.mark.asyncio
async def test_the_provider_is_not_given_a_setting_when_parallel_is_on_and_the_model_is_told_it_may(monkeypatch):
    seen = []
    await timed(monkeypatch, SlowDB(tools=("memory",)), seen)
    assert "parallel_tool_calls" not in (seen[0].model_settings or {})
    assert PARALLEL_INSTRUCTIONS in seen[0].instructions


@pytest.mark.asyncio
async def test_only_an_agent_with_tools_is_told_to_call_them_together():
    names = lambda caps: [type(c).__name__ for c in caps]  # noqa: E731

    async def nobody(db, request):
        return ""

    assert "ParallelCalls" in names(await build_capabilities(FakeDB(tools=("memory",)), nobody))
    assert "ParallelCalls" not in names(await build_capabilities(FakeDB(tools=()), nobody))
    off = FakeDB(tools=("memory",))
    off.context.agent.parallel_tool_calls = False
    assert "ParallelCalls" not in names(await build_capabilities(off, nobody))
    assert ParallelCalls().get_instructions() == PARALLEL_INSTRUCTIONS


def test_the_setting_is_part_of_the_agent_config_and_defaults_to_on():
    assert agent_row({}).parallel_tool_calls is True
    assert agent_row({"parallel_tool_calls": False}).parallel_tool_calls is False
    assert AgentConfig().parallel_tool_calls is None  # unset: the default, not stored
    assert AgentConfigInput(parallel_tool_calls=False).model_dump(exclude_unset=True) == {"parallel_tool_calls": False}
    assert AgentConfigInput(parallel_tool_calls=None).model_dump(exclude_unset=True) == {"parallel_tool_calls": None}  # null: back to the default


@pytest.mark.asyncio
async def test_two_tools_that_ask_the_same_agent_at_once_both_get_its_user():
    from shared import scratch_database

    async with scratch_database("parallel_user") as (pool, db):
        target = await db.create_agent("t", 0, name="target")

        async def arrive():
            handle = db.with_context(agent=target, user=None, chat=None)
            await handle.insure_user("agent_1:alice")
            chat = await handle.ensure_default_chat()
            return handle.context.user.id, chat.id

        results = await asyncio.gather(*[arrive() for _ in range(6)])
        assert len(set(results)) == 1  # one user, one chat, however many arrived together
