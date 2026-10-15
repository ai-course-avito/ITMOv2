import asyncio

import logfire
from fastapi import Depends, Request
from fastapi.responses import StreamingResponse

from api.controller import Controller, current_principal, endpoint
from api.schemas.conversation import MessageRequest, MessageResponse
from api.schemas.users import Interrupted
from api.sse import SseStream
from core import metrics
from domain.access import Principal
from services.conversations import ConversationService


class ClientDisconnected(Exception):
    """The client went away while its request was being answered."""


async def until_disconnect(request: Request, work):
    """Await `work`, but stop it (no more model calls to pay for, nothing stored) as soon as the client has gone away."""
    task = asyncio.ensure_future(work)
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=0.5)
            if done:
                return task.result()
            if await request.is_disconnected():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                metrics.REQUESTS_CANCELLED.inc()
                logfire.info("Client disconnected, request cancelled")
                raise ClientDisconnected()
    except asyncio.CancelledError:
        task.cancel()
        raise


class ConversationController(Controller):
    prefix = "/api/v1"
    tags = ["Main API"]

    def __init__(self, conversations: ConversationService):
        self.conversations = conversations
        super().__init__()

    @endpoint.post("/request", summary="Send a message and get an AI response")
    async def request(self, request: Request, data: MessageRequest, principal: Principal = Depends(current_principal)) -> MessageResponse:
        answered = await until_disconnect(request, self.conversations.answer(principal, data))
        conversation, finished = answered.conversation, answered.finished
        return MessageResponse(
            response=finished.output,
            user=conversation.user,
            chat_id=conversation.chat.id,
            trace=finished.trace if data.trace else None,
        )

    @endpoint.post("/request-stream", summary="Send a message and get an AI response via SSE")
    async def request_stream(self, data: MessageRequest, principal: Principal = Depends(current_principal)) -> StreamingResponse:
        """Server-sent events: `event: user` with the user, then one `data:` event per
        text chunk (a JSON string), then `event: done` with the user, or `event: error`
        with `{"detail": ...}`. With `trace: true`, `event: trace` events (one step of the
        chain of calls each) come in between, as the steps finish. A stream that is stopped (by `POST /users/{id}/interrupt`, or because the same user
        sent a new request) ends with `event: interrupted` (the user) instead of `done`; what was said so far is in the history."""
        stream = await self.conversations.open_stream(principal, data)
        return StreamingResponse(SseStream.lines(stream.events()), media_type="text/event-stream; charset=utf-8")

    @endpoint.post("/users/{user_id}/interrupt", summary="Stop the answer that is being streamed to a user")
    async def interrupt_user(self, user_id: str, principal: Principal = Depends(current_principal)) -> Interrupted:
        """Ends the stream of this user with the agent of the token: the stream gets `event: interrupted`, what was said so far is
        saved to the history (marked `interrupted`) and to the memory, and then this returns. A new request of the same user does
        the same by itself, so this is for stopping without saying anything new."""
        stopped = await self.conversations.interrupt(principal, user_id)
        return Interrupted(interrupted=stopped is not None, text=stopped.text if stopped else "")
