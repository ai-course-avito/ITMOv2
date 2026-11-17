"""api regressions tests"""

import time
import pytest
import httpx
import asyncio

from shared import (
    CALC_ANSWER,
    CALC_QUESTION,
    MCP_CALCULATOR_URL,
    agent_on,
    fake_log,
    fake_model,
    collect_sse,
    digits_only,
    history_of,
    make_user,
)


@pytest.mark.asyncio
@pytest.mark.order(16)
async def test_rag_entries_of_another_agent_can_be_changed_and_deleted(client):
    res = await client.post(
        "/api/v1/admin/agents", json={"name": "test", "prompt": "x", "model_id": 0}
    )
    other = res.json()["id"]
    try:
        res = await client.post(
            f"/api/v1/admin/rag?agent_id={other}", json={"content": "alpha document"}
        )
        assert res.status_code == 201
        rag_id = res.json()["id"]
        url = f"/api/v1/admin/rag/{rag_id}?agent_id={other}"

        res = await client.patch(url, json={"content": "beta document"})
        assert res.status_code == 200 and res.json()["content"] == "beta document"
        assert (await client.get(url)).json()["content"] == "beta document"

        res = await client.delete(url)
        assert res.status_code == 200 and res.json()["id"] == rag_id
        assert (await client.get(url)).status_code == 404
    finally:
        await client.delete(f"/api/v1/admin/agents/{other}")


@pytest.mark.asyncio
@pytest.mark.order(16)
async def test_too_long_external_ids_are_rejected_not_500(client):
    res = await client.post("/api/v1/users", json={"external_id": "u" * 65})
    assert res.status_code == 422
    res = await client.post("/api/v1/users", json={"external_id": ""})
    assert res.status_code == 422

    await make_user(client, "id_length_user")
    try:
        res = await client.patch(
            "/api/v1/users/id_length_user", json={"external_id": "u" * 65}
        )
        assert res.status_code == 422
        res = await client.post("/api/v1/users", json={"external_id": "u" * 64})
        assert res.status_code == 201  # exactly 64 is fine
        await client.delete("/api/v1/users/" + "u" * 64)
    finally:
        await client.delete("/api/v1/users/id_length_user")


@pytest.mark.asyncio
@pytest.mark.order(16)
async def test_mcp_server_options_are_validated(client):
    res = await client.post(
        "/api/v1/admin/mcp-servers",
        json={"name": "test", "config": {"url": MCP_CALCULATOR_URL, "bogus": 1}},
    )
    assert res.status_code == 422 and "bogus" in str(res.json())

    # options that pydantic-ai understands are accepted
    config = {
        "url": MCP_CALCULATOR_URL,
        "headers": {"X-Key": "1"},
        "timeout": 5,
        "tool_prefix": "calc",
    }
    res = await client.post(
        "/api/v1/admin/mcp-servers", json={"name": "test", "config": config}
    )
    assert res.status_code == 201
    mcp_server_id = res.json()["id"]
    try:
        res = await client.patch(
            f"/api/v1/admin/mcp-servers/{mcp_server_id}",
            json={"config": {"url": MCP_CALCULATOR_URL, "http_client": "x"}},
        )
        assert res.status_code == 422
    finally:
        await client.delete(f"/api/v1/admin/mcp-servers/{mcp_server_id}")


@pytest.mark.asyncio
@pytest.mark.order(16)
async def test_model_provider_errors_are_502(client, broken_model):
    user_id = "provider_error_user"
    try:
        res = await client.post(
            "/api/v1/request",
            json={"user_id": user_id, "request": "hi", "save_message": False},
        )
        assert res.status_code == 502
        assert "no/such-model-xyz" in res.json()["detail"]

        result = await collect_sse(client, user_id, "hi", save_message=False)
        assert (
            result["chunks"] == [] and "no/such-model-xyz" in result["error"]["detail"]
        )
        assert result["done"] is None
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(16)
async def test_an_unreachable_mcp_server_does_not_break_the_agent(client):
    agent_id = (await client.get("/api/v1/agents/self")).json()["id"]
    res = await client.post(
        "/api/v1/admin/mcp-servers",
        json={"name": "test", "config": {"url": "http://no-such-host.invalid:9/mcp"}},
    )
    mcp_server_id = res.json()["id"]
    await client.post(f"/api/v1/admin/agents/{agent_id}/mcp-servers/{mcp_server_id}")
    user_id = "dead_mcp_user"
    try:
        # the server is left out and the request is answered without its tools
        res = await client.post(
            "/api/v1/request",
            json={"user_id": user_id, "request": "Say 'pong'.", "save_message": False},
        )
        assert res.status_code == 200 and res.json()["response"]

        # it stays out for a while: the next requests do not wait for it again
        started = time.monotonic()
        result = await collect_sse(client, user_id, "Say 'pong'.", save_message=False)
        assert result["error"] is None and result["chunks"]
        assert time.monotonic() - started < 10
    finally:
        await client.delete(
            f"/api/v1/admin/agents/{agent_id}/mcp-servers/{mcp_server_id}"
        )
        await client.delete(f"/api/v1/admin/mcp-servers/{mcp_server_id}")
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(16)
async def test_a_working_mcp_server_is_still_used_next_to_a_dead_one(client):
    agent_id = (await client.get("/api/v1/agents/self")).json()["id"]
    dead = (
        await client.post(
            "/api/v1/admin/mcp-servers",
            json={
                "name": "test",
                "config": {"url": "http://no-such-host.invalid:9/mcp"},
            },
        )
    ).json()["id"]
    alive = (
        await client.post(
            "/api/v1/admin/mcp-servers",
            json={"name": "test", "config": {"url": MCP_CALCULATOR_URL}},
        )
    ).json()["id"]
    for mcp_server_id in (dead, alive):
        await client.post(
            f"/api/v1/admin/agents/{agent_id}/mcp-servers/{mcp_server_id}"
        )
    user_id = "dead_and_alive_mcp_user"
    try:
        res = await client.post(
            "/api/v1/request",
            json={"user_id": user_id, "request": CALC_QUESTION, "save_message": False},
        )
        assert res.status_code == 200
        assert CALC_ANSWER in digits_only(res.json()["response"])
    finally:
        for mcp_server_id in (dead, alive):
            await client.delete(
                f"/api/v1/admin/agents/{agent_id}/mcp-servers/{mcp_server_id}"
            )
            await client.delete(f"/api/v1/admin/mcp-servers/{mcp_server_id}")
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(16)
async def test_a_request_the_client_gave_up_on_is_cancelled(client):
    # Without cancellation the answer would still be generated and stored.
    user_id = "gave_up_user"
    try:
        with pytest.raises(httpx.ReadTimeout):
            await client.post(
                "/api/v1/request",
                json={
                    "user_id": user_id,
                    "request": "Write a 900 word story about a lighthouse keeper.",
                },
                timeout=1.5,
            )
        await asyncio.sleep(15)  # long enough for the story to be finished and saved
        assert await history_of(client, user_id) == []

        # the service is fine afterwards
        res = await client.post(
            "/api/v1/request", json={"user_id": user_id, "request": "Say 'pong'."}
        )
        assert res.status_code == 200
        assert len(await history_of(client, user_id)) == 2
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(16)
async def test_errors_that_will_not_pass_are_not_retried(client, broken_model):
    # a model the provider does not know is final at once, not after retries and pauses
    started = time.monotonic()
    res = await client.post(
        "/api/v1/request",
        json={"user_id": "no_retry_user", "request": "hi", "save_message": False},
    )
    assert res.status_code == 502
    assert time.monotonic() - started < 2.5  # two retries would add 1s + 2s
    await client.delete("/api/v1/users/no_retry_user")


@pytest.mark.asyncio
@pytest.mark.order(16)
async def test_sampling_options_of_a_model_reach_the_provider(client):
    """Every key of a model's body reaches the provider as the provider's own parameter (the fake LLM server logs what it got; a real reasoning
    model would spend a budget of 60 tokens on thinking and answer nothing)."""
    model = await fake_model(client, "fake/sampling-check")
    res = await client.patch(
        f"/api/v1/admin/models/{model['id']}",
        json={"request_json": {"model": "fake/sampling-check", "max_tokens": 60, "temperature": 0, "top_k": 20, "seed": 7}},
    )
    assert res.status_code == 200, res.text
    async with agent_on(client, model) as (_, c):
        res = await c.post(
            "/api/v1/request",
            json={"user_id": "max_tokens_user", "request": "hi", "save_message": False, "use_memo": False},
        )
        assert res.status_code == 200, res.text
    keys = fake_log("fake/sampling-check")[0]["keys"]
    # the OpenAI protocol calls the limit max_completion_tokens; either name is the limit
    assert {"temperature", "top_k", "seed"} <= set(keys) and {"max_tokens", "max_completion_tokens"} & set(keys)