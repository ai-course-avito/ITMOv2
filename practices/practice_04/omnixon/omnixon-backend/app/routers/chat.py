from typing import Annotated, Sequence

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, StringConstraints

from core import async_logfire_decorator
from database import Chat, Message, PostgresDB
from database.models import NAME_MAX

router = APIRouter()

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NAME_MAX)]


class ChatCreate(BaseModel):
    title: Title | None = None  # empty: named after the first message


class ChatUpdate(BaseModel):
    title: Title


# The conversations of a user with the agent: each is its own thread of messages


async def _user(db: PostgresDB, user_id: str) -> None:
    db.context.user = await db.get_user(user_id)
    if not db.context.user:
        raise HTTPException(status_code=404, detail="User not found")


async def _chat(db: PostgresDB, user_id: str, chat_id: int) -> Chat:
    await _user(db, user_id)
    chat = await db.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    db.context.chat = chat
    return chat


@router.get("/users/{user_id}/chats", summary="The chats of a user, the latest first")
@async_logfire_decorator
async def get_chats(request: Request, user_id: str) -> Sequence[Chat]:
    db: PostgresDB = request.state.db
    await _user(db, user_id)
    return await db.get_chats()


@router.post("/users/{user_id}/chats", summary="Start a chat", status_code=201)
@async_logfire_decorator
async def create_chat(request: Request, user_id: str, data: ChatCreate | None = None) -> Chat:
    db: PostgresDB = request.state.db
    await _user(db, user_id)
    return await db.create_chat(data.title if data else None)


@router.get("/users/{user_id}/chats/{chat_id}", summary="One chat of a user")
@async_logfire_decorator
async def get_chat(request: Request, user_id: str, chat_id: int) -> Chat:
    return await _chat(request.state.db, user_id, chat_id)


@router.patch("/users/{user_id}/chats/{chat_id}", summary="Rename a chat")
@async_logfire_decorator
async def rename_chat(request: Request, user_id: str, chat_id: int, data: ChatUpdate) -> Chat:
    db: PostgresDB = request.state.db
    await _chat(db, user_id, chat_id)
    return await db.rename_chat(chat_id, data.title)


@router.delete("/users/{user_id}/chats/{chat_id}", summary="Delete a chat with its messages")
@async_logfire_decorator
async def delete_chat(request: Request, user_id: str, chat_id: int) -> Chat:
    """The default chat can be deleted too: it is made again when a request without `chat_id` needs it."""
    db: PostgresDB = request.state.db
    await _chat(db, user_id, chat_id)
    return await db.delete_chat(chat_id)


@router.get("/users/{user_id}/chats/{chat_id}/history", summary="The messages of a chat")
@async_logfire_decorator
async def get_chat_history(request: Request, user_id: str, chat_id: int) -> Sequence[Message]:
    db: PostgresDB = request.state.db
    await _chat(db, user_id, chat_id)
    return await db.get_all_messages()


@router.delete(
    "/users/{user_id}/chats/{chat_id}/history",
    summary="Clear a chat (it stays, its messages go)",
    status_code=204,
)
@async_logfire_decorator
async def clear_chat_history(request: Request, user_id: str, chat_id: int) -> None:
    db: PostgresDB = request.state.db
    await _chat(db, user_id, chat_id)
    await db.clear_messages()
