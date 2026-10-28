from decimal import Decimal

import pytest

from app.services.billing import monthly_cost


def test_monthly_cost_monthly():
    assert monthly_cost(Decimal("9.99"), "monthly") == Decimal("9.99")


def test_monthly_cost_yearly():
    assert monthly_cost(Decimal(120), "yearly") == Decimal("10.00")


def test_monthly_cost_weekly():
    assert monthly_cost(Decimal(10), "weekly") == Decimal("43.33")


def test_monthly_cost_custom_days():
    assert monthly_cost(
        Decimal(100), "custom_days", custom_interval_days=10
    ) == Decimal("300.00")


def test_monthly_cost_invalid_cycle_raises():
    with pytest.raises(ValueError):
        monthly_cost(Decimal(10), "biweekly")


def test_monthly_cost_custom_days_without_interval_raises():
    with pytest.raises(ValueError):
        monthly_cost(Decimal(10), "custom_days")
