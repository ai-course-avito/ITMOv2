"""api interrupt tests"""

import pytest
import asyncio

import httpx

from shared import (
    API_URL_2,
    INITIAL_API_KEY,
    agent_on,
    as_token,
    drop_agent,
    fake_log,
    fake_model,
    make_agent,
    make_token,
    slow_stream,
    until,
)


@pytest.mark.asyncio
@pytest.mark.order(26)
async def test_interrupting_a_stream_cuts_it_and_records_what_was_said(client):
    model = await fake_model(client, "fake/slow-interrupt")
    async with agent_on(client, model) as (_, c):
        seen = await slow_stream(c, "cut_user", "Count slowly.")
        await until(lambda: len(seen["chunks"]) >= 3)
        res = await c.post("/api/v1/users/cut_user/interrupt")
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["interrupted"] is True and body["text"].startswith("word0")
        await asyncio.wait_for(seen["task"], 20)
        assert (
            seen["events"][-1] == "interrupted"
            and "done" not in seen["events"]
            and "error" not in seen["events"]
        )
        said = "".join(seen["chunks"])
        assert (
            said.strip() == body["text"].strip() and "word39" not in said
        )  # it was cut, not finished
        history = (await c.get("/api/v1/users/cut_user/history")).json()
        assert [m["content"]["type"] for m in history][-2:] == ["user", "assistant"]
        assert history[-2]["content"]["content"] == "Count slowly."
        assert (
            history[-1]["content"]["interrupted"] is True
            and history[-1]["content"]["content"].strip() == body["text"].strip()
        )
        # nothing is running now
        assert (await c.post("/api/v1/users/cut_user/interrupt")).json() == {
            "interrupted": False,
            "text": "",
        }
        await c.delete("/api/v1/users/cut_user")


@pytest.mark.asyncio
@pytest.mark.order(26)
async def test_interrupting_a_user_who_is_not_streaming_or_not_there(client):
    model = await fake_model(client, "fake/pong-idle-interrupt")
    async with agent_on(client, model) as (_, c):
        assert (await c.post("/api/v1/users/nobody_here/interrupt")).status_code == 404
        res = await c.post(
            "/api/v1/request", json={"request": "Say pong.", "user_id": "idle_user"}
        )
        assert res.status_code == 200
        assert (await c.post("/api/v1/users/idle_user/interrupt")).json()[
            "interrupted"
        ] is False
        assert (
            len((await c.get("/api/v1/users/idle_user/history")).json()) == 2
        )  # an idle interrupt writes nothing
        await c.delete("/api/v1/users/idle_user")


@pytest.mark.asyncio
@pytest.mark.order(26)
async def test_a_new_request_cuts_the_running_stream_and_then_goes_on(client):
    slow = await fake_model(client, "fake/slow-superseded")
    async with agent_on(client, slow) as (agent, c):
        seen = await slow_stream(c, "super_user", "First question")
        await until(lambda: len(seen["chunks"]) >= 2)
        res = await c.post(
            "/api/v1/request",
            json={
                "request": "Second question",
                "user_id": "super_user",
                "save_message": True,
            },
        )
        assert res.status_code == 200, res.text
        await asyncio.wait_for(seen["task"], 30)
        assert seen["events"][-1] == "interrupted"
        history = [
            m["content"]
            for m in (await c.get("/api/v1/users/super_user/history")).json()
        ]
        types = [(m["type"], m["content"][:15]) for m in history]
        # the first question, what was said of it (cut), then the second question and its answer: in this order
        assert types[0] == ("user", "First question")
        assert (
            history[1]["type"] == "assistant" and history[1].get("interrupted") is True
        )
        assert types[2] == ("user", "Second question")
        assert history[3]["type"] == "assistant" and not history[3].get("interrupted")
        # the model saw the cut answer when it was asked the second question
        assert any(
            e["last_user"] == "Second question"
            for e in fake_log("fake/slow-superseded")
        )
        await c.delete("/api/v1/users/super_user")


@pytest.mark.asyncio
@pytest.mark.order(26)
async def test_interrupting_is_per_user_and_agent(client):
    slow = await fake_model(client, "fake/slow-isolated")
    async with agent_on(client, slow) as (_, c):
        other_agent = await make_agent(
            client, model_id=slow["id"], config={"tools": [], "auto_memory": False}
        )
        other_token = await make_token(client, other_agent["id"], "regular")
        try:
            async with as_token(other_token["token"]) as other:
                await other.post("/api/v1/users", json={"external_id": "same_name"})
                seen_mine = await slow_stream(c, "same_name")
                seen_other = await slow_stream(other, "same_name")
                await until(
                    lambda: (
                        len(seen_mine["chunks"]) >= 2 and len(seen_other["chunks"]) >= 2
                    )
                )
                # the same external id on another agent is another user: only that one is stopped
                assert (await other.post("/api/v1/users/same_name/interrupt")).json()[
                    "interrupted"
                ] is True
                await asyncio.wait_for(seen_other["task"], 20)
                assert seen_other["events"][-1] == "interrupted"
                assert not seen_mine["task"].done()
                # a second user of the same agent is not touched either
                assert (
                    await c.post("/api/v1/users", json={"external_id": "someone_else"})
                ).status_code == 201
                assert (await c.post("/api/v1/users/someone_else/interrupt")).json()[
                    "interrupted"
                ] is False
                assert not seen_mine["task"].done()
                assert (await c.post("/api/v1/users/same_name/interrupt")).json()[
                    "interrupted"
                ] is True
                await asyncio.wait_for(seen_mine["task"], 20)
                await other.delete("/api/v1/users/same_name")
                await c.delete("/api/v1/users/same_name")
                await c.delete("/api/v1/users/someone_else")
        finally:
            await client.delete(f"/api/v1/admin/tokens/{other_token['id']}")
            await drop_agent(client, other_agent)


@pytest.mark.asyncio
@pytest.mark.order(26)
async def test_an_interrupted_stream_is_not_counted_as_an_error_in_the_usage(client):
    model = await fake_model(client, "fake/slow-usage")
    async with agent_on(client, model) as (agent, c):
        tokens = (
            await client.get("/api/v1/admin/tokens", params={"agent_id": agent["id"]})
        ).json()
        token_id = tokens[0]["id"]
        seen = await slow_stream(c, "usage_cut_user")
        await until(lambda: len(seen["chunks"]) >= 2)
        await c.post("/api/v1/users/usage_cut_user/interrupt")
        await asyncio.wait_for(seen["task"], 20)
        rows = (
            await client.get("/api/v1/admin/usage", params={"token_id": token_id})
        ).json()
        mine = [r for r in rows if r["model"] == "fake/slow-usage"]
        assert sum(r["requests"] for r in mine) == 1
        assert sum(r["errors"] for r in mine) == 0
        await c.delete("/api/v1/users/usage_cut_user")


@pytest.mark.asyncio
@pytest.mark.order(26)
async def test_acting_as_another_agent_interrupts_that_agents_stream(client):
    model = await fake_model(client, "fake/slow-actas")
    async with agent_on(client, model) as (agent, c):
        seen = await slow_stream(c, "actas_user")
        await until(lambda: len(seen["chunks"]) >= 2)
        async with as_token(INITIAL_API_KEY, act_as=agent["id"]) as admin:
            assert (await admin.post("/api/v1/users/actas_user/interrupt")).json()[
                "interrupted"
            ] is True
        await asyncio.wait_for(seen["task"], 20)
        assert seen["events"][-1] == "interrupted"
        await c.delete("/api/v1/users/actas_user")


@pytest.mark.asyncio
@pytest.mark.order(26)
@pytest.mark.skipif(not API_URL_2, reason="needs the second replica of the test stack")
async def test_a_stream_is_stopped_from_another_replica_and_a_new_message_there_cuts_it_too(
    client,
):
    model = await fake_model(client, "fake/slow-replicas")
    async with agent_on(client, model) as (_, c):
        async with httpx.AsyncClient(
            base_url=API_URL_2, headers=c.headers, timeout=60.0
        ) as other:
            # the stream runs on replica 1; Stop is sent to replica 2
            seen = await slow_stream(c, "replica_user", "Count slowly.")
            await until(lambda: len(seen["chunks"]) >= 3)
            res = await other.post("/api/v1/users/replica_user/interrupt")
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["interrupted"] is True and body["text"].startswith("word0")
            await asyncio.wait_for(seen["task"], 20)
            assert seen["events"][-1] == "interrupted" and "error" not in seen["events"]
            history = (await other.get("/api/v1/users/replica_user/history")).json()
            assert (
                history[-1]["content"]["interrupted"] is True
            )  # saved, and seen from the other replica
            assert (
                await other.post("/api/v1/users/replica_user/interrupt")
            ).json() == {"interrupted": False, "text": ""}

            # a new message that arrives at replica 2 cuts the answer that still comes from replica 1
            seen = await slow_stream(c, "replica_user", "Count again, slowly.")
            await until(lambda: len(seen["chunks"]) >= 3)
            res = await other.post(
                "/api/v1/request",
                json={
                    "request": "Never mind, say hi.",
                    "user_id": "replica_user",
                    "save_message": False,
                },
            )
            assert res.status_code == 200, res.text
            await asyncio.wait_for(seen["task"], 20)
            assert seen["events"][-1] == "interrupted"
            await c.delete("/api/v1/users/replica_user")
