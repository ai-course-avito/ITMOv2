"""Work that runs by itself: jobs that repeat, and tasks that are started and forgotten (but not lost, and stopped at shutdown)."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Optional, Set

import logfire

from core import metrics


class TaskSupervisor:
    """Keeps a reference to every fire-and-forget task (or it may vanish), and cancels what is left at shutdown."""

    def __init__(self) -> None:
        self._tasks: Set[asyncio.Task] = set()

    def spawn(self, work: Awaitable, name: Optional[str] = None) -> asyncio.Task:
        task = asyncio.ensure_future(work)
        if name and hasattr(task, "set_name"):
            task.set_name(name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    @property
    def running(self) -> int:
        return len(self._tasks)

    async def aclose(self) -> None:
        tasks, self._tasks = list(self._tasks), set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


class PeriodicJob:
    """Does `run_once` now and then until stopped; a failure is logged and the job goes on."""

    name = "job"

    def __init__(self, interval: float):
        self.interval = interval
        self._task: Optional[asyncio.Task] = None

    @property
    def enabled(self) -> bool:
        return True

    async def run_once(self) -> None:
        raise NotImplementedError

    async def _loop(self) -> None:
        while True:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logfire.exception("{job} failed", job=self.name)
            await asyncio.sleep(self.interval)

    def start(self) -> None:
        if self.enabled and self._task is None:
            self._task = asyncio.ensure_future(self._loop())

    async def aclose(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


class MessageRetentionJob(PeriodicJob):
    """Messages expire: a conversation older than the TTL is forgotten. Reading ignores expired messages at once; this deletes them, so the
    table does not grow forever."""

    name = "Deleting expired messages"
    BATCH = 10_000

    def __init__(self, pool, ttl_days: float, interval: float, batch: int = BATCH):
        super().__init__(interval)
        self.pool, self.ttl_days, self.batch = pool, ttl_days, batch

    @property
    def enabled(self) -> bool:
        return self.ttl_days > 0

    async def expire(self) -> int:
        """Delete the messages older than the TTL (in batches, so a large backlog does not hold locks for long); how many were deleted."""
        if self.ttl_days <= 0:
            return 0
        query = """
            DELETE FROM messages
            WHERE id IN (SELECT id FROM messages WHERE timestamp < now() - make_interval(secs => $1) LIMIT $2)
        """
        total = 0
        while True:
            async with self.pool.acquire() as connection:
                status = await connection.execute(query, self.ttl_days * 86400, self.batch)
            deleted = int(status.split()[-1])  # "DELETE <n>"
            total += deleted
            if deleted < self.batch:
                break
        if total:
            metrics.MESSAGES_EXPIRED.inc(total)
            logfire.info("Deleted {count} messages older than {days} days", count=total, days=self.ttl_days)
        return total

    async def run_once(self) -> None:
        await self.expire()



FOLD_QUERY = """
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


class UsageCompactionJob(PeriodicJob):
    """Usage rows are kept in detail for the TTL; older ones are folded into one row per token, month and model (usage_monthly), which is
    never deleted. Folding adds to the row that is already there, so it can run any number of times."""

    name = "Folding usage rows"
    BATCH = 20_000

    def __init__(self, pool, ttl_days: float, interval: float, batch: int = BATCH):
        super().__init__(interval)
        self.pool, self.ttl_days, self.batch = pool, ttl_days, batch

    @property
    def enabled(self) -> bool:
        return self.ttl_days > 0

    async def fold(self) -> int:
        """Fold the rows older than the TTL into usage_monthly; how many rows were folded."""
        if self.ttl_days <= 0:
            return 0
        total = 0
        while True:
            async with self.pool.acquire() as connection:
                async with connection.transaction():  # the rows leave one table as they enter the other
                    count = await connection.fetchval(FOLD_QUERY, self.ttl_days * 86400, self.batch)
            total += count
            if count < self.batch:
                break
        if total:
            logfire.info("Folded {count} usage rows older than {days} days", count=total, days=self.ttl_days)
        return total

    async def run_once(self) -> None:
        await self.fold()


class EmbeddingBackfillJob:
    """Gives the memories made before embeddings existed one, once at start. Of several replicas that start together one does it. It must
    never fail the start."""

    LOCK_ID = 7411001

    def __init__(self, pool, memories):
        self.pool, self.memories = pool, memories
        self._task: Optional[asyncio.Task] = None

    async def run_once(self) -> int:
        try:
            async with self.pool.acquire() as connection:
                if not await connection.fetchval("SELECT pg_try_advisory_lock($1)", self.LOCK_ID):
                    return 0  # another replica is at it
                try:
                    done = await self.memories.backfill()
                finally:
                    await connection.execute("SELECT pg_advisory_unlock($1)", self.LOCK_ID)
            if done:
                logfire.info("Added embeddings to {count} memories", count=done)
            return done
        except asyncio.CancelledError:
            raise
        except Exception:
            logfire.exception("Adding embeddings to old memories failed")
            return 0

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.ensure_future(self.run_once())

    async def aclose(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
