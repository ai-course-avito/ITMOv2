"""api model connection tests"""

import json
import pytest

from shared import (
    FAKE_LLM_URL,
    agent_on,
    drop_agent,
    fake_log,
    fake_model,
    make_agent,
)


@pytest.mark.asyncio
@pytest.mark.order(26)
async def test_a_model_has_a_connection_that_defaults_to_openrouter_and_the_system_key(
    client,
):
    res = await client.post(
        "/api/v1/admin/models",
        json={
            "name": "plain",
            "request_json": {"model": "openai/gpt-6-luna"},
        },
    )
    assert res.status_code == 201
    model = res.json()
    try:
        assert model["base_url"] == "https://openrouter.ai/api/v1"
        assert model["use_proxy"] is True
        assert model["has_api_token"] is False
        assert "api_token" not in model
    finally:
        await client.delete(f"/api/v1/admin/models/{model['id']}")


@pytest.mark.asyncio
@pytest.mark.order(26)
async def test_the_token_of_a_model_is_never_returned_and_can_be_changed_and_cleared(
    client,
):
    secret = "sk-test-secret-for-a-model-9f8e7d"
    model = await fake_model(
        client, "fake/pong-token-lifecycle", use_proxy=False, api_token=secret
    )
    mid = model["id"]
    try:
        assert (
            model["has_api_token"] is True
            and model["use_proxy"] is False
            and model["base_url"] == FAKE_LLM_URL
        )
        for res in (
            await client.get(f"/api/v1/admin/models/{mid}"),
            await client.get("/api/v1/admin/models"),
        ):
            assert secret not in res.text
        # the fields not given stay
        res = await client.patch(
            f"/api/v1/admin/models/{mid}", json={"name": "renamed"}
        )
        got = res.json()
        assert (got["base_url"], got["use_proxy"], got["has_api_token"]) == (
            FAKE_LLM_URL,
            False,
            True,
        )
        # a new connection
        res = await client.patch(
            f"/api/v1/admin/models/{mid}",
            json={"use_proxy": True, "api_token": "sk-other-456"},
        )
        got = res.json()
        assert (
            got["use_proxy"] is True
            and got["has_api_token"] is True
            and "sk-other-456" not in res.text
        )
        # "" clears the token, an empty base_url (or the OpenRouter one) goes back to the default
        res = await client.patch(
            f"/api/v1/admin/models/{mid}", json={"api_token": "", "base_url": ""}
        )
        got = res.json()
        assert (
            got["has_api_token"] is False
            and got["base_url"] == "https://openrouter.ai/api/v1"
        )
        res = await client.patch(
            f"/api/v1/admin/models/{mid}", json={"base_url": FAKE_LLM_URL}
        )
        assert res.json()["base_url"] == FAKE_LLM_URL
        res = await client.patch(
            f"/api/v1/admin/models/{mid}",
            json={"base_url": "https://openrouter.ai/api/v1"},
        )
        assert res.json()["base_url"] == "https://openrouter.ai/api/v1"
    finally:
        await client.delete(f"/api/v1/admin/models/{mid}")


@pytest.mark.asyncio
@pytest.mark.order(26)
@pytest.mark.parametrize(
    "bad", ["not a url", "ftp://host/v1", "http://", "javascript:alert(1)"]
)
async def test_a_model_refuses_a_base_url_that_is_not_http(client, bad):
    res = await client.post(
        "/api/v1/admin/models",
        json={"name": "bad url", "request_json": {"model": "x/y"}, "base_url": bad},
    )
    assert res.status_code == 422
    res = await client.patch("/api/v1/admin/models/0", json={"base_url": bad})
    assert res.status_code == 422


@pytest.mark.asyncio
@pytest.mark.order(26)
async def test_the_connection_cannot_hide_inside_the_request_body(client):
    for key in ("base_url", "api_key_env", "api_token", "use_proxy"):
        res = await client.post(
            "/api/v1/admin/models",
            json={"name": "sneaky", "request_json": {"model": "x/y", key: "z"}},
        )
        assert res.status_code == 422, key


@pytest.mark.asyncio
@pytest.mark.order(26)
async def test_a_model_with_its_own_base_url_is_called_there_with_its_own_token(client):
    secret = "sk-own-key-for-the-fake-provider"
    own = await fake_model(client, "fake/pong-own-key", api_token=secret)
    system = await fake_model(client, "fake/pong-system-key")
    async with (
        agent_on(client, own) as (_, c_own),
        agent_on(client, system) as (_, c_sys),
    ):
        res = await c_own.post(
            "/api/v1/request", json={"request": "Say pong.", "user_id": "own_key_user"}
        )
        assert res.status_code == 200, res.text
        assert "pong" in res.json()["response"].lower()
        res = await c_sys.post(
            "/api/v1/request", json={"request": "Say pong.", "user_id": "sys_key_user"}
        )
        assert res.status_code == 200, res.text
        log_own, log_sys = (
            fake_log("fake/pong-own-key"),
            fake_log("fake/pong-system-key"),
        )
        assert log_own and log_own[0]["authorization"] == f"Bearer {secret}"
        assert log_own[0]["path"].endswith("/chat/completions")
        assert (
            log_sys and log_sys[0]["authorization"] != f"Bearer {secret}"
        )  # the system key (whatever it is) was used
        for log in (log_own, log_sys):
            assert not {"base_url", "api_token", "use_proxy"} & set(
                log[0]["keys"]
            )  # the connection is not sent to the provider as a parameter
        await c_own.delete("/api/v1/users/own_key_user")
        await c_sys.delete("/api/v1/users/sys_key_user")


@pytest.mark.asyncio
@pytest.mark.order(26)
@pytest.mark.parametrize("use_proxy", [True, False])
async def test_a_model_is_reached_with_and_without_the_proxy(client, use_proxy):
    model = await fake_model(
        client, f"fake/pong-proxy-{use_proxy}", use_proxy=use_proxy
    )
    async with agent_on(client, model) as (_, c):
        res = await c.post(
            "/api/v1/request", json={"request": "Say pong.", "user_id": "proxy_user"}
        )
        assert res.status_code == 200, res.text
        async with c.stream(
            "POST",
            "/api/v1/request-stream",
            json={"request": "Say pong.", "user_id": "proxy_user"},
        ) as stream:
            body = (await stream.aread()).decode()
        assert "event: done" in body and "event: error" not in body
        assert [e["stream"] for e in fake_log(model["name"])] == [False, True]
        await c.delete("/api/v1/users/proxy_user")


@pytest.mark.asyncio
@pytest.mark.order(26)
async def test_the_agent_versions_know_the_connection_but_never_the_token(client):
    model = await fake_model(
        client, "fake/pong-versioned", api_token="sk-versioned-secret-123"
    )
    agent = await make_agent(client, model_id=model["id"])
    try:
        versions = (
            await client.get(f"/api/v1/admin/agents/{agent['id']}/versions")
        ).json()
        assert "sk-versioned-secret-123" not in json.dumps(versions)
        before = len(versions)
        res = await client.patch(
            f"/api/v1/admin/models/{model['id']}", json={"use_proxy": False}
        )
        assert res.status_code == 200
        versions = (
            await client.get(f"/api/v1/admin/agents/{agent['id']}/versions")
        ).json()
        assert (
            len(versions) == before + 1
        )  # a change of the connection changes the behaviour of the agent
        text = json.dumps(versions)
        assert "sk-versioned-secret-123" not in text and "model_connection" in text
        # changing only the token is a change too, and only its fingerprint shows
        await client.patch(
            f"/api/v1/admin/models/{model['id']}",
            json={"api_token": "sk-versioned-secret-456"},
        )
        versions = (
            await client.get(f"/api/v1/admin/agents/{agent['id']}/versions")
        ).json()
        assert len(versions) == before + 2
        assert "sk-versioned-secret-456" not in json.dumps(versions)
    finally:
        await drop_agent(client, agent)
        await client.delete(f"/api/v1/admin/models/{model['id']}")
