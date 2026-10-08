from typing import Any, Dict, Optional, Sequence

from fastapi import APIRouter, Body, HTTPException, Query, Request
from pydantic import BaseModel, Field

from access import ensure_agent_access
from core import async_logfire_decorator
from database import AgentVersion, PostgresDB
from database.mixins.agent_version import diff_snapshots

router = APIRouter()


class RollbackRequest(BaseModel):
    to: int = Field(ge=1)  # the version to go back to
    comment: Optional[str] = None


class VersionDiff(BaseModel):
    agent_id: int
    from_version: int
    to_version: int
    changes: Dict[str, Dict[str, Any]]  # key -> {"from": ..., "to": ...}


# Agent versions


async def _require_agent(db: PostgresDB, agent_id: int) -> None:
    ensure_agent_access(db, agent_id)
    if not await db.get_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")


async def _require_version(db: PostgresDB, agent_id: int, number: int) -> AgentVersion:
    await _require_agent(db, agent_id)
    version = await db.get_agent_version(agent_id, number)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.get("/agents/{agent_id}/versions", summary="History of an agent (newest first)")
@async_logfire_decorator
async def get_agent_versions(request: Request, agent_id: int) -> Sequence[AgentVersion]:
    db: PostgresDB = request.state.db
    await _require_agent(db, agent_id)
    return await db.get_agent_versions(agent_id)


@router.get("/agents/{agent_id}/versions/{number}", summary="One version of an agent")
@async_logfire_decorator
async def get_agent_version(
    request: Request, agent_id: int, number: int
) -> AgentVersion:
    db: PostgresDB = request.state.db
    return await _require_version(db, agent_id, number)


@router.get(
    "/agents/{agent_id}/versions/{number}/diff",
    summary="What changed between two versions of an agent",
)
@async_logfire_decorator
async def diff_agent_versions(
    request: Request,
    agent_id: int,
    number: int,
    to: Optional[int] = Query(None, ge=1, description="Default: the latest version"),
) -> VersionDiff:
    db: PostgresDB = request.state.db
    old = await _require_version(db, agent_id, number)
    target = to if to is not None else await db.get_latest_version_number(agent_id)
    new = await _require_version(db, agent_id, target)
    return VersionDiff(
        agent_id=agent_id,
        from_version=old.number,
        to_version=new.number,
        changes=diff_snapshots(old.snapshot, new.snapshot),
    )


@router.post(
    "/agents/{agent_id}/rollback",
    summary="Make an agent what one of its versions was (recorded as a new version)",
)
@async_logfire_decorator
async def rollback_agent(
    request: Request, agent_id: int, data: RollbackRequest = Body(...)
) -> AgentVersion:
    db: PostgresDB = request.state.db
    await _require_version(db, agent_id, data.to)
    version = await db.rollback_agent(
        agent_id, data.to, data.comment, db.context.token.id
    )
    if version is None:  # the agent already is that version
        version = await db.get_agent_version(
            agent_id, await db.get_latest_version_number(agent_id)
        )
    return version
