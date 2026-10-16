from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subscription, User
from app.schemas.stats import (
    CycleShare,
    StatsBreakdownResponse,
    StatsSummaryResponse,
    SubscriptionShare,
)
from app.services.billing import monthly_cost

TWO_PLACES = Decimal("0.01")


async def active_monthly_costs(
    session: AsyncSession, user: User
) -> list[tuple[Subscription, Decimal]]:
    """The user's active subscriptions with their monthly-equivalent cost.

    Shared by the summary and the breakdown so their totals cannot diverge.
    """
    stmt = select(Subscription).where(
        Subscription.owner_id == user.id,
        Subscription.is_active.is_(True),
    )
    subscriptions = (await session.execute(stmt)).scalars().all()
    return [
        (
            sub,
            monthly_cost(sub.amount, sub.billing_cycle, sub.custom_interval_days),
        )
        for sub in subscriptions
    ]


def sum_costs(costs: list[Decimal]) -> Decimal:
    return sum(costs, Decimal("0.00")).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


async def get_stats_summary(session: AsyncSession, user: User) -> StatsSummaryResponse:
    pairs = await active_monthly_costs(session, user)
    monthly_total = sum_costs([cost for _, cost in pairs])
    yearly_total = (monthly_total * 12).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    return StatsSummaryResponse(
        monthly_total=monthly_total,
        yearly_total=yearly_total,
        currency=user.default_currency,
    )


def _share_percent(cost: Decimal, total: Decimal) -> Decimal:
    if total == 0:
        return Decimal("0.00")
    return (cost / total * 100).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


async def get_stats_breakdown(
    session: AsyncSession, user: User
) -> StatsBreakdownResponse:
    pairs = await active_monthly_costs(session, user)
    monthly_total = sum_costs([cost for _, cost in pairs])

    by_subscription = [
        SubscriptionShare(
            id=sub.id,
            name=sub.name,
            billing_cycle=sub.billing_cycle,
            monthly_cost=cost,
            share_percent=_share_percent(cost, monthly_total),
        )
        for sub, cost in sorted(
            pairs, key=lambda pair: (-pair[1], pair[0].name.casefold(), pair[0].id)
        )
    ]

    cycle_costs: dict[str, list[Decimal]] = {}
    for sub, cost in pairs:
        cycle_costs.setdefault(sub.billing_cycle, []).append(cost)
    by_cycle = [
        CycleShare(
            billing_cycle=cycle,
            subscription_count=len(costs),
            monthly_cost=sum_costs(costs),
            share_percent=_share_percent(sum_costs(costs), monthly_total),
        )
        for cycle, costs in sorted(
            cycle_costs.items(), key=lambda item: (-sum_costs(item[1]), item[0])
        )
    ]

    return StatsBreakdownResponse(
        currency=user.default_currency,
        monthly_total=monthly_total,
        by_subscription=by_subscription,
        by_cycle=by_cycle,
    )
