"""api mcp servers tests"""

import pytest

from shared import (
    MCP_CALCULATOR_URL,
)


@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_mcp_server_full_lifecycle(client):
    payload = {
        "name": "lifecycle",
        "config": {"url": MCP_CALCULATOR_URL, "transport": "streamable_http"},
    }
    res = await client.post("/api/v1/admin/mcp-servers", json=payload)
    assert res.status_code == 201
    mcp_server = res.json()
    mcp_server_id = mcp_server["id"]
    assert mcp_server["config"]["url"] == MCP_CALCULATOR_URL

    res = await client.get(f"/api/v1/admin/mcp-servers/{mcp_server_id}")
    assert res.status_code == 200
    assert res.json()["config"]["url"] == MCP_CALCULATOR_URL

    res = await client.patch(
        f"/api/v1/admin/mcp-servers/{mcp_server_id}",
        json={"config": {"url": MCP_CALCULATOR_URL, "transport": "sse"}},
    )
    assert res.status_code == 200
    assert res.json()["config"]["transport"] == "sse"

    res = await client.get("/api/v1/admin/mcp-servers")
    assert res.status_code == 200
    ids = [m["id"] for m in res.json()]
    assert mcp_server_id in ids

    res = await client.delete(f"/api/v1/admin/mcp-servers/{mcp_server_id}")
    assert res.status_code == 200
    assert res.json()["id"] == mcp_server_id


@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_mcp_server_config_validation(client):
    res = await client.post(
        "/api/v1/admin/mcp-servers", json={"name": "test", "config": {}}
    )
    assert res.status_code == 422

    res = await client.post(
        "/api/v1/admin/mcp-servers",
        json={
            "name": "test",
            "config": {"url": MCP_CALCULATOR_URL, "transport": "carrier_pigeon"},
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_get_mcp_server_not_found(client):
    res = await client.get("/api/v1/admin/mcp-servers/999999999")
    assert res.status_code == 404
