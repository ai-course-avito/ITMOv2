import calendar
import math
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


def monthly_cost(
    amount: Decimal,
    billing_cycle: str,
    custom_interval_days: int | None = None,
) -> Decimal:
    if billing_cycle == "monthly":
        result = amount
    elif billing_cycle == "yearly":
        result = amount / 12
    elif billing_cycle == "weekly":
        result = amount * 52 / 12
    elif billing_cycle == "custom_days":
        if not custom_interval_days:
            raise ValueError(
                "custom_interval_days is required for custom_days billing_cycle"
            )
        result = amount * 30 / custom_interval_days
    else:
        raise ValueError(f"Unknown billing_cycle: {billing_cycle!r}")

    return result.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _add_months(anchor: date, months: int) -> date:
    """Add months to the anchor, clamping the day to the target month length."""
    total = anchor.year * 12 + (anchor.month - 1) + months
    year, month0 = divmod(total, 12)
    month = month0 + 1
    day = min(anchor.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _require_interval(cycle: str, interval: int | None) -> int:
    if cycle == "custom_days" and (not interval or interval <= 0):
        raise ValueError("custom_interval_days is required for custom_days")
    return interval or 0


def occurrence(anchor: date, cycle: str, interval: int | None, n: int) -> date:
    """The n-th billing date counted from the anchor (n=0 is the anchor itself)."""
    if cycle == "weekly":
        return anchor + timedelta(days=7 * n)
    if cycle == "custom_days":
        return anchor + timedelta(days=_require_interval(cycle, interval) * n)
    if cycle == "monthly":
        return _add_months(anchor, n)
    if cycle == "yearly":
        return _add_months(anchor, 12 * n)
    raise ValueError(f"Unknown billing_cycle: {cycle!r}")


def first_on_or_after(
    anchor: date, cycle: str, interval: int | None, today: date
) -> date:
    """First billing date on or after today in the sequence starting at the anchor."""
    if anchor >= today:
        return anchor
    if cycle in ("weekly", "custom_days"):
        step = 7 if cycle == "weekly" else _require_interval(cycle, interval)
        return occurrence(
            anchor, cycle, interval, math.ceil((today - anchor).days / step)
        )
    if cycle not in ("monthly", "yearly"):
        raise ValueError(f"Unknown billing_cycle: {cycle!r}")
    months_per_step = 1 if cycle == "monthly" else 12
    months = (today.year - anchor.year) * 12 + today.month - anchor.month
    n = months // months_per_step
    while occurrence(anchor, cycle, interval, n) < today:
        n += 1
    return occurrence(anchor, cycle, interval, n)


def default_next_billing_date(
    start_date: date, cycle: str, interval: int | None, today: date
) -> date:
    """Next billing date for a new or re-cycled subscription."""
    return first_on_or_after(start_date, cycle, interval, today)
