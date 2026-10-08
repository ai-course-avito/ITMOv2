from fastapi import APIRouter, Request, Query, Body, HTTPException
from typing import Annotated, Optional, Sequence
from pydantic import BaseModel, StringConstraints
from ai.memory import MAX_MEMORY_CHARS, embed, recall_memories
from database import PostgresDB, Memory
from access import default_agent_id, ensure_agent_access
from core import async_logfire_decorator

router = APIRouter()

MemoryText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MEMORY_CHARS),
]


class MemoryCreate(BaseModel):
    user_id: str  # the user's external id
    content: MemoryText
    agent_id: Optional[int] = None  # default: the agent in context


class MemoryUpdate(BaseModel):
    content: MemoryText


# Memories


async def _own_memory(db: PostgresDB, memory_id: int) -> None:
    """A token may touch a memory only of an agent it may use (a missing one is left to the route's 404)."""
    memory = await db.get_memory(memory_id)
    if memory:
        ensure_agent_access(db, memory.agent_id)


async def _resolve_scope(db: PostgresDB, user_id: str, agent_id: Optional[int]):
    agent_id = default_agent_id(
        db, agent_id
    )  # first: what is not the token's to touch is not looked up
    user = await db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not await db.get_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return user.id, agent_id


@router.get("/memories", summary="List the memories of a user (newest first)")
@async_logfire_decorator
async def get_memories(
    request: Request,
    user_id: str = Query(..., description="The user's external id"),
    agent_id: Optional[int] = Query(None, description="Agent ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    query: Optional[str] = Query(
        None,
        description="Search by meaning (and by the words it contains) instead of "
        "listing the newest; the closest first",
    ),
) -> Sequence[Memory]:
    db: PostgresDB = request.state.db
    scope = await _resolve_scope(db, user_id, agent_id)
    if query and query.strip():
        return await recall_memories(db, scope, query, limit)
    return await db.get_memories(*scope, limit=limit)


@router.post("/memories", summary="Create a memory", status_code=201)
@async_logfire_decorator
async def create_memory(request: Request, data: MemoryCreate = Body(...)) -> Memory:
    db: PostgresDB = request.state.db
    scope = await _resolve_scope(db, data.user_id, data.agent_id)
    return await db.create_memory(*scope, data.content, await embed(data.content))


@router.get("/memories/{memory_id}", summary="Get a memory by ID")
@async_logfire_decorator
async def get_memory(request: Request, memory_id: int) -> Memory:
    db: PostgresDB = request.state.db
    memory = await db.get_memory(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    ensure_agent_access(db, memory.agent_id)
    return memory


@router.patch("/memories/{memory_id}", summary="Update a memory")
@async_logfire_decorator
async def update_memory(
    request: Request, memory_id: int, data: MemoryUpdate = Body(...)
) -> Memory:
    db: PostgresDB = request.state.db
    await _own_memory(db, memory_id)
    memory = await db.update_memory(memory_id, data.content, await embed(data.content))
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


@router.delete("/memories/{memory_id}", summary="Delete a memory")
@async_logfire_decorator
async def delete_memory(request: Request, memory_id: int) -> Memory:
    db: PostgresDB = request.state.db
    await _own_memory(db, memory_id)
    memory = await db.delete_memory(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory
