from collections.abc import AsyncGenerator

from app.db import get_db_session
from app.main import app

ALLOWED = "http://localhost:5173"


async def test_health_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_health_db_down_is_503(client):
    class BrokenSession:
        async def execute(self, *args, **kwargs):
            raise ConnectionError("db down")

    async def broken() -> AsyncGenerator[BrokenSession, None]:
        yield BrokenSession()

    app.dependency_overrides[get_db_session] = broken
    try:
        resp = await client.get("/health")
    finally:
        app.dependency_overrides.pop(get_db_session, None)
    assert resp.status_code == 503


async def test_cors_allowed_origin(client):
    resp = await client.options(
        "/api/auth/me",
        headers={
            "Origin": ALLOWED,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == ALLOWED
    assert "authorization" in resp.headers["access-control-allow-headers"].lower()


async def test_cors_other_origin_gets_no_headers(client):
    resp = await client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in resp.headers
