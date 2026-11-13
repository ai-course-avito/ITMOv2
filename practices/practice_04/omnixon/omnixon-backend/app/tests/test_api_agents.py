"""api agents tests"""

import pytest

from shared import (
    MCP_CALCULATOR_URL,
)


@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_get_all_agents(client):
    res = await client.get("/api/v1/admin/agents")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_get_self_agent(client):
    res = await client.get("/api/v1/agents/self")
    assert res.status_code == 200
    data = res.json()
    assert "id" in data
    assert "prompt" in data
    assert "model_id" in data


@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_agent_full_lifecycle(client):
    model_res = await client.post(
        "/api/v1/admin/models",
        json={
            "name": "test",
            "request_json": {"model": "openai/gpt-6-luna"},
        },
    )
    assert model_res.status_code == 201
    model_id = model_res.json()["id"]

    payload = {"name": "lifecycle", "prompt": "Be a math tutor", "model_id": model_id}
    res = await client.post("/api/v1/admin/agents", json=payload)
    assert res.status_code == 201
    agent = res.json()
    agent_id = agent["id"]
    assert agent["prompt"] == "Be a math tutor"

    res = await client.get(f"/api/v1/admin/agents/{agent_id}")
    assert res.status_code == 200
    assert res.json()["model_id"] == model_id

    res = await client.patch(
        f"/api/v1/admin/agents/{agent_id}",
        json={"prompt": "Be a coding expert"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["prompt"] == "Be a coding expert"
    assert data["model_id"] == model_id

    res = await client.delete(f"/api/v1/admin/agents/{agent_id}")
    assert res.status_code == 200
    assert res.json()["id"] == agent_id

    await client.delete(f"/api/v1/admin/models/{model_id}")


@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_agent_config_defaults(client):
    res = await client.post(
        "/api/v1/admin/agents",
        json={"name": "test", "prompt": "config test", "model_id": 0},
    )
    assert res.status_code == 201
    agent = res.json()
    try:
        # the default config is exactly the tools; limits come from the env defaults
        assert agent["config"] == {"tools": ["rag", "memory"]}
        for removed in ("tools", "chat_limit", "store_history"):
            assert removed not in agent
        res = await client.get(f"/api/v1/admin/agents/{agent['id']}")
        assert res.json()["config"] == {"tools": ["rag", "memory"]}
    finally:
        await client.delete(f"/api/v1/admin/agents/{agent['id']}")


@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_agent_config_create_and_partial_update(client):
    res = await client.post(
        "/api/v1/admin/agents",
        json={
            "name": "test",
            "prompt": "x",
            "model_id": 0,
            "config": {"tools": ["memory"], "message_limit": 4},
        },
    )
    assert res.status_code == 201
    agent_id = res.json()["id"]
    url = f"/api/v1/admin/agents/{agent_id}"
    try:
        assert res.json()["config"] == {"tools": ["memory"], "message_limit": 4}

        # only the given keys change
        res = await client.patch(url, json={"config": {"memo_limit": 7}})
        assert res.json()["config"] == {
            "tools": ["memory"],
            "message_limit": 4,
            "memo_limit": 7,
        }

        # an empty tools list is valid, duplicates collapse
        res = await client.patch(url, json={"config": {"tools": []}})
        assert res.json()["config"]["tools"] == []
        res = await client.patch(url, json={"config": {"tools": ["rag", "rag"]}})
        assert res.json()["config"]["tools"] == ["rag"]

        # null removes a key, so the default applies again
        res = await client.patch(url, json={"config": {"message_limit": None}})
        assert res.json()["config"] == {"tools": ["rag"], "memo_limit": 7}
        res = await client.patch(url, json={"config": {"tools": None}})
        assert res.json()["config"]["tools"] == ["rag", "memory"]  # back to the default
    finally:
        await client.delete(f"/api/v1/admin/agents/{agent_id}")


@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_agent_update_without_config_keeps_it(client):
    res = await client.post(
        "/api/v1/admin/agents",
        json={
            "name": "test",
            "prompt": "x",
            "model_id": 0,
            "config": {"message_limit": 3},
        },
    )
    agent_id = res.json()["id"]
    try:
        res = await client.patch(
            f"/api/v1/admin/agents/{agent_id}", json={"prompt": "changed"}
        )
        assert res.json()["prompt"] == "changed"
        assert res.json()["config"] == {"tools": ["rag", "memory"], "message_limit": 3}
    finally:
        await client.delete(f"/api/v1/admin/agents/{agent_id}")


@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_agent_config_validation(client):
    bad_configs = [
        {"tools": ["rag", "teleport"]},  # unknown tool
        {"message_limit": -1},
        {"message_limit": 1001},
        {"memo_limit": 0},  # at least one memory must be shown
        {"memo_limit": "many"},
        {"colour": "red"},  # unknown key
    ]
    for config in bad_configs:
        res = await client.post(
            "/api/v1/admin/agents",
            json={"name": "test", "prompt": "x", "model_id": 0, "config": config},
        )
        assert res.status_code == 422, config

    res = await client.post(
        "/api/v1/admin/agents", json={"name": "test", "prompt": "x", "model_id": 0}
    )
    agent_id = res.json()["id"]
    try:
        for config in bad_configs:
            res = await client.patch(
                f"/api/v1/admin/agents/{agent_id}", json={"config": config}
            )
            assert res.status_code == 422, config
        # nothing was changed by the rejected updates
        res = await client.get(f"/api/v1/admin/agents/{agent_id}")
        assert res.json()["config"] == {"tools": ["rag", "memory"]}
    finally:
        await client.delete(f"/api/v1/admin/agents/{agent_id}")


@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_agent_mcp_server_association(client):
    model_res = await client.post(
        "/api/v1/admin/models",
        json={
            "name": "test",
            "request_json": {"model": "openai/gpt-6-luna"},
        },
    )
    assert model_res.status_code == 201
    model_id = model_res.json()["id"]

    agent_res = await client.post(
        "/api/v1/admin/agents",
        json={"name": "test", "prompt": "Be a math tutor", "model_id": model_id},
    )
    assert agent_res.status_code == 201
    agent_id = agent_res.json()["id"]

    mcp_res = await client.post(
        "/api/v1/admin/mcp-servers",
        json={"name": "test", "config": {"url": MCP_CALCULATOR_URL}},
    )
    assert mcp_res.status_code == 201
    mcp_server_id = mcp_res.json()["id"]

    res = await client.get(f"/api/v1/admin/agents/{agent_id}/mcp-servers")
    assert res.status_code == 200
    assert res.json() == []

    res = await client.post(
        f"/api/v1/admin/agents/{agent_id}/mcp-servers/{mcp_server_id}"
    )
    assert res.status_code == 201
    ids = [m["id"] for m in res.json()]
    assert mcp_server_id in ids

    res = await client.get(f"/api/v1/admin/agents/{agent_id}/mcp-servers")
    assert res.status_code == 200
    ids = [m["id"] for m in res.json()]
    assert mcp_server_id in ids

    res = await client.delete(
        f"/api/v1/admin/agents/{agent_id}/mcp-servers/{mcp_server_id}"
    )
    assert res.status_code == 200
    assert res.json() == []

    res = await client.get(f"/api/v1/admin/agents/{agent_id}/mcp-servers")
    assert res.status_code == 200
    assert res.json() == []

    await client.delete(f"/api/v1/admin/agents/{agent_id}")
    await client.delete(f"/api/v1/admin/mcp-servers/{mcp_server_id}")
    await client.delete(f"/api/v1/admin/models/{model_id}")


@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_get_agent_not_found(client):
    res = await client.get("/api/v1/admin/agents/999999999")
    assert res.status_code == 404


@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_patch_agent_not_found(client):
    res = await client.patch("/api/v1/admin/agents/999999999", json={"prompt": "x"})
    assert res.status_code == 404


@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_delete_agent_not_found(client):
    res = await client.delete("/api/v1/admin/agents/999999999")
    assert res.status_code == 404
