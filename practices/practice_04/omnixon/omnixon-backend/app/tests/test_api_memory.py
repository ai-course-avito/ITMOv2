"""api memory tests"""

import pytest
import asyncio

from shared import (
    MCP_CALCULATOR_URL,
    collect_sse,
    make_user,
)


async def memories_of(client, user_id: str, **params) -> list:
    res = await client.get(
        "/api/v1/admin/memories", params={"user_id": user_id, **params}
    )
    assert res.status_code == 200
    return res.json()


@pytest.mark.asyncio
@pytest.mark.order(13)
async def test_memory_admin_lifecycle(client):
    user_id = "memory_lifecycle_user"
    await make_user(client, user_id)
    try:
        assert await memories_of(client, user_id) == []

        res = await client.post(
            "/api/v1/admin/memories",
            json={"user_id": user_id, "content": "  Likes tea.  "},
        )
        assert res.status_code == 201
        memory = res.json()
        assert memory["content"] == "Likes tea."  # trimmed
        assert memory["user_id"] > 0 and memory["agent_id"] > 0
        memory_id = memory["id"]

        res = await client.get(f"/api/v1/admin/memories/{memory_id}")
        assert res.status_code == 200 and res.json()["content"] == "Likes tea."

        res = await client.patch(
            f"/api/v1/admin/memories/{memory_id}", json={"content": "Likes coffee."}
        )
        assert res.status_code == 200 and res.json()["content"] == "Likes coffee."

        # newest first
        await client.post(
            "/api/v1/admin/memories", json={"user_id": user_id, "content": "Has a cat."}
        )
        listed = await memories_of(client, user_id)
        assert [m["content"] for m in listed] == ["Has a cat.", "Likes coffee."]
        assert [m["content"] for m in await memories_of(client, user_id, limit=1)] == [
            "Has a cat."
        ]

        res = await client.delete(f"/api/v1/admin/memories/{memory_id}")
        assert res.status_code == 200 and res.json()["id"] == memory_id
        assert [m["content"] for m in await memories_of(client, user_id)] == [
            "Has a cat."
        ]
        assert (
            await client.get(f"/api/v1/admin/memories/{memory_id}")
        ).status_code == 404
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(13)
async def test_memory_admin_validation_and_not_found(client):
    user_id = "memory_validation_user"
    await make_user(client, user_id)
    try:
        for content in ("", "   ", "x" * 2001):
            res = await client.post(
                "/api/v1/admin/memories", json={"user_id": user_id, "content": content}
            )
            assert res.status_code == 422, content

        res = await client.post(
            "/api/v1/admin/memories",
            json={"user_id": "no_such_user_xyz", "content": "a"},
        )
        assert res.status_code == 404
        res = await client.post(
            "/api/v1/admin/memories",
            json={"user_id": user_id, "content": "a", "agent_id": 999999999},
        )
        assert res.status_code == 404
        res = await client.get(
            "/api/v1/admin/memories", params={"user_id": "no_such_user_xyz"}
        )
        assert res.status_code == 404

        assert (await client.get("/api/v1/admin/memories/999999999")).status_code == 404
        res = await client.patch(
            "/api/v1/admin/memories/999999999", json={"content": "a"}
        )
        assert res.status_code == 404
        assert (
            await client.delete("/api/v1/admin/memories/999999999")
        ).status_code == 404
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(13)
async def test_memory_is_scoped_by_agent_and_cascades(client):
    user_id = "memory_scope_user"
    await make_user(client, user_id)
    res = await client.post(
        "/api/v1/admin/agents",
        json={"name": "test", "prompt": "second agent", "model_id": 0},
    )
    other_agent = res.json()["id"]
    try:
        await client.post(
            "/api/v1/admin/memories", json={"user_id": user_id, "content": "own agent"}
        )
        res = await client.post(
            "/api/v1/admin/memories",
            json={
                "user_id": user_id,
                "content": "other agent",
                "agent_id": other_agent,
            },
        )
        other_memory = res.json()["id"]

        assert [m["content"] for m in await memories_of(client, user_id)] == [
            "own agent"
        ]
        listed = await memories_of(client, user_id, agent_id=other_agent)
        assert [m["content"] for m in listed] == ["other agent"]

        # deleting the agent removes its memories only
        await client.delete(f"/api/v1/admin/agents/{other_agent}")
        assert (
            await client.get(f"/api/v1/admin/memories/{other_memory}")
        ).status_code == 404
        assert len(await memories_of(client, user_id)) == 1

        # deleting the user removes the rest
        own_id = (await memories_of(client, user_id))[0]["id"]
        await client.delete(f"/api/v1/users/{user_id}")
        assert (await client.get(f"/api/v1/admin/memories/{own_id}")).status_code == 404
    finally:
        await client.delete(f"/api/v1/admin/agents/{other_agent}")
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(13)
async def test_agent_sees_memories_in_prompt(client):
    user_id = "memory_prompt_user"
    await make_user(client, user_id)
    try:
        await client.post(
            "/api/v1/admin/memories",
            json={
                "user_id": user_id,
                "content": "The user's favourite colour is chartreuse.",
            },
        )
        # no history and nothing saved: only the memory can tell the model this
        res = await client.post(
            "/api/v1/request",
            json={
                "user_id": user_id,
                "request": "What is my favourite colour? Answer with the colour only.",
                "use_memo": False,
                "save_message": False,
            },
        )
        assert res.status_code == 200
        assert "chartreuse" in res.json()["response"].lower()
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(13)
async def test_agent_remembers_via_tool_and_recalls_later(client):
    user_id = "memory_tool_user"
    await make_user(client, user_id)
    try:
        res = await client.post(
            "/api/v1/request",
            json={
                "user_id": user_id,
                "request": (
                    "Please remember for the future that my dog is called Bartholomew."
                ),
                "use_memo": False,
                "save_message": False,
            },
        )
        assert res.status_code == 200
        saved = await memories_of(client, user_id)
        assert any("bartholomew" in m["content"].lower() for m in saved), saved

        # a brand-new, history-free conversation still knows it
        res = await client.post(
            "/api/v1/request",
            json={
                "user_id": user_id,
                "request": "What is my dog called? Answer with the name only.",
                "use_memo": False,
                "save_message": False,
            },
        )
        assert "bartholomew" in res.json()["response"].lower()
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(13)
async def test_stream_agent_uses_memory(client):
    user_id = "memory_stream_user"
    await make_user(client, user_id)
    try:
        await client.post(
            "/api/v1/admin/memories",
            json={"user_id": user_id, "content": "The user's lucky number is 80214."},
        )
        result = await collect_sse(
            client,
            user_id,
            "What is my lucky number? Answer with the number only.",
            use_memo=False,
            save_message=False,
        )
        assert result["error"] is None
        assert "80214" in "".join(result["chunks"])
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(13)
async def test_memory_tool_can_be_disabled_per_agent(client):
    user_id = "memory_disabled_user"
    await make_user(client, user_id)
    agent_id = (await client.get("/api/v1/agents/self")).json()["id"]
    try:
        await client.post(
            "/api/v1/admin/memories",
            json={"user_id": user_id, "content": "The user's lucky number is 80214."},
        )
        res = await client.patch(
            f"/api/v1/admin/agents/{agent_id}", json={"config": {"tools": ["rag"]}}
        )
        assert res.status_code == 200 and res.json()["config"]["tools"] == ["rag"]

        res = await client.post(
            "/api/v1/request",
            json={
                "user_id": user_id,
                "request": "What is my lucky number? If you don't know, say 'unknown'.",
                "use_memo": False,
                "save_message": False,
            },
        )
        assert "80214" not in res.json()["response"]
    finally:
        await client.patch(
            f"/api/v1/admin/agents/{agent_id}",
            json={"config": {"tools": ["rag", "memory"]}},
        )
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(13)
async def test_recall_finds_memories_beyond_the_memo_limit(client):
    # memo_limit caps what is put in the prompt; older memories stay reachable
    # through the recall tool.
    user_id = "memory_limit_user"
    await make_user(client, user_id)
    agent_id = (await client.get("/api/v1/agents/self")).json()["id"]
    res = await client.patch(
        f"/api/v1/admin/agents/{agent_id}", json={"config": {"memo_limit": 3}}
    )
    assert res.status_code == 200
    try:
        await client.post(
            "/api/v1/admin/memories",
            json={"user_id": user_id, "content": "The user's locker code is 3946."},
        )
        for i in range(6):
            await client.post(
                "/api/v1/admin/memories",
                json={"user_id": user_id, "content": f"Filler fact number {i}."},
            )
        assert len(await memories_of(client, user_id)) == 7

        res = await client.post(
            "/api/v1/request",
            json={
                "user_id": user_id,
                "request": (
                    "What is my locker code? Search your memory with the recall tool "
                    "if needed. Answer with the number only."
                ),
                "use_memo": False,
                "save_message": False,
            },
        )
        assert "3946" in res.json()["response"]
    finally:
        await client.patch(
            f"/api/v1/admin/agents/{agent_id}", json={"config": {"memo_limit": None}}
        )
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(14)
async def test_ai_mcp_tool_usage(client):
    self_agent_res = await client.get("/api/v1/agents/self")
    assert self_agent_res.status_code == 200
    agent_id = self_agent_res.json()["id"]

    mcp_res = await client.post(
        "/api/v1/admin/mcp-servers",
        json={"name": "test", "config": {"url": MCP_CALCULATOR_URL}},
    )
    assert mcp_res.status_code == 201
    mcp_server_id = mcp_res.json()["id"]

    try:
        res = await client.post(
            f"/api/v1/admin/agents/{agent_id}/mcp-servers/{mcp_server_id}"
        )
        assert res.status_code == 201
        ids = [m["id"] for m in res.json()]
        assert mcp_server_id in ids

        # A compound arithmetic expression that's effectively impossible to get
        # exactly right without actually invoking the "calculate" MCP tool.
        expression = "847293 * 58204 + 91827 // 13 - 5555 % 37"
        expected = str(eval(expression))

        user_id = "mcp_tool_usage_test_user"
        res = await client.post(
            "/api/v1/request",
            json={
                "user_id": user_id,
                "request": (
                    "You have access to a tool called `calculate` that evaluates Python "
                    f"arithmetic expressions exactly. Use it to compute `{expression}`. "
                    "Reply with only the final integer, no separators, no explanation."
                ),
            },
        )
        assert res.status_code == 200
        answer = res.json()["response"]
        normalized = answer.replace(" ", "").replace(",", "").replace("_", "")
        assert expected in normalized, f"Expected {expected!r} in {answer!r}"

        await client.delete(f"/api/v1/users/{user_id}")
    finally:
        await client.delete(
            f"/api/v1/admin/agents/{agent_id}/mcp-servers/{mcp_server_id}"
        )
        await client.delete(f"/api/v1/admin/mcp-servers/{mcp_server_id}")


async def add_memory(client, user_id: str, content: str) -> dict:
    res = await client.post(
        "/api/v1/admin/memories", json={"user_id": user_id, "content": content}
    )
    assert res.status_code == 201
    return res.json()


@pytest.mark.asyncio
@pytest.mark.order(19)
async def test_memories_are_searched_by_meaning(client):
    user_id = "memory_search_user"
    await make_user(client, user_id)
    try:
        await add_memory(client, user_id, "The user's dog is called Rex.")
        await add_memory(client, user_id, "The user's favourite food is pizza.")
        await add_memory(client, user_id, "The user works as a nurse.")

        async def search(query):
            res = await client.get(
                "/api/v1/admin/memories", params={"user_id": user_id, "query": query}
            )
            assert res.status_code == 200
            return [m["content"] for m in res.json()]

        # none of these questions shares a word with its answer
        assert (await search("what is my pet's name?"))[
            0
        ] == "The user's dog is called Rex."
        assert (await search("what do I like to eat?"))[
            0
        ] == "The user's favourite food is pizza."
        assert (await search("what is my profession?"))[
            0
        ] == "The user works as a nurse."
        assert (await search("что у меня за питомец?"))[
            0
        ] == "The user's dog is called Rex."
        # nothing about this is remembered
        assert await search("what is the capital of France?") == []
        # the words still work, and no query lists the newest first
        assert await search("pizza") == ["The user's favourite food is pizza."]
        res = await client.get("/api/v1/admin/memories", params={"user_id": user_id})
        assert [m["content"] for m in res.json()][0] == "The user works as a nurse."
        res = await client.get(
            "/api/v1/admin/memories",
            params={"user_id": user_id, "query": "my pet", "limit": 1},
        )
        assert len(res.json()) == 1
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(19)
async def test_an_edited_memory_is_found_by_its_new_meaning(client):
    user_id = "memory_edit_search_user"
    await make_user(client, user_id)
    try:
        edited = await add_memory(client, user_id, "The user's dog is called Rex.")
        cat = await add_memory(client, user_id, "The user's cat is called Tom.")
        res = await client.patch(
            f"/api/v1/admin/memories/{edited['id']}",
            json={"content": "The user's favourite colour is green."},
        )
        assert res.status_code == 200

        async def search(query):
            res = await client.get(
                "/api/v1/admin/memories", params={"user_id": user_id, "query": query}
            )
            return [m["id"] for m in res.json()]

        # what the memory says now is what finds it; what it said before no longer does
        assert (await search("what is my favourite colour?"))[0] == edited["id"]
        assert (await search("what is my pet's name?"))[0] == cat["id"]
        assert (
            "embedding"
            not in (await client.get(f"/api/v1/admin/memories/{edited['id']}")).json()
        )
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(19)
async def test_the_model_recalls_by_meaning(client):
    user_id = "memory_meaning_user"
    await make_user(client, user_id)
    agent_id = (await client.get("/api/v1/agents/self")).json()["id"]
    # more memories than the prompt shows, so that only recall can reach the answer
    res = await client.patch(
        f"/api/v1/admin/agents/{agent_id}", json={"config": {"memo_limit": 2}}
    )
    assert res.status_code == 200
    try:
        await add_memory(client, user_id, "The user's dog is called Rex.")
        for fact in (
            "The user lives in Prague.",
            "The user likes jazz.",
            "The user drives a blue car.",
        ):
            await add_memory(client, user_id, fact)

        res = await client.post(
            "/api/v1/request",
            json={
                "user_id": user_id,
                "request": "What is my pet called? Search your memory with the recall tool. Answer with the name only.",
                "use_memo": False,
                "save_message": False,
            },
        )
        assert "rex" in res.json()["response"].lower()
    finally:
        await client.patch(
            f"/api/v1/admin/agents/{agent_id}", json={"config": {"memo_limit": None}}
        )
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(19)
async def test_auto_memory_learns_from_a_conversation_by_default(client):
    agent = (await client.get("/api/v1/agents/self")).json()
    assert (
        "auto_memory" not in agent["config"]
    )  # nothing is set: the default (on) applies
    user_id = "auto_memory_user"
    await make_user(client, user_id)
    try:
        # nothing lasting in this one: nothing is remembered
        res = await client.post(
            "/api/v1/request", json={"user_id": user_id, "request": "What is 2 + 2?"}
        )
        assert res.status_code == 200
        await asyncio.sleep(8)
        assert await memories_of(client, user_id) == []

        res = await client.post(
            "/api/v1/request",
            json={
                "user_id": user_id,
                "request": "Hi! My name is Boris and I live in Lisbon.",
            },
        )
        assert res.status_code == 200

        # the learning happens in the background, after the answer
        remembered = ""
        for _ in range(30):
            remembered = " ".join(
                m["content"] for m in await memories_of(client, user_id)
            ).lower()
            if "boris" in remembered and "lisbon" in remembered:
                break
            await asyncio.sleep(2)
        assert "boris" in remembered and "lisbon" in remembered, remembered
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(19)
async def test_the_agent_answers_from_what_is_remembered_without_tools(client):
    # The memories are in the user's message, so the model needs no tool call to use them.
    user_id = "memory_in_prompt_user"
    await make_user(client, user_id)
    agent_id = (await client.get("/api/v1/agents/self")).json()["id"]
    await client.patch(
        f"/api/v1/admin/agents/{agent_id}", json={"config": {"auto_memory": False}}
    )
    try:
        await add_memory(
            client, user_id, "The user's name is Boris and he lives in Lisbon."
        )
        res = await client.post(
            "/api/v1/request",
            json={
                "user_id": user_id,
                "request": "What do you know about me? Answer in one sentence.",
                "use_memo": False,
                "save_message": False,
            },
        )
        answer = res.json()["response"].lower()
        assert "boris" in answer and "lisbon" in answer
    finally:
        await client.patch(
            f"/api/v1/admin/agents/{agent_id}", json={"config": {"auto_memory": None}}
        )
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(19)
async def test_auto_memory_can_be_switched_off_per_agent(client):
    res = await client.post(
        "/api/v1/admin/agents",
        json={
            "name": "test",
            "prompt": "x",
            "model_id": 0,
            "config": {"auto_memory": False},
        },
    )
    assert res.status_code == 201 and res.json()["config"]["auto_memory"] is False
    agent_id = res.json()["id"]
    try:
        res = await client.patch(
            f"/api/v1/admin/agents/{agent_id}", json={"config": {"auto_memory": None}}
        )
        assert "auto_memory" not in res.json()["config"]  # back to the default
    finally:
        await client.delete(f"/api/v1/admin/agents/{agent_id}")


@pytest.mark.asyncio
@pytest.mark.order(19)
async def test_auto_memory_is_validated(client):
    res = await client.post(
        "/api/v1/admin/agents",
        json={
            "name": "test",
            "prompt": "x",
            "model_id": 0,
            "config": {"auto_memory": "yes please"},
        },
    )
    assert res.status_code == 422
    res = await client.post(
        "/api/v1/admin/agents",
        json={
            "name": "test",
            "prompt": "x",
            "model_id": 0,
            "config": {"auto_memory": True},
        },
    )
    assert res.status_code == 201 and res.json()["config"]["auto_memory"] is True
    await client.delete(f"/api/v1/admin/agents/{res.json()['id']}")
