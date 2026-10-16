from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.subscriptions import SubscriptionCreate, SubscriptionRead

BASE = {
    "name": "Netflix",
    "amount": "9.99",
    "billing_cycle": "monthly",
    "start_date": "2026-01-01",
}


def build(**overrides):
    return SubscriptionCreate.model_validate({**BASE, **overrides})


def test_valid_subscription_parses_decimal():
    sub = build()
    assert sub.amount == Decimal("9.99")
    assert sub.is_active is True
    assert sub.next_billing_date is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": "0"},
        {"amount": "-1"},
        {"amount": "1.234"},
        {"amount": "100000000"},
        {"billing_cycle": "daily"},
        {"name": ""},
        {"name": "x" * 256},
        {"note": "x" * 501},
        {"billing_cycle": "custom_days"},
        {"billing_cycle": "custom_days", "custom_interval_days": 0},
        {"billing_cycle": "monthly", "custom_interval_days": 30},
        {"next_billing_date": "2025-12-31"},
    ],
)
def test_invalid_subscription_is_rejected(overrides):
    with pytest.raises(ValidationError):
        build(**overrides)


def test_custom_days_with_interval_is_valid():
    assert (
        build(billing_cycle="custom_days", custom_interval_days=45).custom_interval_days
        == 45
    )


def test_owner_id_and_id_are_ignored():
    sub = build(owner_id=999, id=5)
    assert not hasattr(sub, "owner_id")
    assert not hasattr(sub, "id")


def test_read_serializes_amount_with_two_decimals():
    read = SubscriptionRead(
        id=1,
        name="x",
        amount=Decimal("10.1"),
        billing_cycle="monthly",
        custom_interval_days=None,
        is_active=True,
        start_date=date(2026, 1, 1),
        next_billing_date=date(2026, 2, 1),
        note=None,
    )
    assert read.model_dump(mode="json")["amount"] == "10.10"
