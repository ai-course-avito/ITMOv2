"""api agent calls tests: an agent asks a connected agent through the running service, end to end (HTTP -> runner -> capabilities -> database ->
the called agent's own run), with models of the fake LLM server that call the tools `ask_agent` / `list_agents`"""

import contextlib
import uuid

import pytest

from shared import (
    as_token,
    collect_sse,
    drop_agent,
    fake_model,
    make_agent,
    make_token,
)

URL = "/api/v1/admin/agent-connections"
QUIET = {"tools": [], "auto_memory": False}


@contextlib.asynccontextmanager
async def agents(client, count, models):
    """`count` agents (default model first, then each gets the model `models[i](ids)` made from the ids of all of them) and a regular token of
    the first. Yields (agents, a client signed in with that token)."""
    made, model_records, token = [], [], None
    try:
        for i in range(count):
            made.append(await make_agent(client, name=f"calls {i}", config=QUIET))
        ids = [a["id"] for a in made]
        for agent, name in zip(made, models):
            record = await fake_model(client, name(ids) + f"-{uuid.uuid4().hex[:6]}")
            model_records.append(record)
            res = await client.patch(f"/api/v1/admin/agents/{agent['id']}", json={"model_id": record["id"]})
            assert res.status_code == 200, res.text
        token = await make_token(client, ids[0], "regular")
        async with as_token(token["token"]) as c:
            yield made, c
    finally:
        if token:
            await client.delete(f"/api/v1/admin/tokens/{token['id']}")
        for agent in made:  # the connections go with their agents
            await drop_agent(client, agent)
        for record in model_records:
            await client.delete(f"/api/v1/admin/models/{record['id']}")


async def connect(client, caller, called, description="answers"):
    res = await client.post(URL, json={"agent1_id": caller["id"], "agent2_id": called["id"], "description": description})
    assert res.status_code == 201, res.text


@pytest.mark.asyncio
@pytest.mark.order(18)
async def test_an_agent_asks_a_connected_one_and_says_what_it_answered_in_json_and_in_a_stream(client):
    async with agents(client, 2, [lambda ids: f"fake/ask-{ids[1]}", lambda ids: "fake/echo-callee"]) as ((a, b), c):
        await connect(client, a, b)

        res = await c.post("/api/v1/request", json={"user_id": "alice", "request": "go"})
        assert res.status_code == 200, res.text
        assert res.json()["response"] == "heard: echo: hello from fake"

        streamed = await collect_sse(c, "alice", "go again")
        assert streamed["error"] is None and "".join(streamed["chunks"]) == "heard: echo: hello from fake"

        # the called agent was asked in its own run, as "agent_<caller>:<person>", and keeps that conversation
        as_b = as_token(client.headers["Authorization"].split()[-1], act_as=b["id"])
        async with as_b as owner_as_b:
            users = (await owner_as_b.get("/api/v1/users", params={"query": f"agent_{a['id']}:"})).json()
            assert [u["external_id"] for u in users] == [f"agent_{a['id']}:alice"]
            history = (await owner_as_b.get(f"/api/v1/users/{users[0]['external_id']}/history")).json()
            assert [m["content"]["content"] for m in history if m["content"]["type"] == "user"] == ["hello from fake", "hello from fake"]


@pytest.mark.asyncio
@pytest.mark.order(18)
async def test_what_an_agent_may_not_call_is_refused_in_words_and_the_answer_goes_on(client):
    async with agents(client, 3, [lambda ids: f"fake/ask-{ids[2]}", lambda ids: "fake/answer", lambda ids: "fake/answer"]) as ((a, b, stranger), c):
        await connect(client, a, b)  # a may call b, not the stranger
        res = await c.post("/api/v1/request", json={"user_id": "alice", "request": "go"})
        assert res.status_code == 200, res.text
        assert f"Refused: agent {a['id']} has no connection to agent {stranger['id']}" in res.json()["response"]


@pytest.mark.asyncio
@pytest.mark.order(18)
async def test_an_agent_with_no_connections_that_asks_for_a_tool_it_does_not_have_still_answers(client):
    """The model calls `ask_agent`, which this agent does not have: pydantic-ai asks it to correct itself, and when it does not, the tool's
    failed result goes to it. That used to end the whole answer in a 502/500 ('exceeded max retries count')."""
    async with agents(client, 2, [lambda ids: f"fake/ask-{ids[1]}", lambda ids: "fake/answer"]) as ((a, b), c):
        res = await c.post("/api/v1/request", json={"user_id": "alice", "request": "go"})
        assert res.status_code == 200, res.text
        answer = res.json()["response"]
        assert answer.startswith("heard: ") and "ask_agent" in answer


@pytest.mark.asyncio
@pytest.mark.order(18)
async def test_agents_that_call_each_other_in_a_circle_stop_at_the_second_visit(client):
    async with agents(client, 2, [lambda ids: f"fake/ask-{ids[1]}", lambda ids: f"fake/ask-{ids[0]}"]) as ((a, b), c):
        await connect(client, a, b)
        await connect(client, b, a)
        res = await c.post("/api/v1/request", json={"user_id": "alice", "request": "go"})
        assert res.status_code == 200, res.text
        assert f"Refused: agent {a['id']} is already in this chain of calls ({a['id']} -> {b['id']})" in res.json()["response"]


@pytest.mark.asyncio
@pytest.mark.order(18)
async def test_list_agents_tells_an_agent_whom_it_may_call_and_what_for(client):
    async with agents(client, 2, [lambda ids: "fake/list", lambda ids: "fake/answer"]) as ((a, b), c):
        await connect(client, a, b, "knows the prices")
        res = await c.post("/api/v1/request", json={"user_id": "alice", "request": "who?"})
        assert res.status_code == 200, res.text
        assert f'"id": {b["id"]}' in res.json()["response"] and "knows the prices" in res.json()["response"]


@pytest.mark.asyncio
@pytest.mark.order(18)
async def test_the_cost_of_a_call_between_agents_is_written_on_the_token_that_started_it(client):
    async with agents(client, 2, [lambda ids: f"fake/ask-{ids[1]}", lambda ids: "fake/answer"]) as ((a, b), c):
        await connect(client, a, b)
        assert (await c.post("/api/v1/request", json={"user_id": "alice", "request": "go"})).status_code == 200
        token_id = (await c.get("/api/v1/tokens/self")).json()["id"]
        rows = (await client.get("/api/v1/admin/usage", params={"token_id": token_id})).json()
        # two model calls, each by its own agent's model, both on the token that asked: the first agent's and the one it called
        assert len(rows) == 2 and len({r["model"] for r in rows}) == 2
        assert sum(r["requests"] for r in rows) == 2 and sum(r["errors"] for r in rows) == 0  # one run each (a request is a run, not a model call)


@pytest.mark.asyncio
@pytest.mark.order(18)
async def test_two_calls_of_one_turn_to_the_same_agent_both_come_back_with_parallel_tool_calls_on_and_off(client):
    async with agents(client, 2, [lambda ids: f"fake/ask2-{ids[1]}", lambda ids: "fake/echo-both"]) as ((a, b), c):
        await connect(client, a, b)
        both = "heard: echo: hello 1 from fake | echo: hello 2 from fake"  # the results come back in the order of the calls

        res = await c.post("/api/v1/request", json={"user_id": "alice", "request": "go"})
        assert res.status_code == 200, res.text
        assert res.json()["response"] == both  # on by default: both asked together, one user and one chat on the called agent

        res = await client.patch(f"/api/v1/admin/agents/{a['id']}", json={"config": {"parallel_tool_calls": False}})
        assert res.status_code == 200 and res.json()["config"]["parallel_tool_calls"] is False, res.text
        res = await c.post("/api/v1/request", json={"user_id": "alice", "request": "go"})
        assert res.status_code == 200 and res.json()["response"] == both  # one after the other, the same answer

        streamed = await collect_sse(c, "alice", "go")
        assert streamed["error"] is None and "".join(streamed["chunks"]) == both

        res = await client.patch(f"/api/v1/admin/agents/{a['id']}", json={"config": {"parallel_tool_calls": None}})
        assert "parallel_tool_calls" not in res.json()["config"] or res.json()["config"]["parallel_tool_calls"] is None  # back to the default
