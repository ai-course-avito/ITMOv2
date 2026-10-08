"""api operations tests"""

import pytest
import httpx
import asyncio


@pytest.mark.asyncio
@pytest.mark.order(18)
async def test_health_endpoints_need_no_token(no_auth_client):
    root = str(no_auth_client.base_url).rstrip("/")
    async with httpx.AsyncClient(
        base_url=root.replace("/api/v1", ""), timeout=30
    ) as plain:
        res = await plain.get("/healthz")
        assert res.status_code == 200 and res.json() == {"status": "ok"}

        res = await plain.get("/readyz")
        assert res.status_code == 200
        body = res.json()
        assert (
            body["status"] == "ok" and body["migration"] >= 6
        )  # the database is at the latest migration


@pytest.mark.asyncio
@pytest.mark.order(18)
async def test_metrics_count_requests_by_route_template(no_auth_client, client):
    root = str(no_auth_client.base_url).rstrip("/").replace("/api/v1", "")

    async def scrape() -> str:
        async with httpx.AsyncClient(base_url=root, timeout=30) as plain:
            res = await plain.get("/metrics")
            assert res.status_code == 200
            assert res.headers["content-type"].startswith("text/plain")
            return res.text

    def count(text: str, selector: str) -> float:
        for line in text.splitlines():
            if line.startswith(selector):
                return float(line.rsplit(" ", 1)[1])
        return 0.0

    selector = 'omnixon_http_requests_total{method="GET",path="/api/v1/users/{user_id}",status="404"}'
    before = await scrape()
    for i in range(3):
        assert (
            await client.get(f"/api/v1/users/no_such_metrics_user_{i}")
        ).status_code == 404
    after = await scrape()

    assert count(after, selector) == count(before, selector) + 3
    assert "no_such_metrics_user" not in after  # ids are never labels
    # the other families are there
    for name in (
        "omnixon_http_request_duration_seconds_bucket",
        "omnixon_http_requests_in_flight",
        "omnixon_active_streams",
        "omnixon_db_pool_size",
        "omnixon_db_pool_max",
        "omnixon_upstream_retries_total",
    ):
        assert name in after, name


@pytest.mark.asyncio
@pytest.mark.order(18)
async def test_active_streams_gauge_goes_up_and_down(no_auth_client, client):
    root = str(no_auth_client.base_url).rstrip("/").replace("/api/v1", "")

    async def active() -> float:
        async with httpx.AsyncClient(base_url=root, timeout=30) as plain:
            for line in (await plain.get("/metrics")).text.splitlines():
                if line.startswith("omnixon_active_streams "):
                    return float(line.split()[1])

    assert await active() == 0
    user_id = "gauge_user"
    try:
        async with client.stream(
            "POST",
            "/api/v1/request-stream",
            json={
                "user_id": user_id,
                "request": "Write 300 words about the sea.",
                "save_message": False,
            },
        ) as res:
            async for line in res.aiter_lines():
                if line.startswith(
                    "event: user"
                ):  # sent at once: the model is still working
                    # (checked here: leaving the loop closes the connection)
                    assert await active() == 1  # the stream is open
                    break
        await asyncio.sleep(1)
        assert await active() == 0
    finally:
        await client.delete(f"/api/v1/users/{user_id}")
