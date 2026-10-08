"""unit job tests: supervised tasks, periodic jobs, retention, folding of usage, the backfill"""

import asyncio

import pytest

from infrastructure.jobs import EmbeddingBackfillJob, MessageRetentionJob, PeriodicJob, TaskSupervisor, UsageCompactionJob
from shared import scratch_database


@pytest.mark.asyncio
async def test_a_supervised_task_is_kept_until_done_and_cancelled_at_close():
    supervisor = TaskSupervisor()
    done = asyncio.Event()

    async def quick():
        done.set()

    supervisor.spawn(quick(), "quick")
    await done.wait()
    await asyncio.sleep(0)
    assert supervisor.running == 0  # forgotten once finished

    cancelled = []

    async def forever():
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    supervisor.spawn(forever())
    await asyncio.sleep(0)
    assert supervisor.running == 1
    await supervisor.aclose()
    assert cancelled == [True] and supervisor.running == 0


@pytest.mark.asyncio
async def test_a_periodic_job_goes_on_after_a_failure_and_stops_when_closed():
    class Flaky(PeriodicJob):
        name = "flaky"

        def __init__(self):
            super().__init__(interval=0.01)
            self.runs = 0

        async def run_once(self):
            self.runs += 1
            if self.runs == 1:
                raise RuntimeError("boom")

    job = Flaky()
    job.start()
    for _ in range(100):
        if job.runs >= 3:
            break
        await asyncio.sleep(0.01)
    assert job.runs >= 3  # the failure did not end it
    await job.aclose()
    seen = job.runs
    await asyncio.sleep(0.05)
    assert job.runs == seen


def test_a_job_with_a_ttl_of_zero_is_not_started():
    assert MessageRetentionJob(None, 0, 1).enabled is False and UsageCompactionJob(None, 0, 1).enabled is False
    assert MessageRetentionJob(None, 7, 1).enabled and UsageCompactionJob(None, 30, 1).enabled


@pytest.mark.asyncio
async def test_expired_messages_are_deleted_in_batches():
    async with scratch_database("jobs_messages") as (pool, db):
        chat = await db.ensure_default_chat()
        for age in (10, 10, 10, 1):
            await pool.pool.execute(
                "INSERT INTO messages (user_id, chat_id, content, timestamp) VALUES ($1, $2, '{}', now() - make_interval(days => $3))",
                db.context.user.id, chat.id, age,
            )
        assert await MessageRetentionJob(pool.pool, 7, 1, batch=2).expire() == 3
        assert await pool.pool.fetchval("SELECT count(*) FROM messages") == 1
        assert await MessageRetentionJob(pool.pool, 0, 1).expire() == 0


@pytest.mark.asyncio
async def test_old_usage_is_folded_into_months_and_adds_to_what_is_there():
    async with scratch_database("jobs_usage") as (pool, db):
        for days in (40, 41, 1):
            await pool.pool.execute(
                """INSERT INTO usage_logs (token_id, token_name, agent_id, model, kind, status, duration_ms, input_tokens, output_tokens, cost, timestamp)
                   VALUES ($1, 't', $2, 'm', 'request', 'ok', 5, 3, 2, 0.5, now() - make_interval(days => $3))""",
                db.context.token.id, db.context.agent.id, days,
            )
        job = UsageCompactionJob(pool.pool, 30, 1, batch=1)
        assert await job.fold() == 2
        assert await pool.pool.fetchval("SELECT count(*) FROM usage_logs") == 1
        assert await pool.pool.fetchval("SELECT sum(requests) FROM usage_monthly") == 2
        assert await job.fold() == 0  # nothing left to fold: it can run any number of times


@pytest.mark.asyncio
async def test_the_backfill_never_fails_the_start_and_one_replica_does_it():
    class Memories:
        def __init__(self, fails=False):
            self.fails, self.calls = fails, 0

        async def backfill(self):
            self.calls += 1
            if self.fails:
                raise RuntimeError("embedding service down")
            return 3

    async with scratch_database("jobs_backfill") as (pool, _):
        assert await EmbeddingBackfillJob(pool.pool, Memories()).run_once() == 3
        assert await EmbeddingBackfillJob(pool.pool, Memories(fails=True)).run_once() == 0  # logged, not raised
        holder = await pool.pool.acquire()  # another replica holds the lock
        try:
            await holder.fetchval("SELECT pg_try_advisory_lock($1)", EmbeddingBackfillJob.LOCK_ID)
            memories = Memories()
            assert await EmbeddingBackfillJob(pool.pool, memories).run_once() == 0 and memories.calls == 0
        finally:
            await holder.execute("SELECT pg_advisory_unlock($1)", EmbeddingBackfillJob.LOCK_ID)
            await pool.pool.release(holder)
