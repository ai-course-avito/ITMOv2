from fastapi import APIRouter, Request, HTTPException
from typing import Sequence
from database import PostgresDB, Message
from core import async_logfire_decorator

router = APIRouter()


# Message history of the default chat of a user (the one a request without chat_id goes to).
# Other chats: see routers/chat.py.


async def _default_chat(db: PostgresDB, user_id: str) -> bool:
    """Make the default chat of the user the current one; False when it has not been needed yet (no messages)."""
    db.context.user = await db.get_user(user_id)
    if not db.context.user:
        raise HTTPException(status_code=404, detail="User not found")
    db.context.chat = await db.get_default_chat()
    return db.context.chat is not None


@router.get("/users/{user_id}/history", summary="Get the message history of the default chat of a user")
@async_logfire_decorator
async def get_history(request: Request, user_id: str) -> Sequence[Message]:
    db: PostgresDB = request.state.db
    if not await _default_chat(db, user_id):
        return []
    return await db.get_all_messages()


@router.delete(
    "/users/{user_id}/history",
    summary="Clear the message history of the default chat of a user",
    status_code=204,
)
@async_logfire_decorator
async def delete_history(request: Request, user_id: str) -> None:
    db: PostgresDB = request.state.db
    if await _default_chat(db, user_id):
        await db.clear_messages()
