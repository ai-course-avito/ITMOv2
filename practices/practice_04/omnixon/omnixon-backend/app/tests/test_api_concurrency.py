"""api concurrency tests"""

import pytest
import asyncio

from shared import (
    history_of,
    make_user,
    versions_of,
)


@pytest.mark.asyncio
@pytest.mark.order(21)
async def test_concurrent_requests_of_one_user_keep_every_question_next_to_its_answer(
    client,
):
    user_id = "concurrent_requests_user"
    await make_user(client, user_id)
    try:
        tokens = [
            f"TOKEN{n}" for n in range(5)
        ]  # 10 messages: the history window (message_limit)
        responses = await asyncio.gather(
            *(
                client.post(
                    "/api/v1/request",
                    json={
                        "user_id": user_id,
                        "request": f"Reply with exactly {token} and nothing else.",
                        "use_memo": False,
                    },
                )
                for token in tokens
            )
        )
        assert [r.status_code for r in responses] == [200] * 5

        history = await history_of(client, user_id)
        assert len(history) == 10
        for i in range(0, 10, 2):
            question, answer = history[i]["content"], history[i + 1]["content"]
            assert question["type"] == "user" and answer["type"] == "assistant"
            token = next(t for t in tokens if t in question["content"])
            assert token in answer["content"], (
                question,
                answer,
            )  # its own answer, right after it
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(21)
async def test_concurrent_updates_of_an_agent_keep_a_consistent_history(client):
    res = await client.post(
        "/api/v1/admin/agents", json={"name": "test", "prompt": "start", "model_id": 0}
    )
    agent_id = res.json()["id"]
    url = f"/api/v1/admin/agents/{agent_id}"
    try:
        responses = await asyncio.gather(
            *(
                client.patch(
                    url, json={"prompt": f"prompt {n}", "comment": f"change {n}"}
                )
                for n in range(10)
            )
        )
        assert [r.status_code for r in responses] == [200] * 10

        versions = await versions_of(client, agent_id)
        assert [v["number"] for v in versions] == list(
            range(11, 0, -1)
        )  # no number lost or repeated
        # the agent is what its latest version says
        assert (await client.get(url)).json()["prompt"] == versions[0]["snapshot"][
            "prompt"
        ]
    finally:
        await client.delete(url)


@pytest.mark.asyncio
@pytest.mark.order(21)
async def test_a_stale_update_loses_when_two_are_made_from_the_same_version(client):
    res = await client.post(
        "/api/v1/admin/agents", json={"name": "test", "prompt": "start", "model_id": 0}
    )
    agent_id = res.json()["id"]
    url = f"/api/v1/admin/agents/{agent_id}"
    try:
        responses = await asyncio.gather(
            *(
                client.patch(url, json={"prompt": f"mine {n}", "expected_version": 1})
                for n in range(5)
            )
        )
        statuses = sorted(r.status_code for r in responses)
        assert statuses == [
            200,
            409,
            409,
            409,
            409,
        ]  # exactly one is based on the current version
        assert len(await versions_of(client, agent_id)) == 2
    finally:
        await client.delete(url)
