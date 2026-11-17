"""api mcp tools tests"""

import pytest

from shared import (
    CALC_ANSWER,
    CALC_QUESTION,
    MCP_CALCULATOR_URL,
    collect_sse,
    digits_only,
)


async def attach_calculator(client) -> tuple:
    agent_id = (await client.get("/api/v1/agents/self")).json()["id"]
    res = await client.post(
        "/api/v1/admin/mcp-servers",
        json={"name": "test", "config": {"url": MCP_CALCULATOR_URL}},
    )
    assert res.status_code == 201
    mcp_server_id = res.json()["id"]
    res = await client.post(
        f"/api/v1/admin/agents/{agent_id}/mcp-servers/{mcp_server_id}"
    )
    assert res.status_code == 201
    return agent_id, mcp_server_id


async def detach_calculator(client, agent_id: int, mcp_server_id: int) -> None:
    await client.delete(f"/api/v1/admin/agents/{agent_id}/mcp-servers/{mcp_server_id}")
    await client.delete(f"/api/v1/admin/mcp-servers/{mcp_server_id}")


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_request_uses_mcp_tool(client):
    user_id = "mcp_request_test_user"
    agent_id, mcp_server_id = await attach_calculator(client)
    try:
        res = await client.post(
            "/api/v1/request", json={"user_id": user_id, "request": CALC_QUESTION}
        )
        assert res.status_code == 200
        assert CALC_ANSWER in digits_only(res.json()["response"])
    finally:
        await detach_calculator(client, agent_id, mcp_server_id)
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_request_stream_uses_mcp_tool(client):
    user_id = "mcp_stream_test_user"
    agent_id, mcp_server_id = await attach_calculator(client)
    try:
        result = await collect_sse(client, user_id, CALC_QUESTION)
        assert result["error"] is None
        assert CALC_ANSWER in digits_only("".join(result["chunks"]))
        assert result["done"]["external_id"] == user_id

        res = await client.get(f"/api/v1/users/{user_id}/history")
        assert CALC_ANSWER in digits_only(res.json()[-1]["content"]["content"])
    finally:
        await detach_calculator(client, agent_id, mcp_server_id)
        await client.delete(f"/api/v1/users/{user_id}")
