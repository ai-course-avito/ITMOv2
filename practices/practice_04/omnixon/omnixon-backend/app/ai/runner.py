"""Running an agent: the one way, for every kind of request.

`AgentRunner.run` is a generator of what happens while an agent answers: the text as it is said, the steps (model calls and tool calls) as they
finish, and at the end the result. The JSON endpoint reads it to the end; the SSE endpoint forwards it; an agent that is asked by another one reads
it to the end too. What the answer costs is written here once, whoever is listening. What is kept of the exchange, and what the model learns from it
(auto_memory), is the conversation service's business: the runner stores nothing.

An agent is `Agent(model, instructions=its prompt, capabilities=...)` (see `AgentFactory`); what goes wrong and how it is survived is in the
capabilities and in the transport (retries of a provider request), not here.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import AsyncIterator, List

from pydantic_ai import Agent
from pydantic_ai.messages import PartDeltaEvent, PartStartEvent, TextPart, TextPartDelta

from database.models import Model
from domain.access import Conversation
from services.knowledge import KnowledgeService
from services.memories import MemoryService
from .deps import RunDeps
from .events import Finished, RunEvent, RunRequest, TextChunk
from .factory import AgentFactory
from .prompts import PromptBuilder
from .trace import TraceStep, Tracer
from .usage import UsageMeter


class AgentRunner:
    def __init__(
        self,
        factory: AgentFactory,
        prompts: PromptBuilder,
        meter: UsageMeter,
        memory: MemoryService,
        knowledge: KnowledgeService,
        timeout_seconds: float,
    ):
        self.factory, self.prompts, self.meter = factory, prompts, meter
        self.memory, self.knowledge, self.timeout_seconds = memory, knowledge, timeout_seconds

    async def run(self, conversation: Conversation, model: Model, request: RunRequest) -> AsyncIterator[RunEvent]:
        """Answer one request. Yields `TextChunk`s as they are said, `TraceStep`s as they finish (with `trace`), then `Finished`.

        Text said before a tool call is yielded as well, separated from later text by a blank line. With `stream` false the model is asked for
        whole answers and no text chunks are yielded. It must be driven by ONE task from start to end (pydantic-ai keeps anyio cancel scopes
        open across the yields) and stopped by cancelling that task, not by closing the generator from elsewhere: see `StreamGuard`."""
        deps = RunDeps(conversation, self.memory, self.knowledge)
        history = await self.prompts.history(conversation, request.use_memo)
        asked = self.prompts.prompt(request.text, request.attachments, await self.prompts.memory_block(conversation))
        agent = await self.factory.build(conversation, model)
        # the calls of one turn run at the same time (pydantic-ai's default) unless the agent says otherwise
        mode = "parallel" if conversation.settings.parallel_tool_calls else "sequential"
        tracer = Tracer()
        steps: List[TraceStep] = []  # all of them, for the result; they are yielded as they finish
        said = False  # text was yielded already, so the next part of it starts a new paragraph
        new_part = False

        async with self.meter.track(conversation.principal, request.kind, str(model.request_json.get("model", "?"))) as usage:
            async with asyncio.timeout(self.timeout_seconds):
                # agent.iter keeps the whole run in this task (run_stream_events would run it in a background task, which is left failing when
                # the client disconnects)
                with agent.parallel_tool_call_execution_mode(mode):
                    async with agent.iter(asked, message_history=history, deps=deps) as run:
                        async for node in run:
                            if request.trace:  # what the nodes before this one did
                                for step in tracer.feed(run.ctx.state.message_history[len(history) :]):
                                    steps.append(step)
                                    yield step
                            if not request.stream or not Agent.is_model_request_node(node):
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
                                    yield TextChunk(chunk)
                        if request.trace:
                            for step in tracer.feed(run.ctx.state.message_history[len(history) :]) + tracer.finish():
                                steps.append(step)
                                yield step
            result = run.result
            usage.add(result.new_messages())

        yield Finished(result.output, steps)

    async def answer(self, conversation: Conversation, model: Model, request: RunRequest) -> Finished:
        """The whole answer, once it is complete (whole answers from the provider, nothing streamed)."""
        async for event in self.run(conversation, model, replace(request, stream=False)):
            if isinstance(event, Finished):
                return event
        raise RuntimeError("an agent run ended without a result")  # not reachable: run always ends with Finished
