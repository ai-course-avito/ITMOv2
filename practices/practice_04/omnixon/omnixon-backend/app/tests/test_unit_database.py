"""unit database tests"""

import asyncio
import contextlib
import json
import uuid
import pytest
from ai import memory as memory_module
from core import DATABASE_CONFIG

from shared import (
    scratch_database,
    scratch_pool,
    stored,
)


@pytest.mark.asyncio
async def test_slow_requests_do_not_hold_database_connections():
    """A request waits for the model most of the time; that must not use up the pool."""
    from database import Context, PostgresDB, PostgresPool

    name = f"pool_test_{uuid.uuid4().hex[:8]}"
    admin = await scratch_pool(name)
    try:
        async with PostgresPool({**DATABASE_CONFIG, "database": name}) as pool:
            size = pool.pool.get_max_size()

            async def request(i):
                async with PostgresDB(
                    pool, Context(agent=None, token=None, user=None)
                ) as db:
                    await db.get_model(0)
                    await asyncio.sleep(1)  # waiting for the model
                    return await db.get_model(0)

            started = asyncio.get_event_loop().time()
            results = await asyncio.wait_for(
                asyncio.gather(*(request(i) for i in range(size * 3))), timeout=10
            )
            assert all(r is not None for r in results)
            # all of them waited at the same time; with a connection held per
            # request they would have queued up behind each other
            assert asyncio.get_event_loop().time() - started < 4
    finally:
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()


@pytest.mark.asyncio
async def test_several_replicas_can_initialise_at_the_same_time():
    from database import PostgresPool

    name = f"init_test_{uuid.uuid4().hex[:8]}"
    admin = await scratch_pool(name)
    try:
        pools = [PostgresPool({**DATABASE_CONFIG, "database": name}) for _ in range(5)]
        # five services starting together: all of them migrate and seed model 0; none may fail
        await asyncio.gather(*(p.__aenter__() for p in pools))
        try:
            async with pools[0].pool.acquire() as connection:
                assert (
                    await connection.fetchval(
                        "SELECT count(*) FROM models WHERE id = 0"
                    )
                    == 1
                )
                assert await connection.fetchval("SELECT count(*) FROM roles") == 4
        finally:
            for p in pools:
                await p.__aexit__()
    finally:
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()


@pytest.mark.asyncio
async def test_deleting_an_agent_drops_its_rag_partition():
    from database import Context, PostgresDB, PostgresPool

    name = f"rag_test_{uuid.uuid4().hex[:8]}"
    admin = await scratch_pool(name)
    try:
        async with PostgresPool({**DATABASE_CONFIG, "database": name}) as pool:
            async with PostgresDB(
                pool, Context(agent=None, token=None, user=None)
            ) as db:
                agent = await db.create_agent("x", 0, name="a")
                await db.create_rag("doc", [0.1] * 1536, {}, agent.id)

                async def partitions():
                    rows = await db.fetch_all(
                        "SELECT tablename AS t FROM pg_tables WHERE tablename LIKE 'rag\\_%'"
                    )
                    return {r["t"] for r in rows or []}

                assert f"rag_{agent.id}" in await partitions()
                assert await db.delete_agent(agent.id) is not None
                assert f"rag_{agent.id}" not in await partitions()
                assert await db.delete_agent(agent.id) is None  # nothing left to drop
    finally:
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()


async def message_fixture(pool):
    """A user with messages of 10, 8, 6 and 1 days ago (and the context to read them)."""
    from core import INITIAL_API_KEY
    from database import Context, PostgresDB

    db = PostgresDB(pool, Context(agent=None, token=None, user=None))
    db.context.token = await db.ensure_initial_token(INITIAL_API_KEY)
    db.context.agent = await db.create_agent("x", 0, name="a")
    db.context.user = await db.create_user("ttl_user")
    db.context.chat = await db.ensure_default_chat()
    for days in (10, 8, 6, 1):
        await db.execute(
            "INSERT INTO messages (user_id, chat_id, content, timestamp) "
            "VALUES ($1, $4, $2, now() - make_interval(days => $3))",
            (db.context.user.id, {"type": "user", "content": f"{days} days ago"}, days, db.context.chat.id),
        )
    return db


@pytest.mark.asyncio
async def test_messages_older_than_the_ttl_are_not_read_and_are_deleted():
    from database import PostgresPool
    from database.retention import expire_messages

    name = f"ttl_test_{uuid.uuid4().hex[:8]}"
    admin = await scratch_pool(name)
    try:
        async with PostgresPool({**DATABASE_CONFIG, "database": name}) as pool:
            db = await message_fixture(pool)

            # a week (the default): the two oldest are forgotten even before they are deleted
            read = [m.content["content"] for m in await db.get_all_messages()]
            assert read == ["6 days ago", "1 days ago"]
            assert len(await stored(db)) == 4

            assert await expire_messages(pool.pool, ttl_days=7) == 2
            assert await stored(db) == ["6 days ago", "1 days ago"]
            assert (
                await expire_messages(pool.pool, ttl_days=7) == 0
            )  # nothing left to delete

            assert (
                await expire_messages(pool.pool, ttl_days=3) == 1
            )  # a shorter TTL deletes more
            assert await stored(db) == ["1 days ago"]
    finally:
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()


@pytest.mark.asyncio
async def test_a_ttl_of_zero_keeps_everything_and_big_backlogs_are_deleted_in_batches():
    from database import PostgresPool
    from database.retention import expire_messages

    name = f"ttl_batch_test_{uuid.uuid4().hex[:8]}"
    admin = await scratch_pool(name)
    try:
        async with PostgresPool({**DATABASE_CONFIG, "database": name}) as pool:
            db = await message_fixture(pool)
            assert await expire_messages(pool.pool, ttl_days=0) == 0
            assert len(await stored(db)) == 4

            for _ in range(5):  # more old messages than fit one batch
                await db.execute(
                    "INSERT INTO messages (user_id, chat_id, content, timestamp) VALUES ($1, $3, $2, now() - interval '30 days')",
                    (db.context.user.id, {"type": "user", "content": "ancient"}, db.context.chat.id),
                )
            assert (
                await expire_messages(pool.pool, ttl_days=7, batch=2) == 7
            )  # 2 + 2 + 2 + 1
            assert await stored(db) == ["6 days ago", "1 days ago"]
    finally:
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()


@pytest.mark.asyncio
async def test_the_retention_loop_deletes_now_and_stops_when_cancelled():
    from database import PostgresPool
    from database.retention import run_retention

    name = f"ttl_loop_test_{uuid.uuid4().hex[:8]}"
    admin = await scratch_pool(name)
    try:
        async with PostgresPool({**DATABASE_CONFIG, "database": name}) as pool:
            db = await message_fixture(pool)
            task = asyncio.create_task(
                run_retention(pool.pool, ttl_days=7, interval=0.1)
            )
            await asyncio.sleep(0.5)  # at start, then every 0.1s
            assert await stored(db) == ["6 days ago", "1 days ago"]

            await db.execute(
                "INSERT INTO messages (user_id, chat_id, content, timestamp) VALUES ($1, $3, $2, now() - interval '9 days')",
                (db.context.user.id, {"type": "user", "content": "late arrival"}, db.context.chat.id),
            )
            await asyncio.sleep(0.5)
            assert await stored(db) == ["6 days ago", "1 days ago"]

            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            assert task.cancelled()

            # a TTL of 0 means no loop at all
            assert (
                await asyncio.wait_for(run_retention(pool.pool, ttl_days=0), timeout=1)
                is None
            )
    finally:
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()


async def count_memories_of(db):
    return await db.count_memories(db.context.user.id, db.context.agent.id)


@pytest.mark.asyncio
async def test_a_transaction_commits_everything_or_nothing():
    async with scratch_database() as (pool, db):
        scope = (db.context.user.id, db.context.agent.id)

        async with db.transaction():
            await db.create_memory(*scope, "one")
            await db.create_memory(*scope, "two")
        assert await count_memories_of(db) == 2

        with pytest.raises(RuntimeError, match="halfway"):
            async with db.transaction():
                await db.create_memory(*scope, "three")
                await db.create_memory(*scope, "four")
                raise RuntimeError("halfway")
        assert await count_memories_of(db) == 2  # neither of the two was kept


@pytest.mark.asyncio
async def test_a_transaction_runs_on_one_connection_and_hides_its_work_until_commit():
    from database import Context, PostgresDB

    async with scratch_database() as (pool, db):
        scope = (db.context.user.id, db.context.agent.id)
        other = PostgresDB(pool, Context(agent=None, token=None, user=None))

        async with db.transaction():
            first = (await db.fetch_one("SELECT pg_backend_pid() AS pid"))["pid"]
            await db.create_memory(*scope, "uncommitted")
            second = (await db.fetch_one("SELECT pg_backend_pid() AS pid"))["pid"]
            assert first == second  # the same connection for the whole block
            assert await count_memories_of(db) == 1  # it sees its own work
            assert await other.count_memories(*scope) == 0  # nobody else does
        assert await other.count_memories(*scope) == 1


@pytest.mark.asyncio
async def test_other_tasks_do_not_run_inside_a_transaction_of_the_same_object():
    """The tools of an agent share the request's database object. A transaction of one
    of them must not drag the others onto its connection."""
    async with scratch_database() as (pool, db):
        scope = (db.context.user.id, db.context.agent.id)
        go, seen = asyncio.Event(), []

        async def bystander():
            await go.wait()
            seen.append(await count_memories_of(db))

        task = asyncio.create_task(bystander())  # started before the transaction
        async with db.transaction():
            await db.create_memory(*scope, "uncommitted")
            go.set()
            await asyncio.wait_for(
                task, timeout=5
            )  # not blocked by the open transaction
            assert seen == [0]  # and not part of it
        assert await count_memories_of(db) == 1


@pytest.mark.asyncio
async def test_an_inner_transaction_can_fail_alone():
    async with scratch_database() as (pool, db):
        scope = (db.context.user.id, db.context.agent.id)

        async with db.transaction():
            await db.create_memory(*scope, "outer")
            try:
                async with db.transaction():  # a savepoint
                    await db.create_memory(*scope, "inner")
                    raise ValueError("only the inner block fails")
            except ValueError:
                pass
            await db.create_memory(*scope, "after")

        contents = sorted(m.content for m in await db.get_memories(*scope))
        assert contents == ["after", "outer"]


@pytest.mark.asyncio
async def test_a_lock_needs_a_transaction_and_puts_work_in_line():
    async with scratch_database() as (pool, db):
        with pytest.raises(RuntimeError, match="transaction"):
            await db.lock("anything")

        inside, overlaps = [], []

        async def work(name):
            async with db.transaction():
                await db.lock("same thing")
                inside.append(name)
                if len(inside) > 1:
                    overlaps.append(name)
                await asyncio.sleep(0.1)
                inside.remove(name)

        await asyncio.gather(*(work(i) for i in range(5)))
        assert overlaps == []  # one at a time

        # different keys do not wait for each other
        started = asyncio.get_event_loop().time()

        async def other(key):
            async with db.transaction():
                await db.lock(key)
                await asyncio.sleep(0.3)

        await asyncio.gather(other("a"), other("b"), other("c"))
        assert asyncio.get_event_loop().time() - started < 0.8


@pytest.mark.asyncio
async def test_the_messages_of_concurrent_requests_do_not_interleave():
    async with scratch_database() as (pool, db):

        async def exchange(n):
            await db.create_messages(
                [
                    {"type": "user", "content": f"q{n}"},
                    {"type": "assistant", "content": f"a{n}"},
                ]
            )

        await asyncio.gather(*(exchange(n) for n in range(30)))

        rows = await db.fetch_all(
            "SELECT content FROM messages WHERE user_id=$1 ORDER BY id",
            (db.context.user.id,),
        )
        texts = [json.loads(r["content"])["content"] for r in rows]
        assert len(texts) == 60
        for i in range(0, 60, 2):  # every question is followed by its own answer
            assert texts[i].startswith("q") and texts[i + 1] == "a" + texts[i][1:], (
                texts[i : i + 2]
            )


@pytest.mark.asyncio
async def test_a_failing_pair_of_messages_is_not_half_written():
    async with scratch_database() as (pool, db):
        with pytest.raises(Exception):
            await db.create_messages(
                [
                    {"type": "user", "content": "q"},
                    {"type": "assistant", "content": object()},
                ]
            )
        assert await db.get_all_messages() == []


@pytest.mark.asyncio
async def test_concurrent_changes_of_an_agent_get_one_version_each():
    async with scratch_database() as (pool, db):
        agent_id = db.context.agent.id

        async def change(n):
            async with db.transaction():
                await db.lock(f"agent-versions:{agent_id}")
                await db.update_agent(agent_id, prompt=f"prompt {n}")
                await db.record_agent_version(agent_id, f"change {n}")

        await asyncio.gather(*(change(n) for n in range(12)))

        numbers = sorted(v.number for v in await db.get_agent_versions(agent_id))
        assert numbers == list(
            range(1, 14)
        )  # "created" and 12 changes: none lost, none repeated


@pytest.mark.asyncio
async def test_a_rollback_that_fails_halfway_changes_nothing():
    async with scratch_database() as (pool, db):
        agent_id = db.context.agent.id
        model = await db.create_model({"model": "a/b", "temperature": 0.1}, "m")
        await db.fetch_one(
            "UPDATE agents SET model_id=$1 WHERE id=$2 RETURNING id",
            (model.id, agent_id),
        )
        await db.record_agent_version(agent_id, "own model")  # version 2
        await db.update_agent(agent_id, prompt="second")
        await db.update_model(
            model.id, {"model": "a/b", "temperature": 0.9}
        )  # the model moved on
        await db.record_agent_version(agent_id, "changed")  # version 3

        models_before = len(await db.get_all_models())

        async def boom(*args, **kwargs):
            raise RuntimeError("fails after the agent was changed")

        db.record_agent_version = boom
        with pytest.raises(RuntimeError, match="fails"):
            await db.rollback_agent(
                agent_id, 2
            )  # needs a new model record for the old content

        agent = await db.get_agent(agent_id)
        assert agent.prompt == "second" and agent.model_id == model.id
        assert (
            len(await db.get_all_models()) == models_before
        )  # the new record was undone


@pytest.mark.asyncio
async def test_an_agent_and_its_first_version_are_created_together():
    async with scratch_database() as (pool, db):

        async def boom(*args, **kwargs):
            raise RuntimeError("no version")

        before = len(await db.get_all_agents())
        db.record_agent_version = boom
        with pytest.raises(RuntimeError):
            await db.create_agent("second", 0, name="a")
        assert len(await db.get_all_agents()) == before  # no agent without a version


@pytest.mark.asyncio
async def test_the_same_fact_learned_twice_at_once_is_saved_once():
    async with scratch_database() as (pool, db):
        scope = (db.context.user.id, db.context.agent.id)
        results = await asyncio.gather(
            *(memory_module.save_memory(db, scope, "Likes tea.") for _ in range(8))
        )
        assert sum(1 for _, is_new, _ in results if is_new) == 1
        assert [m.content for m in await db.get_memories(*scope)] == ["Likes tea."]


def test_only_coroutine_methods_are_wrapped_by_the_class_decorator():
    import inspect

    from core import async_logfire_class_decorator
    from database import PostgresDB

    @async_logfire_class_decorator
    class Example:
        def plain(self):
            return 42

        async def coroutine(self):
            return 43

        @contextlib.asynccontextmanager
        async def manager(self):
            yield 44

    assert Example().plain() == 42  # left alone: it was not made to need `await`
    assert not inspect.iscoroutinefunction(Example.plain)
    assert asyncio.run(Example().coroutine()) == 43

    async def use():
        async with Example().manager() as value:
            return value

    assert asyncio.run(use()) == 44
    assert not inspect.iscoroutinefunction(PostgresDB.transaction)  # a context manager
    assert inspect.iscoroutinefunction(PostgresDB.get_agent)


@pytest.mark.asyncio
async def test_recent_users_are_those_with_kept_messages_latest_first(monkeypatch):
    from database.mixins import user as user_mixin

    async with scratch_database("recent_users_test") as (pool, db):
        agent_id = db.context.agent.id
        other_agent = await pool.pool.fetchval(
            "INSERT INTO agents (prompt, model_id) VALUES ('', 0) RETURNING id"
        )

        async def user(external_id, agent=agent_id):
            return await pool.pool.fetchval(
                "INSERT INTO users (agent_id, external_id) VALUES ($1, $2) RETURNING id",
                agent,
                external_id,
            )

        async def said(user_id, days_ago, text="hi"):
            chat = await pool.pool.fetchval(
                "INSERT INTO chats (user_id, is_default) VALUES ($1, TRUE) ON CONFLICT (user_id) WHERE is_default DO UPDATE SET is_default = TRUE RETURNING id",
                user_id,
            )
            await pool.pool.execute(
                "INSERT INTO messages (user_id, chat_id, content, timestamp) VALUES ($1, $4, $2, now() - make_interval(days => $3))",
                user_id,
                json.dumps({"type": "user", "content": text}),
                days_ago,
                chat,
            )

        fresh, week_old, ancient, silent, foreign = [
            await user(n) for n in ("fresh", "week_old", "ancient", "silent")
        ] + [await user("foreign", other_agent)]
        await said(week_old, 6)
        await said(fresh, 1)
        await said(fresh, 0)
        await said(ancient, 8)  # older than the week: forgotten
        await said(foreign, 0)

        rows = await db.recent_users()
        assert [r.external_id for r in rows] == [
            "fresh",
            "week_old",
        ]  # the latest first; not the silent, the ancient, or another agent's
        assert (rows[0].messages, rows[1].messages) == (2, 1)
        assert rows[0].last_active > rows[1].last_active
        assert [r.external_id for r in await db.recent_users(limit=1)] == ["fresh"]

        # the TTL decides what is kept: a longer one brings the ancient back, 0 keeps everything
        monkeypatch.setattr(user_mixin, "MESSAGE_TTL_DAYS", 30)
        assert [r.external_id for r in await db.recent_users()] == [
            "fresh",
            "week_old",
            "ancient",
        ]
        monkeypatch.setattr(user_mixin, "MESSAGE_TTL_DAYS", 0)
        assert len(await db.recent_users()) == 3
