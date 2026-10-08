from fastapi import APIRouter, Request, HTTPException
from database import PostgresDB, Agent, Token
from core import async_logfire_decorator

router = APIRouter()

# What a token may know about itself, whatever its role (the admin panel signs in with it).


@router.get("/tokens/self", summary="Get the token in use: its role and its agent")
@async_logfire_decorator
async def get_self_token(request: Request) -> Token:
    db: PostgresDB = request.state.db
    token = await db.get_token(db.context.token.id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    return token


@router.get("/agents/self", summary="Get the agent of the token (or the one acted as)")
@async_logfire_decorator
async def get_self_agent(request: Request) -> Agent:
    db: PostgresDB = request.state.db
    return db.context.agent
