from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subscription, User
from tests.conftest import authenticate_as


async def _make_user(session: AsyncSession, email: str, currency: str = "USD") -> User:
    user = User(email=email, hashed_password="x", default_currency=currency)
    session.add(user)
    await session.flush()
    return user


async def test_summary_sums_only_active_subscriptions(
    session: AsyncSession, client: AsyncClient
):
    user = await _make_user(session, "owner@example.com")
    session.add_all(
        [
            Subscription(
                owner_id=user.id,
                name="monthly sub",
                amount=Decimal("9.99"),
                billing_cycle="monthly",
                is_active=True,
            ),
            Subscription(
                owner_id=user.id,
                name="yearly sub",
                amount=Decimal(120),
                billing_cycle="yearly",
                is_active=True,
            ),
            Subscription(
                owner_id=user.id,
                name="cancelled sub",
                amount=Decimal(50),
                billing_cycle="monthly",
                is_active=False,
            ),
        ]
    )
    await session.commit()
    authenticate_as(user)

    response = await client.get("/api/stats/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["monthly_total"] == "19.99"
    assert body["yearly_total"] == "239.88"
    assert body["currency"] == "USD"


async def test_summary_returns_zero_with_no_subscriptions(
    session: AsyncSession, client: AsyncClient
):
    user = await _make_user(session, "empty@example.com", currency="EUR")
    await session.commit()
    authenticate_as(user)

    response = await client.get("/api/stats/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["monthly_total"] == "0.00"
    assert body["yearly_total"] == "0.00"
    assert body["currency"] == "EUR"


async def test_summary_is_isolated_per_owner(
    session: AsyncSession, client: AsyncClient
):
    owner_a = await _make_user(session, "a@example.com")
    owner_b = await _make_user(session, "b@example.com")
    session.add_all(
        [
            Subscription(
                owner_id=owner_a.id,
                name="a sub",
                amount=Decimal(10),
                billing_cycle="monthly",
                is_active=True,
            ),
            Subscription(
                owner_id=owner_b.id,
                name="b sub",
                amount=Decimal(1000),
                billing_cycle="monthly",
                is_active=True,
            ),
        ]
    )
    await session.commit()
    authenticate_as(owner_a)

    response = await client.get("/api/stats/summary")

    assert response.status_code == 200
    assert response.json()["monthly_total"] == "10.00"


async def test_summary_requires_authentication(client: AsyncClient):
    response = await client.get("/api/stats/summary")

    assert response.status_code in (401, 403)
