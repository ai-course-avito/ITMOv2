import asyncio
import json
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple, AsyncIterator, Union

from pydantic_ai import Agent
from pydantic_ai.messages import (
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)

from .attachments import Attachment, contents_of
from .deps import Dependencies
from .agent import generate_agent
from .memory import MEMORY_INSTRUCTIONS, build_memory_block, schedule_extraction
from .agent_calls import connected_agents
from .mcp_calls import server_label
from .resume import Progress
from .resilience import Attempts, ServerList, run_with_attempts
from .trace import Tracer, TraceStep
from .usage import track_usage
from .utils import (
    get_conversation_history,
    store_exchange,
    generate_model,
    build_mcp_server,
    get_embedding_vector,
)
from core import DEFAULT_TOOLS, REQUEST_TIMEOUT_SECONDS, TOOL_MEMORY
from database import PostgresDB


async def get_embedding(text: str) -> List[float]:
    return await get_embedding_vector(text)


async def _build_agent(db: PostgresDB, attempts: Attempts) -> Tuple[Agent, ServerList]:
    """The agent of this request with the MCP servers that can be used right now."""
    servers = []
    missing = []  # servers left out: the model is told, so it can say why their tools are not there
    if db.context.agent:
        for row in await db.get_agent_mcp_servers(db.context.agent.id):
            key = json.dumps(row.config, sort_keys=True)  # a server is its config
            if attempts.usable(key):
                servers.append((key, build_mcp_server(row.config)))
            else:
                missing.append(
                    f"- {row.name} ({server_label(row.config.get('url', ''))}): {attempts.why_left_out(key)}"
                )

    model_id = db.context.agent.model_id if db.context.agent else 0
    model = await db.get_model(model_id)
    agent = generate_agent(
        generate_model(model.request_json, **model.connection),
        [server for _, server in servers],
        _get_agent_tools(db),
        instructions=_unavailable_servers_note(missing),
        connected=await connected_agents(db),
    )
    return agent, servers


def _unavailable_servers_note(missing: Sequence[str]) -> Optional[str]:
    if not missing:
        return None
    return (
        "These MCP servers of yours cannot be reached right now, so their tools are missing from this answer:\n"
        + "\n".join(missing)
        + "\nIf the user asks for something only they could do, say that the server is unavailable and why."
    )


def _get_agent_tools(db: PostgresDB) -> Sequence[str]:
    return db.context.agent.tools if db.context.agent else DEFAULT_TOOLS


async def _model_name(db: PostgresDB) -> str:
    model = await db.get_model(db.context.agent.model_id if db.context.agent else 0)
    return str(model.request_json.get("model", "?")) if model else "?"


async def _learn(db: PostgresDB, user_input: str, answer: str) -> None:
    """auto_memory: let the model pick what is worth remembering (in the background).
    Only for exchanges that are saved: with save_message=false nothing is kept."""
    if not db.context.agent:
        return
    model = await db.get_model(db.context.agent.model_id)
    schedule_extraction(db, model.request_json, user_input, answer, model.connection)


async def _build_system_prompt(db: PostgresDB) -> str:
    if not db.context.agent:
        return "Be nice, helpful and friendly."

    # an agent may have no prompt at all: then there is nothing to put in front of the instructions
    parts = [db.context.agent.prompt.strip()]
    if TOOL_MEMORY in db.context.agent.tools:
        parts.append(MEMORY_INSTRUCTIONS)
    return "\n\n".join(part for part in parts if part)


async def _memory_block(db: PostgresDB) -> str:
    """What the model knows about the user, to be put in front of their message."""
    if db.context.agent and TOOL_MEMORY in db.context.agent.tools:
        return await build_memory_block(db)
    return ""


def _user_prompt(
    user_input: str, attachments: Sequence[Attachment], memory_block: str = ""
):
    """What the model is asked: the memories about the user, the text, then the files.
    (Only the user's own text is stored in the history, not the memory block.)"""
    text = f"{memory_block}\n\n{user_input}" if memory_block else user_input
    if not attachments:
        return text
    return [text, *contents_of(attachments)]


def _user_message(attachments: Sequence[Attachment]) -> dict:
    return {"attachments": [a.note() for a in attachments]} if attachments else {}


@dataclass
class AgentRun:
    output: str
    trace: List[TraceStep] = field(default_factory=list)


async def agent_run(
    db: PostgresDB,
    user_input: str,
    save_message: bool = True,
    use_memo: bool = True,
    attachments: Sequence[Attachment] = (),
    trace: bool = False,
    kind: str = "request",
) -> AgentRun:
    """Answer one request. With `trace` the result also lists the calls that led to the answer."""
    deps = Dependencies(db=db)

    system_prompt = await _build_system_prompt(db)
    messages = await get_conversation_history(db, system_prompt, use_memo)
    memory_block = await _memory_block(db)

    async def build(attempts: Attempts):
        return await _build_agent(db, attempts)

    progress = Progress(messages)

    async def call(agent: Agent):
        holder = {}
        try:
            async with agent.iter(
                progress.prompt(_user_prompt(user_input, attachments, memory_block)),
                message_history=progress.message_history(),
                deps=deps,
            ) as run:
                holder["run"] = run
                async for _ in run:
                    pass
        except Exception:
            progress.remember(holder.get("run"))  # the next attempt goes on from here
            raise
        return run.result

    # a provider failure is retried, from where it broke; an MCP server that is down is left out
    async with track_usage(db, kind, await _model_name(db)) as usage:
        async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
            result = await run_with_attempts(build, call)
        done = progress.new_messages(result)
        usage.add(done)

    if save_message:
        await store_exchange(
            db, user_input, result.output, **_user_message(attachments)
        )
        await _learn(db, user_input, result.output)

    steps: List[TraceStep] = []
    if trace:
        tracer = Tracer()
        steps = tracer.feed(done) + tracer.finish()
    return AgentRun(result.output, steps)


async def save_interrupted(
    db: PostgresDB,
    user_input: str,
    partial: str,
    attachments: Sequence[Attachment] = (),
) -> None:
    """An answer that was stopped: the question and what was said of the answer go into the history (the answer marked `interrupted`; no
    answer row at all when nothing had been said), and into the memory like any exchange."""
    rows = [{"type": "user", "content": user_input, **_user_message(attachments)}]
    said = partial.strip()
    if said:
        rows.append({"type": "assistant", "content": partial, "interrupted": True})
    await db.create_messages(rows)
    if said:
        await _learn(db, user_input, partial)


async def agent_endpoint(
    db: PostgresDB,
    user_input: str,
    save_message: bool = True,
    use_memo: bool = True,
    attachments: Sequence[Attachment] = (),
) -> str:
    return (await agent_run(db, user_input, save_message, use_memo, attachments)).output


async def agent_stream_endpoint(
    db: PostgresDB,
    user_input: str,
    save_message: bool = True,
    use_memo: bool = True,
    attachments: Sequence[Attachment] = (),
    trace: bool = False,
) -> AsyncIterator[Union[str, TraceStep]]:
    """Yield the assistant's text as it is generated.

    With `trace` the steps (model calls and tool calls) are yielded too, as `TraceStep`
    objects, as soon as they have finished.

    Text produced before a tool call (e.g. an MCP tool) is streamed as well,
    separated from later text by a blank line. Unless `save_message` is false, the
    conversation is stored once the run has finished, using the agent's final
    output (same as agent_endpoint). `use_memo=False` skips the stored history.
    A failure is retried like in agent_endpoint as long as nothing was sent yet.
    """
    deps = Dependencies(db=db)

    system_prompt = await _build_system_prompt(db)
    messages = await get_conversation_history(db, system_prompt, use_memo)
    memory_block = await _memory_block(db)

    async with track_usage(db, "stream", await _model_name(db)) as usage:
        attempts = Attempts()
        progress = Progress(messages)
        tracer = Tracer()  # one for all attempts: a retry goes on from where the run broke
        streamed_text = (
            False  # something was sent: the answer can no longer be restarted
        )

        while True:
            agent, servers = await _build_agent(db, attempts)
            new_text_part = False
            run = None

            try:
                # agent.iter keeps the whole run in this task (run_stream_events would run
                # it in a background task, which is left failing when the client disconnects)
                async with agent.iter(
                    progress.prompt(_user_prompt(user_input, attachments, memory_block)),
                    message_history=progress.message_history(),
                    deps=deps,
                ) as run:
                    async for node in run:
                        if trace:  # what the nodes before this one did
                            for step in tracer.feed(
                                run.ctx.state.message_history[len(messages) :]
                            ):
                                yield step
                        if not Agent.is_model_request_node(node):
                            continue

                        async with node.stream(run.ctx) as events:
                            async for event in events:
                                chunk = ""
                                if isinstance(event, PartStartEvent) and isinstance(
                                    event.part, TextPart
                                ):
                                    chunk = event.part.content
                                    new_text_part = True
                                elif isinstance(event, PartDeltaEvent) and isinstance(
                                    event.delta, TextPartDelta
                                ):
                                    chunk = event.delta.content_delta

                                if not chunk:
                                    continue

                                if new_text_part and streamed_text:
                                    chunk = "\n\n" + chunk
                                new_text_part = False
                                streamed_text = True
                                yield chunk
                    if trace:
                        for step in (
                            tracer.feed(run.ctx.state.message_history[len(messages) :])
                            + tracer.finish()
                        ):
                            yield step
                break
            except Exception as exc:
                if streamed_text:
                    raise
                progress.remember(run)  # the next attempt goes on from here
                tracer.rewind(len(progress.kept))
                await attempts.after_failure(exc, servers)

        if run.result:
            usage.add(progress.new_messages(run.result))

    output = run.result.output if run.result else None

    if save_message:
        await store_exchange(db, user_input, output or "", **_user_message(attachments))
        await _learn(db, user_input, output or "")
