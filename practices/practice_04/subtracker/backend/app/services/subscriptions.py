import json
from datetime import date, timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subscription, User
from app.schemas.subscriptions import (
    BillingCycle,
    SubscriptionCreate,
    SubscriptionUpdate,
    UpcomingCharge,
)
from app.services.billing import default_next_billing_date, first_on_or_after

FIELDS = (
    "name",
    "amount",
    "billing_cycle",
    "custom_interval_days",
    "start_date",
    "next_billing_date",
    "note",
    "is_active",
)
RECOMPUTE_TRIGGERS = {"billing_cycle", "custom_interval_days", "start_date"}


class SubscriptionValidationError(Exception):
    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__("Invalid subscription")
        self.errors = errors


def _ensure_next_date(data: SubscriptionCreate, today: date) -> dict[str, Any]:
    values = data.model_dump()
    if values["next_billing_date"] is None:
        values["next_billing_date"] = default_next_billing_date(
            data.start_date, data.billing_cycle.value, data.custom_interval_days, today
        )
    values["billing_cycle"] = data.billing_cycle.value
    return values


async def create_subscription(
    session: AsyncSession, user: User, data: SubscriptionCreate, today: date
) -> Subscription:
    subscription = Subscription(owner_id=user.id, **_ensure_next_date(data, today))
    session.add(subscription)
    await session.commit()
    await session.refresh(subscription)
    return subscription


async def list_subscriptions(
    session: AsyncSession,
    user: User,
    is_active: bool | None,
    limit: int,
    offset: int,
) -> list[Subscription]:
    stmt = select(Subscription).where(Subscription.owner_id == user.id)
    if is_active is not None:
        stmt = stmt.where(Subscription.is_active.is_(is_active))
    stmt = stmt.order_by(Subscription.id).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


async def get_owned_subscription(
    session: AsyncSession, user: User, subscription_id: int
) -> Subscription | None:
    # Ownership is part of the query: someone else's row is the same as a missing one.
    stmt = select(Subscription).where(
        Subscription.id == subscription_id, Subscription.owner_id == user.id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def update_subscription(
    session: AsyncSession,
    user: User,
    subscription_id: int,
    patch: SubscriptionUpdate,
    today: date,
) -> Subscription | None:
    subscription = await get_owned_subscription(session, user, subscription_id)
    if subscription is None:
        return None

    changes = patch.model_dump(exclude_unset=True)
    merged = {name: getattr(subscription, name) for name in FIELDS} | changes
    if RECOMPUTE_TRIGGERS & changes.keys() and "next_billing_date" not in changes:
        merged["next_billing_date"] = None
    if (
        changes.get("billing_cycle") not in (None, BillingCycle.custom_days.value)
        and "custom_interval_days" not in changes
    ):
        merged["custom_interval_days"] = None  # leaving custom_days drops its interval

    try:
        validated = SubscriptionCreate.model_validate(merged)
    except ValidationError as exc:
        raise SubscriptionValidationError(
            json.loads(
                exc.json(include_url=False, include_context=False, include_input=False)
            )
        ) from exc

    for name, value in _ensure_next_date(validated, today).items():
        setattr(subscription, name, value)
    await session.commit()
    await session.refresh(subscription)
    return subscription


async def delete_subscription(
    session: AsyncSession, user: User, subscription_id: int
) -> bool:
    subscription = await get_owned_subscription(session, user, subscription_id)
    if subscription is None:
        return False
    await session.delete(subscription)
    await session.commit()
    return True


async def upcoming_charges(
    session: AsyncSession, user: User, days: int, today: date
) -> list[UpcomingCharge]:
    """Active subscriptions charged from today through today+days. Read-only."""
    stmt = select(Subscription).where(
        Subscription.owner_id == user.id, Subscription.is_active.is_(True)
    )
    horizon = today + timedelta(days=days)
    charges = []
    for sub in (await session.execute(stmt)).scalars().all():
        charge_date = first_on_or_after(
            sub.next_billing_date, sub.billing_cycle, sub.custom_interval_days, today
        )
        if charge_date <= horizon:
            charges.append(
                UpcomingCharge(
                    id=sub.id,
                    name=sub.name,
                    amount=sub.amount,
                    billing_cycle=sub.billing_cycle,
                    charge_date=charge_date,
                    days_until=(charge_date - today).days,
                )
            )
    return sorted(charges, key=lambda c: (c.charge_date, c.name))
