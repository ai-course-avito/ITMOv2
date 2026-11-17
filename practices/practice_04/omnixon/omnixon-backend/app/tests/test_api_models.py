"""api models tests"""

import pytest


@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_model_full_lifecycle(client):
    payload = {"name": "lifecycle", "request_json": {"model": "openai/gpt-6-luna"}}
    res = await client.post("/api/v1/admin/models", json=payload)
    assert res.status_code == 201
    model = res.json()
    model_id = model["id"]
    assert model["request_json"] == {"model": "openai/gpt-6-luna"}

    res = await client.get(f"/api/v1/admin/models/{model_id}")
    assert res.status_code == 200
    assert res.json()["request_json"]["model"] == "openai/gpt-6-luna"

    res = await client.patch(
        f"/api/v1/admin/models/{model_id}",
        json={"request_json": {"model": "z-ai/glm-5.3-20260816"}},
    )
    assert res.status_code == 200
    assert res.json()["request_json"]["model"] == "z-ai/glm-5.3-20260816"

    res = await client.get("/api/v1/admin/models")
    assert res.status_code == 200
    ids = [m["id"] for m in res.json()]
    assert model_id in ids

    res = await client.delete(f"/api/v1/admin/models/{model_id}")
    assert res.status_code == 200
    assert res.json()["id"] == model_id


@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_get_model_not_found(client):
    res = await client.get("/api/v1/admin/models/999999999")
    assert res.status_code == 404


@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_model_requires_model_name(client):
    res = await client.post("/api/v1/admin/models", json={"name": "test", "request_json": {}})
    assert res.status_code == 422

    res = await client.post(
        "/api/v1/admin/models", json={"name": "test", "request_json": {"provider": {}}}
    )
    assert res.status_code == 422


@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_cannot_delete_default_or_used_model(client):
    res = await client.delete("/api/v1/admin/models/0")
    assert res.status_code == 409

    model_res = await client.post(
        "/api/v1/admin/models",
        json={"name": "test", "request_json": {"model": "openai/gpt-6-luna"}},
    )
    model_id = model_res.json()["id"]
    agent_res = await client.post(
        "/api/v1/admin/agents", json={"name": "test", "prompt": "x", "model_id": model_id}
    )
    agent_id = agent_res.json()["id"]

    res = await client.delete(f"/api/v1/admin/models/{model_id}")
    assert res.status_code == 409

    await client.delete(f"/api/v1/admin/agents/{agent_id}")
    res = await client.delete(f"/api/v1/admin/models/{model_id}")
    assert res.status_code == 200
