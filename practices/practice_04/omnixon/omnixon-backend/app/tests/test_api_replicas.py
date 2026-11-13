"""api replicas tests: what the replicas of the api share through Redis (the test stack has two, `API_URL` and `API_URL_2`; the stop of a stream
from another replica is in test_api_interrupt.py)"""

import uuid

import httpx
import pytest

from shared import API_URL, API_URL_2, agent_on, fake_model


def dropped(base_url: str) -> float:
    """omnixon_mcp_servers_dropped_total of one replica: how many times it found an MCP server down."""
    for line in httpx.get(base_url.rstrip("/") + "/metrics", timeout=10).text.splitlines():
        if line.startswith("omnixon_mcp_servers_dropped_total"):
            return float(line.split()[-1])
    return 0.0


@pytest.mark.asyncio
@pytest.mark.order(26)
@pytest.mark.skipif(not API_URL_2, reason="needs the second replica of the test stack")
async def test_an_mcp_server_found_dead_by_one_replica_is_left_alone_by_the_other(client):
    model = await fake_model(client, f"fake/answer-replicas-{uuid.uuid4().hex[:6]}")
    server = (
        await client.post(
            "/api/v1/admin/mcp-servers",
            json={"name": "dead", "config": {"url": f"http://no-such-host.invalid:9/mcp?replicas={uuid.uuid4().hex}"}},
        )
    ).json()
    async with agent_on(client, model) as (agent, c):
        await client.post(f"/api/v1/admin/agents/{agent['id']}/mcp-servers/{server['id']}")
        try:
            async with httpx.AsyncClient(base_url=API_URL_2, headers=c.headers, timeout=60.0) as other:
                first, second = dropped(API_URL), dropped(API_URL_2)

                res = await c.post("/api/v1/request", json={"user_id": "replica_mcp", "request": "hi", "save_message": False})
                assert res.status_code == 200, res.text  # answered without the server's tools
                assert dropped(API_URL) >= first + 1  # replica 1 tried it and found it dead

                res = await other.post("/api/v1/request", json={"user_id": "replica_mcp", "request": "hi", "save_message": False})
                assert res.status_code == 200, res.text
                assert dropped(API_URL_2) == second  # replica 2 did not even try: it knew from Redis
        finally:
            await client.delete(f"/api/v1/admin/agents/{agent['id']}/mcp-servers/{server['id']}")
            await client.delete(f"/api/v1/admin/mcp-servers/{server['id']}")
