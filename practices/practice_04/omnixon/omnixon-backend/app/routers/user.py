from fastapi import APIRouter, Request, HTTPException, Query
from typing import Optional, Sequence
from pydantic import BaseModel, Field
from ai import interrupt
from database import PostgresDB, RecentUser, User
from core import async_logfire_decorator

router = APIRouter()


class UserCreate(BaseModel):
    external_id: str = Field(min_length=1, max_length=64)


class UserUpdate(BaseModel):
    external_id: Optional[str] = Field(None, min_length=1, max_length=64)


class Interrupted(BaseModel):
    interrupted: bool  # false: no answer was being streamed to this user
    text: str = ""  # what had been said of it (and is now in the history)


# Users


@router.get("/users", summary="Find users by the start of their external ID")
@async_logfire_decorator
async def search_users(
    request: Request,
    query: str = Query(
        ...,
        min_length=3,
        max_length=64,
        description="The start of the external ID (at least 3 characters: there is no "
        "list of all users)",
    ),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results"),
) -> Sequence[User]:
    db: PostgresDB = request.state.db
    return await db.search_users(query, limit)


@router.get(
    "/users/recent",
    summary="The users of the agent who wrote lately (their messages are still kept)",
)
@async_logfire_decorator
async def recent_users(
    request: Request,
    limit: int = Query(20, ge=1, le=100, description="Maximum number of users"),
) -> Sequence[RecentUser]:
    """Latest first, by the latest message that has not expired (`MESSAGE_TTL_DAYS`, 7 by default). Not a list of all users: a user
    with no kept messages is not in it, but can still be found by `GET /users?query=`."""
    db: PostgresDB = request.state.db
    return await db.recent_users(limit)


@router.post("/users", summary="Create a new user", status_code=201)
@async_logfire_decorator
async def create_user(request: Request, data: UserCreate) -> User:
    db: PostgresDB = request.state.db
    user = await db.create_user(data.external_id)
    if not user:
        raise HTTPException(status_code=409, detail="User already exists")
    return user


@router.get("/users/{user_id}", summary="Get a user by external ID")
@async_logfire_decorator
async def get_user(request: Request, user_id: str) -> User:
    db: PostgresDB = request.state.db
    user = await db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/users/{user_id}", summary="Update a user")
@async_logfire_decorator
async def update_user(request: Request, user_id: str, data: UserUpdate) -> User:
    db: PostgresDB = request.state.db
    db.context.user = await db.get_user(user_id)

    if not db.context.user:
        raise HTTPException(status_code=404, detail="User not found")

    db.context.user.external_id = data.external_id or db.context.user.external_id

    result = await db.update_user()
    if not result:
        raise HTTPException(
            status_code=409, detail="Failed to update user: duplicate external_id"
        )
    return result


@router.delete("/users/{user_id}", summary="Delete a user")
@async_logfire_decorator
async def delete_user(request: Request, user_id: str) -> User:
    db: PostgresDB = request.state.db
    db.context.user = await db.get_user(user_id)

    if not db.context.user:
        raise HTTPException(status_code=404, detail="User not found")

    return await db.delete_user()


@router.post(
    "/users/{user_id}/interrupt",
    summary="Stop the answer that is being streamed to a user",
)
@async_logfire_decorator
async def interrupt_user(request: Request, user_id: str) -> Interrupted:
    """Ends the stream of this user with the agent of the token: the stream gets `event: interrupted`, what was said so far is
    saved to the history (marked `interrupted`) and to the memory, and then this returns. A new request of the same user does
    the same by itself, so this is for stopping without saying anything new."""
    db: PostgresDB = request.state.db
    user = await db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    stopped = await interrupt.stop(db.context.agent.id, user.id)
    return Interrupted(
        interrupted=stopped is not None, text=stopped.text if stopped else ""
    )
