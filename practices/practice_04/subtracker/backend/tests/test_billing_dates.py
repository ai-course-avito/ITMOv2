from datetime import date

import pytest

from app.services.billing import (
    default_next_billing_date,
    first_on_or_after,
    occurrence,
)

D = date


def test_weekly_occurrences():
    assert occurrence(D(2026, 1, 1), "weekly", None, 3) == D(2026, 1, 22)


def test_custom_days_occurrences():
    assert occurrence(D(2026, 1, 1), "custom_days", 45, 2) == D(2026, 4, 1)


def test_monthly_month_end_clamp_without_drift():
    anchor = D(2026, 1, 31)
    assert occurrence(anchor, "monthly", None, 1) == D(2026, 2, 28)
    assert occurrence(anchor, "monthly", None, 2) == D(2026, 3, 31)
    assert occurrence(anchor, "monthly", None, 13) == D(2027, 2, 28)


def test_monthly_leap_february():
    assert occurrence(D(2028, 1, 31), "monthly", None, 1) == D(2028, 2, 29)


def test_yearly_leap_day():
    anchor = D(2028, 2, 29)
    assert occurrence(anchor, "yearly", None, 1) == D(2029, 2, 28)
    assert occurrence(anchor, "yearly", None, 4) == D(2032, 2, 29)


def test_unknown_cycle_and_missing_interval_raise():
    with pytest.raises(ValueError):
        occurrence(D(2026, 1, 1), "daily", None, 1)
    with pytest.raises(ValueError):
        occurrence(D(2026, 1, 1), "custom_days", None, 1)


@pytest.mark.parametrize(
    ("anchor", "cycle", "interval", "today", "expected"),
    [
        (D(2026, 3, 10), "monthly", None, D(2026, 3, 1), D(2026, 3, 10)),  # future
        (D(2026, 3, 10), "monthly", None, D(2026, 3, 10), D(2026, 3, 10)),  # today
        (D(2026, 1, 10), "monthly", None, D(2026, 3, 11), D(2026, 4, 10)),
        (D(2026, 1, 10), "monthly", None, D(2026, 3, 10), D(2026, 3, 10)),
        (D(2026, 1, 31), "monthly", None, D(2026, 2, 28), D(2026, 2, 28)),
        (D(2026, 1, 31), "monthly", None, D(2026, 3, 1), D(2026, 3, 31)),
        (D(2025, 6, 15), "yearly", None, D(2026, 6, 16), D(2027, 6, 15)),
        (D(2025, 6, 15), "yearly", None, D(2026, 6, 15), D(2026, 6, 15)),
        (D(2026, 1, 1), "weekly", None, D(2026, 1, 9), D(2026, 1, 15)),
        (D(2026, 1, 1), "weekly", None, D(2026, 1, 8), D(2026, 1, 8)),
        (D(2026, 1, 1), "custom_days", 90, D(2026, 6, 1), D(2026, 6, 30)),
    ],
)
def test_first_on_or_after(anchor, cycle, interval, today, expected):
    result = first_on_or_after(anchor, cycle, interval, today)
    assert result == expected
    assert result >= today


@pytest.mark.parametrize("cycle", ["weekly", "monthly", "yearly"])
def test_default_next_billing_date_not_before_today_or_start(cycle):
    today = D(2026, 10, 16)
    for start in (D(2024, 2, 29), D(2026, 10, 16), D(2027, 1, 5)):
        result = default_next_billing_date(start, cycle, None, today)
        assert result >= today
        assert result >= start


def test_default_next_billing_date_custom_days():
    result = default_next_billing_date(
        D(2026, 1, 1), "custom_days", 30, D(2026, 10, 16)
    )
    assert result >= D(2026, 10, 16)
    assert (result - D(2026, 1, 1)).days % 30 == 0
