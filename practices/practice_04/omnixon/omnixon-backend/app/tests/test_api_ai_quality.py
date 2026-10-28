"""api ai quality tests"""

import re
import pytest


@pytest.mark.asyncio
@pytest.mark.order(8)
async def test_ai_preference_retention(client, evaluator_agent):
    user_id = "test_user_strict"

    await client.post(
        "/api/v1/request",
        json={
            "user_id": user_id,
            "request": "Отвечай только сухими фактами без эмодзи.",
        },
    )

    res = await client.post(
        "/api/v1/request",
        json={"user_id": user_id, "request": "Какое расстояние до Луны?"},
    )
    assert res.status_code == 200
    resp_text = res.json()["response"]

    eval_prompt = f"""
<evaluation>
  <text_to_evaluate>{resp_text}</text_to_evaluate>
  <criteria>
    <criterion>The text must contain factual information about the distance to the Moon.</criterion>
    <criterion>The text must NOT contain any emojis.</criterion>
  </criteria>
</evaluation>
"""
    eval_res = await evaluator_agent.run(eval_prompt)
    print(f"Response: {resp_text}\nEvaluator: {eval_res.output}")
    assert "PASS" in eval_res.output


@pytest.mark.asyncio
@pytest.mark.order(9)
async def test_ai_context_window(client, evaluator_agent):
    user_id = "test_user_context_flow"

    history = ["Меня зовут Иван.", "Я живу в Праге.", "Я люблю пиццу."]
    for msg in history:
        await client.post("/api/v1/request", json={"user_id": user_id, "request": msg})

    res = await client.post(
        "/api/v1/request",
        json={"user_id": user_id, "request": "Где я живу и как меня зовут?"},
    )
    assert res.status_code == 200
    resp_text = res.json()["response"]

    eval_prompt = f"""
<evaluation>
  <text_to_evaluate>{resp_text}</text_to_evaluate>
  <criteria>
    <criterion>The text must explicitly identify the user's name as Ivan.</criterion>
    <criterion>The text must explicitly identify the user's location as Prague.</criterion>
  </criteria>
</evaluation>
"""
    eval_res = await evaluator_agent.run(eval_prompt)
    print(f"Response: {resp_text}\nEvaluator: {eval_res.output}")
    assert "PASS" in eval_res.output


@pytest.mark.asyncio
@pytest.mark.order(10)
async def test_ai_logic_and_math(client, evaluator_agent):
    self_agent_res = await client.get("/api/v1/agents/self")
    assert self_agent_res.status_code == 200
    agent_id = self_agent_res.json()["id"]
    original_prompt = self_agent_res.json()["prompt"]
    original_model_id = self_agent_res.json()["model_id"]

    model_res = await client.post(
        "/api/v1/admin/models",
        json={"name": "test", "request_json": {"model": "openai/gpt-6-luna"}},
    )
    assert model_res.status_code == 201
    model_id = model_res.json()["id"]

    try:
        setup_res = await client.patch(
            f"/api/v1/admin/agents/{agent_id}",
            json={
                "prompt": "You are a strict assistant. Give short, plain text answers. No emojis, no markdown, no formatting.",
                "model_id": model_id,
            },
        )
        assert setup_res.status_code == 200, f"Setup failed: {setup_res.text}"

        user_id = "math_test_user"
        math_request = "Если у меня есть 15 яблок и я отдал 3 другу, а потом купил еще 10, сколько у меня яблок? Напиши только число."

        res = await client.post(
            "/api/v1/request", json={"user_id": user_id, "request": math_request}
        )
        assert res.status_code == 200
        answer = res.json()["response"]

        eval_prompt = f"""
<evaluation>
  <text_to_evaluate>{answer}</text_to_evaluate>
  <criteria>
    <criterion>The text must contain the correct mathematical result: 22.</criterion>
    <criterion>The text must be exactly or primarily the number itself, avoiding conversational text.</criterion>
  </criteria>
</evaluation>
"""
        eval_res = await evaluator_agent.run(eval_prompt)
        print(f"Response: {answer}\nEvaluator: {eval_res.output}")
        assert "PASS" in eval_res.output
    finally:
        # Don't leak this test's model/prompt override into later tests.
        await client.patch(
            f"/api/v1/admin/agents/{agent_id}",
            json={"prompt": original_prompt, "model_id": original_model_id},
        )
        await client.delete(f"/api/v1/admin/models/{model_id}")


@pytest.mark.asyncio
@pytest.mark.order(11)
async def test_ai_consistency_and_format(client):
    user_id = "format_test_user"
    request = "Напиши короткий рассказ из 2 предложений про кота."

    res = await client.post(
        "/api/v1/request", json={"user_id": user_id, "request": request}
    )
    assert res.status_code == 200
    answer = res.json()["response"]
    print(f"Response: {answer}")

    # Checked in code: an LLM judge kept rejecting correct two-sentence answers.
    sentences = re.findall(r"[^.!?…]+[.!?…]+", answer)
    assert len(sentences) == 2, sentences
    assert not re.search(r"[*_#`]", answer), "Markdown syntax"
    assert not any(
        ord(ch) >= 0x1F000 or 0x2600 <= ord(ch) <= 0x27BF for ch in answer
    ), "emoji"
    assert "cat" in answer.lower() or "кот" in answer.lower() or "кош" in answer.lower()


@pytest.mark.asyncio
@pytest.mark.order(12)
async def test_ai_negative_constraints(client, evaluator_agent):
    user_id = "negative_test_user"
    request = "Расскажи о Париже, но не упоминай Эйфелеву башню."

    res = await client.post(
        "/api/v1/request", json={"user_id": user_id, "request": request}
    )
    assert res.status_code == 200
    answer = res.json()["response"]

    eval_prompt = f"""
<evaluation>
  <text_to_evaluate>{answer}</text_to_evaluate>
  <criteria>
    <criterion>The text must provide descriptive information about Paris.</criterion>
    <criterion>The text must NOT mention the Eiffel Tower in any form or language (e.g., Эйфелева башня, Eiffel Tower, Tour Eiffel).</criterion>
  </criteria>
</evaluation>
"""
    eval_res = await evaluator_agent.run(eval_prompt)
    print(f"Response: {answer}\nEvaluator: {eval_res.output}")
    assert "PASS" in eval_res.output
