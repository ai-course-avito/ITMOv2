"""api agent connections tests: making, changing and deleting connections between agents, what is refused, and
that each change is a version of the calling agent"""

import pytest

from shared import drop_agent, make_agent

URL = "/api/v1/admin/agent-connections"


async def versions(client, agent_id):
    return (await client.get(f"/api/v1/admin/agents/{agent_id}/versions")).json()


@pytest.mark.asyncio
@pytest.mark.order(17)
async def test_a_connection_is_made_changed_and_deleted_and_each_change_is_a_version_of_the_caller(
    client,
):
    a = await make_agent(client, name="caller")
    b = await make_agent(client, name="called")
    try:
        before = len(await versions(client, a["id"]))
        res = await client.post(
            URL,
            json={
                "agent1_id": a["id"],
                "agent2_id": b["id"],
                "description": "  knows prices  ",
            },
        )
        assert res.status_code == 201, res.text
        made = res.json()
        assert (made["agent1_id"], made["agent2_id"], made["description"]) == (
            a["id"],
            b["id"],
            "knows prices",
        )

        listed = (await client.get(URL, params={"agent_id": a["id"]})).json()
        assert [c["id"] for c in listed] == [made["id"]]
        assert (
            await client.get(URL, params={"agent_id": b["id"]})
        ).json() == []  # only the ones going out
        assert made["id"] in [c["id"] for c in (await client.get(URL)).json()]

        res = await client.patch(
            f"{URL}/{made['id']}", json={"description": "knows prices and stock"}
        )
        assert (
            res.status_code == 200
            and res.json()["description"] == "knows prices and stock"
        )
        assert (await client.get(f"{URL}/{made['id']}")).json()[
            "description"
        ] == "knows prices and stock"

        history = await versions(client, a["id"])
        assert len(history) == before + 2
        assert history[0]["snapshot"]["connections"] == [
            {"agent2_id": b["id"], "description": "knows prices and stock"}
        ]
        assert history[0]["comment"] == f"description of agent {b['id']} changed"
        assert (
            len(await versions(client, b["id"])) == 1
        )  # the called agent is not changed by it

        assert (await client.delete(f"{URL}/{made['id']}")).status_code == 200
        assert (await client.get(f"{URL}/{made['id']}")).status_code == 404
        assert (await versions(client, a["id"]))[0]["snapshot"]["connections"] == []
    finally:
        await drop_agent(client, a)
        await drop_agent(client, b)


@pytest.mark.asyncio
@pytest.mark.order(17)
async def test_a_connection_to_itself_twice_or_to_nobody_is_refused(client):
    a = await make_agent(client, name="caller")
    b = await make_agent(client, name="called")
    try:
        body = {"agent1_id": a["id"], "agent2_id": b["id"], "description": "x"}
        assert (await client.post(URL, json=body)).status_code == 201
        assert (
            await client.post(URL, json=body)
        ).status_code == 409  # the same pair again
        assert (
            await client.post(URL, json={**body, "agent2_id": a["id"]})
        ).status_code == 409  # to itself
        res = await client.post(URL, json={**body, "agent2_id": 999999999})
        assert res.status_code == 404 and "999999999" in res.text
        assert (
            await client.post(URL, json={**body, "description": "   "})
        ).status_code == 422
        assert (
            await client.patch(f"{URL}/999999999", json={"description": "x"})
        ).status_code == 404
        # the way back is a connection of its own
        assert (
            await client.post(
                URL, json={**body, "agent1_id": b["id"], "agent2_id": a["id"]}
            )
        ).status_code == 201
    finally:
        await drop_agent(client, a)
        await drop_agent(client, b)


@pytest.mark.asyncio
@pytest.mark.order(17)
async def test_deleting_an_agent_removes_its_connections_and_is_a_version_of_those_that_called_it(
    client,
):
    a = await make_agent(client, name="caller")
    b = await make_agent(client, name="called")
    try:
        await client.post(
            URL, json={"agent1_id": a["id"], "agent2_id": b["id"], "description": "x"}
        )
        assert (
            await client.delete(f"/api/v1/admin/agents/{b['id']}")
        ).status_code == 200
        assert (await client.get(URL, params={"agent_id": a["id"]})).json() == []
        latest = (await versions(client, a["id"]))[0]
        assert (
            latest["snapshot"]["connections"] == []
            and latest["comment"] == f"agent {b['id']} deleted: may no longer call it"
        )
    finally:
        await drop_agent(client, a)
        await client.delete(f"/api/v1/admin/agents/{b['id']}")
