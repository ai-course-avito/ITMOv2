"""Talking to an agent: the use case behind `/request` and `/request-stream`, and what an agent does when it asks another.

It finds the user and the chat, stops the answer that still comes to the same person, runs the agent through the runner (which stores
nothing), keeps the exchange (or the part of it that was said before a stop), and lets the model learn from it in the background."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import AsyncIterator, Optional, Union

import logfire

from ai.events import Finished, RunRequest, TextChunk
from ai.interrupts import ActiveStream, InterruptRegistry, StreamGuard
from ai.memory_extractor import MemoryExtractor
from ai.prompts import PromptBuilder
from ai.runner import AgentRunner
from ai.trace import TraceStep
from config import AgentDefaults
from core import error_response, metrics
from database.models import Chat, Model, User
from domain.access import AccessPolicy, Conversation, Principal
from domain.chain import CallChain, caller_user_id
from domain.errors import Failed, NotFound
from repositories.agents import AgentRepository
from repositories.models import ModelRepository
from repositories.people import ChatRepository, MessageRepository
from repositories.unit_of_work import UnitOfWork
from .connections import ConnectionService
from .users import ChatService, UserService


@dataclass
class Answered:
    """The result of a plain request."""

    conversation: Conversation
    finished: Finished


@dataclass(frozen=True)
class UserEvent:
    user: User


@dataclass(frozen=True)
class DoneEvent:
    user: User


@dataclass(frozen=True)
class InterruptedEvent:
    user: User


@dataclass(frozen=True)
class ErrorEvent:
    detail: str


StreamEvent = Union[UserEvent, TextChunk, TraceStep, DoneEvent, InterruptedEvent, ErrorEvent]


class ConversationService:
    def __init__(
        self,
        users: UserService,
        chats: ChatService,
        chat_repo: ChatRepository,
        messages: MessageRepository,
        agents: AgentRepository,
        models: ModelRepository,
        runner: AgentRunner,
        interrupts: InterruptRegistry,
        extractor: MemoryExtractor,
        connections: ConnectionService,
        policy: AccessPolicy,
        uow: UnitOfWork,
        defaults: AgentDefaults,
        call_depth: int,
    ):
        self.users, self.chats, self.chat_repo, self.messages = users, chats, chat_repo, messages
        self.agents, self.models, self.runner, self.interrupts = agents, models, runner, interrupts
        self.extractor, self.connections, self.policy, self.uow = extractor, connections, policy, uow
        self.defaults, self.call_depth = defaults, call_depth

    # -- the conversation of a request ----------------------------------------------------------------------------------------

    async def begin(self, principal: Principal, user_id: Optional[str], chat_id: Optional[int]) -> Conversation:
        """Find or make the user of the request (a request with no id gets a new user), and the chat it goes to."""
        agent = principal.agent
        if user_id is None or not user_id.strip():
            user: Optional[User] = None
            for _ in range(5):
                user = await self.users.users.insert(agent.id, uuid.uuid4().hex)
                if user:
                    break
            if not user:
                raise Failed("Could not create a new user")
        else:
            user = await self.users.ensure(agent.id, user_id)
        chat = await self.chats.resolve(user, chat_id)
        return Conversation(principal, user, chat, agent.settings(self.defaults))

    async def _model(self, conversation: Conversation) -> Model:
        model = await self.models.get(conversation.agent.model_id)
        if model is None:
            raise NotFound("Model not found")
        return model

    async def _store(self, conversation: Conversation, model: Model, text: str, attachments, answer: str) -> None:
        """Keep a question and its answer, next to each other even when the user has other requests running, and let the model learn from it."""
        user_row = {"type": "user", "content": text, **PromptBuilder.stored(attachments)}
        await self._write(conversation, [user_row, {"type": "assistant", "content": answer}], text)
        self.extractor.schedule(conversation, model, text, answer)

    async def _write(self, conversation: Conversation, rows, first_text: Optional[str]) -> None:
        chat_id, user_id, agent_id = conversation.chat.id, conversation.user.id, conversation.agent.id
        async with self.uow.transaction():
            await self.uow.lock(f"messages:{chat_id}")
            for row in rows:
                await self.messages.append(user_id, chat_id, agent_id, row)
            await self.chat_repo.touch(chat_id, first_text)

    # -- /request ------------------------------------------------------------------------------------------------------------

    async def answer(self, principal: Principal, data) -> Answered:
        conversation = await self.begin(principal, data.user_id, data.chat_id)
        await self.interrupts.stop(conversation.agent.id, conversation.user.id)  # a stream still coming to this user is cut off and saved first
        model = await self._model(conversation)
        request = RunRequest(data.request, tuple(data.attachments), data.use_memo, data.trace, stream=False)
        finished = await self.runner.answer(conversation, model, request)
        if data.save_message:
            await self._store(conversation, model, data.request, data.attachments, finished.output)
        return Answered(conversation, finished)

    # -- /request-stream -----------------------------------------------------------------------------------------------------

    async def open_stream(self, principal: Principal, data) -> "ConversationStream":
        """Everything that can be refused is decided here, before the first byte: the events come from `ConversationStream.events()`."""
        conversation = await self.begin(principal, data.user_id, data.chat_id)
        await self.interrupts.stop(conversation.agent.id, conversation.user.id)
        return ConversationStream(self, conversation, await self._model(conversation), data)

    async def interrupt(self, principal: Principal, external_id: str) -> Optional[ActiveStream]:
        """Stop the answer that is being streamed to this user (here or in another replica); None if there was none."""
        user = await self.users.get(principal, external_id)
        return await self.interrupts.stop(principal.agent.id, user.id)

    # -- an agent asks another -------------------------------------------------------------------------------------------------

    async def ask_as_agent(self, conversation: Conversation, agent_id: int, request: str) -> str:
        """What `ask_agent` does. The called agent is run like any request to it would be, in this process, with its own prompt, model, tools
        and history, as the user `agent_<caller>:<person>`; it is given the text of the request only. A call that is refused, or fails, is the
        answer (in words, for the model to read): it never ends the caller's run."""
        principal, caller = conversation.principal, conversation.agent
        chain = principal.chain or CallChain(agents=(caller.id,), human=conversation.user.external_id)
        if (why := chain.refusal(agent_id, self.call_depth)) is not None:
            return why
        asking = principal.continued_as(caller, chain)
        if not self.policy.may_act_as(asking, agent_id, await self.connections.has_connection(chain.agents[-1], agent_id)):
            return f"Refused: agent {caller.id} has no connection to agent {agent_id}. Call list_agents to see which it has."
        target = await self.agents.get(agent_id)
        if target is None:
            return f"Refused: there is no agent {agent_id}."
        try:
            user = await self.users.ensure(target.id, caller_user_id(caller.id, chain.human))
            called = Conversation(
                principal.continued_as(target, chain.then(agent_id)), user, await self.chats.resolve(user, None), target.settings(self.defaults)
            )
            model = await self._model(called)
            finished = await self.runner.answer(called, model, RunRequest(request, kind="agent_call", stream=False))
            await self._store(called, model, request, (), finished.output)
            return finished.output
        except Exception as exc:  # the caller goes on without this answer
            status, detail = error_response(exc)
            logfire.warning("Agent {caller} could not ask agent {agent}: {detail}", caller=caller.id, agent=agent_id, detail=detail)
            return f"Agent {agent_id} could not answer (HTTP {status}): {detail}"


class ConversationStream:
    """One answer being streamed: the events, in order. A stopped stream ends with `InterruptedEvent` after what was said has been saved."""

    def __init__(self, service: ConversationService, conversation: Conversation, model: Model, data):
        self.service, self.conversation, self.model, self.data = service, conversation, model, data

    async def events(self) -> AsyncIterator[StreamEvent]:
        service, conversation, data = self.service, self.conversation, self.data
        user = conversation.user
        metrics.ACTIVE_STREAMS.inc()
        stream = service.interrupts.start((conversation.agent.id, user.id))
        try:
            # First, so the client has the (possibly new) user even if the stream fails
            yield UserEvent(user)
            request = RunRequest(data.request, tuple(data.attachments), data.use_memo, data.trace, stream=True)
            run = service.runner.run(conversation, self.model, request)
            try:
                async for event in StreamGuard.items(run, stream):
                    if isinstance(event, Finished):
                        if data.save_message:
                            await service._store(conversation, self.model, data.request, data.attachments, event.output)
                        continue  # the exchange is kept; `done` says it is over
                    if isinstance(event, TextChunk):
                        stream.partial.append(event.text)
                    yield event
            finally:
                await run.aclose()
            if stream.interrupted:
                if data.save_message:
                    await self._save_interrupted(stream.text)
                stream.finished.set()  # saved: whoever asked for the stop need not wait for the client to read the last event
                yield InterruptedEvent(user)
            else:
                yield DoneEvent(user)
        except Exception as exc:
            status, detail = error_response(exc)
            log = logfire.exception if status == 500 else logfire.warning
            log("SSE stream failed: {error}", error=detail, _exc_info=exc)
            yield ErrorEvent(detail)
        finally:
            service.interrupts.end(stream)
            metrics.ACTIVE_STREAMS.dec()

    async def _save_interrupted(self, partial: str) -> None:
        """An answer that was stopped: the question and what was said of the answer go into the history (the answer marked `interrupted`; no
        answer row at all when nothing had been said), and into the memory like any exchange."""
        data = self.data
        rows = [{"type": "user", "content": data.request, **PromptBuilder.stored(data.attachments)}]
        said = partial.strip()
        if said:
            rows.append({"type": "assistant", "content": partial, "interrupted": True})
        await self.service._write(self.conversation, rows, data.request)
        if said:
            self.service.extractor.schedule(self.conversation, self.model, data.request, partial)
