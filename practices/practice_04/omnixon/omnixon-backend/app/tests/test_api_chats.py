"""api chats tests: a user's conversations, each its own thread; requests without a chat go to the default one"""

import asyncio
import json

import pytest

from shared import (
    agent_on,
    as_token,
    collect_sse,
    drop_agent,
    fake_log,
    fake_model,
    make_agent,
    make_token,
    until,
)


async def say(c, user, text, chat_id=None, **extra):
    res = await c.post("/api/v1/request", json={"user_id": user, "request": text, "chat_id": chat_id, **extra})
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.asyncio
@pytest.mark.order(27)
async def test_chats_are_made_listed_renamed_and_deleted(client):
    model = await fake_model(client, "fake/pong-chats-crud")
    async with agent_on(client, model) as (_, c):
        assert (await c.post("/api/v1/users", json={"external_id": "chat_ann"})).status_code == 201
        assert (await c.get("/api/v1/users/chat_ann/chats")).json() == []  # nobody has written yet: no chat

        named = await c.post("/api/v1/users/chat_ann/chats", json={"title": "  Prices  "})
        assert named.status_code == 201
        assert named.json()["title"] == "Prices" and named.json()["is_default"] is False and named.json()["messages"] == 0
        plain = (await c.post("/api/v1/users/chat_ann/chats")).json()  # no body at all is fine
        assert plain["title"] == f"Chat {plain['id']}"
        assert [x["id"] for x in (await c.get("/api/v1/users/chat_ann/chats")).json()] == [plain["id"], named.json()["id"]]  # the latest first

        url = f"/api/v1/users/chat_ann/chats/{named.json()['id']}"
        assert (await c.get(url)).json()["title"] == "Prices"
        renamed = await c.patch(url, json={"title": "Plans"})
        assert renamed.status_code == 200 and renamed.json()["title"] == "Plans"
        for bad in ({}, {"title": ""}, {"title": "   "}, {"title": "x" * 121}):
            assert (await c.patch(url, json=bad)).status_code == 422, bad

        assert (await c.delete(url)).json()["id"] == named.json()["id"]
        assert (await c.get(url)).status_code == 404
        assert (await c.delete(url)).status_code == 404
        await c.delete("/api/v1/users/chat_ann")


@pytest.mark.asyncio
@pytest.mark.order(27)
async def test_a_chat_belongs_to_one_user_of_one_agent(client):
    model = await fake_model(client, "fake/pong-chats-scope")
    async with agent_on(client, model) as (_, c):
        for user in ("scope_ann", "scope_bob"):
            await c.post("/api/v1/users", json={"external_id": user})
        ann_chat = (await c.post("/api/v1/users/scope_ann/chats", json={"title": "Ann's"})).json()
        # the chat of ann is not bob's: wherever it is asked for
        for method, path in (
            ("GET", f"/api/v1/users/scope_bob/chats/{ann_chat['id']}"),
            ("PATCH", f"/api/v1/users/scope_bob/chats/{ann_chat['id']}"),
            ("DELETE", f"/api/v1/users/scope_bob/chats/{ann_chat['id']}"),
            ("GET", f"/api/v1/users/scope_bob/chats/{ann_chat['id']}/history"),
            ("DELETE", f"/api/v1/users/scope_bob/chats/{ann_chat['id']}/history"),
        ):
            res = await c.request(method, path, json={"title": "stolen"} if method == "PATCH" else None)
            assert res.status_code == 404, (method, path)
        res = await c.post("/api/v1/request", json={"user_id": "scope_bob", "request": "hi", "chat_id": ann_chat["id"]})
        assert res.status_code == 404 and res.json()["detail"] == "Chat not found"
        async with c.stream("POST", "/api/v1/request-stream", json={"user_id": "scope_bob", "request": "hi", "chat_id": ann_chat["id"]}) as stream:
            assert stream.status_code == 404  # refused before any stream starts
        assert (await c.get("/api/v1/users/scope_bob/chats")).json() == []
        assert (await c.get("/api/v1/users/nobody_at_all/chats")).status_code == 404
        assert (await c.post("/api/v1/users/nobody_at_all/chats")).status_code == 404
        assert (await c.get("/api/v1/users/scope_ann/chats/999999999")).status_code == 404
        for user in ("scope_ann", "scope_bob"):
            await c.delete(f"/api/v1/users/{user}")


@pytest.mark.asyncio
@pytest.mark.order(27)
async def test_each_chat_is_its_own_thread_for_the_model(client):
    model = await fake_model(client, "fake/pong-chats-threads")
    async with agent_on(client, model) as (_, c):
        await c.post("/api/v1/users", json={"external_id": "thread_user"})
        chat_a = (await c.post("/api/v1/users/thread_user/chats")).json()
        chat_b = (await c.post("/api/v1/users/thread_user/chats")).json()

        first = await say(c, "thread_user", "I like apples", chat_a["id"])
        assert first["chat_id"] == chat_a["id"]
        await say(c, "thread_user", "I like bananas", chat_b["id"])
        await say(c, "thread_user", "Which fruit again?", chat_a["id"])

        # what the model was given in the third message: the thread of chat A and nothing of chat B
        seen = fake_log(model["name"])[-1]["messages"]
        texts = [t for _, t in seen]
        assert "I like apples" in texts and "Which fruit again?" in texts
        assert "I like bananas" not in texts

        for chat, expected in ((chat_a, ["I like apples", "pong", "Which fruit again?", "pong"]), (chat_b, ["I like bananas", "pong"])):
            history = (await c.get(f"/api/v1/users/thread_user/chats/{chat['id']}/history")).json()
            assert [m["content"]["content"] for m in history] == expected
            assert all(m["chat_id"] == chat["id"] for m in history)

        # the chats are named after what was said first, the latest first, with the number of messages
        chats = (await c.get("/api/v1/users/thread_user/chats")).json()
        assert [(x["id"], x["title"], x["messages"]) for x in chats] == [(chat_a["id"], "I like apples", 4), (chat_b["id"], "I like bananas", 2)]

        # the exchange is not stored when the request says so, but it is still in that chat's turn
        await say(c, "thread_user", "off the record", chat_b["id"], save_message=False)
        assert len((await c.get(f"/api/v1/users/thread_user/chats/{chat_b['id']}/history")).json()) == 2

        # clearing a chat empties it and leaves the other; the chat stays
        assert (await c.delete(f"/api/v1/users/thread_user/chats/{chat_a['id']}/history")).status_code == 204
        assert (await c.get(f"/api/v1/users/thread_user/chats/{chat_a['id']}/history")).json() == []
        assert (await c.get(f"/api/v1/users/thread_user/chats/{chat_a['id']}")).json()["messages"] == 0
        assert len((await c.get(f"/api/v1/users/thread_user/chats/{chat_b['id']}/history")).json()) == 2
        # deleting a chat takes its messages
        assert (await c.delete(f"/api/v1/users/thread_user/chats/{chat_b['id']}")).status_code == 200
        assert (await c.get(f"/api/v1/users/thread_user/chats/{chat_b['id']}/history")).status_code == 404
        await c.delete("/api/v1/users/thread_user")


@pytest.mark.asyncio
@pytest.mark.order(27)
async def test_a_request_without_a_chat_goes_to_the_default_chat_like_it_always_did(client):
    model = await fake_model(client, "fake/pong-chats-default")
    async with agent_on(client, model) as (_, c):
        first = await say(c, "bot_user", "hello from a bot")  # a client that knows nothing about chats
        second = await say(c, "bot_user", "and again")
        assert first["chat_id"] == second["chat_id"]  # the same chat each time

        chats = (await c.get("/api/v1/users/bot_user/chats")).json()
        assert [(x["id"], x["is_default"], x["title"], x["messages"]) for x in chats] == [(first["chat_id"], True, "Default chat", 4)]

        # the old history routes are the history of that chat
        old = (await c.get("/api/v1/users/bot_user/history")).json()
        assert [m["content"]["content"] for m in old] == ["hello from a bot", "pong", "and again", "pong"]
        assert all(m["chat_id"] == first["chat_id"] for m in old)

        # a chat of the user's own does not disturb it
        mine = (await c.post("/api/v1/users/bot_user/chats", json={"title": "Panel"})).json()
        await say(c, "bot_user", "from the panel", mine["id"])
        assert len((await c.get("/api/v1/users/bot_user/history")).json()) == 4
        seen = [t for _, t in fake_log(model["name"])[-1]["messages"]]
        assert "hello from a bot" not in seen  # the model did not get the bot's thread in the panel's chat

        # deleting the default chat is allowed: the next request makes it again
        assert (await c.delete(f"/api/v1/users/bot_user/chats/{first['chat_id']}")).status_code == 200
        assert (await c.get("/api/v1/users/bot_user/history")).json() == []
        again = await say(c, "bot_user", "back")
        assert again["chat_id"] != first["chat_id"]
        assert (await c.delete("/api/v1/users/bot_user/history")).status_code == 204
        assert (await c.get("/api/v1/users/bot_user/history")).json() == []
        # an unknown user has no history to read or clear
        assert (await c.get("/api/v1/users/never_seen/history")).status_code == 404
        # a user who has not written has an empty history, not an error
        await c.post("/api/v1/users", json={"external_id": "quiet_user"})
        assert (await c.get("/api/v1/users/quiet_user/history")).json() == []
        assert (await c.delete("/api/v1/users/quiet_user/history")).status_code == 204
        # deleting the user takes the chats with it
        await c.delete("/api/v1/users/bot_user")
        assert (await c.get("/api/v1/users/bot_user/chats")).status_code == 404
        await c.delete("/api/v1/users/quiet_user")


@pytest.mark.asyncio
@pytest.mark.order(27)
async def test_a_stream_writes_in_its_chat_and_so_does_a_stopped_one(client):
    fast = await fake_model(client, "fake/pong-chats-stream")
    async with agent_on(client, fast) as (_, c):
        await c.post("/api/v1/users", json={"external_id": "stream_chat_user"})
        chat = (await c.post("/api/v1/users/stream_chat_user/chats")).json()
        result = await collect_sse(c, "stream_chat_user", "stream me", chat_id=chat["id"])
        assert result["error"] is None and "".join(result["chunks"]) == "pong"
        history = (await c.get(f"/api/v1/users/stream_chat_user/chats/{chat['id']}/history")).json()
        assert [m["content"]["content"] for m in history] == ["stream me", "pong"]
        assert (await c.get("/api/v1/users/stream_chat_user/history")).json() == []  # not the default chat
        await c.delete("/api/v1/users/stream_chat_user")

    slow = await fake_model(client, "fake/slow-chats")
    async with agent_on(client, slow) as (_, c):
        await c.post("/api/v1/users", json={"external_id": "cut_chat_user"})
        chat = (await c.post("/api/v1/users/cut_chat_user/chats")).json()
        seen = {"chunks": [], "events": [], "status": None}

        async def run():
            async with c.stream("POST", "/api/v1/request-stream", json={"user_id": "cut_chat_user", "request": "Count slowly.", "chat_id": chat["id"]}) as res:
                event = "message"
                async for line in res.aiter_lines():
                    if line.startswith("event:"):
                        event = line[6:].strip()
                        seen["events"].append(event)
                    elif line.startswith("data:") and event == "message":
                        seen["chunks"].append(json.loads(line[5:].strip()))
                    elif line == "":
                        event = "message"

        task = asyncio.create_task(run())
        await until(lambda: len(seen["chunks"]) >= 2)
        assert (await c.post("/api/v1/users/cut_chat_user/interrupt")).json()["interrupted"] is True
        await asyncio.wait_for(task, 20)
        assert seen["events"][-1] == "interrupted"
        history = (await c.get(f"/api/v1/users/cut_chat_user/chats/{chat['id']}/history")).json()
        assert [m["content"]["type"] for m in history] == ["user", "assistant"] and history[-1]["content"]["interrupted"] is True
        assert (await c.get("/api/v1/users/cut_chat_user/history")).json() == []
        await c.delete("/api/v1/users/cut_chat_user")


@pytest.mark.asyncio
@pytest.mark.order(27)
async def test_a_regular_token_manages_users_and_chats_but_only_of_its_own_agent(client):
    model = await fake_model(client, "fake/pong-chats-regular")
    async with agent_on(client, model) as (agent, c):
        await c.post("/api/v1/users", json={"external_id": "reg_user"})
        chat = (await c.post("/api/v1/users/reg_user/chats", json={"title": "mine"})).json()
        # the same id on another agent is another user with other chats
        other_agent = await make_agent(client, model_id=model["id"], config={"tools": [], "auto_memory": False})
        other_token = await make_token(client, other_agent["id"], "regular")
        try:
            async with as_token(other_token["token"]) as other:
                await other.post("/api/v1/users", json={"external_id": "reg_user"})
                assert (await other.get("/api/v1/users/reg_user/chats")).json() == []
                assert (await other.get(f"/api/v1/users/reg_user/chats/{chat['id']}")).status_code == 404
                await other.delete("/api/v1/users/reg_user")
        finally:
            await client.delete(f"/api/v1/admin/tokens/{other_token['id']}")
            await drop_agent(client, other_agent)

        # users: renamed, found, deleted, with the chats following
        assert (await c.patch("/api/v1/users/reg_user", json={"external_id": "reg_renamed"})).status_code == 200
        assert [x["title"] for x in (await c.get("/api/v1/users/reg_renamed/chats")).json()] == ["mine"]
        assert [u["external_id"] for u in (await c.get("/api/v1/users", params={"query": "reg_ren"})).json()] == ["reg_renamed"]
        assert (await c.delete("/api/v1/users/reg_renamed")).status_code == 200
        assert (await c.get("/api/v1/users/reg_renamed/chats")).status_code == 404
