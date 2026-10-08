"""unit usage tests"""

import asyncio
import pytest
from pydantic_ai.messages import ModelRequest

from shared import (
    scratch_database,
)


def response(input_tokens, output_tokens, cost=None):
    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.usage import RequestUsage

    return ModelResponse(
        parts=[TextPart("x")],
        usage=RequestUsage(input_tokens=input_tokens, output_tokens=output_tokens),
        provider_details={"cost": cost} if cost is not None else None,
    )


def test_tokens_and_cost_are_summed_over_the_answers_of_a_run():
    from ai.usage import spent_of

    spent = spent_of(
        [ModelRequest(parts=[]), response(10, 5, 0.001), response(20, 7, 0.002)]
    )
    assert (spent.input_tokens, spent.output_tokens) == (30, 12)
    assert spent.cost == pytest.approx(0.003)


def test_an_unpriced_answer_leaves_the_cost_unknown_not_zero():
    from ai.usage import spent_of

    spent = spent_of([response(10, 5)])
    assert (spent.input_tokens, spent.output_tokens, spent.cost) == (10, 5, None)
    mixed = spent_of([response(1, 1), response(1, 1, 0.5)])
    assert mixed.cost == 0.5  # what is known is added


@pytest.mark.asyncio
async def test_each_call_is_written_on_the_token_that_made_it_with_no_text_at_all():
    from ai.usage import track_usage

    async with scratch_database("usage_test") as (pool, db):
        async with track_usage(db, "request", "a/model") as usage:
            usage.add([response(100, 50, 0.01)])
        rows = await pool.pool.fetch("SELECT * FROM usage_logs")
        assert len(rows) == 1
        row = rows[0]
        assert (row["token_id"], row["token_name"]) == (
            db.context.token.id,
            db.context.token.name,
        )
        assert row["agent_id"] == db.context.agent.id
        assert (row["model"], row["kind"], row["status"]) == (
            "a/model",
            "request",
            "ok",
        )
        assert (row["input_tokens"], row["output_tokens"]) == (100, 50) and float(
            row["cost"]
        ) == 0.01
        assert row["duration_ms"] >= 0

        # what is there to hold a text? nothing
        columns = {
            r["column_name"]
            for r in await pool.pool.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name IN ('usage_logs', 'usage_monthly')"
            )
        }
        assert not columns & {
            "content",
            "text",
            "prompt",
            "request",
            "response",
            "answer",
            "message",
        }


@pytest.mark.asyncio
async def test_failures_and_cancellations_are_counted_too():
    from ai.usage import track_usage
    from core.errors import error_response
    from pydantic_ai.exceptions import ModelHTTPError

    async with scratch_database("usage_fail_test") as (pool, db):
        with pytest.raises(ModelHTTPError):
            async with track_usage(db, "stream", "a/model"):
                raise ModelHTTPError(400, "a/model", {"message": "no"})
        with pytest.raises(asyncio.CancelledError):
            async with track_usage(db, "request", "a/model"):
                raise asyncio.CancelledError()
        with pytest.raises(ValueError):
            async with track_usage(db, "request", "a/model"):
                raise ValueError("boom")
        statuses = [
            r["status"]
            for r in await pool.pool.fetch("SELECT status FROM usage_logs ORDER BY id")
        ]
        assert statuses == ["502", "cancelled", "500"]
        assert error_response(ValueError("x"))[0] == 500
        # nothing spent, nothing priced
        assert (
            await pool.pool.fetchval(
                "SELECT count(*) FROM usage_logs WHERE input_tokens=0 AND cost IS NULL"
            )
            == 3
        )


@pytest.mark.asyncio
async def test_a_failure_to_write_usage_never_fails_the_request(monkeypatch):
    from ai.usage import track_usage

    async with scratch_database("usage_safe_test") as (pool, db):

        async def broken(**kw):
            raise RuntimeError("the table is gone")

        monkeypatch.setattr(db, "record_usage", broken)
        async with track_usage(db, "request", "a/model"):
            pass  # no exception reaches the caller


async def old_row(
    pool, token_id, name, days, model="a/m", tokens=10, cost=0.5, status="ok"
):
    await pool.pool.execute(
        """INSERT INTO usage_logs (token_id, token_name, model, kind, status, duration_ms,
                                   input_tokens, output_tokens, cost, timestamp)
           VALUES ($1, $2, $3, 'request', $4, 100, $5, $5, $6, now() - make_interval(days => $7))""",
        token_id,
        name,
        model,
        status,
        tokens,
        cost,
        days,
    )


@pytest.mark.asyncio
async def test_old_usage_is_folded_into_one_row_per_token_month_and_model_that_stays():
    from database.usage_compaction import compact_usage

    async with scratch_database("fold_test") as (pool, db):
        t = db.context.token
        for days in (100, 99, 98):  # old, same month or neighbours
            await old_row(pool, t.id, t.name, days)
        await old_row(pool, t.id, t.name, 100, model="b/other", status="502", cost=None)
        await old_row(pool, t.id, t.name, 2)  # recent: stays in detail
        await old_row(pool, t.id, t.name, 29)  # inside the TTL

        assert await compact_usage(pool.pool, ttl_days=30) == 4
        assert await pool.pool.fetchval("SELECT count(*) FROM usage_logs") == 2
        assert await compact_usage(pool.pool, ttl_days=30) == 0  # nothing more to fold

        monthly = await pool.pool.fetch("SELECT * FROM usage_monthly")
        assert sum(r["requests"] for r in monthly) == 4
        assert sum(r["input_tokens"] for r in monthly) == 40
        assert sum(float(r["cost"]) for r in monthly) == pytest.approx(
            1.5
        )  # the unpriced call adds nothing
        assert sum(r["errors"] for r in monthly) == 1
        assert {r["model"] for r in monthly} == {"a/m", "b/other"}
        assert all(r["token_id"] == t.id and r["token_name"] == t.name for r in monthly)
        assert all(r["month"].day == 1 for r in monthly)  # months

        # the folded rows have no expiry: a second fold only adds
        await old_row(pool, t.id, t.name, 100)
        before = {(r["month"], r["model"]): r["requests"] for r in monthly}
        await compact_usage(pool.pool, ttl_days=30)
        after = {
            (r["month"], r["model"]): r["requests"]
            for r in await pool.pool.fetch("SELECT * FROM usage_monthly")
        }
        assert sum(after.values()) == sum(before.values()) + 1
        assert len(after) == len(before)  # one row per month and model, still


@pytest.mark.asyncio
async def test_usage_survives_the_deletion_of_its_token_under_its_old_name():
    from database.usage_compaction import compact_usage

    async with scratch_database("usage_deleted_test") as (pool, db):
        gone = await db.create_token("old bot", db.context.agent.id, "regular")
        await old_row(pool, gone.id, "old bot", 5)
        await old_row(pool, gone.id, "old bot", 100)
        await compact_usage(pool.pool, ttl_days=30)
        await db.delete_token(gone.id)
        logs = await pool.pool.fetch("SELECT token_id, token_name FROM usage_logs")
        monthly = await pool.pool.fetch(
            "SELECT token_id, token_name FROM usage_monthly"
        )
        assert [(r["token_id"], r["token_name"]) for r in logs + monthly] == [
            (None, "old bot")
        ] * 2


@pytest.mark.asyncio
async def test_usage_is_read_by_day_and_month_and_limited_to_the_tokens_of_an_agent():
    from datetime import date, timedelta
    from database.usage_compaction import compact_usage

    async with scratch_database("usage_read_test") as (pool, db):
        mine = db.context.token
        second = await db.create_agent("second", 0, name="b")
        theirs = await db.create_token("theirs", second.id, "user")
        await old_row(pool, mine.id, mine.name, 0, tokens=1)
        await old_row(pool, mine.id, mine.name, 0, tokens=2)
        await old_row(pool, theirs.id, "theirs", 1, tokens=4)
        await old_row(pool, mine.id, mine.name, 90, tokens=8)
        await compact_usage(pool.pool, ttl_days=30)

        today = date.today()
        daily = await db.usage_daily(today - timedelta(days=30), today)
        assert sorted(
            (r["token_name"], r["requests"], r["input_tokens"]) for r in daily
        ) == [(mine.name, 2, 3), ("theirs", 1, 4)]
        assert all(
            isinstance(r["day"], str) and isinstance(r["cost"], float) for r in daily
        )
        # one token, one agent (what a user token is limited to)
        assert [
            r["token_name"]
            for r in await db.usage_daily(
                today - timedelta(days=30), today, token_id=theirs.id
            )
        ] == ["theirs"]
        assert [
            r["token_name"]
            for r in await db.usage_daily(
                today - timedelta(days=30), today, own_agent_id=second.id
            )
        ] == ["theirs"]
        assert (
            await db.usage_daily(
                today - timedelta(days=30),
                today,
                token_id=theirs.id,
                own_agent_id=mine.agent_id,
            )
            == []
        )

        monthly = await db.usage_monthly()
        assert [(r["token_name"], r["input_tokens"]) for r in monthly] == [
            (mine.name, 8)
        ]
        assert await db.usage_monthly(own_agent_id=second.id) == []
        assert len(await db.usage_monthly(own_agent_id=mine.agent_id)) == 1


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
