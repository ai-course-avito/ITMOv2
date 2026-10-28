BASE = {
    "name": "Netflix",
    "amount": "9.99",
    "billing_cycle": "monthly",
    "start_date": "2026-01-05",
}
URL = "/api/subscriptions"


async def create(client, headers, **overrides):
    resp = await client.post(URL, json={**BASE, **overrides}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_returns_201_and_appears_in_list(
    client, make_headers, pinned_today
):
    headers = await make_headers("a@example.com")
    created = await create(client, headers, note="family plan")
    assert created["amount"] == "9.99"
    assert created["next_billing_date"] == "2026-11-05"
    assert created["note"] == "family plan"
    assert created["is_active"] is True

    listed = (await client.get(URL, headers=headers)).json()
    assert [s["id"] for s in listed] == [created["id"]]


async def test_create_keeps_explicit_next_billing_date(
    client, make_headers, pinned_today
):
    headers = await make_headers("a@example.com")
    created = await create(client, headers, next_billing_date="2026-12-24")
    assert created["next_billing_date"] == "2026-12-24"


async def test_money_is_returned_exactly(client, make_headers, pinned_today):
    headers = await make_headers("a@example.com")
    created = await create(client, headers, amount="10.10")
    assert created["amount"] == "10.10"
    created = await create(client, headers, amount="10")
    assert created["amount"] == "10.00"


async def test_unauthenticated_requests_are_401(client):
    assert (await client.post(URL, json=BASE)).status_code == 401
    assert (await client.get(URL)).status_code == 401
    assert (await client.get(f"{URL}/1")).status_code == 401
    assert (await client.patch(f"{URL}/1", json={})).status_code == 401
    assert (await client.delete(f"{URL}/1")).status_code == 401


async def test_validation_errors_are_422(client, make_headers, pinned_today):
    headers = await make_headers("a@example.com")
    bad = [
        {"amount": "0"},
        {"amount": "-3"},
        {"amount": "1.999"},
        {"billing_cycle": "daily"},
        {"billing_cycle": "custom_days"},
        {"billing_cycle": "monthly", "custom_interval_days": 10},
        {"next_billing_date": "2025-12-31"},
        {"name": ""},
    ]
    for overrides in bad:
        resp = await client.post(URL, json={**BASE, **overrides}, headers=headers)
        assert resp.status_code == 422, overrides
    assert (await client.get(URL, headers=headers)).json() == []


async def test_get_one_and_unknown_id(client, make_headers, pinned_today):
    headers = await make_headers("a@example.com")
    created = await create(client, headers)
    ok = await client.get(f"{URL}/{created['id']}", headers=headers)
    assert ok.status_code == 200 and ok.json()["name"] == "Netflix"
    assert (await client.get(f"{URL}/99999", headers=headers)).status_code == 404


async def test_list_filter_and_paging(client, make_headers, pinned_today):
    headers = await make_headers("a@example.com")
    await create(client, headers, name="A")
    await create(client, headers, name="B", is_active=False)
    await create(client, headers, name="C")

    active = (
        await client.get(URL, params={"is_active": "true"}, headers=headers)
    ).json()
    assert [s["name"] for s in active] == ["A", "C"]
    page = (
        await client.get(URL, params={"limit": 1, "offset": 1}, headers=headers)
    ).json()
    assert [s["name"] for s in page] == ["B"]
    assert (
        await client.get(URL, params={"limit": 501}, headers=headers)
    ).status_code == 422


async def test_patch_partial_update(client, make_headers, pinned_today):
    headers = await make_headers("a@example.com")
    created = await create(client, headers, note="keep")
    resp = await client.patch(
        f"{URL}/{created['id']}", json={"amount": "12.50"}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["amount"] == "12.50"
    assert body["note"] == "keep" and body["name"] == "Netflix"
    assert body["next_billing_date"] == created["next_billing_date"]


async def test_patch_invalid_merge_is_422_and_unchanged(
    client, make_headers, pinned_today
):
    headers = await make_headers("a@example.com")
    created = await create(client, headers)
    resp = await client.patch(
        f"{URL}/{created['id']}", json={"billing_cycle": "custom_days"}, headers=headers
    )
    assert resp.status_code == 422
    after = (await client.get(f"{URL}/{created['id']}", headers=headers)).json()
    assert after == created


async def test_patch_cycle_change_recomputes_date(client, make_headers, pinned_today):
    headers = await make_headers("a@example.com")
    created = await create(client, headers)
    resp = await client.patch(
        f"{URL}/{created['id']}", json={"billing_cycle": "yearly"}, headers=headers
    )
    assert resp.json()["next_billing_date"] == "2027-01-05"


async def test_delete_then_404(client, make_headers, pinned_today):
    headers = await make_headers("a@example.com")
    created = await create(client, headers)
    assert (
        await client.delete(f"{URL}/{created['id']}", headers=headers)
    ).status_code == 204
    assert (
        await client.get(f"{URL}/{created['id']}", headers=headers)
    ).status_code == 404
    assert (
        await client.delete(f"{URL}/{created['id']}", headers=headers)
    ).status_code == 404


async def test_user_b_cannot_read_change_or_delete_user_a(
    client, make_headers, pinned_today
):
    a = await make_headers("a@example.com")
    b = await make_headers("b@example.com")
    created = await create(client, a)
    path = f"{URL}/{created['id']}"

    assert (await client.get(path, headers=b)).status_code == 404
    assert (
        await client.patch(path, json={"name": "hacked"}, headers=b)
    ).status_code == 404
    assert (await client.delete(path, headers=b)).status_code == 404
    assert (await client.get(URL, headers=b)).json() == []
    # A's subscription is untouched.
    assert (await client.get(path, headers=a)).json() == created


async def test_client_cannot_set_owner_or_id(client, make_headers, pinned_today):
    a = await make_headers("a@example.com")
    b = await make_headers("b@example.com")
    created = await create(client, a, owner_id=999, id=12345)
    assert created["id"] != 12345
    assert len((await client.get(URL, headers=a)).json()) == 1
    assert (await client.get(URL, headers=b)).json() == []

    resp = await client.patch(
        f"{URL}/{created['id']}", json={"owner_id": 1, "name": "ok"}, headers=a
    )
    assert resp.status_code == 200
    assert (await client.get(URL, headers=b)).json() == []


async def test_free_plan_has_no_subscription_limit(client, make_headers, pinned_today):
    headers = await make_headers("a@example.com")
    for i in range(8):
        await create(client, headers, name=f"S{i}")
    assert len((await client.get(URL, headers=headers)).json()) == 8


async def test_stats_summary_reflects_created_subscriptions(
    client, make_headers, pinned_today
):
    headers = await make_headers("a@example.com")
    await create(client, headers, name="M", amount="9.99")
    await create(client, headers, name="Y", amount="120.00", billing_cycle="yearly")
    await create(client, headers, name="Off", amount="50.00", is_active=False)

    stats = (await client.get("/api/stats/summary", headers=headers)).json()
    assert stats["monthly_total"] == "19.99"
    assert stats["yearly_total"] == "239.88"
