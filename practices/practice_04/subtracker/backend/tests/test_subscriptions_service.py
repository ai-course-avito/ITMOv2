from datetime import date
from decimal import Decimal

from app.models import User
from app.schemas.subscriptions import SubscriptionCreate, SubscriptionUpdate
from app.services import subscriptions as service

TODAY = date(2026, 10, 16)


async def make_user(session, email="u@example.com") -> User:
    user = User(email=email, hashed_password="x")
    session.add(user)
    await session.flush()
    return user


def payload(**overrides) -> SubscriptionCreate:
    data = {
        "name": "Netflix",
        "amount": "9.99",
        "billing_cycle": "monthly",
        "start_date": "2026-01-05",
    }
    return SubscriptionCreate.model_validate({**data, **overrides})


async def test_create_computes_default_next_billing_date(session):
    user = await make_user(session)
    sub = await service.create_subscription(session, user, payload(), TODAY)
    assert sub.owner_id == user.id
    assert sub.next_billing_date == date(2026, 11, 5)
    assert sub.amount == Decimal("9.99")


async def test_create_keeps_explicit_next_billing_date(session):
    user = await make_user(session)
    sub = await service.create_subscription(
        session, user, payload(next_billing_date="2026-12-01"), TODAY
    )
    assert sub.next_billing_date == date(2026, 12, 1)


async def test_foreign_id_returns_nothing_for_every_operation(session):
    owner = await make_user(session, "a@example.com")
    other = await make_user(session, "b@example.com")
    sub = await service.create_subscription(session, owner, payload(), TODAY)

    assert await service.get_owned_subscription(session, other, sub.id) is None
    assert (
        await service.update_subscription(
            session, other, sub.id, SubscriptionUpdate(name="hacked"), TODAY
        )
        is None
    )
    assert await service.delete_subscription(session, other, sub.id) is False
    assert (
        await service.get_owned_subscription(session, owner, sub.id)
    ).name == "Netflix"


async def test_list_filters_paging_and_owner(session):
    owner = await make_user(session, "a@example.com")
    other = await make_user(session, "b@example.com")
    first = await service.create_subscription(session, owner, payload(name="A"), TODAY)
    await service.create_subscription(
        session, owner, payload(name="B", is_active=False), TODAY
    )
    await service.create_subscription(session, other, payload(name="C"), TODAY)

    everything = await service.list_subscriptions(session, owner, None, 100, 0)
    assert [s.name for s in everything] == ["A", "B"]
    active = await service.list_subscriptions(session, owner, True, 100, 0)
    assert [s.id for s in active] == [first.id]
    paged = await service.list_subscriptions(session, owner, None, 1, 1)
    assert [s.name for s in paged] == ["B"]


async def test_update_merges_and_keeps_other_fields(session):
    user = await make_user(session)
    sub = await service.create_subscription(session, user, payload(note="hi"), TODAY)
    before = sub.next_billing_date
    updated = await service.update_subscription(
        session, user, sub.id, SubscriptionUpdate(amount=Decimal("12.50")), TODAY
    )
    assert updated.amount == Decimal("12.50")
    assert updated.note == "hi"
    assert updated.next_billing_date == before


async def test_update_cycle_recomputes_date_and_drops_interval(session):
    user = await make_user(session)
    sub = await service.create_subscription(
        session,
        user,
        payload(billing_cycle="custom_days", custom_interval_days=10),
        TODAY,
    )
    updated = await service.update_subscription(
        session, user, sub.id, SubscriptionUpdate(billing_cycle="yearly"), TODAY
    )
    assert updated.custom_interval_days is None
    assert updated.next_billing_date == date(2027, 1, 5)


async def test_update_invalid_merge_raises_and_changes_nothing(session):
    import pytest

    user = await make_user(session)
    sub = await service.create_subscription(session, user, payload(), TODAY)
    with pytest.raises(service.SubscriptionValidationError):
        await service.update_subscription(
            session,
            user,
            sub.id,
            SubscriptionUpdate(billing_cycle="custom_days"),
            TODAY,
        )
    await session.refresh(sub)
    assert sub.billing_cycle == "monthly"


async def test_update_null_for_required_field_is_rejected(session):
    import pytest

    user = await make_user(session)
    sub = await service.create_subscription(session, user, payload(), TODAY)
    with pytest.raises(service.SubscriptionValidationError):
        await service.update_subscription(
            session, user, sub.id, SubscriptionUpdate(amount=None), TODAY
        )


async def test_delete_removes_row(session):
    user = await make_user(session)
    sub = await service.create_subscription(session, user, payload(), TODAY)
    assert await service.delete_subscription(session, user, sub.id) is True
    assert await service.get_owned_subscription(session, user, sub.id) is None
