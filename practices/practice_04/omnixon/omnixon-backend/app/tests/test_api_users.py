"""api users tests"""

import pytest

from shared import (
    agent_on,
    as_token,
    drop_agent,
    fake_model,
    make_agent,
    make_token,
)


@pytest.mark.asyncio
@pytest.mark.order(5)
async def test_get_user_not_found(client):
    res = await client.get("/api/v1/users/nonexistent_user_xyz_000")
    assert res.status_code == 404


@pytest.mark.asyncio
@pytest.mark.order(5)
async def test_users_are_found_by_the_start_of_their_id(client):
    mine = ["srch_alpha_1", "srch_alpha_2", "srch_beta", "srchXalpha"]
    for external_id in mine:
        assert (
            await client.post("/api/v1/users", json={"external_id": external_id})
        ).status_code == 201
    agent = await make_agent(client)
    token = await make_token(client, agent["id"], "regular")
    try:
        async with as_token(token["token"]) as other:
            await other.post("/api/v1/users", json={"external_id": "srch_alpha_other"})

            res = await client.get("/api/v1/users", params={"query": "srch_al"})
            assert res.status_code == 200
            # sorted; `_` is not a wildcard (srchXalpha is not found); another agent's user is not seen
            assert [u["external_id"] for u in res.json()] == [
                "srch_alpha_1",
                "srch_alpha_2",
            ]

            res = await client.get(
                "/api/v1/users", params={"query": "srch_", "limit": 2}
            )
            assert [u["external_id"] for u in res.json()] == [
                "srch_alpha_1",
                "srch_alpha_2",
            ]  # limited

            assert (
                await client.get("/api/v1/users", params={"query": "srch%"})
            ).json() == []  # % is literal
            assert (
                await client.get("/api/v1/users", params={"query": "zzz_nothing"})
            ).json() == []

            # the other agent sees only its own
            res = await other.get("/api/v1/users", params={"query": "srch_"})
            assert [u["external_id"] for u in res.json()] == ["srch_alpha_other"]
            await other.delete("/api/v1/users/srch_alpha_other")

        # too short a query is refused: there is no way to list every user
        for query in ("", "ab"):
            assert (
                await client.get("/api/v1/users", params={"query": query})
            ).status_code == 422
        assert (
            await client.get("/api/v1/users", params={"query": "abc", "limit": 0})
        ).status_code == 422
        assert (
            await client.get("/api/v1/users", params={"query": "abc", "limit": 51})
        ).status_code == 422
    finally:
        for external_id in mine:
            await client.delete(f"/api/v1/users/{external_id}")
        await client.delete(f"/api/v1/admin/tokens/{token['id']}")
        await drop_agent(client, agent)


@pytest.mark.asyncio
@pytest.mark.order(5)
async def test_user_full_lifecycle(client):
    external_id = "test_lifecycle_user_abc"

    res = await client.post("/api/v1/users", json={"external_id": external_id})
    assert res.status_code == 201
    user = res.json()
    assert user["external_id"] == external_id

    res = await client.post("/api/v1/users", json={"external_id": external_id})
    assert res.status_code == 409

    res = await client.get(f"/api/v1/users/{external_id}")
    assert res.status_code == 200
    assert res.json()["external_id"] == external_id

    new_external_id = "test_lifecycle_user_abc_renamed"
    res = await client.patch(
        f"/api/v1/users/{external_id}",
        json={"external_id": new_external_id},
    )
    assert res.status_code == 200
    updated = res.json()
    assert updated["external_id"] == new_external_id
    current_id = updated["external_id"]

    res = await client.delete(f"/api/v1/users/{current_id}")
    assert res.status_code == 200

    res = await client.get(f"/api/v1/users/{current_id}")
    assert res.status_code == 404


@pytest.mark.asyncio
@pytest.mark.order(5)
async def test_patch_user_not_found(client):
    res = await client.patch(
        "/api/v1/users/nonexistent_user_xyz_000",
        json={"external_id": "nonexistent_user_xyz_000"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
@pytest.mark.order(5)
async def test_delete_user_not_found(client):
    res = await client.delete("/api/v1/users/nonexistent_user_xyz_000")
    assert res.status_code == 404


@pytest.mark.asyncio
@pytest.mark.order(6)
async def test_history_not_found_for_missing_user(client):
    res = await client.get("/api/v1/users/nonexistent_user_xyz_000/history")
    assert res.status_code == 404


@pytest.mark.asyncio
@pytest.mark.order(6)
async def test_delete_history_not_found_for_missing_user(client):
    res = await client.delete("/api/v1/users/nonexistent_user_xyz_000/history")
    assert res.status_code == 404


@pytest.mark.asyncio
@pytest.mark.order(6)
async def test_history_lifecycle(client):
    user_id = "history_test_user_xyz"

    res = await client.post("/api/v1/users", json={"external_id": user_id})
    assert res.status_code == 201

    res = await client.post(
        "/api/v1/request",
        json={"user_id": user_id, "request": "Say hello."},
    )
    assert res.status_code == 200

    res = await client.get(f"/api/v1/users/{user_id}/history")
    assert res.status_code == 200
    history = res.json()
    assert isinstance(history, list)
    assert len(history) > 0

    res = await client.delete(f"/api/v1/users/{user_id}/history")
    assert res.status_code == 204

    res = await client.get(f"/api/v1/users/{user_id}/history")
    assert res.status_code == 200
    assert res.json() == []

    await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(26)
async def test_the_recent_users_of_an_agent_are_those_with_kept_messages_latest_first(
    client,
):
    model = await fake_model(client, "fake/pong-recent")
    async with agent_on(client, model) as (agent, c):
        other_agent = await make_agent(
            client, model_id=model["id"], config={"tools": [], "auto_memory": False}
        )
        other_token = await make_token(client, other_agent["id"], "regular")
        try:
            assert (
                await c.get("/api/v1/users/recent")
            ).json() == []  # nobody has written yet
            for user in ("recent_a", "recent_b", "recent_c"):
                assert (
                    await c.post(
                        "/api/v1/request",
                        json={"request": "Say pong.", "user_id": user},
                    )
                ).status_code == 200
            assert (
                await c.post(
                    "/api/v1/request",
                    json={"request": "Say pong.", "user_id": "recent_a"},
                )
            ).status_code == 200  # a writes again
            await c.post(
                "/api/v1/users", json={"external_id": "recent_silent"}
            )  # exists, has written nothing
            async with as_token(other_token["token"]) as other:
                await other.post(
                    "/api/v1/request",
                    json={"request": "Say pong.", "user_id": "recent_other"},
                )

                res = await c.get("/api/v1/users/recent")
                assert res.status_code == 200
                rows = res.json()
                assert (
                    [u["external_id"] for u in rows]
                    == ["recent_a", "recent_c", "recent_b"]
                )  # the latest writer first; the silent one and the other agent's are not there
                assert rows[0]["messages"] == 4 and rows[1]["messages"] == 2
                assert all(
                    u["agent_id"] == agent["id"] and u["last_active"] for u in rows
                )
                assert [
                    u["external_id"]
                    for u in (await other.get("/api/v1/users/recent")).json()
                ] == ["recent_other"]
                await other.delete("/api/v1/users/recent_other")

            assert [
                u["external_id"]
                for u in (
                    await c.get("/api/v1/users/recent", params={"limit": 2})
                ).json()
            ] == ["recent_a", "recent_c"]
            for bad in (0, 101):
                assert (
                    await c.get("/api/v1/users/recent", params={"limit": bad})
                ).status_code == 422

            # the history cleared or the user deleted: nothing kept, not recent any more
            await c.delete("/api/v1/users/recent_c/history")
            await c.delete("/api/v1/users/recent_b")
            assert [
                u["external_id"] for u in (await c.get("/api/v1/users/recent")).json()
            ] == ["recent_a"]
            # it is not mistaken for a user called "recent"
            assert (await c.get("/api/v1/users/recent")).status_code == 200
            for user in ("recent_a", "recent_silent", "recent_c"):
                await c.delete(f"/api/v1/users/{user}")
        finally:
            await client.delete(f"/api/v1/admin/tokens/{other_token['id']}")
            await drop_agent(client, other_agent)
