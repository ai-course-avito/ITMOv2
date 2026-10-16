from decimal import Decimal

from app.models import User
from app.services.stats import get_stats_breakdown

BASE = {
    "name": "x",
    "amount": "10.00",
    "billing_cycle": "monthly",
    "start_date": "2026-01-01",
}
URL = "/api/stats/breakdown"


async def add(client, headers, **overrides):
    resp = await client.post(
        "/api/subscriptions", json={**BASE, **overrides}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def get_breakdown(client, headers):
    resp = await client.get(URL, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_by_subscription_is_ordered_by_cost_then_name(
    client, make_headers, pinned_today
):
    h = await make_headers("a@example.com")
    await add(client, h, name="five", amount="5.00")
    await add(client, h, name="twenty", amount="20.00")
    await add(client, h, name="ten-b", amount="10.00")
    await add(client, h, name="Ten-a", amount="10.00")
    body = await get_breakdown(client, h)
    assert [s["name"] for s in body["by_subscription"]] == [
        "twenty",
        "Ten-a",
        "ten-b",
        "five",
    ]
    assert body["by_subscription"][0]["monthly_cost"] == "20.00"


async def test_share_percent_values(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    await add(client, h, name="big", amount="75.00")
    await add(client, h, name="small", amount="25.00")
    body = await get_breakdown(client, h)
    assert body["monthly_total"] == "100.00"
    assert [s["share_percent"] for s in body["by_subscription"]] == ["75.00", "25.00"]
    assert [c["share_percent"] for c in body["by_cycle"]] == ["100.00"]


async def test_share_rounds_half_up(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    for name in ("a", "b", "c"):
        await add(client, h, name=name, amount="10.00")
    body = await get_breakdown(client, h)
    assert [s["share_percent"] for s in body["by_subscription"]] == ["33.33"] * 3


async def test_by_cycle_groups_and_counts(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    await add(client, h, name="m1", amount="10.00")
    await add(client, h, name="m2", amount="5.00")
    await add(client, h, name="y", amount="120.00", billing_cycle="yearly")
    await add(
        client,
        h,
        name="c1",
        amount="30.00",
        billing_cycle="custom_days",
        custom_interval_days=30,
    )
    await add(
        client,
        h,
        name="c2",
        amount="60.00",
        billing_cycle="custom_days",
        custom_interval_days=60,
    )
    body = await get_breakdown(client, h)
    cycles = {c["billing_cycle"]: c for c in body["by_cycle"]}
    assert cycles["monthly"]["subscription_count"] == 2
    assert cycles["monthly"]["monthly_cost"] == "15.00"
    assert cycles["yearly"]["subscription_count"] == 1
    assert cycles["custom_days"]["subscription_count"] == 2
    assert cycles["custom_days"]["monthly_cost"] == "60.00"
    assert [c["billing_cycle"] for c in body["by_cycle"]] == [
        "custom_days",
        "monthly",
        "yearly",
    ]
    assert "weekly" not in cycles


async def test_totals_match_summary_and_lists_sum_to_total(
    client, make_headers, pinned_today
):
    h = await make_headers("a@example.com")
    await add(client, h, name="a", amount="15.49")
    await add(client, h, name="b", amount="35.88", billing_cycle="yearly")
    await add(client, h, name="c", amount="6.00", billing_cycle="weekly")
    await add(
        client,
        h,
        name="d",
        amount="19.90",
        billing_cycle="custom_days",
        custom_interval_days=90,
    )
    breakdown = await get_breakdown(client, h)
    summary = (await client.get("/api/stats/summary", headers=h)).json()
    assert breakdown["monthly_total"] == summary["monthly_total"]
    assert breakdown["currency"] == summary["currency"]
    total = Decimal(breakdown["monthly_total"])
    assert (
        sum(Decimal(s["monthly_cost"]) for s in breakdown["by_subscription"]) == total
    )
    assert sum(Decimal(c["monthly_cost"]) for c in breakdown["by_cycle"]) == total


async def test_inactive_excluded_and_empty_state(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    assert await get_breakdown(client, h) == {
        "currency": "USD",
        "monthly_total": "0.00",
        "by_subscription": [],
        "by_cycle": [],
    }
    await add(client, h, name="paused", amount="50.00", is_active=False)
    body = await get_breakdown(client, h)
    assert body["by_subscription"] == [] and body["monthly_total"] == "0.00"


async def test_total_rounding_to_zero_gives_zero_shares_without_error(session):
    from app.models import Subscription

    user = User(email="z@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    session.add(
        Subscription(
            owner_id=user.id,
            name="tiny",
            amount=Decimal("0.01"),
            billing_cycle="yearly",
        )
    )
    await session.commit()

    body = await get_stats_breakdown(session, user)
    assert body.monthly_total == Decimal("0.00")
    assert [s.share_percent for s in body.by_subscription] == [Decimal("0.00")]
    assert [c.share_percent for c in body.by_cycle] == [Decimal("0.00")]


async def test_breakdown_is_private_and_authenticated(
    client, make_headers, pinned_today
):
    a = await make_headers("a@example.com")
    b = await make_headers("b@example.com")
    await add(client, a, name="mine", amount="10.00")
    await add(client, b, name="theirs", amount="99.00")
    body = await get_breakdown(client, a)
    assert [s["name"] for s in body["by_subscription"]] == ["mine"]
    assert (await client.get(URL)).status_code == 401
