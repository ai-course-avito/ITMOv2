"""unit conversation tests: a plain request, a streamed one and a stopped one, and agents asking agents (a scripted model on a scratch database)"""

import asyncio
import json
from types import SimpleNamespace

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import DeltaToolCall, FunctionModel

from ai.events import TextChunk
from ai.interrupts import InterruptRegistry
from ai.trace import TraceStep
from domain.errors import NotFound
from repositories.connections import ConnectionRepository
from repositories.data import MemoryRepository
from repositories.people import ChatRepository, MessageRepository, UserRepository
from services.conversations import ConversationService, DoneEvent, ErrorEvent, InterruptedEvent, UserEvent
from world import FakeEmbedder, world

NO_TOOLS = {"tools": [], "auto_memory": False}


def ask(text="hi", **fields):
    return SimpleNamespace(**{"user_id": "alice", "request": text, "save_message": True, "use_memo": True, "chat_id": None, "attachments": [], "trace": False, **fields})


def saying(answer="ok"):
    async def stream(messages, info):
        yield answer

    return FunctionModel(lambda m, i: ModelResponse(parts=[TextPart(answer)]), stream_function=stream)


def scripted(messages, info):
    """A model whose behaviour is its instructions (the prompt of the agent): `call <id>` asks agent <id> and repeats what it said, `list`
    repeats list_agents, anything else answers with the prompt itself."""
    from ai.capabilities.parallel import PARALLEL_INSTRUCTIONS

    prompt = info.instructions.replace("\n\n" + PARALLEL_INSTRUCTIONS, "")
    returned = [p for m in messages for p in getattr(m, "parts", []) if isinstance(p, ToolReturnPart)]
    if returned:
        return ModelResponse(parts=[TextPart(f"[{prompt}] heard: {returned[-1].content}")])
    if prompt.startswith("call "):
        return ModelResponse(parts=[ToolCallPart("ask_agent", {"agent_id": int(prompt.split()[1]), "request": "hello from " + prompt})])
    if prompt == "list":
        return ModelResponse(parts=[ToolCallPart("list_agents", {})])
    return ModelResponse(parts=[TextPart(f"I am {prompt}")])


async def scripted_stream(messages, info):
    for part in scripted(messages, info).parts:
        if isinstance(part, TextPart):
            yield part.content
        else:
            yield {0: DeltaToolCall(name=part.tool_name, json_args=json.dumps(part.args))}


def script():
    return FunctionModel(scripted, stream_function=scripted_stream)


async def history(w, conversation):
    return [m.content for m in await w.get(MessageRepository).window_of(conversation.chat.id, 20)]


# -- a plain request ------------------------------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_request_makes_the_user_and_the_chat_answers_and_keeps_the_exchange():
    async with world(model=saying("hello!")) as w:
        service = w.get(ConversationService)
        p = await w.principal("regular")
        answered = await service.answer(p, ask("hi", user_id=None))  # no id: a user is made
        c = answered.conversation
        assert answered.finished.output == "hello!" and len(c.user.external_id) == 32 and c.chat.is_default
        assert await history(w, c) == [{"type": "user", "content": "hi"}, {"type": "assistant", "content": "hello!"}]
        again = await service.answer(p, ask("and?", user_id=c.user.external_id))
        assert again.conversation.user.id == c.user.id and again.conversation.chat.id == c.chat.id
        assert len(await history(w, c)) == 4


@pytest.mark.asyncio
async def test_what_is_not_saved_is_not_kept_and_a_chat_of_another_user_is_not_found():
    async with world(model=saying()) as w:
        service = w.get(ConversationService)
        p = await w.principal("regular")
        data = ask("secret")
        data.save_message = False
        c = (await service.answer(p, data)).conversation
        assert await history(w, c) == []
        other = await w.get(ChatRepository).insert((await w.get(UserRepository).insert(p.agent.id, "bob")).id)
        with pytest.raises(NotFound, match="^Chat not found$"):
            await service.answer(p, ask("hi", chat_id=other.id))


@pytest.mark.asyncio
async def test_a_chat_is_named_after_the_first_message_and_files_leave_only_a_note():
    from ai.attachments import Attachment

    async with world(model=saying()) as w:
        service = w.get(ConversationService)
        p = await w.principal("regular")
        user = await w.get(UserRepository).insert(p.agent.id, "alice")
        chat = await w.get(ChatRepository).insert(user.id)
        data = ask("what is this?", chat_id=chat.id)
        data.attachments = [Attachment(data="aGk=", media_type="image/png", name="cat.png")]
        await service.answer(p, data)
        assert (await w.get(ChatRepository).get(user.id, chat.id)).title == "what is this?"
        assert (await w.get(MessageRepository).window_of(chat.id, 5))[0].content["attachments"] == [{"media_type": "image/png", "kind": "image", "name": "cat.png"}]


@pytest.mark.asyncio
async def test_the_messages_of_concurrent_requests_of_one_user_do_not_interleave():
    async with world(model=saying()) as w:
        service = w.get(ConversationService)
        p = await w.principal("regular")
        await asyncio.gather(*[service.answer(p, ask(f"q{i}")) for i in range(5)])
        c = (await service.answer(p, ask("last"))).conversation
        kinds = [m["type"] for m in await history(w, c)]
        assert kinds == ["user", "assistant"] * 6


@pytest.mark.asyncio
async def test_a_failing_pair_of_messages_is_not_half_written(monkeypatch):
    async with world(model=saying()) as w:
        service = w.get(ConversationService)
        p = await w.principal("regular")
        c = await service.begin(p, "alice", None)
        messages, calls = w.get(MessageRepository), []
        original = messages.append

        async def failing(*args):
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError("the second row fails")
            return await original(*args)

        monkeypatch.setattr(messages, "append", failing)
        with pytest.raises(RuntimeError):
            await service._store(c, await service._model(c), "q", [], "a")
        monkeypatch.undo()
        assert await history(w, c) == []  # all or none


# -- a stream -------------------------------------------------------------------------------------------------------------------

async def events_of(service, p, data):
    stream = await service.open_stream(p, data)
    return [event async for event in stream.events()]


@pytest.mark.asyncio
async def test_a_stream_says_the_user_first_then_the_text_then_that_it_is_done_and_keeps_the_exchange():
    async with world(model=saying("a streamed answer")) as w:
        service = w.get(ConversationService)
        p = await w.principal("regular")
        events = await events_of(service, p, ask("hi"))
        assert isinstance(events[0], UserEvent) and isinstance(events[-1], DoneEvent) and events[0].user == events[-1].user
        assert "".join(e.text for e in events if isinstance(e, TextChunk)) == "a streamed answer"
        c = await service.begin(p, "alice", None)
        assert await history(w, c) == [{"type": "user", "content": "hi"}, {"type": "assistant", "content": "a streamed answer"}]
        assert w.get(InterruptRegistry)._active == {}  # nothing is left registered


@pytest.mark.asyncio
async def test_a_stream_that_fails_ends_with_an_error_event_and_cleans_up():
    def broken(messages, info):
        raise RuntimeError("the provider fell over")

    async with world(model=FunctionModel(broken, stream_function=None)) as w:
        service = w.get(ConversationService)
        events = await events_of(service, await w.principal("regular"), ask("hi"))
        assert isinstance(events[0], UserEvent) and isinstance(events[-1], ErrorEvent) and w.get(InterruptRegistry)._active == {}


@pytest.mark.asyncio
async def test_trace_steps_come_between_the_text_when_asked_for():
    async with world(model=saying()) as w:
        data = ask("hi")
        data.trace = True
        events = await events_of(w.get(ConversationService), await w.principal("regular"), data)
        assert [e.kind for e in events if isinstance(e, TraceStep)] == ["model"]


@pytest.mark.asyncio
async def test_a_stopped_stream_saves_what_was_said_marked_interrupted_and_nothing_more():
    async def slow(messages, info):
        yield "one two "
        await asyncio.sleep(30)  # the model is thinking
        yield "three"

    model = FunctionModel(lambda m, i: ModelResponse(parts=[TextPart("x")]), stream_function=slow)
    async with world(model=model, default_rag_limit=1) as w:
        service = w.get(ConversationService)
        p = await w.principal("regular")
        stream = await service.open_stream(p, ask("count"))
        seen = []

        async def read():
            async for event in stream.events():
                seen.append(event)

        reading = asyncio.ensure_future(read())
        while not any(isinstance(e, TextChunk) for e in seen):
            await asyncio.sleep(0.01)
        stopped = await asyncio.wait_for(service.interrupt(p, "alice"), 10)  # waits until it has saved
        await asyncio.wait_for(reading, 5)
        assert stopped.text == "one two " and isinstance(seen[-1], InterruptedEvent)
        c = await service.begin(p, "alice", None)
        assert await history(w, c) == [{"type": "user", "content": "count"}, {"type": "assistant", "content": "one two ", "interrupted": True}]
        assert await service.interrupt(p, "alice") is None  # nothing is streaming now


@pytest.mark.asyncio
async def test_a_stop_before_anything_was_said_keeps_the_question_only_and_a_new_request_cuts_the_old_stream():
    async def slow(messages, info):
        await asyncio.sleep(30)
        yield "never"

    model = FunctionModel(lambda m, i: ModelResponse(parts=[TextPart("x")]), stream_function=slow)
    async with world(model=model) as w:
        service = w.get(ConversationService)
        p = await w.principal("regular")
        stream = await service.open_stream(p, ask("hello?"))
        reading = asyncio.ensure_future(_drain(stream))
        await asyncio.sleep(0.5)
        # a new request of the same user cuts the answer that still comes
        w.get(InterruptRegistry).stop_timeout = 5
        await service.interrupts.stop(p.agent.id, (await service.begin(p, "alice", None)).user.id)
        await asyncio.wait_for(reading, 5)
        c = await service.begin(p, "alice", None)
        assert await history(w, c) == [{"type": "user", "content": "hello?"}]


async def _drain(stream):
    return [event async for event in stream.events()]


@pytest.mark.asyncio
async def test_a_cut_answer_is_given_to_the_model_as_an_answer_of_its_own():
    async with world(model=saying()) as w:
        service = w.get(ConversationService)
        p = await w.principal("regular")
        c = await service.begin(p, "alice", None)
        await service._write(c, [{"type": "user", "content": "count to ten"}, {"type": "assistant", "content": "one two three", "interrupted": True}], "count to ten")
        from ai.prompts import PromptBuilder

        history_ = await w.get(PromptBuilder).history(c)
        assert [type(m).__name__ for m in history_][-2:] == ["ModelRequest", "ModelResponse"] and "one two three" in str(history_[-1])


# -- an agent asks another ---------------------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_an_agent_asks_a_connected_one_as_its_caller_and_its_person_and_hears_the_answer():
    async with world(model=script()) as w:
        service = w.get(ConversationService)
        b = await w.agent("Answerer", prompt="I answer", **NO_TOOLS)
        a = await w.agent("Caller", prompt=f"call {b.id}", **NO_TOOLS)
        await w.get(ConnectionRepository).insert(a.id, b.id, "answers questions")
        p = await w.principal("user", agent=a)
        answered = await service.answer(p, ask("hi"))
        assert answered.finished.output == f"[call {b.id}] heard: I am I answer"

        # b was asked by "agent_<a>:alice", in a chat of its own, and remembers it
        asked = await w.get(UserRepository).get(b.id, f"agent_{a.id}:alice")
        assert asked is not None
        chat = await w.get(ChatRepository).default(asked.id)
        assert [m.content["content"] for m in await w.get(MessageRepository).window_of(chat.id, 10)] == [f"hello from call {b.id}", "I am I answer"]
        kinds = [r["kind"] for r in await w.get(ConnectionRepository).db.fetch_all("SELECT kind FROM usage_logs ORDER BY id")]
        assert kinds == ["agent_call", "request"]  # b finished first


@pytest.mark.asyncio
async def test_list_agents_shows_the_connected_agents_with_the_description_of_the_connection():
    async with world(model=script()) as w:
        b = await w.agent("Prices", prompt="x", **NO_TOOLS)
        a = await w.agent("Lister", prompt="list", **NO_TOOLS)
        await w.get(ConnectionRepository).insert(a.id, b.id, "knows the prices")
        answered = await w.get(ConversationService).answer(await w.principal("user", agent=a), ask("who is there?"))
        listed = json.loads(answered.finished.output.split("heard: ", 1)[1])
        assert listed == [{"id": b.id, "name": "Prices", "description": "knows the prices"}]


@pytest.mark.asyncio
async def test_a_chain_never_calls_an_agent_twice_and_never_goes_deeper_than_the_limit():
    async with world(model=script(), agent_call_depth=2) as w:
        service = w.get(ConversationService)
        connections = w.get(ConnectionRepository)
        # a -> b -> a: b may not call a back in the same request
        a = await w.agent("a", prompt="placeholder", **NO_TOOLS)
        b = await w.agent("b", prompt=f"call {a.id}", **NO_TOOLS)
        from repositories.agents import AgentRepository

        await w.get(AgentRepository).update(a.id, prompt=f"call {b.id}")
        await connections.insert(a.id, b.id, "b")
        await connections.insert(b.id, a.id, "a")
        a = await w.get(AgentRepository).get(a.id)  # (the copy in hand has the old prompt)
        out = (await service.answer(await w.principal("user", agent=a), ask("go"))).finished.output
        assert f"Refused: agent {a.id} is already in this chain of calls ({a.id} -> {b.id})" in out

        # a chain of 4 agents with a depth of 2: the third call is refused
        ids = [(await w.agent(f"n{i}", prompt="placeholder", **NO_TOOLS)).id for i in range(4)]
        for here, there in zip(ids, ids[1:]):
            await w.get(AgentRepository).update(here, prompt=f"call {there}")
            await connections.insert(here, there, "next")
        out = (await service.answer(await w.principal("user", agent=await w.get(AgentRepository).get(ids[0])), ask("go"))).finished.output
        assert "Refused: this request is already 2 agents deep" in out


@pytest.mark.asyncio
async def test_asking_an_agent_that_is_not_there_or_not_connected_is_refused_in_words():
    async with world(model=script()) as w:
        service = w.get(ConversationService)
        owner = await w.conversation(role="admin")
        assert (await service.ask_as_agent(owner, 999999, "hi")).startswith("Refused: there is no agent 999999")
        c = await w.agent("c", **NO_TOOLS)
        regular = await w.conversation(role="regular")
        assert await service.ask_as_agent(regular, c.id, "hi") == f"Refused: agent {regular.agent.id} has no connection to agent {c.id}. Call list_agents to see which it has."


@pytest.mark.asyncio
async def test_a_called_agent_that_fails_is_the_tools_answer_not_the_callers_failure(monkeypatch):
    async with world(model=script()) as w:
        service = w.get(ConversationService)
        b = await w.agent("b", prompt="x", **NO_TOOLS)
        caller = await w.conversation(role="user")
        await w.get(ConnectionRepository).insert(caller.agent.id, b.id, "b")

        async def broken(*args, **kwargs):
            raise TimeoutError("the model did not answer")

        monkeypatch.setattr(service.runner, "answer", broken)
        assert (await service.ask_as_agent(caller, b.id, "hi")).startswith(f"Agent {b.id} could not answer (HTTP 504)")
