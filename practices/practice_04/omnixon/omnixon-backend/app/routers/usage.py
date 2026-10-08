from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from access import default_agent_id, ensure_agent_access
from core import USAGE_TTL_DAYS, async_logfire_decorator
from database import PostgresDB, RANK

router = APIRouter()


class UsageRow(BaseModel):
    token_id: Optional[int] = None  # None: the token has been deleted
    token_name: str
    model: str
    requests: int
    errors: int
    input_tokens: int
    output_tokens: int
    cost: float  # the sum of what the provider reported; calls without a price add nothing
    duration_ms_sum: int


class DailyUsage(UsageRow):
    day: date


class MonthlyUsage(UsageRow):
    month: date


def _scope(db: PostgresDB, agent_id: Optional[int]) -> Dict[str, Optional[int]]:
    """Below admin the statistics are those of the tokens of the own agent; an admin sees all, or one agent's."""
    if db.context.token.rank >= RANK["admin"]:
        if agent_id is not None:
            ensure_agent_access(db, agent_id)
        return {"agent_id": agent_id, "own_agent_id": None}
    return {"agent_id": None, "own_agent_id": default_agent_id(db, agent_id)}


# Usage of the models (no texts are kept)


@router.get(
    "/usage",
    summary="Recent usage by day, token and model (the last USAGE_TTL_DAYS days are in detail)",
)
@async_logfire_decorator
async def get_usage(
    request: Request,
    days: int = Query(
        30, ge=1, le=366, description="How many days back, counting today"
    ),
    token_id: Optional[int] = Query(None, description="Only this token"),
    agent_id: Optional[int] = Query(None, description="Only the tokens of this agent"),
) -> List[DailyUsage]:
    db: PostgresDB = request.state.db
    today = date.today()
    rows = await db.usage_daily(
        today - timedelta(days=days - 1),
        today,
        token_id=token_id,
        **_scope(db, agent_id),
    )
    return [DailyUsage(**row) for row in rows]


@router.get(
    "/usage/monthly",
    summary="Older usage, folded into one row per token, month and model",
)
@async_logfire_decorator
async def get_usage_monthly(
    request: Request,
    token_id: Optional[int] = Query(None, description="Only this token"),
    agent_id: Optional[int] = Query(None, description="Only the tokens of this agent"),
) -> List[MonthlyUsage]:
    db: PostgresDB = request.state.db
    rows = await db.usage_monthly(token_id=token_id, **_scope(db, agent_id))
    return [MonthlyUsage(**row) for row in rows]
