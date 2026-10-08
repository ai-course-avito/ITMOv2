from fastapi import APIRouter, Depends, Request, Body, HTTPException
from typing import Sequence
from typing import Annotated, Optional
from pydantic import BaseModel, StringConstraints, field_validator
from ai.capabilities.mcp import MCP_OPTIONS
from database import PostgresDB, MCPServer, RANK
from database.models import NAME_MAX
from access import default_agent_id, forbidden, rank_of, require
from core import async_logfire_decorator

router = APIRouter()

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NAME_MAX)
]


def _validate_mcp_config(value: dict) -> dict:
    if not isinstance(value.get("url"), str) or not value["url"]:
        raise ValueError('config must contain a non-empty "url" string')
    if value.get("transport", "streamable_http") not in ("streamable_http", "sse"):
        raise ValueError('transport must be "streamable_http" or "sse"')
    unknown = sorted(set(value) - {"url", "transport"} - MCP_OPTIONS)
    if unknown:
        raise ValueError(
            f"Unknown options: {', '.join(unknown)}. "
            f"Allowed: url, transport, {', '.join(sorted(MCP_OPTIONS))}"
        )
    return value


class MCPServerCreate(BaseModel):
    name: Name  # required
    config: dict
    # Attach the new server to this agent at once. A user token always does it, to its own agent (the
    # only agent it may give one to); an admin may leave it out to make a server of nobody's.
    agent_id: Optional[int] = None

    _check = field_validator("config")(_validate_mcp_config)


class MCPServerUpdate(BaseModel):
    name: Optional[Name] = None
    config: Optional[dict] = None

    @field_validator("config")
    @classmethod
    def _check(cls, value):
        return None if value is None else _validate_mcp_config(value)


# MCP Servers


async def _check_use(db: PostgresDB, mcp_server_id: int, *, change: bool) -> None:
    """Below admin a token sees the servers of its own agent, and changes only those that nothing else uses
    (a server shared with another agent would change that agent too)."""
    if rank_of(db) >= RANK["admin"]:
        return
    agents = set(await db.agent_ids_using_mcp_server(mcp_server_id))
    own = db.context.token.agent_id
    if own not in agents:
        raise forbidden(
            "Forbidden: this MCP server is not attached to the token's agent"
        )
    if change and agents != {own}:
        raise forbidden(
            "Forbidden: this MCP server is shared with another agent, so it cannot be changed here"
        )


@router.get(
    "/mcp-servers",
    summary="List all MCP servers",
    dependencies=[Depends(require("admin"))],
)
@async_logfire_decorator
async def get_mcp_servers(request: Request) -> Sequence[MCPServer]:
    db: PostgresDB = request.state.db
    return await db.get_all_mcp_servers()


@router.post("/mcp-servers", summary="Create a new MCP server", status_code=201)
@async_logfire_decorator
async def create_mcp_server(
    request: Request, data: MCPServerCreate = Body(...)
) -> MCPServer:
    db: PostgresDB = request.state.db
    agent_id = data.agent_id
    if rank_of(db) < RANK["admin"]:
        agent_id = default_agent_id(db, agent_id)
    elif agent_id is not None and not await db.get_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    async with db.transaction():
        created = await db.create_mcp_server(data.config, data.name)
        if agent_id is not None:
            await db.add_agent_mcp_server(agent_id, created.id)
            await db.record_agent_version(
                agent_id, f"MCP server {created.id} created", db.context.token.id
            )
    return created


@router.get("/mcp-servers/{mcp_server_id}", summary="Get an MCP server by ID")
@async_logfire_decorator
async def get_mcp_server(request: Request, mcp_server_id: int) -> MCPServer:
    db: PostgresDB = request.state.db
    mcp_server = await db.get_mcp_server(mcp_server_id)
    if not mcp_server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    await _check_use(db, mcp_server_id, change=False)
    return mcp_server


@router.patch("/mcp-servers/{mcp_server_id}", summary="Update an MCP server")
@async_logfire_decorator
async def update_mcp_server(
    request: Request, mcp_server_id: int, data: MCPServerUpdate = Body(...)
) -> MCPServer:
    db: PostgresDB = request.state.db
    if not await db.get_mcp_server(mcp_server_id):
        raise HTTPException(status_code=404, detail="MCP server not found")
    await _check_use(db, mcp_server_id, change=True)
    async with db.transaction():
        mcp_server = await db.update_mcp_server(mcp_server_id, data.config, data.name)
        if not mcp_server:
            raise HTTPException(status_code=404, detail="MCP server not found")
        await db.record_versions_of(
            await db.agent_ids_using_mcp_server(mcp_server_id),
            f"MCP server {mcp_server_id} updated",
            db.context.token.id,
        )
    return mcp_server


@router.delete("/mcp-servers/{mcp_server_id}", summary="Delete an MCP server")
@async_logfire_decorator
async def delete_mcp_server(request: Request, mcp_server_id: int) -> MCPServer:
    db: PostgresDB = request.state.db
    if not await db.get_mcp_server(mcp_server_id):
        raise HTTPException(status_code=404, detail="MCP server not found")
    await _check_use(db, mcp_server_id, change=True)
    async with db.transaction():
        agent_ids = await db.agent_ids_using_mcp_server(
            mcp_server_id
        )  # detached by the delete
        mcp_server = await db.delete_mcp_server(mcp_server_id)
        if not mcp_server:
            raise HTTPException(status_code=404, detail="MCP server not found")
        await db.record_versions_of(
            agent_ids, f"MCP server {mcp_server_id} deleted", db.context.token.id
        )
    return mcp_server
