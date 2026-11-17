"""api rag tests"""

import pytest


@pytest.mark.asyncio
@pytest.mark.order(4)
async def test_rag_full_lifecycle(client):
    content = "The Eiffel Tower is located in Paris, France."

    res = await client.post("/api/v1/admin/rag", json={"content": content})
    assert res.status_code == 201
    rag = res.json()
    rag_id = rag["id"]
    assert rag["content"] == content

    res = await client.get(f"/api/v1/admin/rag/{rag_id}")
    assert res.status_code == 200
    assert res.json()["id"] == rag_id
    assert res.json()["content"] == content

    new_content = "The Eiffel Tower was built in 1889."
    res = await client.patch(
        f"/api/v1/admin/rag/{rag_id}",
        json={"content": new_content, "metadata": {"source": "wiki"}},
    )
    assert res.status_code == 200
    updated = res.json()
    assert updated["content"] == new_content
    assert updated["metadata"]["source"] == "wiki"

    res = await client.get("/api/v1/admin/rag?query=Eiffel+Tower&limit=5")
    assert res.status_code == 200
    results = res.json()
    assert isinstance(results, list)
    ids = [r["id"] for r in results]
    assert rag_id in ids

    res = await client.delete(f"/api/v1/admin/rag/{rag_id}")
    assert res.status_code == 200
    assert res.json()["id"] == rag_id

    res = await client.get(f"/api/v1/admin/rag/{rag_id}")
    assert res.status_code == 404


@pytest.mark.asyncio
@pytest.mark.order(4)
async def test_rag_create_with_metadata(client):
    res = await client.post(
        "/api/v1/admin/rag",
        json={
            "content": "Some RAG content",
            "metadata": {"tag": "test", "priority": 1},
        },
    )
    assert res.status_code == 201
    rag = res.json()
    rag_id = rag["id"]
    assert rag["metadata"]["tag"] == "test"
    assert rag["metadata"]["priority"] == 1

    await client.delete(f"/api/v1/admin/rag/{rag_id}")


@pytest.mark.asyncio
@pytest.mark.order(4)
async def test_rag_search_returns_list(client):
    res = await client.get("/api/v1/admin/rag?query=hello+world")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
@pytest.mark.order(4)
async def test_rag_search_limit(client):
    ids = []
    for i in range(3):
        res = await client.post(
            "/api/v1/admin/rag", json={"content": f"Limit test entry {i}"}
        )
        assert res.status_code == 201
        ids.append(res.json()["id"])

    res = await client.get("/api/v1/admin/rag?query=limit+test&limit=2")
    assert res.status_code == 200
    assert len(res.json()) <= 2

    for rid in ids:
        await client.delete(f"/api/v1/admin/rag/{rid}")


@pytest.mark.asyncio
@pytest.mark.order(4)
async def test_get_rag_not_found(client):
    res = await client.get("/api/v1/admin/rag/999999999")
    assert res.status_code == 404


@pytest.mark.asyncio
@pytest.mark.order(4)
async def test_patch_rag_not_found(client):
    res = await client.patch("/api/v1/admin/rag/999999999", json={"content": "x"})
    assert res.status_code == 404


@pytest.mark.asyncio
@pytest.mark.order(4)
async def test_delete_rag_not_found(client):
    res = await client.delete("/api/v1/admin/rag/999999999")
    assert res.status_code == 404
