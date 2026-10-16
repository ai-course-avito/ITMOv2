BASE = {
    "name": "x",
    "amount": "10.00",
    "billing_cycle": "monthly",
    "start_date": "2026-01-01",
}


async def add(client, headers, **overrides):
    resp = await client.post(
        "/api/subscriptions", json={**BASE, **overrides}, headers=headers
    )
    assert resp.status_code == 201, resp.text


async def summary(client, headers):
    resp = await client.get("/api/stats/summary", headers=headers)
    assert resp.status_code == 200
    return resp.json()


async def test_weekly_cost_is_amount_times_52_over_12(
    client, make_headers, pinned_today
):
    h = await make_headers("a@example.com")
    await add(client, h, amount="6.00", billing_cycle="weekly")
    body = await summary(client, h)
    assert body["monthly_total"] == "26.00"
    assert body["yearly_total"] == "312.00"


async def test_custom_interval_cost(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    await add(
        client, h, amount="19.90", billing_cycle="custom_days", custom_interval_days=90
    )
    assert (await summary(client, h))["monthly_total"] == "6.63"


async def test_yearly_cost(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    await add(client, h, amount="120.00", billing_cycle="yearly")
    assert (await summary(client, h))["monthly_total"] == "10.00"


async def test_inactive_and_foreign_subscriptions_do_not_count(
    client, make_headers, pinned_today
):
    a = await make_headers("a@example.com")
    b = await make_headers("b@example.com")
    await add(client, a, amount="5.00")
    await add(client, a, amount="500.00", is_active=False)
    await add(client, b, amount="1000.00")
    assert (await summary(client, a))["monthly_total"] == "5.00"


async def test_empty_summary_and_missing_token(client, make_headers):
    h = await make_headers("a@example.com")
    body = await summary(client, h)
    assert body == {"monthly_total": "0.00", "yearly_total": "0.00", "currency": "USD"}
    assert (await client.get("/api/stats/summary")).status_code == 401
