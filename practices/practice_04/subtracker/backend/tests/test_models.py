import pytest
from sqlalchemy.exc import IntegrityError

from app.models import User


async def test_user_plan_defaults_to_free(session):
    user = User(email="a@example.com", hashed_password="x")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    assert user.plan == "free"


async def test_user_plan_rejects_unknown_value(session):
    session.add(User(email="b@example.com", hashed_password="x", plan="gold"))
    with pytest.raises(IntegrityError):
        await session.commit()


async def _user(session) -> User:
    user = User(email="owner@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    return user


def _sub(user, **overrides):
    from decimal import Decimal

    from app.models import Subscription

    fields = {
        "owner_id": user.id,
        "name": "Netflix",
        "amount": Decimal("9.99"),
        "billing_cycle": "monthly",
    }
    fields.update(overrides)
    return Subscription(**fields)


async def test_valid_subscriptions_are_accepted(session):
    user = await _user(session)
    session.add_all(
        [
            _sub(user),
            _sub(user, billing_cycle="custom_days", custom_interval_days=45),
        ]
    )
    await session.commit()


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": 0},
        {"amount": -5},
        {"billing_cycle": "daily"},
        {"billing_cycle": "monthly", "custom_interval_days": 30},
        {"billing_cycle": "custom_days"},
        {"billing_cycle": "custom_days", "custom_interval_days": 0},
    ],
)
async def test_invalid_subscription_rows_are_rejected(session, overrides):
    user = await _user(session)
    session.add(_sub(user, **overrides))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_subscription_has_dates_and_optional_note(session):
    user = await _user(session)
    sub = _sub(user)
    session.add(sub)
    await session.commit()
    assert sub.start_date is not None
    assert sub.next_billing_date is not None
    assert sub.note is None
