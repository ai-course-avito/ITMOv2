"""unit usage tests: what a call costs is written once, on the token that made it, and never with a text"""

import asyncio

import pytest
from pydantic_ai.messages import ModelRequest

from ai.usage import UsageMeter, spent_of
from jobs_support import fold_usage
from repositories.data import UsageRepository
from repositories.people import TokenRepository
from services.usage import UsageService
from world import world


def response(input_tokens, output_tokens, cost=None):
    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.usage import RequestUsage

    return ModelResponse(
        parts=[TextPart("x")],
        usage=RequestUsage(input_tokens=input_tokens, output_tokens=output_tokens),
        provider_details={"cost": cost} if cost is not None else None,
    )


def test_tokens_and_cost_are_summed_over_the_answers_of_a_run():
    spent = spent_of([ModelRequest(parts=[]), response(100, 50, 0.01), response(10, 5, 0.005)])
    assert (spent.input_tokens, spent.output_tokens) == (110, 55) and spent.cost == pytest.approx(0.015)


def test_an_unpriced_answer_leaves_the_cost_unknown_not_zero():
    assert spent_of([response(10, 5)]).cost is None
    assert spent_of([response(10, 5), response(1, 1, 0.5)]).cost == 0.5


@pytest.mark.asyncio
async def test_each_call_is_written_on_the_token_that_made_it_with_no_text_at_all():
    async with world() as w:
        p = await w.principal("user")
        async with w.get(UsageMeter).track(p, "request", "a/model") as usage:
            usage.add([response(100, 50, 0.01)])
        rows = await w.get(UsageRepository).db.fetch_all("SELECT * FROM usage_logs")
        assert len(rows) == 1
        row = rows[0]
        assert (row["token_id"], row["token_name"], row["agent_id"]) == (p.token.id, p.token.name, p.agent.id)
        assert (row["model"], row["kind"], row["status"]) == ("a/model", "request", "ok")
        assert (row["input_tokens"], row["output_tokens"]) == (100, 50) and float(row["cost"]) == 0.01 and row["duration_ms"] >= 0
        # what is there to hold a text? nothing
        columns = {
            r["column_name"]
            for r in await w.get(UsageRepository).db.fetch_all(
                "SELECT column_name FROM information_schema.columns WHERE table_name IN ('usage_logs', 'usage_monthly')"
            )
        }
        assert not columns & {"content", "text", "prompt", "request", "response", "answer", "message"}


@pytest.mark.asyncio
async def test_failures_and_cancellations_are_counted_too():
    from core.errors import error_response
    from pydantic_ai.exceptions import ModelHTTPError

    async with world() as w:
        meter, p = w.get(UsageMeter), await w.principal("user")
        with pytest.raises(ModelHTTPError):
            async with meter.track(p, "stream", "a/model"):
                raise ModelHTTPError(400, "a/model", {"message": "no"})
        with pytest.raises(asyncio.CancelledError):
            async with meter.track(p, "request", "a/model"):
                raise asyncio.CancelledError()
        with pytest.raises(ValueError):
            async with meter.track(p, "request", "a/model"):
                raise ValueError("boom")
        db = w.get(UsageRepository).db
        assert [r["status"] for r in await db.fetch_all("SELECT status FROM usage_logs ORDER BY id")] == ["502", "cancelled", "500"]
        assert error_response(ValueError("x"))[0] == 500
        assert (await db.fetch_one("SELECT count(*) AS n FROM usage_logs WHERE input_tokens=0 AND cost IS NULL"))["n"] == 3  # nothing spent, nothing priced


@pytest.mark.asyncio
async def test_a_failure_to_write_usage_never_fails_the_request(monkeypatch):
    async with world() as w:
        usage = w.get(UsageRepository)

        async def broken(**kw):
            raise RuntimeError("the table is gone")

        monkeypatch.setattr(usage, "record", broken)
        async with w.get(UsageMeter).track(await w.principal("user"), "request", "a/model"):
            pass  # no exception reaches the caller


@pytest.mark.asyncio
async def test_usage_survives_the_deletion_of_its_token_under_its_old_name():
    async with world() as w:
        db, tokens = w.get(UsageRepository).db, w.get(TokenRepository)
        p = await w.principal("user")
        gone = await tokens.insert("old bot", p.agent.id, "regular")
        for days in (5, 100):
            await db.execute(
                """INSERT INTO usage_logs (token_id, token_name, model, kind, status, duration_ms, input_tokens, output_tokens, cost, timestamp)
                   VALUES ($1, 'old bot', 'a/m', 'request', 'ok', 100, 10, 10, 0.5, now() - make_interval(days => $2))""",
                (gone.id, days),
            )
        await fold_usage(db, 30)
        await tokens.delete(gone.id)
        logs = await db.fetch_all("SELECT token_id, token_name FROM usage_logs") + await db.fetch_all("SELECT token_id, token_name FROM usage_monthly")
        assert [(r["token_id"], r["token_name"]) for r in logs] == [(None, "old bot")] * 2


@pytest.mark.asyncio
async def test_usage_is_read_by_day_and_month_and_limited_to_the_tokens_of_an_agent():
    async with world() as w:
        usage, db = w.get(UsageService), w.get(UsageRepository).db
        mine, second, admin = await w.principal("user"), await w.principal("user"), await w.principal("admin")
        for p, days in ((mine, 1), (mine, 60), (second, 2)):
            await db.execute(
                """INSERT INTO usage_logs (token_id, token_name, agent_id, model, kind, status, duration_ms, input_tokens, output_tokens, cost, timestamp)
                   VALUES ($1, 't', $2, 'a/m', 'request', 'ok', 5, 3, 2, 0.5, now() - make_interval(days => $3))""",
                (p.token.id, p.agent.id, days),
            )
        await fold_usage(db, 30)
        assert {r["token_id"] for r in await usage.daily(mine, 30, None, None)} == {mine.token.id}
        assert {mine.token.id, second.token.id} <= {r["token_id"] for r in await usage.daily(admin, 30, None, None)}
        assert len(await usage.monthly(mine, None, None)) == 1 and await usage.monthly(second, None, None) == []
        assert len(await usage.monthly(admin, None, mine.agent.id)) == 1


def test_tokens_are_counted_from_the_response_for_models_without_known_prices():
    from pydantic_ai.models import openai as openai_models

    # a model that pydantic-ai has no price table for: its own mapping leaves the counts at 0
    from openai.types import CompletionUsage
    from openai.types.chat import ChatCompletion

    response = ChatCompletion(
        id="x",
        object="chat.completion",
        created=0,
        model="z-ai/some-unknown-model",
        choices=[],
        usage=CompletionUsage(
            prompt_tokens=14, completion_tokens=169, total_tokens=183
        ),
    )
    usage = openai_models._map_usage(
        response,
        "openrouter",
        "https://openrouter.ai/api/v1",
        "z-ai/some-unknown-model",
    )
    assert (usage.input_tokens, usage.output_tokens) == (14, 169)


def test_a_service_tier_openrouter_invents_does_not_fail_the_answer():
    from pydantic_ai.models import openrouter

    chunk = {
        "id": "x",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "m",
        "provider": "Somebody",
        "service_tier": "provisioned",
        "choices": [
            {
                "index": 0,
                "delta": {"content": "hi"},
                "finish_reason": None,
                "native_finish_reason": None,
            }
        ],
    }
    parsed = openrouter._OpenRouterChatCompletionChunk.model_validate(chunk)
    assert parsed.service_tier == "provisioned"
    whole = {
        **chunk,
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "hi"},
                "finish_reason": "stop",
                "native_finish_reason": "stop",
            }
        ],
    }
    assert (
        openrouter._OpenRouterChatCompletion.model_validate(whole).service_tier
        == "provisioned"
    )
    # the usual ones still pass
    assert (
        openrouter._OpenRouterChatCompletionChunk.model_validate(
            {**chunk, "service_tier": "default"}
        ).service_tier
        == "default"
    )
