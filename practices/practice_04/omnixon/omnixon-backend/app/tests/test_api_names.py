"""api names tests"""

import pytest

from shared import (
    MCP_CALCULATOR_URL,
    as_token,
    drop_agent,
    make_agent,
    make_token,
    versions_of,
)


ENTITIES = {
    "agents": {"prompt": "Name test prompt", "model_id": 0},
    "models": {"request_json": {"model": "a/name-test"}},
    "mcp-servers": {"config": {"url": MCP_CALCULATOR_URL}},
}


@pytest.mark.asyncio
@pytest.mark.order(22)
@pytest.mark.parametrize("kind", list(ENTITIES))
async def test_an_entity_is_created_with_a_name_and_returns_it(client, kind):
    res = await client.post(
        f"/api/v1/admin/{kind}", json={"name": "  My name  ", **ENTITIES[kind]}
    )
    assert res.status_code == 201
    entity = res.json()
    try:
        assert entity["name"] == "My name"  # trimmed
        again = await client.get(f"/api/v1/admin/{kind}/{entity['id']}")
        assert again.json()["name"] == "My name"
        listed = await client.get(f"/api/v1/admin/{kind}")
        assert {e["id"]: e["name"] for e in listed.json()}[entity["id"]] == "My name"
    finally:
        await client.delete(f"/api/v1/admin/{kind}/{entity['id']}")


@pytest.mark.asyncio
@pytest.mark.order(22)
@pytest.mark.parametrize("kind", list(ENTITIES))
@pytest.mark.parametrize("bad", [None, "", "   ", 5, "x" * 121])
async def test_an_entity_cannot_be_created_without_a_proper_name(client, kind, bad):
    body = dict(ENTITIES[kind])
    if bad is not None:
        body["name"] = bad
    before = len((await client.get(f"/api/v1/admin/{kind}")).json())
    res = await client.post(f"/api/v1/admin/{kind}", json=body)
    assert res.status_code == 422, res.text
    assert len((await client.get(f"/api/v1/admin/{kind}")).json()) == before


@pytest.mark.asyncio
@pytest.mark.order(22)
@pytest.mark.parametrize("kind", list(ENTITIES))
async def test_an_entity_can_be_renamed_but_not_made_nameless(client, kind):
    entity = (
        await client.post(
            f"/api/v1/admin/{kind}", json={"name": "before", **ENTITIES[kind]}
        )
    ).json()
    url = f"/api/v1/admin/{kind}/{entity['id']}"
    try:
        res = await client.patch(url, json={"name": "after"})
        assert res.status_code == 200 and res.json()["name"] == "after"
        assert (await client.get(url)).json()["name"] == "after"
        # the rest is untouched by a rename
        for key in ENTITIES[kind]:
            assert res.json()[key] == entity[key]
        # a change without a name keeps the name
        if kind == "agents":
            res = await client.patch(url, json={"comment": "x"})
            assert res.status_code == 200 and res.json()["name"] == "after"
        for bad in ("", "   ", None):
            res = await client.patch(url, json={"name": bad})
            # null means "keep"; an empty name is refused
            assert res.status_code == (200 if bad is None else 422)
        assert (await client.get(url)).json()["name"] == "after"
    finally:
        await client.delete(url)


@pytest.mark.asyncio
@pytest.mark.order(22)
async def test_renaming_an_agent_model_or_mcp_server_adds_no_agent_version(client):
    model = (
        await client.post(
            "/api/v1/admin/models",
            json={"name": "m", "request_json": {"model": "a/name-test"}},
        )
    ).json()
    mcp = (
        await client.post(
            "/api/v1/admin/mcp-servers",
            json={"name": "s", "config": {"url": MCP_CALCULATOR_URL}},
        )
    ).json()
    agent = (
        await client.post(
            "/api/v1/admin/agents",
            json={"name": "a", "prompt": "p", "model_id": model["id"]},
        )
    ).json()
    try:
        await client.post(f"/api/v1/admin/agents/{agent['id']}/mcp-servers/{mcp['id']}")
        count = len(await versions_of(client, agent["id"]))
        for path, body in (
            (f"agents/{agent['id']}", {"name": "a2"}),
            (f"models/{model['id']}", {"name": "m2"}),
            (f"mcp-servers/{mcp['id']}", {"name": "s2"}),
        ):
            assert (
                await client.patch(f"/api/v1/admin/{path}", json=body)
            ).status_code == 200
        assert len(await versions_of(client, agent["id"])) == count
        # the snapshot copies hold no name: a name is not behaviour
        latest = (await versions_of(client, agent["id"]))[0]
        full = (
            await client.get(
                f"/api/v1/admin/agents/{agent['id']}/versions/{latest['number']}"
            )
        ).json()
        assert "name" not in full["snapshot"]["model"]
    finally:
        await client.delete(f"/api/v1/admin/agents/{agent['id']}")
        await client.delete(f"/api/v1/admin/mcp-servers/{mcp['id']}")
        await client.delete(f"/api/v1/admin/models/{model['id']}")


@pytest.mark.asyncio
@pytest.mark.order(22)
async def test_the_default_model_shows_its_own_name_as_a_fallback(client):
    model = (await client.get("/api/v1/admin/models/0")).json()
    assert model["name"] == model["request_json"]["model"]  # seeded without a name


@pytest.mark.asyncio
@pytest.mark.order(22)
async def test_an_agent_without_a_name_would_show_the_start_of_its_prompt(client):
    # agents are made with a name now; the fallback is for old rows (see tests/test_unit_access.py). Once named, the name wins
    agent = await make_agent(
        client, name="Pirate captain", prompt="\n  You are a pirate.\nSecond line"
    )
    try:
        assert agent["name"] == "Pirate captain"
        assert (await client.get(f"/api/v1/admin/agents/{agent['id']}")).json()[
            "name"
        ] == "Pirate captain"
    finally:
        await drop_agent(client, agent)


@pytest.mark.asyncio
@pytest.mark.order(22)
async def test_a_token_is_named_when_it_is_made_and_the_name_is_required(client):
    agent = await make_agent(client)
    try:
        token = await make_token(client, agent["id"], "user", name="Telegram bot")
        assert token["name"] == "Telegram bot"
        async with as_token(token["token"]) as me:
            assert (await me.get("/api/v1/tokens/self")).json()[
                "name"
            ] == "Telegram bot"
        await client.delete(f"/api/v1/admin/tokens/{token['id']}")
    finally:
        await drop_agent(client, agent)


@pytest.mark.asyncio
@pytest.mark.order(23)
async def test_rag_without_a_query_lists_every_entry_of_the_agent(client):
    agent = (
        await client.post(
            "/api/v1/admin/agents", json={"name": "kb", "prompt": "", "model_id": 0}
        )
    ).json()
    url = "/api/v1/admin/rag"
    try:
        texts = [f"list entry {i}" for i in range(5)]
        for text in texts:
            res = await client.post(
                url, params={"agent_id": agent["id"]}, json={"content": text}
            )
            assert res.status_code == 201
        res = await client.get(url, params={"agent_id": agent["id"], "limit": 1000})
        assert res.status_code == 200
        assert [e["content"] for e in res.json()] == texts  # in the order made
        assert all(e["embedding"] is None for e in res.json())
        # paging
        page = await client.get(
            url, params={"agent_id": agent["id"], "limit": 2, "offset": 3}
        )
        assert [e["content"] for e in page.json()] == texts[3:]
        # an empty query is a listing too; another agent's entries are not mixed in
        res = await client.get(url, params={"agent_id": agent["id"], "query": ""})
        assert len(res.json()) == 5
        other = (await client.get(url, params={"agent_id": 0, "limit": 1000})).json()
        assert not {e["content"] for e in other} & set(texts)
        # a search still limits itself
        res = await client.get(
            url, params={"agent_id": agent["id"], "query": "list entry", "limit": 101}
        )
        assert res.status_code == 422
        res = await client.get(url, params={"agent_id": agent["id"], "limit": 1001})
        assert res.status_code == 422
        # a search with a query keeps working
        res = await client.get(
            url, params={"agent_id": agent["id"], "query": "list entry 3", "limit": 2}
        )
        assert res.status_code == 200 and len(res.json()) == 2
    finally:
        await client.delete(f"/api/v1/admin/agents/{agent['id']}")


@pytest.mark.asyncio
@pytest.mark.order(23)
async def test_an_empty_knowledge_base_lists_nothing(client):
    agent = (
        await client.post(
            "/api/v1/admin/agents",
            json={"name": "empty kb", "prompt": "", "model_id": 0},
        )
    ).json()
    try:
        res = await client.get(
            "/api/v1/admin/rag", params={"agent_id": agent["id"], "limit": 1000}
        )
        assert res.status_code == 200 and res.json() == []
    finally:
        await client.delete(f"/api/v1/admin/agents/{agent['id']}")
