import asyncpg
from fastapi import APIRouter, Depends, Request, Body, HTTPException
from typing import Annotated, List, Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from database import PostgresDB, Agent, MCPServer
from database.models import NAME_MAX
from access import ensure_agent_access, require
from core import async_logfire_decorator, validate_tools

router = APIRouter()

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NAME_MAX)
]


class AgentConfigInput(BaseModel):
    """Settings of an agent (agents.config). On update only the given keys change,
    and a key set to null goes back to its default."""

    model_config = ConfigDict(extra="forbid")

    tools: Optional[List[str]] = None  # default: ["rag", "memory"]
    message_limit: Optional[int] = Field(None, ge=0, le=1000)
    memo_limit: Optional[int] = Field(None, ge=1, le=1000)
    rag_limit: Optional[int] = Field(
        None, ge=1, le=100
    )  # default: DEFAULT_RAG_LIMIT (8)
    auto_memory: Optional[bool] = None  # default: on (DEFAULT_AUTO_MEMORY)
    parallel_tool_calls: Optional[bool] = None  # default: on (DEFAULT_PARALLEL_TOOL_CALLS)

    _check_tools = field_validator("tools")(validate_tools)


class AgentCreate(BaseModel):
    name: Name  # required
    prompt: str
    model_id: int
    config: Optional[AgentConfigInput] = None
    comment: Optional[str] = None  # shown in the history of the agent


class AgentUpdate(BaseModel):
    name: Optional[Name] = None
    prompt: Optional[str] = None
    model_id: Optional[int] = None
    config: Optional[AgentConfigInput] = None
    comment: Optional[str] = None  # shown in the history of the agent
    # Optimistic locking: the number of the version this change is based on. If the
    # agent has moved on since, nothing changes and the answer is 409.
    expected_version: Optional[int] = Field(None, ge=1)


def _config_changes(config: Optional[AgentConfigInput]) -> Optional[dict]:
    return None if config is None else config.model_dump(exclude_unset=True)


# Agents


@router.get(
    "/agents", summary="List all agents", dependencies=[Depends(require("admin"))]
)
@async_logfire_decorator
async def get_agents(request: Request) -> Sequence[Agent]:
    db: PostgresDB = request.state.db
    return await db.get_all_agents()


@router.post(
    "/agents",
    summary="Create a new agent",
    status_code=201,
    dependencies=[Depends(require("admin"))],
)
@async_logfire_decorator
async def create_agent(request: Request, data: AgentCreate = Body(...)) -> Agent:
    db: PostgresDB = request.state.db
    try:
        agent = await db.create_agent(
            data.prompt,
            data.model_id,
            _config_changes(data.config),
            data.comment,
            db.context.token.id,
            data.name,
        )
    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(status_code=404, detail="Model not found")
    return agent


@router.get("/agents/{agent_id}", summary="Get an agent by ID")
@async_logfire_decorator
async def get_agent(request: Request, agent_id: int) -> Agent:
    db: PostgresDB = request.state.db
    ensure_agent_access(db, agent_id)
    agent = await db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.patch("/agents/{agent_id}", summary="Update an agent")
@async_logfire_decorator
async def update_agent(
    request: Request,
    agent_id: int,
    data: AgentUpdate = Body(...),
) -> Agent:
    db: PostgresDB = request.state.db
    ensure_agent_access(db, agent_id)
    try:
        async with (
            db.transaction()
        ):  # the change and its version stand or fall together
            await db.lock(f"agent-versions:{agent_id}")  # so the version check holds
            if data.expected_version is not None:
                latest = await db.get_latest_version_number(agent_id)
                if latest is not None and latest != data.expected_version:
                    raise HTTPException(
                        status_code=409,
                        detail=f"The agent is at version {latest}, not {data.expected_version}",
                    )
            agent = await db.update_agent(
                agent_id,
                data.prompt,
                data.model_id,
                _config_changes(data.config),
                data.name,
            )
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")
            await db.record_agent_version(
                agent_id, data.comment or "updated", db.context.token.id
            )
    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(status_code=404, detail="Model not found")
    return agent


@router.delete(
    "/agents/{agent_id}",
    summary="Delete an agent",
    dependencies=[Depends(require("admin"))],
)
@async_logfire_decorator
async def delete_agent(request: Request, agent_id: int) -> Agent:
    db: PostgresDB = request.state.db
    try:
        async with db.transaction():
            # the agents that could call it lose that: a change of their behaviour, so a version of each
            callers = await db.agent_ids_calling(agent_id)
            agent = await db.delete_agent(agent_id)
            if agent:
                await db.record_versions_of(
                    callers,
                    f"agent {agent_id} deleted: may no longer call it",
                    db.context.token.id,
                )
    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(status_code=409, detail="Agent still has tokens")
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


# Agent <-> MCP server associations


@router.get(
    "/agents/{agent_id}/mcp-servers", summary="List MCP servers attached to an agent"
)
@async_logfire_decorator
async def get_agent_mcp_servers(request: Request, agent_id: int) -> Sequence[MCPServer]:
    db: PostgresDB = request.state.db
    ensure_agent_access(db, agent_id)
    agent = await db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return await db.get_agent_mcp_servers(agent_id)


@router.post(
    "/agents/{agent_id}/mcp-servers/{mcp_server_id}",
    summary="Attach an existing MCP server to an agent",
    status_code=201,
    dependencies=[Depends(require("admin"))],
)
@async_logfire_decorator
async def add_agent_mcp_server(
    request: Request, agent_id: int, mcp_server_id: int
) -> Sequence[MCPServer]:
    db: PostgresDB = request.state.db
    agent = await db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    mcp_server = await db.get_mcp_server(mcp_server_id)
    if not mcp_server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    async with db.transaction():
        await db.add_agent_mcp_server(agent_id, mcp_server_id)
        await db.record_agent_version(
            agent_id, f"MCP server {mcp_server_id} attached", db.context.token.id
        )
    return await db.get_agent_mcp_servers(agent_id)


@router.delete(
    "/agents/{agent_id}/mcp-servers/{mcp_server_id}",
    summary="Detach an MCP server from an agent",
)
@async_logfire_decorator
async def remove_agent_mcp_server(
    request: Request, agent_id: int, mcp_server_id: int
) -> Sequence[MCPServer]:
    db: PostgresDB = request.state.db
    ensure_agent_access(db, agent_id)
    agent = await db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    async with db.transaction():
        await db.remove_agent_mcp_server(agent_id, mcp_server_id)
        await db.record_agent_version(
            agent_id, f"MCP server {mcp_server_id} detached", db.context.token.id
        )
    return await db.get_agent_mcp_servers(agent_id)
