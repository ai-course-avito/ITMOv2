"""api requests tests"""

import pytest

from shared import (
    collect_sse,
    history_of,
)


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_request_endpoint_basic(client):
    user_id = "basic_request_test_user"
    res = await client.post(
        "/api/v1/request",
        json={"user_id": user_id, "request": "Say 'pong'."},
    )
    assert res.status_code == 200
    data = res.json()
    assert "response" in data
    assert isinstance(data["response"], str)
    assert len(data["response"]) > 0
    assert "user" in data

    await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_request_missing_fields_returns_422(client):
    res = await client.post("/api/v1/request", json={"user_id": "u1"})
    assert res.status_code == 422


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_request_stream_basic(client):
    user_id = "stream_basic_test_user"
    try:
        result = await collect_sse(client, user_id, "Say 'pong'.")
        assert result["error"] is None
        assert len(result["chunks"]) > 0
        assert all(isinstance(chunk, str) for chunk in result["chunks"])
        assert result["done"]["external_id"] == user_id

        # The full conversation is persisted exactly like /request does.
        res = await client.get(f"/api/v1/users/{user_id}/history")
        assert res.status_code == 200
        history = [m["content"] for m in res.json()]
        assert [m["type"] for m in history] == ["user", "assistant"]
        assert history[0]["content"] == "Say 'pong'."
        assert history[1]["content"].strip() == "".join(result["chunks"]).strip()
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_request_stream_uses_history(client):
    user_id = "stream_history_test_user"
    try:
        await client.post(
            "/api/v1/request",
            json={"user_id": user_id, "request": "My favourite number is 7391."},
        )
        result = await collect_sse(
            client, user_id, "What is my favourite number? Answer with the number."
        )
        assert result["error"] is None
        assert "7391" in "".join(result["chunks"])
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_request_returns_the_chain_of_calls_only_when_asked(client):
    ask = {"user_id": "trace_user", "request": "Say 'pong'.", "save_message": False}

    res = await client.post("/api/v1/request", json={**ask, "trace": True})
    assert res.status_code == 200
    steps = res.json()["trace"]
    assert steps and [s["step"] for s in steps] == list(range(1, len(steps) + 1))
    assert steps[0]["kind"] == "model" and steps[0]["name"]
    assert all(s["kind"] in ("model", "tool") for s in steps)
    assert (
        steps[-1]["kind"] == "model" and steps[-1]["text"]
    )  # the last call wrote the answer

    res = await client.post("/api/v1/request", json=ask)
    assert res.status_code == 200 and res.json()["trace"] is None
    await client.delete("/api/v1/users/trace_user")


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_request_stream_sends_trace_events_only_when_asked(client):
    traced = await collect_sse(
        client, "trace_stream", "Say 'pong'.", save_message=False, trace=True
    )
    assert traced["error"] is None and traced["done"]
    assert traced["trace"] and traced["trace"][0]["kind"] == "model"
    assert "".join(traced["chunks"])  # the text still arrives as before

    plain = await collect_sse(client, "trace_stream", "Say 'pong'.", save_message=False)
    assert plain["trace"] == [] and "".join(plain["chunks"])
    await client.delete("/api/v1/users/trace_stream")


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_request_stream_missing_fields_returns_422(client):
    res = await client.post("/api/v1/request-stream", json={"user_id": "u1"})
    assert res.status_code == 422


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_request_stream_requires_auth(no_auth_client):
    res = await no_auth_client.post(
        "/api/v1/request-stream", json={"user_id": "u1", "request": "hi"}
    )
    assert res.status_code == 403


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_stream_does_not_leak_connections(client):
    # Each stream holds a pooled DB connection until it finishes or the client
    # goes away; abandoning streams must hand the connections back.
    user_id = "stream_disconnect_test_user"
    try:
        for _ in range(15):
            async with client.stream(
                "POST",
                "/api/v1/request-stream",
                json={"user_id": user_id, "request": "Count from 1 to 50."},
            ) as res:
                assert res.status_code == 200
                async for _line in res.aiter_lines():
                    break  # disconnect after the first line

        res = await client.get("/api/v1/")
        assert res.status_code == 200
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(7)
@pytest.mark.parametrize("payload_user", [{"user_id": ""}, {"user_id": "   "}, {}])
async def test_request_without_user_id_creates_user(client, payload_user):
    res = await client.post(
        "/api/v1/request",
        json={"request": "Say 'pong'.", **payload_user},
    )
    assert res.status_code == 200
    user = res.json()["user"]
    external_id = user["external_id"]
    try:
        assert len(external_id) == 32 and int(external_id, 16) >= 0  # uuid4 hex
        # the user exists, belongs to the unit, and owns the saved exchange
        res = await client.get(f"/api/v1/users/{external_id}")
        assert res.status_code == 200 and res.json()["id"] == user["id"]
        assert len(await history_of(client, external_id)) == 2
    finally:
        await client.delete(f"/api/v1/users/{external_id}")


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_each_request_without_user_id_gets_its_own_user(client):
    created = []
    try:
        for _ in range(2):
            res = await client.post("/api/v1/request", json={"request": "Say 'pong'."})
            created.append(res.json()["user"]["external_id"])
        assert created[0] != created[1]
    finally:
        for external_id in created:
            await client.delete(f"/api/v1/users/{external_id}")


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_returned_user_id_continues_the_conversation(client):
    res = await client.post(
        "/api/v1/request", json={"request": "My secret code word is ZEBRA-4471."}
    )
    external_id = res.json()["user"]["external_id"]
    try:
        res = await client.post(
            "/api/v1/request",
            json={
                "user_id": external_id,
                "request": "What is my secret code word? Reply with the word only.",
            },
        )
        assert res.json()["user"]["external_id"] == external_id
        assert "ZEBRA-4471" in res.json()["response"]
    finally:
        await client.delete(f"/api/v1/users/{external_id}")


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_stream_without_user_id_creates_user(client):
    result = await collect_sse(client, "", "Say 'pong'.")
    external_id = result["user"]["external_id"]
    try:
        assert result["error"] is None and result["chunks"]
        assert len(external_id) == 32
        assert result["done"]["external_id"] == external_id  # same user in done event
        assert len(await history_of(client, external_id)) == 2
    finally:
        await client.delete(f"/api/v1/users/{external_id}")


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_too_long_user_id_returns_422(client):
    res = await client.post(
        "/api/v1/request", json={"user_id": "u" * 65, "request": "hi"}
    )
    assert res.status_code == 422


@pytest.mark.asyncio
@pytest.mark.order(13)
async def test_agent_has_no_store_history_field(client):
    res = await client.get("/api/v1/agents/self")
    assert res.status_code == 200
    assert "store_history" not in res.json()


@pytest.mark.asyncio
@pytest.mark.order(13)
async def test_save_message_false_does_not_store(client):
    user_id = "save_message_false_user"
    try:
        res = await client.post(
            "/api/v1/request",
            json={"user_id": user_id, "request": "Say 'pong'.", "save_message": False},
        )
        assert res.status_code == 200
        assert res.json()["response"]
        assert await history_of(client, user_id) == []

        # default (save_message omitted) stores the exchange
        res = await client.post(
            "/api/v1/request", json={"user_id": user_id, "request": "Say 'pong'."}
        )
        assert res.status_code == 200
        assert len(await history_of(client, user_id)) == 2

        # and an unsaved call afterwards leaves the history untouched
        await client.post(
            "/api/v1/request",
            json={"user_id": user_id, "request": "Say 'ping'.", "save_message": False},
        )
        assert len(await history_of(client, user_id)) == 2
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(13)
async def test_stream_save_message_flag(client):
    user_id = "stream_save_message_user"
    try:
        result = await collect_sse(client, user_id, "Say 'pong'.", save_message=False)
        assert result["error"] is None and result["chunks"]
        assert await history_of(client, user_id) == []

        result = await collect_sse(client, user_id, "Say 'pong'.")
        assert result["error"] is None
        assert len(await history_of(client, user_id)) == 2
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(13)
async def test_use_memo_false_ignores_history(client, evaluator_agent, memory_tool_off):
    user_id = "use_memo_false_user"
    try:
        await client.post(
            "/api/v1/request",
            json={"user_id": user_id, "request": "Меня зовут Светлана, я живу в Осло."},
        )
        assert len(await history_of(client, user_id)) == 2

        res = await client.post(
            "/api/v1/request",
            json={
                "user_id": user_id,
                "request": "Как меня зовут и где я живу?",
                "use_memo": False,
            },
        )
        assert res.status_code == 200
        answer = res.json()["response"]

        # use_memo only affects what the model sees, the exchange is still saved
        assert len(await history_of(client, user_id)) == 4

        eval_prompt = f"""
<evaluation>
  <text_to_evaluate>{answer}</text_to_evaluate>
  <criteria>
    <criterion>The text must NOT correctly state that the user's name is Svetlana.</criterion>
    <criterion>The text must NOT correctly state that the user lives in Oslo.</criterion>
  </criteria>
</evaluation>
"""
        eval_res = await evaluator_agent.run(eval_prompt)
        print(f"Response (use_memo=False): {answer}\nEvaluator: {eval_res.output}")
        assert "PASS" in eval_res.output

        # default (use_memo omitted) sees the history again
        res = await client.post(
            "/api/v1/request",
            json={"user_id": user_id, "request": "Как меня зовут и где я живу?"},
        )
        answer = res.json()["response"]
        eval_prompt = f"""
<evaluation>
  <text_to_evaluate>{answer}</text_to_evaluate>
  <criteria>
    <criterion>The text must explicitly identify the user's name as Svetlana.</criterion>
    <criterion>The text must explicitly identify the user's location as Oslo.</criterion>
  </criteria>
</evaluation>
"""
        eval_res = await evaluator_agent.run(eval_prompt)
        print(f"Response (use_memo default): {answer}\nEvaluator: {eval_res.output}")
        assert "PASS" in eval_res.output
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(13)
async def test_stream_use_memo_false_ignores_history(client, memory_tool_off):
    user_id = "stream_use_memo_false_user"
    try:
        await client.post(
            "/api/v1/request",
            json={"user_id": user_id, "request": "My secret code word is ZEBRA-4471."},
        )
        result = await collect_sse(
            client,
            user_id,
            "What is my secret code word? If you don't know, say 'unknown'.",
            use_memo=False,
        )
        assert result["error"] is None
        assert "ZEBRA-4471" not in "".join(result["chunks"])

        result = await collect_sse(
            client, user_id, "What is my secret code word? Reply with the word only."
        )
        assert "ZEBRA-4471" in "".join(result["chunks"])
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(13)
async def test_fully_stateless_request(client):
    user_id = "stateless_user"
    try:
        res = await client.post(
            "/api/v1/request",
            json={
                "user_id": user_id,
                "request": "Say 'pong'.",
                "save_message": False,
                "use_memo": False,
            },
        )
        assert res.status_code == 200
        assert res.json()["user"]["external_id"] == user_id  # user is still created
        assert await history_of(client, user_id) == []
    finally:
        await client.delete(f"/api/v1/users/{user_id}")
