"""api auth tests"""

import pytest


@pytest.mark.asyncio
@pytest.mark.order(0)
async def test_no_token_returns_403(no_auth_client):
    res = await no_auth_client.get("/api/v1/")
    assert res.status_code == 403


@pytest.mark.asyncio
@pytest.mark.order(0)
async def test_wrong_token_returns_403(bad_auth_client):
    res = await bad_auth_client.get("/api/v1/")
    assert res.status_code == 403


@pytest.mark.asyncio
@pytest.mark.order(1)
async def test_root(client):
    res = await client.get("/api/v1/")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
