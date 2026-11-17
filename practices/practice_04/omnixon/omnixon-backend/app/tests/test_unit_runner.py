"""unit runner tests: what the model is given, the events of a run, the order and the time of tool calls, and what a run leaves behind"""

import asyncio
import time

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import DeltaToolCall, FunctionModel

from ai.events import Finished, RunRequest, TextChunk
from ai.interrupts import InterruptRegistry, StreamGuard
from ai.prompts import PromptBuilder
from ai.runner import AgentRunner
from ai.trace import TraceStep
from infrastructure.llm import Embedder
from repositories.data import MemoryRepository, UsageRepository
from repositories.models import ModelRepository
from repositories.people import MessageRepository
from services.memories import MEMORY_INSTRUCTIONS
from world import FakeEmbedder, world


def recorder(answer="ok"):
    """A model that records the messages it is given and says `answer`."""
    seen = []

    def respond(messages, info):
        seen.append((messages, info))
        return ModelResponse(parts=[TextPart(answer)])

    async def stream(messages, info):
        seen.append((messages, info))
        yield answer

    return FunctionModel(respond, stream_function=stream), seen


def parts(messages, kind):
    return [p.content for m in messages for p in m.parts if p.part_kind == kind]


async def run(w, conversation, text="hi", **options):
    model = await w.get(ModelRepository).get(0)
    return [event async for event in w.get(AgentRunner).run(conversation, model, RunRequest(text, **options))]


@pytest.mark.asyncio
async def test_memories_go_in_front_of_the_users_message_not_into_the_system_prompt():
    model, seen = recorder()
    async with world(model=model, embedder=FakeEmbedder({"Likes tea.": 0.0, "Lives in Prague.": 2.0})) as w:
        c = await w.conversation(agent=await w.agent("a", prompt="Be helpful."))
        for fact in ("Lives in Prague.", "Likes tea."):
            await w.get(MemoryRepository).insert(c.user.id, c.agent.id, fact)
        events = await run(w, c, "What do you know about me?")
        assert events[-1] == Finished("ok", [])
        messages, info = seen[0]
        system = info.instructions
        user = parts(messages, "user-prompt")[-1]
        assert MEMORY_INSTRUCTIONS in system and "Be helpful." in system  # the same for every user: instructions, no personal data
        assert "Likes tea." not in system
        assert user.startswith("<Memory>") and "Likes tea." in user and "Lives in Prague." in user
        assert user.endswith("What do you know about me?") and user.index("</Memory>") < user.index("What do you")


@pytest.mark.asyncio
async def test_without_the_memory_tool_the_model_gets_neither_instructions_nor_memories():
    model, seen = recorder()
    async with world(model=model) as w:
        c = await w.conversation(agent=await w.agent("a", tools=["rag"]))
        await w.get(MemoryRepository).insert(c.user.id, c.agent.id, "Likes tea.")
        await run(w, c, "hello")
        messages, info = seen[0]
        assert MEMORY_INSTRUCTIONS not in (info.instructions or "") and parts(messages, "user-prompt")[-1] == "hello"


@pytest.mark.asyncio
async def test_the_history_is_what_was_written_and_the_memory_block_does_not_pile_up_in_it():
    model, seen = recorder()
    async with world(model=model) as w:
        c = await w.conversation()
        for row in ({"type": "user", "content": "I like tea."}, {"type": "assistant", "content": "Noted."}):
            await w.get(MessageRepository).append(c.user.id, c.chat.id, c.agent.id, row)
        await w.get(MemoryRepository).insert(c.user.id, c.agent.id, "Likes tea.")
        await run(w, c, "again")
        users = parts(seen[0][0], "user-prompt")
        assert users[0] == "I like tea."  # an old message is as it was written
        assert users[-1].startswith("<Memory>") and users[-1].endswith("again") and sum("<Memory>" in u for u in users) == 1
        seen.clear()
        await run(w, c, "alone", use_memo=False)  # the history only: memories stay
        assert len(parts(seen[0][0], "user-prompt")) == 1


@pytest.mark.asyncio
async def test_the_history_never_starts_with_an_answer_and_old_files_are_a_note():
    async with world(model=recorder()[0]) as w:
        c = await w.conversation()
        rows = [
            {"type": "assistant", "content": "a1"},
            {"type": "user", "content": "q2", "attachments": [{"kind": "image", "media_type": "image/png", "name": "cat.png"}]},
            {"type": "assistant", "content": "a2"},
        ]
        for row in rows:
            await w.get(MessageRepository).append(c.user.id, c.chat.id, c.agent.id, row)
        history = await w.get(PromptBuilder).history(c)
        assert [m.parts[0].content for m in history] == ["q2\n[attached image: cat.png]", "a2"]
        assert await w.get(PromptBuilder).history(c, use_memo=False) == []


def test_the_prompt_is_the_memory_block_then_the_text_and_the_files_after_it():
    from ai.attachments import Attachment

    assert PromptBuilder.prompt("hi", []) == "hi"
    assert PromptBuilder.prompt("hi", [], "<Memory>x</Memory>") == "<Memory>x</Memory>\n\nhi"
    files = [Attachment(data="aGk=", media_type="image/png", name="a.png")]
    asked = PromptBuilder.prompt("hi", files, "<Memory>x</Memory>")
    assert asked[0] == "<Memory>x</Memory>\n\nhi" and len(asked) == 2
    assert PromptBuilder.stored([]) == {} and PromptBuilder.stored(files) == {"attachments": [{"media_type": "image/png", "kind": "image", "name": "a.png"}]}


def forgetting_model():
    """A model that says something, calls the `forget` tool once, then answers."""
    calls = []

    def respond(messages, info):
        calls.append(1)
        if len(calls) == 1:
            return ModelResponse(parts=[TextPart("Let me check."), ToolCallPart("forget", {"memory_id": 2})])
        return ModelResponse(parts=[TextPart("Done.")])

    async def stream(messages, info):
        calls.append(1)
        if len(calls) == 1:
            yield "Let me check."
            yield {0: DeltaToolCall(name="forget", json_args='{"memory_id": 2}')}
        else:
            yield "Done."

    return FunctionModel(respond, stream_function=stream)


@pytest.mark.asyncio
async def test_a_run_reports_its_model_and_tool_calls_only_when_asked_and_streams_the_text_between_them():
    async with world(model=forgetting_model()) as w:
        c = await w.conversation()
        events = await run(w, c, "forget tea", trace=True)
        steps = [e for e in events if isinstance(e, TraceStep)]
        assert [(s.step, s.kind) for s in steps] == [(1, "model"), (2, "tool"), (3, "model")]
        first, tool, last = steps
        assert first.text == "Let me check." and tool.name == "forget" and tool.args == {"memory_id": 2} and tool.result and last.text == "Done."
        text = "".join(e.text for e in events if isinstance(e, TextChunk))
        assert text == "Let me check.\n\nDone."  # a blank line between the text of different turns
        assert events[-1].output == "Done." and [s.step for s in events[-1].trace] == [1, 2, 3]

    async with world(model=forgetting_model()) as w:
        c = await w.conversation()
        plain = await run(w, c, "forget tea")
        assert not [e for e in plain if isinstance(e, TraceStep)] and plain[-1].trace == []


@pytest.mark.asyncio
async def test_asking_for_whole_answers_streams_nothing():
    model, seen = recorder("whole")
    async with world(model=model) as w:
        c = await w.conversation()
        events = await run(w, c, "hi", stream=False)
        assert [type(e).__name__ for e in events] == ["Finished"] and events[0].output == "whole"
        done = await w.get(AgentRunner).answer(c, await w.get(ModelRepository).get(0), RunRequest("hi"))
        assert done.output == "whole"  # `answer` asks for whole answers whatever the request says


# -- tool calls of one turn --------------------------------------------------------------------------------------------------

PAUSE, CALLS = 0.3, 4


class SlowMemories(MemoryRepository):
    async def newest(self, *args, **kwargs):
        await asyncio.sleep(PAUSE)
        return []


def four_recalls():
    def respond(messages, info):
        if len(messages) == 1:
            return ModelResponse(parts=[ToolCallPart("recall", {}, tool_call_id=f"c{i}") for i in range(CALLS)])
        return ModelResponse(parts=[TextPart("done")])

    async def stream(messages, info):
        if len(messages) == 1:
            yield {i: DeltaToolCall(name="recall", json_args="{}", tool_call_id=f"c{i}") for i in range(CALLS)}
        else:
            yield "done"

    return FunctionModel(respond, stream_function=stream)


async def timed(w, conversation, **options):
    w.get(MemoryRepository).newest = SlowMemories(w.get(MemoryRepository).db).newest  # every `recall` takes a moment
    started = time.monotonic()
    events = await run(w, conversation, "go", stream=False, **options)
    assert events[-1].output == "done"
    return time.monotonic() - started


@pytest.mark.asyncio
async def test_the_calls_of_one_turn_run_together_unless_the_agent_says_no():
    async with world(model=four_recalls()) as w:
        assert await timed(w, await w.conversation(agent=await w.agent("on"))) < PAUSE * 3  # the memory block, then four calls together
    async with world(model=four_recalls()) as w:
        assert await timed(w, await w.conversation(agent=await w.agent("off", parallel_tool_calls=False))) >= PAUSE * CALLS


# -- what a run leaves behind ----------------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_run_writes_one_usage_row_on_the_token_and_stores_no_message():
    model, _ = recorder()
    async with world(model=model) as w:
        c = await w.conversation()
        await run(w, c, "hi")
        rows = await w.get(UsageRepository).db.fetch_all("SELECT token_id, kind, status, model FROM usage_logs")
        assert [(r["token_id"], r["kind"], r["status"]) for r in rows] == [(c.principal.token.id, "request", "ok")]
        assert await w.get(MessageRepository).window_of(c.chat.id, 10) == []  # keeping the exchange is not the runner's business


@pytest.mark.asyncio
async def test_a_run_that_is_stopped_before_its_end_leaves_a_row_that_says_interrupted_and_stores_nothing():
    async def slow(messages, info):
        yield "part one "
        await asyncio.sleep(30)  # the model is thinking: a stop must not wait for it
        yield "part two"

    model = FunctionModel(lambda m, i: ModelResponse(parts=[TextPart("x")]), stream_function=slow)
    async with world(model=model) as w:
        c = await w.conversation()
        registry = w.get(InterruptRegistry)
        stream = registry.start((c.agent.id, c.user.id))
        seen = []
        try:
            async with asyncio.timeout(5):  # not the 30 seconds of the model
                async for event in StreamGuard.items(w.get(AgentRunner).run(c, await w.get(ModelRepository).get(0), RunRequest("hi")), stream):
                    seen.append(event)
                    stream.interrupted = True
                    stream.wanted.set()
        finally:
            registry.end(stream)
        assert seen == [TextChunk("part one ")]
        rows = await w.get(UsageRepository).db.fetch_all("SELECT status FROM usage_logs")
        assert [r["status"] for r in rows] == ["interrupted"]
        assert await w.get(MessageRepository).window_of(c.chat.id, 10) == []
