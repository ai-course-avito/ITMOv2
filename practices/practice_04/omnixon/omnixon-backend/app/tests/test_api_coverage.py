"""api coverage tests"""

import pytest

from shared import (
    MCP_CALCULATOR_URL,
    as_token,
    drop_agent,
    history_of,
    make_agent,
    make_token,
    make_user,
)


@pytest.mark.asyncio
@pytest.mark.order(15)
async def test_agent_with_unknown_model_returns_404(client):
    res = await client.post(
        "/api/v1/admin/agents",
        json={"name": "test", "prompt": "x", "model_id": 999999999},
    )
    assert res.status_code == 404

    res = await client.post(
        "/api/v1/admin/agents", json={"name": "test", "prompt": "x", "model_id": 0}
    )
    agent_id = res.json()["id"]
    try:
        res = await client.patch(
            f"/api/v1/admin/agents/{agent_id}", json={"model_id": 999999999}
        )
        assert res.status_code == 404
        # nothing was changed
        assert (await client.get(f"/api/v1/admin/agents/{agent_id}")).json()[
            "model_id"
        ] == 0
    finally:
        await client.delete(f"/api/v1/admin/agents/{agent_id}")


@pytest.mark.asyncio
@pytest.mark.order(15)
async def test_a_regular_token_is_limited_and_its_users_are_its_agents(client):
    agent = await make_agent(client)
    token = await make_token(client, agent["id"], "regular")
    user_id = "isolation_test_user"
    try:
        async with as_token(token["token"]) as other:
            # no admin API
            for path in (
                "/api/v1/admin/agents",
                "/api/v1/admin/tokens",
                "/api/v1/admin/memories?user_id=x",
            ):
                assert (await other.get(path)).status_code == 403, path
            assert (
                await other.post(
                    "/api/v1/admin/models",
                    json={"name": "test", "request_json": {"model": "a/b"}},
                )
            ).status_code == 403

            # but the main API works, with its own agent and its own users
            res = await other.post(
                "/api/v1/request", json={"user_id": user_id, "request": "Say 'pong'."}
            )
            assert res.status_code == 200 and res.json()["response"]
            assert res.json()["user"]["agent_id"] == agent["id"]
            assert (await other.get(f"/api/v1/users/{user_id}")).status_code == 200

            # the owner (another agent) does not see that agent's user
            assert (await client.get(f"/api/v1/users/{user_id}")).status_code == 404

            assert (await other.delete(f"/api/v1/users/{user_id}")).status_code == 200
    finally:
        await client.delete(f"/api/v1/admin/tokens/{token['id']}")
        await drop_agent(client, agent)


@pytest.mark.asyncio
@pytest.mark.order(15)
async def test_update_user_to_existing_external_id_conflicts(client):
    first, second = "conflict_user_a", "conflict_user_b"
    await make_user(client, first)
    await make_user(client, second)
    try:
        res = await client.patch(f"/api/v1/users/{first}", json={"external_id": second})
        assert res.status_code == 409
        assert (await client.get(f"/api/v1/users/{first}")).status_code == 200
    finally:
        await client.delete(f"/api/v1/users/{first}")
        await client.delete(f"/api/v1/users/{second}")


@pytest.mark.asyncio
@pytest.mark.order(15)
async def test_history_is_limited_by_the_default_message_limit(client):
    agent = (await client.get("/api/v1/agents/self")).json()
    assert "message_limit" not in agent["config"]  # the env default (10) applies
    user_id = "chat_limit_user"
    try:
        for i in range(7):
            res = await client.post(
                "/api/v1/request",
                json={
                    "user_id": user_id,
                    "request": f"msg {i}: say ok",
                    "use_memo": False,
                },
            )
            assert res.status_code == 200

        history = await history_of(client, user_id)
        assert len(history) == 10  # 14 stored, the latest 10 returned, oldest first
        assert history[0]["content"]["content"] == "msg 2: say ok"
        assert history[-2]["content"]["content"] == "msg 6: say ok"
        assert [m["content"]["type"] for m in history] == ["user", "assistant"] * 5
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(15)
async def test_message_limit_of_an_agent(client):
    agent_id = (await client.get("/api/v1/agents/self")).json()["id"]
    user_id = "message_limit_user"
    res = await client.patch(
        f"/api/v1/admin/agents/{agent_id}", json={"config": {"message_limit": 2}}
    )
    assert res.status_code == 200
    try:
        for text in ("Say 'one'.", "Say 'two'."):
            await client.post(
                "/api/v1/request",
                json={"user_id": user_id, "request": text, "use_memo": False},
            )
        # 4 messages are stored, only the latest 2 are used (and returned)
        history = await history_of(client, user_id)
        assert len(history) == 2 and history[0]["content"]["content"] == "Say 'two'."

        # 0: no history at all
        await client.patch(
            f"/api/v1/admin/agents/{agent_id}", json={"config": {"message_limit": 0}}
        )
        assert await history_of(client, user_id) == []

        # removing the override brings back the default (10)
        await client.patch(
            f"/api/v1/admin/agents/{agent_id}", json={"config": {"message_limit": None}}
        )
        assert len(await history_of(client, user_id)) == 4
    finally:
        await client.patch(
            f"/api/v1/admin/agents/{agent_id}", json={"config": {"message_limit": None}}
        )
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(15)
async def test_model_keeps_openrouter_options(client):
    options = {
        "model": "openai/gpt-6-luna",
        "provider": {"order": ["openai"], "allow_fallbacks": False},
        "reasoning": {"effort": "low"},
    }
    res = await client.post(
        "/api/v1/admin/models", json={"name": "test", "request_json": options}
    )
    assert res.status_code == 201
    model_id = res.json()["id"]
    try:
        assert (await client.get(f"/api/v1/admin/models/{model_id}")).json()[
            "request_json"
        ] == options

        res = await client.patch(
            f"/api/v1/admin/models/{model_id}", json={"request_json": {}}
        )
        assert res.status_code == 422
        res = await client.patch(
            "/api/v1/admin/models/999999999", json={"request_json": options}
        )
        assert res.status_code == 404
    finally:
        await client.delete(f"/api/v1/admin/models/{model_id}")


@pytest.mark.asyncio
@pytest.mark.order(15)
async def test_mcp_server_update_validation_and_not_found(client):
    res = await client.patch(
        "/api/v1/admin/mcp-servers/999999999",
        json={"config": {"url": MCP_CALCULATOR_URL}},
    )
    assert res.status_code == 404

    res = await client.post(
        "/api/v1/admin/mcp-servers",
        json={"name": "test", "config": {"url": MCP_CALCULATOR_URL}},
    )
    mcp_server_id = res.json()["id"]
    try:
        res = await client.patch(
            f"/api/v1/admin/mcp-servers/{mcp_server_id}",
            json={"config": {"transport": "sse"}},
        )
        assert res.status_code == 422
    finally:
        await client.delete(f"/api/v1/admin/mcp-servers/{mcp_server_id}")


@pytest.mark.asyncio
@pytest.mark.order(15)
async def test_agent_mcp_association_errors(client):
    res = await client.post(
        "/api/v1/admin/agents", json={"name": "test", "prompt": "x", "model_id": 0}
    )
    agent_id = res.json()["id"]
    res = await client.post(
        "/api/v1/admin/mcp-servers",
        json={"name": "test", "config": {"url": MCP_CALCULATOR_URL}},
    )
    mcp_server_id = res.json()["id"]
    try:
        assert (
            await client.post(
                f"/api/v1/admin/agents/999999999/mcp-servers/{mcp_server_id}"
            )
        ).status_code == 404
        assert (
            await client.post(f"/api/v1/admin/agents/{agent_id}/mcp-servers/999999999")
        ).status_code == 404
        assert (
            await client.get("/api/v1/admin/agents/999999999/mcp-servers")
        ).status_code == 404

        # attaching twice is harmless; deleting the server detaches it
        for _ in range(2):
            res = await client.post(
                f"/api/v1/admin/agents/{agent_id}/mcp-servers/{mcp_server_id}"
            )
            assert res.status_code == 201 and len(res.json()) == 1
        await client.delete(f"/api/v1/admin/mcp-servers/{mcp_server_id}")
        res = await client.get(f"/api/v1/admin/agents/{agent_id}/mcp-servers")
        assert res.json() == []
    finally:
        await client.delete(f"/api/v1/admin/agents/{agent_id}")
        await client.delete(f"/api/v1/admin/mcp-servers/{mcp_server_id}")


@pytest.mark.asyncio
@pytest.mark.order(15)
async def test_docs_do_not_require_a_token(no_auth_client):
    assert (await no_auth_client.get("/docs")).status_code == 200
    assert (await no_auth_client.get("/openapi.json")).status_code == 200
