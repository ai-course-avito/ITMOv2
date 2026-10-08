from typing import Annotated, Optional, Sequence

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, StringConstraints

from access import require
from core import async_logfire_decorator
from database import AgentConnection, PostgresDB

# Connections between agents: agent1 may call agent2 (the tools list_agents and ask_agent), and the description
# tells agent1 what agent2 is for. A connection is part of agent1's behaviour, so each change is a version of it.
# Only admins see and change them (they are the ones who see every agent).
router = APIRouter(dependencies=[Depends(require("admin"))])

Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]


class AgentConnectionCreate(BaseModel):
    agent1_id: int  # the one that calls
    agent2_id: int  # the one that is called
    description: Description  # what agent2 is for, as agent1 sees it in list_agents


class AgentConnectionUpdate(BaseModel):
    description: Description


async def _connection(db: PostgresDB, connection_id: int) -> AgentConnection:
    connection = await db.get_agent_connection(connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Agent connection not found")
    return connection


@router.get(
    "/agent-connections",
    summary="List the connections between agents (or those going out of one agent)",
)
@async_logfire_decorator
async def get_agent_connections(
    request: Request, agent_id: Optional[int] = None
) -> Sequence[AgentConnection]:
    db: PostgresDB = request.state.db
    return await db.get_agent_connections(agent_id)


@router.post(
    "/agent-connections", summary="Let one agent call another", status_code=201
)
@async_logfire_decorator
async def create_agent_connection(
    request: Request, data: AgentConnectionCreate
) -> AgentConnection:
    db: PostgresDB = request.state.db
    if data.agent1_id == data.agent2_id:
        raise HTTPException(
            status_code=409, detail="An agent cannot be connected to itself"
        )
    for agent_id in (data.agent1_id, data.agent2_id):
        if not await db.get_agent(agent_id):
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    try:
        async with db.transaction():
            connection = await db.create_agent_connection(
                data.agent1_id, data.agent2_id, data.description
            )
            await db.record_agent_version(
                data.agent1_id, f"may call agent {data.agent2_id}", db.context.token.id
            )
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=409,
            detail=f"Agent {data.agent1_id} is already connected to agent {data.agent2_id}",
        )
    except asyncpg.ForeignKeyViolationError:  # an agent deleted meanwhile
        raise HTTPException(status_code=404, detail="Agent not found")
    return connection


@router.get(
    "/agent-connections/{connection_id}", summary="Get a connection between agents"
)
@async_logfire_decorator
async def get_agent_connection(request: Request, connection_id: int) -> AgentConnection:
    return await _connection(request.state.db, connection_id)


@router.patch(
    "/agent-connections/{connection_id}",
    summary="Change what a connection tells the calling agent",
)
@async_logfire_decorator
async def update_agent_connection(
    request: Request, connection_id: int, data: AgentConnectionUpdate
) -> AgentConnection:
    db: PostgresDB = request.state.db
    connection = await _connection(db, connection_id)
    async with db.transaction():
        updated = await db.update_agent_connection(connection_id, data.description)
        await db.record_agent_version(
            connection.agent1_id,
            f"description of agent {connection.agent2_id} changed",
            db.context.token.id,
        )
    if not updated:
        raise HTTPException(status_code=404, detail="Agent connection not found")
    return updated


@router.delete(
    "/agent-connections/{connection_id}", summary="Stop one agent from calling another"
)
@async_logfire_decorator
async def delete_agent_connection(
    request: Request, connection_id: int
) -> AgentConnection:
    db: PostgresDB = request.state.db
    connection = await _connection(db, connection_id)
    async with db.transaction():
        deleted = await db.delete_agent_connection(connection_id)
        await db.record_agent_version(
            connection.agent1_id,
            f"may no longer call agent {connection.agent2_id}",
            db.context.token.id,
        )
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent connection not found")
    return deleted
