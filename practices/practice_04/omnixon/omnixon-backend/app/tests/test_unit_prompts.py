"""unit prompts tests"""

import pytest
from ai.memory import MEMORY_INSTRUCTIONS
from ai.attachments import Attachment

from shared import (
    FakeDB,
    NOW,
    PNG_B64,
    memory,
)


def capture_model(answer="ok"):
    """A model that records the messages it is given."""
    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.models.function import FunctionModel

    seen = []

    def respond(messages, info):
        seen.append(messages)
        return ModelResponse(parts=[TextPart(answer)])

    return FunctionModel(respond), seen


def parts_of(messages, kind):
    return [p.content for m in messages for p in m.parts if p.part_kind == kind]


@pytest.mark.asyncio
async def test_memories_are_put_in_front_of_the_users_message_not_in_the_system_prompt(
    monkeypatch,
):
    from ai import endpoint

    db = FakeDB(memories=[memory(2, "Likes tea."), memory(1, "Lives in Prague.")])
    model, seen = capture_model()
    monkeypatch.setattr(endpoint, "generate_model", lambda request_json, **kw: model)

    answer = await endpoint.agent_endpoint(db, "What do you know about me?")
    assert answer == "ok"

    system = "\n".join(parts_of(seen[0], "system-prompt"))
    user = parts_of(seen[0], "user-prompt")[-1]
    # the system prompt is the same for every user: instructions, no personal data
    assert MEMORY_INSTRUCTIONS in system and "Be helpful." in system
    assert (
        "Likes tea." not in system and "What you remember about this user" not in system
    )
    # the user's message carries what is remembered, then their own words
    assert (
        user.startswith("<Memory>")
        and "[2] Likes tea." in user
        and "[1] Lives in Prague." in user
    )
    assert user.endswith("What do you know about me?")
    assert user.index("</Memory>") < user.index("What do you know about me?")
    # only what the user wrote is kept in the history
    assert db.stored[0] == {"type": "user", "content": "What do you know about me?"}


@pytest.mark.asyncio
async def test_without_the_memory_tool_the_model_gets_neither_instructions_nor_memories(
    monkeypatch,
):
    from ai import endpoint

    db = FakeDB(memories=[memory(1, "Likes tea.")], tools=("rag",))
    model, seen = capture_model()
    monkeypatch.setattr(endpoint, "generate_model", lambda request_json, **kw: model)

    await endpoint.agent_endpoint(db, "hello")
    assert MEMORY_INSTRUCTIONS not in "\n".join(parts_of(seen[0], "system-prompt"))
    assert parts_of(seen[0], "user-prompt")[-1] == "hello"


@pytest.mark.asyncio
async def test_the_memory_block_does_not_pile_up_in_the_history(monkeypatch):
    from ai import endpoint
    from database import Message

    history = [
        Message(
            id=1,
            user_id=7,
            timestamp=NOW,
            content={"type": "user", "content": "I like tea."},
        ),
        Message(
            id=2,
            user_id=7,
            timestamp=NOW,
            content={"type": "assistant", "content": "Noted."},
        ),
    ]
    db = FakeDB(memories=[memory(1, "Likes tea.")], messages=history)
    model, seen = capture_model()
    monkeypatch.setattr(endpoint, "generate_model", lambda request_json, **kw: model)

    await endpoint.agent_endpoint(db, "again")
    users = parts_of(seen[0], "user-prompt")
    assert users[0] == "I like tea."  # an old message is as it was written
    assert users[-1].startswith("<Memory>") and users[-1].endswith("again")
    assert sum("<Memory>" in text for text in users) == 1


def tool_then_answer_model():
    """A model that calls the `forget` tool once, then answers."""
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
    from pydantic_ai.models.function import FunctionModel

    calls = []

    def respond(messages, info):
        calls.append(1)
        if len(calls) == 1:
            return ModelResponse(
                parts=[
                    TextPart("Let me check."),
                    ToolCallPart("forget", {"memory_id": 2}),
                ]
            )
        return ModelResponse(parts=[TextPart("Done.")])

    async def stream(messages, info):  # the same, for streamed requests
        from pydantic_ai.models.function import DeltaToolCall

        calls.append(1)
        if len(calls) == 1:
            yield "Let me check."
            yield {0: DeltaToolCall(name="forget", json_args='{"memory_id": 2}')}
        else:
            yield "Done."

    return FunctionModel(respond, stream_function=stream)


@pytest.mark.asyncio
async def test_a_run_reports_its_model_and_tool_calls_only_when_asked(monkeypatch):
    from ai import endpoint

    monkeypatch.setattr(
        endpoint, "generate_model", lambda j, **kw: tool_then_answer_model()
    )
    run = await endpoint.agent_run(
        FakeDB(memories=[memory(2, "Likes tea.")]), "forget tea", trace=True
    )

    assert run.output == "Done."
    assert [(s.step, s.kind) for s in run.trace] == [
        (1, "model"),
        (2, "tool"),
        (3, "model"),
    ]
    first, tool, last = run.trace
    assert first.text == "Let me check." and first.duration_ms is not None
    assert tool.name == "forget" and tool.args == {"memory_id": 2} and tool.result
    assert tool.error is None and tool.duration_ms is not None
    assert last.text == "Done."

    monkeypatch.setattr(
        endpoint, "generate_model", lambda j, **kw: tool_then_answer_model()
    )
    plain = await endpoint.agent_run(
        FakeDB(memories=[memory(2, "Likes tea.")]), "forget tea"
    )
    assert plain.output == "Done." and plain.trace == []


@pytest.mark.asyncio
async def test_a_stream_yields_the_steps_between_the_text(monkeypatch):
    from ai import endpoint
    from ai.trace import TraceStep

    db = FakeDB(memories=[memory(2, "Likes tea.")])
    monkeypatch.setattr(
        endpoint, "generate_model", lambda j, **kw: tool_then_answer_model()
    )
    seen = [
        c async for c in endpoint.agent_stream_endpoint(db, "forget tea", trace=True)
    ]

    steps = [c for c in seen if isinstance(c, TraceStep)]
    text = "".join(c for c in seen if isinstance(c, str))
    assert [s.kind for s in steps] == ["model", "tool", "model"]
    assert [s.step for s in steps] == [1, 2, 3]
    assert "Done." in text

    monkeypatch.setattr(
        endpoint, "generate_model", lambda j, **kw: tool_then_answer_model()
    )
    only_text = [
        c
        async for c in endpoint.agent_stream_endpoint(
            FakeDB(memories=[memory(2, "x")]), "go"
        )
    ]
    assert all(isinstance(c, str) for c in only_text)


def test_the_tracer_keeps_a_failed_tool_and_clips_long_results():
    from datetime import timedelta
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        RetryPromptPart,
        ToolCallPart,
        ToolReturnPart,
    )
    from ai.trace import MAX_CHARS, Tracer, clip

    t0 = NOW
    messages = [
        ModelResponse(
            parts=[
                ToolCallPart("a", {"x": 1}, tool_call_id="1"),
                ToolCallPart("b", "{}", tool_call_id="2"),
                ToolCallPart("c", {}, tool_call_id="3"),
            ],
            model_name="m",
            timestamp=t0,
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    "a",
                    "y" * (MAX_CHARS * 2),
                    tool_call_id="1",
                    timestamp=t0 + timedelta(seconds=2),
                ),
                RetryPromptPart(
                    "bad arguments",
                    tool_name="b",
                    tool_call_id="2",
                    timestamp=t0 + timedelta(seconds=1),
                ),
            ]
        ),
    ]
    tracer = Tracer()
    steps = tracer.feed(messages) + tracer.finish()

    by_name = {s.name: s for s in steps if s.kind == "tool"}
    assert (
        by_name["a"].duration_ms == 2000 and len(by_name["a"].result) < MAX_CHARS + 50
    )
    assert by_name["a"].result.endswith("more characters)")
    assert by_name["b"].error == "bad arguments" and by_name["b"].result is None
    assert by_name["c"].error == "no result"  # never answered
    assert clip({"k": [1, 2]}) == {"k": [1, 2]} and clip(object).startswith("<class")


@pytest.mark.asyncio
async def test_an_agent_without_a_prompt_gets_no_empty_system_message():
    from ai.endpoint import _build_system_prompt
    from ai.utils import get_conversation_history

    db = FakeDB()
    db.context.agent.prompt = ""
    # with the memory tool the system prompt is just the instructions, no blank lines in front
    assert await _build_system_prompt(db) == MEMORY_INSTRUCTIONS
    db.context.agent.tools = ["rag"]
    assert await _build_system_prompt(db) == ""

    # nothing to say: no system message at all (an empty one is refused by some providers)
    assert list(await get_conversation_history(db, "", True)) == []
    with_prompt = await get_conversation_history(db, "Be helpful.", True)
    assert [p.part_kind for m in with_prompt for p in m.parts] == ["system-prompt"]


def test_the_memory_block_goes_before_the_text_and_files_after_it():
    from ai.endpoint import _user_prompt

    assert _user_prompt("hi", [], "") == "hi"
    assert _user_prompt("hi", [], "<Memory>x</Memory>") == "<Memory>x</Memory>\n\nhi"
    files = [Attachment(data=PNG_B64, media_type="image/png")]
    prompt = _user_prompt("hi", files, "<Memory>x</Memory>")
    assert prompt[0] == "<Memory>x</Memory>\n\nhi" and len(prompt) == 2
