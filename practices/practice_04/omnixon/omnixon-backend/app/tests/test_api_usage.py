"""api usage tests"""

import asyncio

import pytest

from shared import (
    as_token,
    drop_agent,
    make_agent,
    make_token,
    role_clients,
    spent,
)


USAGE_KEYS = {
    "day",
    "token_id",
    "token_name",
    "model",
    "requests",
    "errors",
    "input_tokens",
    "output_tokens",
    "cost",
    "duration_ms_sum",
}


@pytest.mark.asyncio
@pytest.mark.order(25)
async def test_a_request_is_written_on_its_token_and_the_numbers_show_in_the_statistics(
    client,
):
    async with role_clients(client) as x:
        regular, user = x.clients["regular"], x.clients["user"]
        token_id = x.tokens["regular"]["id"]
        assert (
            spent((await user.get("/api/v1/admin/usage")).json(), token_id).requests
            == 0
        )

        marker = "zebra-marker-7431"
        res = await regular.post(
            "/api/v1/request",
            json={"request": f"Say pong. ({marker})", "user_id": "usage_user"},
        )
        assert res.status_code == 200

        rows = (await user.get("/api/v1/admin/usage")).json()
        row = next(r for r in rows if r["token_id"] == token_id)
        assert set(row) == USAGE_KEYS
        assert (
            row["token_name"] == "regular token"
            and row["requests"] >= 1
            and row["errors"] == 0
        )
        assert row["input_tokens"] > 0 and row["output_tokens"] > 0
        assert row["cost"] >= 0 and row["duration_ms_sum"] > 0 and row["model"]
        # only what happened, never what was said
        text = (await user.get("/api/v1/admin/usage")).text + (
            await client.get("/api/v1/admin/usage")
        ).text
        assert marker not in text and "pong" not in text.lower()
        # one filter by token, one by agent
        assert [
            r["token_id"]
            for r in (
                await user.get("/api/v1/admin/usage", params={"token_id": token_id})
            ).json()
        ] == [token_id]
        assert (
            await user.get(
                "/api/v1/admin/usage", params={"token_id": x.tokens["owner"]["id"]}
            )
        ).json() == []

        # a stream counts too
        async with regular.stream(
            "POST",
            "/api/v1/request-stream",
            json={"request": "Say pong.", "user_id": "usage_user"},
        ) as stream:
            async for _ in stream.aiter_lines():
                pass
        after = spent((await user.get("/api/v1/admin/usage")).json(), token_id)
        # the stream counted too (and so does the model call of auto_memory that follows a saved exchange)
        assert after.requests >= 2 and after.input > row["input_tokens"]
        await regular.delete("/api/v1/users/usage_user")


@pytest.mark.asyncio
@pytest.mark.order(25)
async def test_usage_can_be_read_by_user_tokens_of_that_agent_only(client):
    async with role_clients(client) as x:
        await x.clients["regular"].post(
            "/api/v1/request", json={"request": "Say pong.", "user_id": "usage_scope"}
        )
        try:
            assert (
                await x.clients["regular"].get("/api/v1/admin/usage")
            ).status_code == 403
            seen_by_user = (await x.clients["user"].get("/api/v1/admin/usage")).json()
            assert {r["token_id"] for r in seen_by_user} == {x.tokens["regular"]["id"]}
            # a user of another agent sees nothing of it
            other = await make_token(client, x.b["id"], "user", name="B user")
            try:
                async with as_token(other["token"]) as on_b:
                    assert (await on_b.get("/api/v1/admin/usage")).json() == []
                    assert (
                        await on_b.get(
                            "/api/v1/admin/usage", params={"agent_id": x.a["id"]}
                        )
                    ).status_code == 403
                    assert (
                        await on_b.get(
                            "/api/v1/admin/usage",
                            params={"token_id": x.tokens["regular"]["id"]},
                        )
                    ).json() == []
            finally:
                await client.delete(f"/api/v1/admin/tokens/{other['id']}")
            # an admin sees it under the agent or under all
            assert x.tokens["regular"]["id"] in {
                r["token_id"]
                for r in (await x.clients["admin"].get("/api/v1/admin/usage")).json()
            }
            by_agent = (
                await client.get("/api/v1/admin/usage", params={"agent_id": x.a["id"]})
            ).json()
            assert x.tokens["regular"]["id"] in {r["token_id"] for r in by_agent}
            assert (await client.get("/api/v1/admin/usage/monthly")).status_code == 200
        finally:
            await x.clients["regular"].delete("/api/v1/users/usage_scope")


@pytest.mark.asyncio
@pytest.mark.order(25)
async def test_a_failed_request_is_counted_with_nothing_spent(client):
    model = (
        await client.post(
            "/api/v1/admin/models",
            json={"name": "bad", "request_json": {"model": "no/such-model-xyz"}},
        )
    ).json()
    agent = await make_agent(client, model_id=model["id"])
    token = await make_token(client, agent["id"], "regular")
    try:
        async with as_token(token["token"]) as c:
            assert (
                await c.post(
                    "/api/v1/request", json={"request": "hi", "user_id": "fail_user"}
                )
            ).status_code == 502
        rows = (
            await client.get("/api/v1/admin/usage", params={"token_id": token["id"]})
        ).json()
        assert len(rows) == 1
        assert rows[0]["requests"] == 1 and rows[0]["errors"] == 1
        assert rows[0]["input_tokens"] == 0 and rows[0]["model"] == "no/such-model-xyz"
    finally:
        await client.delete(f"/api/v1/admin/tokens/{token['id']}")
        await drop_agent(client, agent)
        await client.delete(f"/api/v1/admin/models/{model['id']}")


@pytest.mark.asyncio
@pytest.mark.order(25)
async def test_acting_as_another_agent_is_paid_by_the_token_of_the_admin(client):
    async with role_clients(client) as x:
        owner = (await client.get("/api/v1/tokens/self")).json()
        # earlier tests leave background work on the owner token (auto_memory runs after the answer): wait until the count stops moving
        before, steady = None, 0
        for _ in range(60):
            now = spent((await client.get("/api/v1/admin/usage")).json(), owner["id"]).requests
            steady = steady + 1 if now == before else 0
            if steady >= 6:  # three seconds without a change
                break
            before = now
            await asyncio.sleep(0.5)
        async with as_token(x.tokens["admin"]["token"], act_as=x.b["id"]) as admin_on_b:
            res = await admin_on_b.post(
                "/api/v1/request",
                json={"request": "Say pong.", "user_id": "paid_by_admin"},
            )
            assert (
                res.status_code == 200 and res.json()["user"]["agent_id"] == x.b["id"]
            )  # it was agent B that answered
            await admin_on_b.delete("/api/v1/users/paid_by_admin")
        rows = (await client.get("/api/v1/admin/usage")).json()
        assert (
            spent(rows, x.tokens["admin"]["id"]).requests == 1
        )  # on the admin's own token ...
        assert spent(rows, owner["id"]).requests == before
        row = next(r for r in rows if r["token_id"] == x.tokens["admin"]["id"])
        assert row["token_name"] == "admin token"


@pytest.mark.asyncio
@pytest.mark.order(25)
async def test_a_deleted_tokens_usage_stays_under_its_old_name(client):
    agent = await make_agent(client)
    token = await make_token(client, agent["id"], "regular", name="short lived")
    try:
        async with as_token(token["token"]) as c:
            await c.post(
                "/api/v1/request",
                json={"request": "Say pong.", "user_id": "short_lived_user"},
            )
            await c.delete("/api/v1/users/short_lived_user")
        await client.delete(f"/api/v1/admin/tokens/{token['id']}")
        rows = (await client.get("/api/v1/admin/usage")).json()
        gone = [r for r in rows if r["token_name"] == "short lived"]
        assert (
            gone
            and all(r["token_id"] is None for r in gone)
            and sum(r["requests"] for r in gone) >= 1
        )
    finally:
        await client.delete(f"/api/v1/admin/tokens/{token['id']}")
        await drop_agent(client, agent)
