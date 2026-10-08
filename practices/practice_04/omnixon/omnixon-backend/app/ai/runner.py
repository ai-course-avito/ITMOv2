"""Running an agent: the one way, for every kind of request.

`run_agent` is a generator of what happens while an agent answers: the text as it is said, the steps (model calls and tool calls) as they
finish, and at the end the result. The JSON endpoint reads it to the end (`agent_run`); the SSE endpoint forwards it; an agent that is asked by
another one reads it to the end too (`agent_text`). What the answer costs, what is kept of the exchange and what the model learns from it
(auto_memory) happen here once, whoever is listening.

An agent is `Agent(model, instructions=its prompt, capabilities=...)`: what it can do is in `capabilities.build_capabilities`, what goes wrong
and how it is survived is in the capabilities and in `transport` (retries of a provider request), not here.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import AsyncIterator, List, Sequence, Union

from pydantic_ai import Agent
from pydantic_ai.messages import PartDeltaEvent, PartStartEvent, TextPart, TextPartDelta

from core import DEFAULT_PARALLEL_TOOL_CALLS, REQUEST_TIMEOUT_SECONDS, TOOL_MEMORY
from database import PostgresDB
from .attachments import Attachment, contents_of
from .capabilities import build_capabilities
from .deps import Dependencies
from .memory import build_memory_block, schedule_extraction
from .trace import TraceStep, Tracer
from .usage import track_usage
from .utils import generate_model, get_conversation_history, store_exchange

DEFAULT_PROMPT = "Be nice, helpful and friendly."


@dataclass
class Finished:
    """The last item of a run: what the agent said, and the steps behind it (only if they were asked for)."""

    output: str
    trace: List[TraceStep] = field(default_factory=list)


RunItem = Union[str, TraceStep, Finished]


async def build_agent(db: PostgresDB) -> Agent:
    """The agent of this request: its model, its prompt as the instructions, and what it can do."""
    agent = db.context.agent
    model = await db.get_model(agent.model_id if agent else 0)
    prompt = agent.prompt.strip() if agent else DEFAULT_PROMPT  # an agent may have no prompt: then no instructions at all
    parallel = agent.parallel_tool_calls if agent else DEFAULT_PARALLEL_TOOL_CALLS
    return Agent(
        generate_model(model.request_json, **model.connection),
        deps_type=Dependencies,
        instructions=prompt or None,
        capabilities=await build_capabilities(db, answer=agent_text),
        # sent only when it is off (an OpenAI-compatible server may not know it); a model's own `parallel_tool_calls` still wins
        model_settings=None if parallel else {"parallel_tool_calls": False},
        retries={"tools": 2},
    )


async def _model_name(db: PostgresDB) -> str:
    model = await db.get_model(db.context.agent.model_id if db.context.agent else 0)
    return str(model.request_json.get("model", "?")) if model else "?"


def user_prompt(user_input: str, attachments: Sequence[Attachment], memory_block: str = ""):
    """What the model is asked: the memories about the user, the text, then the files. (Only the user's own text is stored in the history,
    not the memory block.)"""
    text = f"{memory_block}\n\n{user_input}" if memory_block else user_input
    if not attachments:
        return text
    return [text, *contents_of(attachments)]


def user_message(attachments: Sequence[Attachment]) -> dict:
    return {"attachments": [a.note() for a in attachments]} if attachments else {}


async def _memory_block(db: PostgresDB) -> str:
    """What the model knows about the user, to be put in front of their message."""
    if db.context.agent and TOOL_MEMORY in db.context.agent.tools:
        return await build_memory_block(db)
    return ""


async def _learn(db: PostgresDB, user_input: str, answer: str) -> None:
    """auto_memory: let the model pick what is worth remembering (in the background). Only for exchanges that are saved."""
    if not db.context.agent:
        return
    model = await db.get_model(db.context.agent.model_id)
    schedule_extraction(db, model.request_json, user_input, answer, model.connection)


async def run_agent(
    db: PostgresDB,
    user_input: str,
    save_message: bool = True,
    use_memo: bool = True,
    attachments: Sequence[Attachment] = (),
    trace: bool = False,
    kind: str = "request",
    stream: bool = True,
) -> AsyncIterator[RunItem]:
    """Answer one request. Yields text chunks (`str`) as they are said, `TraceStep`s as they finish (with `trace`), then `Finished`.

    With `stream` false the model is asked for whole answers (a provider request without streaming) and no text chunks are yielded: for whoever
    only wants the end (`agent_run`).

    Text said before a tool call is yielded as well, separated from later text by a blank line. Unless `save_message` is false the exchange is
    stored once the run has finished. A run that is cancelled before the end (a stream that is stopped) stores nothing here: whoever
    stopped it stores what was said (`save_interrupted`). It must be driven by ONE task from start to end (pydantic-ai keeps anyio cancel scopes
    open across the yields) and stopped by cancelling that task, not by closing the generator from elsewhere: see `interrupt.until_stopped`."""
    deps = Dependencies(db=db)
    history = await get_conversation_history(db, use_memo)
    memory_block = await _memory_block(db)
    agent = await build_agent(db)
    # the calls of one turn run at the same time (pydantic-ai's default) unless the agent says otherwise
    mode = "parallel" if not db.context.agent or db.context.agent.parallel_tool_calls else "sequential"
    tracer = Tracer()
    steps: List[TraceStep] = []  # all of them, for the result; they are yielded as they finish
    said = False  # text was yielded already, so the next part of it starts a new paragraph
    new_part = False

    async with track_usage(db, kind, await _model_name(db)) as usage:
        async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
            # agent.iter keeps the whole run in this task (run_stream_events would run it in a background task, which is left failing when
            # the client disconnects)
            with agent.parallel_tool_call_execution_mode(mode):
                async with agent.iter(user_prompt(user_input, attachments, memory_block), message_history=history, deps=deps) as run:
                    async for node in run:
                        if trace:  # what the nodes before this one did
                            for step in tracer.feed(run.ctx.state.message_history[len(history) :]):
                                steps.append(step)
                                yield step
                        if not stream or not Agent.is_model_request_node(node):
                            continue  # the node is run by the iteration itself
                        async with node.stream(run.ctx) as events:
                            async for event in events:
                                chunk = ""
                                if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                                    chunk, new_part = event.part.content, True
                                elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                                    chunk = event.delta.content_delta
                                if not chunk:
                                    continue
                                if new_part and said:
                                    chunk = "\n\n" + chunk
                                new_part, said = False, True
                                yield chunk
                    if trace:
                        for step in tracer.feed(run.ctx.state.message_history[len(history) :]) + tracer.finish():
                            steps.append(step)
                            yield step
        result = run.result
        usage.add(result.new_messages())

    output = result.output
    if save_message:
        await store_exchange(db, user_input, output, **user_message(attachments))
        await _learn(db, user_input, output)
    yield Finished(output, steps)


async def agent_run(db: PostgresDB, user_input: str, **options) -> Finished:
    """The whole answer, once it is complete (the JSON endpoint)."""
    options.setdefault("stream", False)
    async for item in run_agent(db, user_input, **options):
        if isinstance(item, Finished):
            return item
    raise RuntimeError("an agent run ended without a result")  # not reachable: run_agent always ends with Finished


async def agent_text(db: PostgresDB, user_input: str) -> str:
    """What an agent says to a request that another agent made (not a person): the text only."""
    return (await agent_run(db, user_input, kind="agent_call")).output


async def save_interrupted(db: PostgresDB, user_input: str, partial: str, attachments: Sequence[Attachment] = ()) -> None:
    """An answer that was stopped: the question and what was said of the answer go into the history (the answer marked `interrupted`; no
    answer row at all when nothing had been said), and into the memory like any exchange."""
    rows = [{"type": "user", "content": user_input, **user_message(attachments)}]
    said = partial.strip()
    if said:
        rows.append({"type": "assistant", "content": partial, "interrupted": True})
    await db.create_messages(rows)
    if said:
        await _learn(db, user_input, partial)


async def get_embedding(text: str):
    from .utils import get_embedding_vector

    return await get_embedding_vector(text)
