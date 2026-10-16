from sqlalchemy import select

from app.models import Subscription

URL = "/api/subscriptions"
BASE = {
    "name": "x",
    "amount": "10.00",
    "billing_cycle": "monthly",
    "start_date": "2026-01-01",
}
# pinned_today is 2026-10-16


async def add(client, headers, **overrides):
    body = {**BASE, **overrides}
    resp = await client.post(URL, json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def names(client, headers, **params):
    resp = await client.get(URL, params=params, headers=headers)
    assert resp.status_code == 200, resp.text
    return [item["name"] for item in resp.json()]


# --- search -------------------------------------------------------------


async def test_search_is_case_insensitive_and_trims(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    await add(client, h, name="Netflix")
    await add(client, h, name="Spotify")
    assert await names(client, h, q="  NET ") == ["Netflix"]


async def test_search_cyrillic(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    await add(client, h, name="Яндекс Плюс")
    await add(client, h, name="Netflix")
    assert await names(client, h, q="яндекс") == ["Яндекс Плюс"]
    assert await names(client, h, q="ПЛЮС") == ["Яндекс Плюс"]


async def test_search_looks_in_note(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    await add(client, h, name="One", note="family plan")
    await add(client, h, name="Two")
    assert await names(client, h, q="family") == ["One"]


async def test_search_wildcards_are_literal(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    await add(client, h, name="50% off")
    await add(client, h, name="plain")
    await add(client, h, name="a_b")
    assert await names(client, h, q="%") == ["50% off"]
    assert await names(client, h, q="_") == ["a_b"]


async def test_blank_search_is_ignored_and_too_long_is_422(
    client, make_headers, pinned_today
):
    h = await make_headers("a@example.com")
    await add(client, h, name="A")
    assert await names(client, h, q="   ") == ["A"]
    resp = await client.get(URL, params={"q": "x" * 101}, headers=h)
    assert resp.status_code == 422


async def test_search_never_crosses_users(client, make_headers, pinned_today):
    a = await make_headers("a@example.com")
    b = await make_headers("b@example.com")
    await add(client, b, name="Secret thing")
    assert await names(client, a, q="secret") == []


# --- billing_cycle filter -------------------------------------------------


async def test_billing_cycle_filter(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    await add(client, h, name="m")
    await add(client, h, name="y", billing_cycle="yearly")
    assert await names(client, h, billing_cycle="yearly") == ["y"]
    resp = await client.get(URL, params={"billing_cycle": "daily"}, headers=h)
    assert resp.status_code == 422


# --- sorting ----------------------------------------------------------------


async def test_default_order_is_by_id(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    for name in ("b", "a", "c"):
        await add(client, h, name=name)
    assert await names(client, h) == ["b", "a", "c"]


async def test_sort_by_name_is_case_insensitive_with_desc(
    client, make_headers, pinned_today
):
    h = await make_headers("a@example.com")
    for name in ("banana", "Apple", "cherry"):
        await add(client, h, name=name)
    assert await names(client, h, sort="name") == ["Apple", "banana", "cherry"]
    assert await names(client, h, sort="name", order="desc") == [
        "cherry",
        "banana",
        "Apple",
    ]


async def test_sort_by_monthly_cost_descending(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    await add(
        client, h, name="yearly-120", amount="120.00", billing_cycle="yearly"
    )  # 10.00
    await add(
        client, h, name="weekly-6", amount="6.00", billing_cycle="weekly"
    )  # 26.00
    await add(client, h, name="monthly-15", amount="15.00")  # 15.00
    assert await names(client, h, sort="monthly_cost", order="desc") == [
        "weekly-6",
        "monthly-15",
        "yearly-120",
    ]


async def test_sort_by_amount_uses_billed_amount(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    await add(client, h, name="yearly-120", amount="120.00", billing_cycle="yearly")
    await add(client, h, name="monthly-15", amount="15.00")
    assert await names(client, h, sort="amount") == ["monthly-15", "yearly-120"]


async def test_ties_break_by_id_ascending_in_both_orders(
    client, make_headers, pinned_today
):
    h = await make_headers("a@example.com")
    for name in ("first", "second", "third"):
        await add(client, h, name=name, amount="10.00")
    assert await names(client, h, sort="amount") == ["first", "second", "third"]
    assert await names(client, h, sort="amount", order="desc") == [
        "first",
        "second",
        "third",
    ]


async def test_sort_by_charge_date_puts_inactive_last_in_both_orders(
    client, make_headers, pinned_today
):
    h = await make_headers("a@example.com")
    await add(client, h, name="late", next_billing_date="2026-12-01")
    await add(client, h, name="paused", next_billing_date="2026-10-17", is_active=False)
    await add(client, h, name="soon", next_billing_date="2026-10-18")
    assert await names(client, h, sort="charge_date") == ["soon", "late", "paused"]
    assert await names(client, h, sort="charge_date", order="desc") == [
        "late",
        "soon",
        "paused",
    ]


async def test_paging_applies_after_sorting(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    for name in ("d", "b", "a", "c"):
        await add(client, h, name=name)
    assert await names(client, h, sort="name", limit=2, offset=2) == ["c", "d"]


async def test_unknown_sort_or_order_is_422(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    assert (
        await client.get(URL, params={"sort": "nope"}, headers=h)
    ).status_code == 422
    assert (await client.get(URL, params={"order": "up"}, headers=h)).status_code == 422


# --- computed fields ----------------------------------------------------------


async def test_stale_date_is_rolled_forward_without_writing(
    client, make_headers, session, pinned_today
):
    h = await make_headers("a@example.com")
    await add(client, h, name="old", next_billing_date="2026-09-06")
    resp = await client.get(URL, headers=h)
    item = resp.json()[0]
    assert item["charge_date"] == "2026-11-06"
    assert item["days_until"] == 21
    assert item["next_billing_date"] == "2026-09-06"

    session.expire_all()
    stored = (
        (await session.execute(select(Subscription.next_billing_date))).scalars().all()
    )
    assert [d.isoformat() for d in stored] == ["2026-09-06"]


async def test_inactive_item_has_null_charge_fields_but_monthly_cost(
    client, make_headers, pinned_today
):
    h = await make_headers("a@example.com")
    await add(
        client, h, name="off", amount="120.00", billing_cycle="yearly", is_active=False
    )
    item = (await client.get(URL, headers=h)).json()[0]
    assert item["charge_date"] is None and item["days_until"] is None
    assert item["monthly_cost"] == "10.00"


async def test_monthly_cost_value_and_charge_today(client, make_headers, pinned_today):
    h = await make_headers("a@example.com")
    await add(
        client,
        h,
        name="y",
        amount="120.00",
        billing_cycle="yearly",
        next_billing_date="2026-10-16",
    )
    item = (await client.get(URL, headers=h)).json()[0]
    assert item["monthly_cost"] == "10.00"
    assert item["days_until"] == 0


# --- backward compatibility ---------------------------------------------------


async def test_other_responses_have_no_computed_fields(
    client, make_headers, pinned_today
):
    h = await make_headers("a@example.com")
    created = await add(client, h)
    fetched = (await client.get(f"{URL}/{created['id']}", headers=h)).json()
    patched = (
        await client.patch(f"{URL}/{created['id']}", json={"note": "n"}, headers=h)
    ).json()
    for body in (created, fetched, patched):
        assert not {"monthly_cost", "charge_date", "days_until"} & body.keys()
