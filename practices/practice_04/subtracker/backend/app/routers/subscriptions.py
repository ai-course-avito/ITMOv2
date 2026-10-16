from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db_session
from app.dependencies import get_today
from app.models import Subscription, User
from app.schemas.subscriptions import (
    BillingCycle,
    SortField,
    SortOrder,
    SubscriptionCreate,
    SubscriptionListItem,
    SubscriptionRead,
    SubscriptionUpdate,
    UpcomingCharge,
)
from app.services import subscriptions as service

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
    )


@router.post("", response_model=SubscriptionRead, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    body: SubscriptionCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    today: date = Depends(get_today),
) -> Subscription:
    return await service.create_subscription(session, user, body, today)


@router.get("", response_model=list[SubscriptionListItem])
async def list_subscriptions(
    is_active: bool | None = None,
    billing_cycle: BillingCycle | None = None,
    q: str | None = Query(None, max_length=100),
    sort: SortField = SortField.id,
    order: SortOrder = SortOrder.asc,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    today: date = Depends(get_today),
) -> list[SubscriptionListItem]:
    query = service.SubscriptionListQuery(
        is_active=is_active,
        billing_cycle=billing_cycle,
        q=q,
        sort=sort,
        order=order,
        limit=limit,
        offset=offset,
    )
    return await service.list_subscriptions(session, user, query, today)


# Declared before "/{subscription_id}" so "upcoming" is not parsed as an id.
@router.get("/upcoming", response_model=list[UpcomingCharge])
async def read_upcoming_charges(
    days: int = Query(7, ge=1, le=365),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    today: date = Depends(get_today),
) -> list[UpcomingCharge]:
    return await service.upcoming_charges(session, user, days, today)


@router.get("/{subscription_id}", response_model=SubscriptionRead)
async def read_subscription(
    subscription_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Subscription:
    subscription = await service.get_owned_subscription(session, user, subscription_id)
    if subscription is None:
        raise _not_found()
    return subscription


@router.patch("/{subscription_id}", response_model=SubscriptionRead)
async def update_subscription(
    subscription_id: int,
    body: SubscriptionUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    today: date = Depends(get_today),
) -> Subscription:
    try:
        subscription = await service.update_subscription(
            session, user, subscription_id, body, today
        )
    except service.SubscriptionValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc
    if subscription is None:
        raise _not_found()
    return subscription


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    subscription_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    if not await service.delete_subscription(session, user, subscription_id):
        raise _not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
