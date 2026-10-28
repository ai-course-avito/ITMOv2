from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db_session
from app.models import User
from app.schemas.stats import StatsBreakdownResponse, StatsSummaryResponse
from app.services import stats as stats_service

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/summary", response_model=StatsSummaryResponse)
async def read_stats_summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StatsSummaryResponse:
    return await stats_service.get_stats_summary(session, current_user)


@router.get("/breakdown", response_model=StatsBreakdownResponse)
async def read_stats_breakdown(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StatsBreakdownResponse:
    return await stats_service.get_stats_breakdown(session, current_user)
