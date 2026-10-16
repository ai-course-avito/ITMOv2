from sqlalchemy import select

from app.models import Subscription

URL = "/api/subscriptions"
UPCOMING = f"{URL}/upcoming"
# pinned_today is 2026-10-16


async def add(client, headers, name, next_date, **overrides):
    body = {
        "name": name,
        "amount": "5.00",
        "billing_cycle": "monthly",
        "start_date": "2025-01-01",
        "next_billing_date": next_date,
        **overrides,
    }
    resp = await client.post(URL, json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_inside_and_outside_window(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    await add(client, h, "soon", "2026-10-19")
    await add(client, h, "far", "2026-10-26")

    items = (await client.get(UPCOMING, params={"days": 7}, headers=h)).json()
    assert [(i["name"], i["days_until"]) for i in items] == [("soon", 3)]
    assert items[0]["charge_date"] == "2026-10-19"
    assert items[0]["amount"] == "5.00"


async def test_default_window_is_7_days(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    await add(client, h, "in7", "2026-10-23")
    await add(client, h, "in8", "2026-10-24")
    items = (await client.get(UPCOMING, headers=h)).json()
    assert [i["name"] for i in items] == ["in7"]


async def test_charge_today_has_zero_days_until(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    await add(client, h, "today", "2026-10-16")
    items = (await client.get(UPCOMING, headers=h)).json()
    assert items[0]["days_until"] == 0


async def test_past_date_is_rolled_forward(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    await add(
        client, h, "monthly", "2026-09-06"
    )  # 40 days ago -> Oct 6 passed -> Nov 6
    await add(client, h, "weekly", "2026-10-01", billing_cycle="weekly")  # -> Oct 22
    items = (await client.get(UPCOMING, params={"days": 30}, headers=h)).json()
    assert [(i["name"], i["charge_date"]) for i in items] == [
        ("weekly", "2026-10-22"),
        ("monthly", "2026-11-06"),
    ]


async def test_sorted_by_date_then_name(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    await add(client, h, "b", "2026-10-18")
    await add(client, h, "a", "2026-10-18")
    await add(client, h, "z", "2026-10-17")
    items = (await client.get(UPCOMING, headers=h)).json()
    assert [i["name"] for i in items] == ["z", "a", "b"]


async def test_excludes_inactive_and_other_users(client, make_headers, pinned_today):
    a = await make_headers("a@example.com")
    b = await make_headers("b@example.com")
    await add(client, a, "off", "2026-10-17", is_active=False)
    await add(client, b, "theirs", "2026-10-17")
    await add(client, a, "mine", "2026-10-17")
    items = (await client.get(UPCOMING, headers=a)).json()
    assert [i["name"] for i in items] == ["mine"]


async def test_invalid_days_is_422(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    for days in ("0", "366", "abc"):
        resp = await client.get(UPCOMING, params={"days": days}, headers=h)
        assert resp.status_code == 422, days


async def test_requires_authentication(client):
    assert (await client.get(UPCOMING)).status_code == 401


async def test_read_has_no_side_effects(client, make_headers, session, pinned_today):
    h = await make_headers("a@example.com")
    await add(client, h, "old", "2026-08-01")
    before = (
        (await session.execute(select(Subscription.next_billing_date))).scalars().all()
    )

    items = (await client.get(UPCOMING, params={"days": 60}, headers=h)).json()
    assert items  # it was rolled forward in the response...

    session.expire_all()
    after = (
        (await session.execute(select(Subscription.next_billing_date))).scalars().all()
    )
    assert after == before  # ...but nothing was written
