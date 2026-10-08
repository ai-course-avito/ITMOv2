import json
import uuid
import asyncio
import logfire
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from typing import AsyncIterator, List, Optional
from pydantic import BaseModel, Field
from database import PostgresDB, User
from ai import interrupt
from ai.trace import TraceStep
from ai.attachments import Attachment
from core import (
    metrics,
)
from ai import Finished, agent_run, run_agent, save_interrupted
from core import (
    async_logfire_decorator,
    error_response,
)

router = APIRouter()


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


class MessageRequest(BaseModel):
    # The user's external id. Empty or omitted: a new user is created for the agent
    # and returned in the response.
    user_id: Optional[str] = Field(None, max_length=64)
    request: str
    # Save this exchange to the user's history.
    save_message: bool = True
    # Pass the user's previous messages to the model.
    use_memo: bool = True
    # The chat to write in (one of the user's chats, see /users/{id}/chats). Omitted: the default chat of the user, which is where the
    # clients that know nothing about chats (a bot) always are.
    chat_id: Optional[int] = None
    # Files for the model (the model must understand them: e.g. be able to see images)
    attachments: List[Attachment] = []
    # Also return the chain of calls behind the answer: each call to the model and each
    # tool it called (`trace` in the response; `event: trace` in the stream).
    trace: bool = False


class MessageResponse(BaseModel):
    response: str
    user: User
    chat_id: int  # the chat it was written in
    trace: Optional[List[TraceStep]] = None  # only when the request asked for it


# AI request


async def _ensure_user(db: PostgresDB, user_id: Optional[str]) -> User:
    """Find or create the user of a request and make it the current one."""
    if user_id is None or not user_id.strip():
        user = None
        for _ in range(5):
            user = await db.create_user(uuid.uuid4().hex)
            if user:
                break
        if not user:
            raise HTTPException(status_code=500, detail="Could not create a new user")
    else:
        await db.insure_user(user_id)
        user = await db.get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=404, detail="User not found after insurance"
            )

    db.context.user = user
    return user


async def _ensure_chat(db: PostgresDB, chat_id: Optional[int]) -> None:
    """The chat of a request: the one asked for (it must be the user's), else the default chat of the user."""
    if chat_id is None:
        db.context.chat = await db.ensure_default_chat()
        return
    chat = await db.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    db.context.chat = chat


class ClientDisconnected(Exception):
    """The client went away while its request was being answered."""


async def _until_disconnect(request: Request, work):
    """Await `work`, but stop it (no more model calls to pay for, nothing stored)
    as soon as the client has gone away."""
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


@router.post("/request", summary="Send a message and get an AI response")
@async_logfire_decorator
async def request(request: Request, data: MessageRequest) -> MessageResponse:
    db: PostgresDB = request.state.db

    user = await _ensure_user(db, data.user_id)
    await _ensure_chat(db, data.chat_id)
    await interrupt.stop(
        db.context.agent.id, user.id
    )  # a stream still coming to this user is cut off and saved first

    run = await _until_disconnect(
        request,
        agent_run(
            db,
            data.request,
            save_message=data.save_message,
            use_memo=data.use_memo,
            attachments=data.attachments,
            trace=data.trace,
        ),
    )
    return MessageResponse(
        response=run.output,
        user=db.context.user,
        chat_id=db.context.chat.id,
        trace=run.trace if data.trace else None,
    )


@router.post("/request-stream", summary="Send a message and get an AI response via SSE")
async def request_stream(request: Request, data: MessageRequest) -> StreamingResponse:
    """Server-sent events: `event: user` with the user, then one `data:` event per
    text chunk (a JSON string), then `event: done` with the user, or `event: error`
    with `{"detail": ...}`. With `trace: true`, `event: trace` events (one step of the
    chain of calls each) come in between, as the steps finish. A stream that is stopped (by `POST /users/{id}/interrupt`, or because the same user
    sent a new request) ends with `event: interrupted` (the user) instead of `done`; what was said so far is in the history."""
    db: PostgresDB = request.state.db

    user = await _ensure_user(db, data.user_id)
    await _ensure_chat(db, data.chat_id)
    await interrupt.stop(
        db.context.agent.id, user.id
    )  # a stream still coming to this user is cut off and saved first

    user_snapshot = db.context.user

    async def event_generator() -> AsyncIterator[str]:
        metrics.ACTIVE_STREAMS.inc()
        stream = interrupt.start((db.context.agent.id, user_snapshot.id))
        interrupt.current.set(stream)
        try:
            # First, so the client has the (possibly new) user even if the stream fails
            yield _sse_event("user", json.loads(user_snapshot.model_dump_json()))
            chunks = run_agent(
                db,
                data.request,
                save_message=data.save_message,
                use_memo=data.use_memo,
                attachments=data.attachments,
                trace=data.trace,
            )
            try:
                async for chunk in interrupt.until_stopped(chunks, stream):
                    if isinstance(chunk, Finished):
                        continue  # the run has stored the exchange; `done` says it is over
                    if isinstance(chunk, TraceStep):
                        yield _sse_event("trace", chunk.model_dump(exclude_none=True))
                    else:
                        stream.partial.append(chunk)
                        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            finally:
                await chunks.aclose()
            if stream.interrupted:
                if data.save_message:
                    await save_interrupted(
                        db, data.request, stream.text, data.attachments
                    )
                stream.finished.set()  # saved: whoever asked for the stop need not wait for the client to read the last event
                yield _sse_event(
                    "interrupted", json.loads(user_snapshot.model_dump_json())
                )
            else:
                yield _sse_event("done", json.loads(user_snapshot.model_dump_json()))
        except Exception as e:
            status, detail = error_response(e)
            log = logfire.exception if status == 500 else logfire.warning
            log("SSE stream failed: {error}", error=detail, _exc_info=e)
            yield _sse_event("error", {"detail": detail})
        finally:
            interrupt.end(stream)
            metrics.ACTIVE_STREAMS.dec()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
    )
