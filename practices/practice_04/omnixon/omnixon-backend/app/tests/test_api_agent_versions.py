"""api agent versions tests"""

import pytest

from shared import (
    MCP_CALCULATOR_URL,
    history_of,
    versions_of,
)


async def new_agent(client, **extra) -> dict:
    res = await client.post(
        "/api/v1/admin/agents",
        json={"name": "test", "prompt": "first", "model_id": 0, **extra},
    )
    assert res.status_code == 201
    return res.json()


@pytest.mark.asyncio
@pytest.mark.order(17)
async def test_a_new_agent_starts_at_version_1(client):
    agent = await new_agent(client, comment="for the test")
    try:
        versions = await versions_of(client, agent["id"])
        assert [v["number"] for v in versions] == [1]
        v1 = versions[0]
        assert v1["comment"] == "for the test" and v1["created_by_token_id"] > 0
        assert v1["snapshot"]["prompt"] == "first"
        assert v1["snapshot"]["model_id"] == 0
        assert v1["snapshot"]["model"]["model"]  # a copy of the model, not just its id
        assert v1["snapshot"]["config"] == {"tools": ["rag", "memory"]}
        assert v1["snapshot"]["mcp_servers"] == []

        res = await client.get(f"/api/v1/admin/agents/{agent['id']}/versions/1")
        assert res.status_code == 200 and res.json()["id"] == v1["id"]
    finally:
        await client.delete(f"/api/v1/admin/agents/{agent['id']}")


@pytest.mark.asyncio
@pytest.mark.order(17)
async def test_changes_add_versions_and_no_ops_do_not(client):
    agent = await new_agent(client)
    url = f"/api/v1/admin/agents/{agent['id']}"
    try:
        await client.patch(url, json={"prompt": "second", "comment": "reworded"})
        await client.patch(url, json={"config": {"memo_limit": 5}})
        # nothing differs: no version
        await client.patch(url, json={"prompt": "second"})
        await client.patch(url, json={"config": {"memo_limit": 5}})
        await client.patch(url, json={})

        versions = await versions_of(client, agent["id"])
        assert [v["number"] for v in versions] == [3, 2, 1]
        assert versions[1]["comment"] == "reworded"
        assert versions[0]["comment"] == "updated"  # the default comment
        assert versions[0]["snapshot"]["config"] == {
            "tools": ["rag", "memory"],
            "memo_limit": 5,
        }
        assert versions[0]["snapshot"]["prompt"] == "second"
    finally:
        await client.delete(url)


@pytest.mark.asyncio
@pytest.mark.order(17)
async def test_diff_between_versions(client):
    agent = await new_agent(client)
    url = f"/api/v1/admin/agents/{agent['id']}"
    try:
        await client.patch(url, json={"prompt": "second"})
        await client.patch(url, json={"config": {"message_limit": 3}})

        res = await client.get(f"{url}/versions/1/diff")  # to the latest
        assert res.status_code == 200
        diff = res.json()
        assert (diff["from_version"], diff["to_version"]) == (1, 3)
        assert set(diff["changes"]) == {"prompt", "config"}
        assert diff["changes"]["prompt"] == {"from": "first", "to": "second"}
        assert diff["changes"]["config"]["to"]["message_limit"] == 3

        diff = (await client.get(f"{url}/versions/2/diff", params={"to": 3})).json()
        assert set(diff["changes"]) == {"config"}
        assert (await client.get(f"{url}/versions/1/diff", params={"to": 1})).json()[
            "changes"
        ] == {}

        assert (await client.get(f"{url}/versions/9/diff")).status_code == 404
        assert (
            await client.get(f"{url}/versions/1/diff", params={"to": 9})
        ).status_code == 404
    finally:
        await client.delete(url)


@pytest.mark.asyncio
@pytest.mark.order(17)
async def test_rollback_restores_the_agent_and_is_recorded_as_a_new_version(client):
    agent = await new_agent(client, config={"message_limit": 4})
    url = f"/api/v1/admin/agents/{agent['id']}"
    try:
        await client.patch(
            url,
            json={
                "prompt": "second",
                "config": {"message_limit": None, "memo_limit": 9},
            },
        )
        res = await client.post(f"{url}/rollback", json={"to": 1})
        assert res.status_code == 200
        assert (
            res.json()["number"] == 3
            and res.json()["comment"] == "rolled back to version 1"
        )

        restored = (await client.get(url)).json()
        assert restored["prompt"] == "first"
        assert restored["config"] == {
            "tools": ["rag", "memory"],
            "message_limit": 4,
        }  # memo_limit gone

        # the history keeps everything; a rollback to the current state adds nothing
        assert [v["number"] for v in await versions_of(client, agent["id"])] == [
            3,
            2,
            1,
        ]
        res = await client.post(f"{url}/rollback", json={"to": 3, "comment": "again"})
        assert res.status_code == 200 and res.json()["number"] == 3
        assert len(await versions_of(client, agent["id"])) == 3

        assert (await client.post(f"{url}/rollback", json={"to": 9})).status_code == 404
        assert (await client.post(f"{url}/rollback", json={"to": 0})).status_code == 422
        assert (
            await client.post("/api/v1/admin/agents/999999999/rollback", json={"to": 1})
        ).status_code == 404
    finally:
        await client.delete(url)


@pytest.mark.asyncio
@pytest.mark.order(17)
async def test_rollback_brings_back_the_model_and_mcp_servers_of_that_time(client):
    res = await client.post(
        "/api/v1/admin/models",
        json={
            "name": "test",
            "request_json": {
                "model": "openai/gpt-6-luna",
                "temperature": 0.1,
            },
        },
    )
    model_id = res.json()["id"]
    res = await client.post(
        "/api/v1/admin/mcp-servers",
        json={"name": "test", "config": {"url": MCP_CALCULATOR_URL}},
    )
    mcp_id = res.json()["id"]
    agent = await new_agent(client)
    url = f"/api/v1/admin/agents/{agent['id']}"
    created = []
    try:
        await client.patch(url, json={"model_id": model_id})  # v2
        await client.post(f"{url}/mcp-servers/{mcp_id}")  # v3
        # the model and the MCP server are edited afterwards: the agent changed too
        await client.patch(
            f"/api/v1/admin/models/{model_id}",
            json={
                "request_json": {
                    "model": "openai/gpt-6-luna",
                    "temperature": 0.9,
                }
            },
        )  # v4
        await client.patch(
            f"/api/v1/admin/mcp-servers/{mcp_id}",
            json={"config": {"url": MCP_CALCULATOR_URL, "timeout": 3}},
        )  # v5
        versions = await versions_of(client, agent["id"])
        assert [v["comment"] for v in versions] == [
            f"MCP server {mcp_id} updated",
            f"model {model_id} updated",
            f"MCP server {mcp_id} attached",
            "updated",
            "created",
        ]

        res = await client.post(f"{url}/rollback", json={"to": 3})
        assert res.status_code == 200
        restored = (await client.get(url)).json()
        # the model record now says 0.9, so the old content got a record of its own
        assert restored["model_id"] != model_id
        created.append(restored["model_id"])
        model = (
            await client.get(f"/api/v1/admin/models/{restored['model_id']}")
        ).json()
        assert model["request_json"]["temperature"] == 0.1

        servers = (await client.get(f"{url}/mcp-servers")).json()
        assert len(servers) == 1 and servers[0]["config"] == {"url": MCP_CALCULATOR_URL}
        created.append(("mcp", servers[0]["id"]))

        # the records that were edited are untouched
        assert (await client.get(f"/api/v1/admin/models/{model_id}")).json()[
            "request_json"
        ]["temperature"] == 0.9

        # back to before the MCP server: it is detached
        res = await client.post(f"{url}/rollback", json={"to": 2})
        assert (await client.get(f"{url}/mcp-servers")).json() == []
        created.append((await client.get(url)).json()["model_id"])
    finally:
        await client.delete(url)
        for item in created:
            if isinstance(item, tuple):
                await client.delete(f"/api/v1/admin/mcp-servers/{item[1]}")
        await client.delete(f"/api/v1/admin/mcp-servers/{mcp_id}")
        for model in {model_id, *[c for c in created if isinstance(c, int)]}:
            await client.delete(f"/api/v1/admin/models/{model}")


@pytest.mark.asyncio
@pytest.mark.order(17)
async def test_expected_version_protects_against_lost_updates(client):
    agent = await new_agent(client)
    url = f"/api/v1/admin/agents/{agent['id']}"
    try:
        res = await client.patch(url, json={"prompt": "mine", "expected_version": 1})
        assert res.status_code == 200
        # somebody else still works from version 1
        res = await client.patch(url, json={"prompt": "theirs", "expected_version": 1})
        assert res.status_code == 409 and "version 2" in res.json()["detail"]
        assert (await client.get(url)).json()["prompt"] == "mine"

        res = await client.patch(url, json={"prompt": "theirs", "expected_version": 2})
        assert res.status_code == 200
        assert (
            await client.patch(url, json={"prompt": "x", "expected_version": 0})
        ).status_code == 422
    finally:
        await client.delete(url)


@pytest.mark.asyncio
@pytest.mark.order(17)
async def test_mcp_changes_are_versions(client):
    res = await client.post(
        "/api/v1/admin/mcp-servers",
        json={"name": "test", "config": {"url": MCP_CALCULATOR_URL}},
    )
    mcp_id = res.json()["id"]
    agent = await new_agent(client)
    url = f"/api/v1/admin/agents/{agent['id']}"
    try:
        await client.post(f"{url}/mcp-servers/{mcp_id}")
        await client.post(
            f"{url}/mcp-servers/{mcp_id}"
        )  # attached already: nothing new
        await client.delete(f"{url}/mcp-servers/{mcp_id}")
        versions = await versions_of(client, agent["id"])
        assert [v["comment"] for v in versions] == [
            f"MCP server {mcp_id} detached",
            f"MCP server {mcp_id} attached",
            "created",
        ]
        assert versions[1]["snapshot"]["mcp_servers"] == [
            {"id": mcp_id, "config": {"url": MCP_CALCULATOR_URL}}
        ]

        await client.post(f"{url}/mcp-servers/{mcp_id}")
        await client.delete(
            f"/api/v1/admin/mcp-servers/{mcp_id}"
        )  # detaches it everywhere
        versions = await versions_of(client, agent["id"])
        assert versions[0]["comment"] == f"MCP server {mcp_id} deleted"
        assert versions[0]["snapshot"]["mcp_servers"] == []
    finally:
        await client.delete(url)
        await client.delete(f"/api/v1/admin/mcp-servers/{mcp_id}")


@pytest.mark.asyncio
@pytest.mark.order(17)
async def test_messages_know_the_version_that_produced_them(client):
    agent_id = (await client.get("/api/v1/agents/self")).json()["id"]
    user_id = "version_message_user"
    try:
        await client.post(
            "/api/v1/request",
            json={"user_id": user_id, "request": "Say 'one'.", "use_memo": False},
        )
        await client.patch(
            f"/api/v1/admin/agents/{agent_id}",
            json={"prompt": "You are terse. Be brief."},
        )
        latest = (await versions_of(client, agent_id))[0]["number"]
        await client.post(
            "/api/v1/request",
            json={"user_id": user_id, "request": "Say 'two'.", "use_memo": False},
        )

        history = await history_of(client, user_id)
        assert [m["agent_version"] for m in history] == [latest - 1] * 2 + [latest] * 2
    finally:
        await client.patch(
            f"/api/v1/admin/agents/{agent_id}",
            json={"prompt": ""},  # what an agent made for a unit starts with
        )
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(17)
async def test_versions_not_found_and_deleted_with_the_agent(client):
    assert (
        await client.get("/api/v1/admin/agents/999999999/versions")
    ).status_code == 404
    agent = await new_agent(client)
    assert (
        await client.get(f"/api/v1/admin/agents/{agent['id']}/versions/7")
    ).status_code == 404
    await client.delete(f"/api/v1/admin/agents/{agent['id']}")
    assert (
        await client.get(f"/api/v1/admin/agents/{agent['id']}/versions")
    ).status_code == 404
