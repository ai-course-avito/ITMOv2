"""Usage rows are kept in detail for USAGE_TTL_DAYS; older ones are folded into one row per token, month and
model (usage_monthly), which is never deleted. Folding adds to the row that is already there, so it can run
any number of times."""

import asyncio

import logfire

from core import USAGE_COMPACT_INTERVAL_SECONDS, USAGE_TTL_DAYS

BATCH_SIZE = 20_000

_FOLD = """
WITH old AS (
    DELETE FROM usage_logs
    WHERE id IN (
        SELECT id FROM usage_logs
        WHERE timestamp < now() - make_interval(secs => $1)
        ORDER BY id
        LIMIT $2
    )
    RETURNING token_id, token_name, timestamp, model, status, duration_ms, input_tokens, output_tokens, cost
), folded AS (
    SELECT token_id, token_name, date_trunc('month', timestamp)::date AS month, model,
           count(*) AS requests,
           count(*) FILTER (WHERE status NOT IN ('ok', 'interrupted')) AS errors,
           sum(input_tokens) AS input_tokens,
           sum(output_tokens) AS output_tokens,
           COALESCE(sum(cost), 0) AS cost,
           sum(duration_ms) AS duration_ms_sum
    FROM old
    GROUP BY 1, 2, 3, 4
), added AS (
    INSERT INTO usage_monthly (token_id, token_name, month, model, requests, errors,
                               input_tokens, output_tokens, cost, duration_ms_sum)
    SELECT token_id, token_name, month, model, requests, errors,
           input_tokens, output_tokens, cost, duration_ms_sum
    FROM folded
    ON CONFLICT (token_id, token_name, month, model) DO UPDATE SET
        requests = usage_monthly.requests + EXCLUDED.requests,
        errors = usage_monthly.errors + EXCLUDED.errors,
        input_tokens = usage_monthly.input_tokens + EXCLUDED.input_tokens,
        output_tokens = usage_monthly.output_tokens + EXCLUDED.output_tokens,
        cost = usage_monthly.cost + EXCLUDED.cost,
        duration_ms_sum = usage_monthly.duration_ms_sum + EXCLUDED.duration_ms_sum
    RETURNING 1
)
SELECT (SELECT count(*) FROM old) AS folded_rows
"""


async def compact_usage(
    pool, ttl_days: float = USAGE_TTL_DAYS, batch: int = BATCH_SIZE
) -> int:
    """Fold the rows older than `ttl_days` into usage_monthly. Returns how many rows were folded."""
    if ttl_days <= 0:
        return 0
    total = 0
    while True:
        async with pool.acquire() as connection:
            async with (
                connection.transaction()
            ):  # the rows leave one table as they enter the other
                count = await connection.fetchval(_FOLD, ttl_days * 86400, batch)
        total += count
        if count < batch:
            break
    if total:
        logfire.info(
            "Folded {count} usage rows older than {days} days",
            count=total,
            days=ttl_days,
        )
    return total


async def run_usage_compaction(
    pool,
    ttl_days: float = USAGE_TTL_DAYS,
    interval: float = USAGE_COMPACT_INTERVAL_SECONDS,
) -> None:
    if ttl_days <= 0:
        return
    while True:
        try:
            await compact_usage(pool, ttl_days)
        except asyncio.CancelledError:
            raise
        except Exception:
            logfire.exception("Folding usage rows failed")
        await asyncio.sleep(interval)
