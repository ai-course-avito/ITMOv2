from typing import Annotated, Literal, Optional, Sequence

from fastapi import APIRouter, Body, HTTPException, Query, Request
from pydantic import BaseModel, StringConstraints, model_validator

from access import (
    can_manage_token,
    default_agent_id,
    forbidden,
    may_grant,
)
from core import async_logfire_decorator
from database import NewToken, PostgresDB, RANK, Token
from database.models import NAME_MAX

router = APIRouter()

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NAME_MAX)
]
RoleName = Literal["regular", "user", "admin", "owner"]


class TokenCreate(BaseModel):
    name: Name  # required
    role: RoleName
    # The agent the token gives access to. Default: the agent in context. A user token may only
    # name its own agent.
    agent_id: Optional[int] = None


class TokenUpdate(BaseModel):
    name: Optional[Name] = None
    role: Optional[RoleName] = (
        None  # the role may be changed up to what the caller may hand out
    )

    @model_validator(mode="after")
    def something_to_change(self):
        if self.name is None and self.role is None:
            raise ValueError("give a name, a role, or both")
        return self


# Tokens


@router.get("/tokens", summary="List tokens (of one agent, or of all for an admin)")
@async_logfire_decorator
async def get_tokens(
    request: Request,
    agent_id: Optional[int] = Query(
        None,
        description="Only the tokens of this agent. Below admin: always the own agent",
    ),
) -> Sequence[Token]:
    db: PostgresDB = request.state.db
    if agent_id is None and db.context.token.rank >= RANK["admin"]:
        return await db.get_tokens()
    return await db.get_tokens(default_agent_id(db, agent_id))


@router.post(
    "/tokens",
    summary="Make a token. Its secret is in the answer, and only there",
    status_code=201,
)
@async_logfire_decorator
async def create_token(request: Request, data: TokenCreate = Body(...)) -> NewToken:
    db: PostgresDB = request.state.db
    if not may_grant(db, data.role):
        raise forbidden(f"Forbidden: this token may not hand out the {data.role} role")
    agent_id = default_agent_id(db, data.agent_id)
    if not await db.get_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return await db.create_token(data.name, agent_id, data.role)


async def _managed(db: PostgresDB, token_id: int) -> Token:
    target = await db.get_token(token_id)
    if not target:
        raise HTTPException(status_code=404, detail="Token not found")
    if not can_manage_token(db, target):
        raise forbidden(
            "Forbidden: this token may not manage a token of that role or agent"
        )
    return target


@router.patch("/tokens/{token_id}", summary="Rename a token and/or change its role")
@async_logfire_decorator
async def update_token(
    request: Request, token_id: int, data: TokenUpdate = Body(...)
) -> Token:
    db: PostgresDB = request.state.db
    target = await _managed(db, token_id)
    if data.role is not None and data.role != target.role:
        if not may_grant(db, data.role):
            raise forbidden(
                f"Forbidden: this token may not hand out the {data.role} role"
            )
        if target.id == db.context.token.id:
            raise HTTPException(
                status_code=409, detail="The token in use cannot change its own role"
            )
        if target.is_initial:
            raise HTTPException(
                status_code=409,
                detail="The role of the initial token cannot be changed",
            )
    return await db.update_token(token_id, data.name, data.role)


@router.delete(
    "/tokens/{token_id}", summary="Delete a token (it stops working at once)"
)
@async_logfire_decorator
async def delete_token(request: Request, token_id: int) -> Token:
    db: PostgresDB = request.state.db
    target = await _managed(db, token_id)
    if target.id == db.context.token.id:
        raise HTTPException(
            status_code=409, detail="The token in use cannot delete itself"
        )
    if target.is_initial:
        raise HTTPException(
            status_code=409, detail="The initial token cannot be deleted"
        )
    return await db.delete_token(token_id)
