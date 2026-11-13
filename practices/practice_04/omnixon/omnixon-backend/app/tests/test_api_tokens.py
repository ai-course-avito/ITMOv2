"""api tokens tests"""

import pytest

from shared import (
    as_token,
    drop_agent,
    make_agent,
    make_token,
)


@pytest.mark.asyncio
@pytest.mark.order(3)
async def test_the_initial_token_is_an_owner(client):
    res = await client.get("/api/v1/tokens/self")
    assert res.status_code == 200
    me = res.json()
    assert (
        me["role"] == "owner" and me["is_initial"] is True and me["name"] == "initial"
    )
    assert me["agent_id"] > 0
    assert "token" not in me and "token_sha256" not in me  # a token is never read back


@pytest.mark.asyncio
@pytest.mark.order(3)
async def test_get_self_agent_is_the_agent_of_the_token(client):
    me = (await client.get("/api/v1/tokens/self")).json()
    agent = (await client.get("/api/v1/agents/self")).json()
    assert agent["id"] == me["agent_id"]


@pytest.mark.asyncio
@pytest.mark.order(3)
async def test_token_full_lifecycle(client):
    agent = await make_agent(client)
    try:
        res = await client.post(
            "/api/v1/admin/tokens",
            json={"name": "  my bot  ", "role": "regular", "agent_id": agent["id"]},
        )
        assert res.status_code == 201
        made = res.json()
        assert (
            made["name"] == "my bot"
            and made["role"] == "regular"
            and made["agent_id"] == agent["id"]
        )
        assert len(made["token"]) == 64  # the secret: shown here and nowhere else
        assert "token_sha256" not in made and made["is_initial"] is False

        # listed without the secret
        listed = (
            await client.get("/api/v1/admin/tokens", params={"agent_id": agent["id"]})
        ).json()
        assert [t["id"] for t in listed] == [made["id"]]
        assert "token" not in listed[0] and "token_sha256" not in listed[0]
        assert made["token"] not in (await client.get("/api/v1/admin/tokens")).text

        # it works as a Bearer token and says who it is
        async with as_token(made["token"]) as me:
            self_token = (await me.get("/api/v1/tokens/self")).json()
            assert self_token["id"] == made["id"] and self_token["role"] == "regular"
            assert (await me.get("/api/v1/agents/self")).json()["id"] == agent["id"]

        # renamed
        res = await client.patch(
            f"/api/v1/admin/tokens/{made['id']}", json={"name": "renamed"}
        )
        assert res.status_code == 200 and res.json()["name"] == "renamed"
        assert (
            await client.patch(
                f"/api/v1/admin/tokens/{made['id']}", json={"name": "  "}
            )
        ).status_code == 422

        # deleted: it stops working at once
        res = await client.delete(f"/api/v1/admin/tokens/{made['id']}")
        assert res.status_code == 200 and res.json()["id"] == made["id"]
        async with as_token(made["token"]) as me:
            assert (await me.get("/api/v1/tokens/self")).status_code == 403
        assert (
            await client.delete(f"/api/v1/admin/tokens/{made['id']}")
        ).status_code == 404
    finally:
        await drop_agent(client, agent)


@pytest.mark.asyncio
@pytest.mark.order(3)
async def test_a_token_needs_a_name_a_known_role_and_a_real_agent(client):
    agent = await make_agent(client)
    try:
        base = {"name": "t", "role": "user", "agent_id": agent["id"]}
        for bad in (
            {k: v for k, v in base.items() if k != "name"},
            {**base, "name": ""},
            {**base, "name": "   "},
            {**base, "name": "x" * 121},
            {k: v for k, v in base.items() if k != "role"},
            {**base, "role": "superuser"},
        ):
            assert (
                await client.post("/api/v1/admin/tokens", json=bad)
            ).status_code == 422, bad
        assert (
            await client.post(
                "/api/v1/admin/tokens", json={**base, "agent_id": 999999999}
            )
        ).status_code == 404
        assert (
            await client.get("/api/v1/admin/tokens", params={"agent_id": agent["id"]})
        ).json() == []  # none was made
        assert (
            await client.patch("/api/v1/admin/tokens/999999999", json={"name": "x"})
        ).status_code == 404
    finally:
        await drop_agent(client, agent)


@pytest.mark.asyncio
@pytest.mark.order(3)
async def test_a_token_without_an_agent_defaults_to_the_agent_of_the_caller(client):
    me = (await client.get("/api/v1/tokens/self")).json()
    made = (
        await client.post(
            "/api/v1/admin/tokens", json={"name": "default agent", "role": "regular"}
        )
    ).json()
    try:
        assert made["agent_id"] == me["agent_id"]
    finally:
        await client.delete(f"/api/v1/admin/tokens/{made['id']}")


@pytest.mark.asyncio
@pytest.mark.order(3)
async def test_the_token_in_use_and_the_initial_token_cannot_be_deleted(client):
    me = (await client.get("/api/v1/tokens/self")).json()
    second = (
        await client.post(
            "/api/v1/admin/tokens", json={"name": "second owner", "role": "owner"}
        )
    ).json()
    try:
        async with as_token(second["token"]) as owner2:
            assert (
                await owner2.delete(f"/api/v1/admin/tokens/{second['id']}")
            ).status_code == 409  # itself
            assert (
                await owner2.delete(f"/api/v1/admin/tokens/{me['id']}")
            ).status_code == 409  # the initial one
        assert (
            await client.delete(f"/api/v1/admin/tokens/{me['id']}")
        ).status_code == 409
        assert (await client.get("/api/v1/tokens/self")).status_code == 200
    finally:
        await client.delete(f"/api/v1/admin/tokens/{second['id']}")


@pytest.mark.asyncio
@pytest.mark.order(3)
async def test_an_agent_with_tokens_cannot_be_deleted(client):
    agent = await make_agent(client)
    token = await make_token(client, agent["id"], "regular")
    try:
        res = await client.delete(f"/api/v1/admin/agents/{agent['id']}")
        assert res.status_code == 409
        assert (
            await client.delete(f"/api/v1/admin/tokens/{token['id']}")
        ).status_code == 200
        assert (
            await client.delete(f"/api/v1/admin/agents/{agent['id']}")
        ).status_code == 200
    finally:
        await client.delete(f"/api/v1/admin/tokens/{token['id']}")
        await drop_agent(client, agent)
