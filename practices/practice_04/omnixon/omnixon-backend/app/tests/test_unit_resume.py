"""unit resume tests: a run that fails and is tried again goes on from where it broke, and does not call its tools again"""

import pytest
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import DeltaToolCall, DeltaToolCalls, FunctionModel

from ai import endpoint, resilience
from ai.trace import TraceStep

from shared import FakeDB


def broken_model(fail_on_step: int, failures: int = 1):
    """A model that asks for the tool `remember` first; the step `fail_on_step` (1 = the first) breaks `failures` times (a 503)."""
    state = {"step": 0, "broken": 0, "seen": []}

    def step(messages):
        returned = [p for m in messages for p in getattr(m, "parts", []) if isinstance(p, ToolReturnPart)]
        state["seen"].append(len(messages))
        state["step"] += 1
        stage = 1 if returned else 0  # 0: the model is to ask for the tool, 1: to answer
        if stage + 1 == fail_on_step and state["broken"] < failures:
            state["broken"] += 1
            raise ModelHTTPError(503, "m", "busy")
        return returned

    def function(messages, info):
        if not step(messages):
            return ModelResponse(
                parts=[ToolCallPart("remember", {"fact": "likes tea"})]
            )
        return ModelResponse(parts=[TextPart("all done")])

    async def stream(messages, info):
        if not step(messages):
            yield {
                0: DeltaToolCall(name="remember", json_args='{"fact": "likes tea"}')
            }
        else:
            yield "all done"

    return FunctionModel(function, stream_function=stream), state


@pytest.fixture(autouse=True)
def no_pause(monkeypatch):
    async def instant(_seconds):
        return None

    monkeypatch.setattr(resilience.asyncio, "sleep", instant)


def made(db):
    return [call for call in db.calls if call[0] == "create_memory"]


@pytest.mark.asyncio
async def test_a_failure_after_a_tool_has_run_does_not_run_the_tool_again(monkeypatch):
    model, state = broken_model(fail_on_step=2)
    monkeypatch.setattr(endpoint, "generate_model", lambda request_json, **kw: model)
    db = FakeDB(user=True, tools=("memory",))

    run = await endpoint.agent_run(db, "I like tea", trace=True)

    assert run.output == "all done"
    assert len(made(db)) == 1  # not twice
    assert (
        state["broken"] == 1 and state["step"] == 3
    )  # step 1, step 2 (broke), step 2 again
    # the whole run is in the trace, once: the first model call, the tool, the answer
    assert [(s.kind, s.name) for s in run.trace if s.kind == "tool"] == [
        ("tool", "remember")
    ]
    assert sum(1 for s in run.trace if s.kind == "model") == 2


@pytest.mark.asyncio
async def test_a_failure_of_the_first_step_just_asks_again(monkeypatch):
    model, state = broken_model(fail_on_step=1, failures=2)
    monkeypatch.setattr(endpoint, "generate_model", lambda request_json, **kw: model)
    db = FakeDB(user=True, tools=("memory",))

    run = await endpoint.agent_run(db, "I like tea")

    assert run.output == "all done" and len(made(db)) == 1
    assert state["broken"] == 2
    assert (
        db.stored[0]["content"] == "I like tea"
    )  # the question is in the history once


@pytest.mark.asyncio
async def test_a_stream_that_has_said_nothing_goes_on_from_where_it_broke(monkeypatch):
    model, state = broken_model(fail_on_step=2)
    monkeypatch.setattr(endpoint, "generate_model", lambda request_json, **kw: model)
    db = FakeDB(user=True, tools=("memory",))

    items = [
        item
        async for item in endpoint.agent_stream_endpoint(db, "I like tea", trace=True)
    ]

    assert "".join(i for i in items if isinstance(i, str)) == "all done"
    assert len(made(db)) == 1
    steps = [i for i in items if isinstance(i, TraceStep)]
    assert [s.step for s in steps] == sorted(
        {s.step for s in steps}
    )  # no step is sent twice
    assert sum(1 for s in steps if s.kind == "tool") == 1


@pytest.mark.asyncio
async def test_a_run_that_fails_for_good_still_fails(monkeypatch):
    model, state = broken_model(fail_on_step=2, failures=99)
    monkeypatch.setattr(endpoint, "generate_model", lambda request_json, **kw: model)
    db = FakeDB(user=True, tools=("memory",))

    with pytest.raises(ModelHTTPError):
        await endpoint.agent_run(db, "I like tea")
    assert (
        len(made(db)) == 1
    )  # the tool ran once, however many times the step was asked
