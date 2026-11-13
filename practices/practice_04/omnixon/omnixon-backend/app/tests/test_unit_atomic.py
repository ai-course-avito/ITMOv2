"""unit tests of what must stand or fall together, what must not wait for what, and what a scratch database starts with"""

import asyncio
import contextlib
import inspect
import json
import uuid

import pytest

from api.schemas.agents import AgentCreate, AgentUpdate
from config import Settings
from domain.errors import NotFound
from infrastructure.jobs import MessageRetentionJob
from infrastructure.postgres import PostgresPool
from repositories.agents import AgentRepository
from repositories.database import Database
from repositories.models import ModelRepository
from repositories.people import ChatRepository, MessageRepository, UserRepository
from repositories.versions import VersionRepository
from services.agents import AgentService
from services.versions import VersionRecorder, VersionService
from shared import scratch_pool
from world import world

DATABASE = Settings.from_env().database


@pytest.mark.asyncio
async def test_slow_requests_do_not_hold_database_connections():
    """A request waits for the model most of the time; that must not use up the pool."""
    name = f"pool_test_{uuid.uuid4().hex[:8]}"
    admin = await scratch_pool(name)
    try:
        async with PostgresPool({**DATABASE, "database": name}) as pool:
            database = Database(pool.pool)
            size = pool.pool.get_max_size()

            async def request(i):
                await database.fetch_one("SELECT * FROM models WHERE id = 0")
                await asyncio.sleep(1)  # waiting for the model
                return await database.fetch_one("SELECT * FROM models WHERE id = 0")

            started = asyncio.get_event_loop().time()
            results = await asyncio.wait_for(asyncio.gather(*(request(i) for i in range(size * 3))), timeout=10)
            assert all(r is not None for r in results)
            # all of them waited at the same time; with a connection held per request they would have queued up behind each other
            assert asyncio.get_event_loop().time() - started < 4
    finally:
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()


@pytest.mark.asyncio
async def test_several_replicas_can_initialise_at_the_same_time():
    name = f"init_test_{uuid.uuid4().hex[:8]}"
    admin = await scratch_pool(name)
    try:
        pools = [PostgresPool({**DATABASE, "database": name}) for _ in range(5)]
        # five services starting together: all of them migrate and seed model 0; none may fail
        await asyncio.gather(*(p.__aenter__() for p in pools))
        try:
            async with pools[0].pool.acquire() as connection:
                assert await connection.fetchval("SELECT count(*) FROM models WHERE id = 0") == 1
                assert await connection.fetchval("SELECT count(*) FROM roles") == 4
        finally:
            for p in pools:
                await p.__aexit__()
    finally:
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()


async def messages_of_ages(w):
    """A user with messages of 10, 8, 6 and 1 days ago."""
    agent = await w.agent("ttl")
    user = await w.get(UserRepository).insert(agent.id, "ttl_user")
    chat = await w.get(ChatRepository).ensure_default(user.id)
    db = w.get(Database)
    for days in (10, 8, 6, 1):
        await db.execute(
            "INSERT INTO messages (user_id, chat_id, content, timestamp) VALUES ($1, $4, $2, now() - make_interval(days => $3))",
            (user.id, {"type": "user", "content": f"{days} days ago"}, days, chat.id),
        )
    return chat


async def kept(w):
    return [json.loads(r["content"])["content"] for r in await w.get(Database).fetch_all("SELECT content FROM messages ORDER BY id")]


@pytest.mark.asyncio
async def test_messages_older_than_the_ttl_are_not_read_and_are_deleted():
    async with world() as w:
        chat = await messages_of_ages(w)
        # a week (the default): the two oldest are forgotten even before they are deleted
        assert [m.content["content"] for m in await w.get(MessageRepository).window_of(chat.id, 10)] == ["6 days ago", "1 days ago"]
        assert len(await kept(w)) == 4
        job = MessageRetentionJob(w.get(Database).pool, 7, 1)
        assert await job.expire() == 2 and await kept(w) == ["6 days ago", "1 days ago"]
        assert await job.expire() == 0  # nothing left to delete
        assert await MessageRetentionJob(w.get(Database).pool, 3, 1).expire() == 1  # a shorter TTL deletes more
        assert await kept(w) == ["1 days ago"]


@pytest.mark.asyncio
async def test_a_ttl_of_zero_keeps_everything_and_reads_everything():
    async with world(message_ttl_days=0) as w:
        chat = await messages_of_ages(w)
        assert len(await w.get(MessageRepository).window_of(chat.id, 10)) == 4  # "0": nothing expires
        assert await MessageRetentionJob(w.get(Database).pool, 0, 1).expire() == 0 and len(await kept(w)) == 4


@pytest.mark.asyncio
async def test_the_retention_loop_deletes_now_and_stops_when_closed():
    async with world() as w:
        await messages_of_ages(w)
        job = MessageRetentionJob(w.get(Database).pool, 7, 0.1)
        job.start()
        await asyncio.sleep(0.5)  # at start, then every 0.1 s
        assert await kept(w) == ["6 days ago", "1 days ago"]
        await job.aclose()
        assert job._task is None


@pytest.mark.asyncio
async def test_concurrent_changes_of_an_agent_get_one_version_each():
    async with world() as w:
        agents, versions = w.get(AgentService), w.get(VersionRepository)
        admin = await w.principal("admin")
        agent = await agents.create(admin, AgentCreate(name="a", prompt="p", model_id=0))
        await asyncio.gather(*(agents.update(admin, agent.id, AgentUpdate(prompt=f"prompt {n}")) for n in range(12)))
        numbers = sorted(v.number for v in await versions.list(agent.id))
        assert numbers == list(range(1, 14))  # "created" and 12 changes: none lost, none repeated


@pytest.mark.asyncio
async def test_a_rollback_that_fails_halfway_changes_nothing(monkeypatch):
    async with world() as w:
        agents, models, versions = w.get(AgentService), w.get(ModelRepository), w.get(VersionService)
        admin = await w.principal("admin")
        model = await models.insert({"model": "a/b", "temperature": 0.1}, "m")
        agent = await agents.create(admin, AgentCreate(name="a", prompt="first", model_id=model.id))  # version 1
        await agents.update(admin, agent.id, AgentUpdate(prompt="second"))  # version 2
        await models.update(model.id, {"model": "a/b", "temperature": 0.9})  # the model moved on
        await w.get(VersionRecorder).record(agent.id, "changed", None)  # version 3
        before = len(await models.list())

        async def boom(*args, **kwargs):
            raise RuntimeError("fails after the agent was changed")

        monkeypatch.setattr(versions.recorder, "record", boom)
        with pytest.raises(RuntimeError, match="fails"):
            await versions.rollback(admin, agent.id, 1, None)  # needs a new model record for the old content
        current = await w.get(AgentRepository).get(agent.id)
        assert current.prompt == "second" and current.model_id == model.id
        assert len(await models.list()) == before  # the new record was undone


@pytest.mark.asyncio
async def test_an_agent_and_its_first_version_are_created_together(monkeypatch):
    async with world() as w:
        agents, repo = w.get(AgentService), w.get(AgentRepository)
        admin = await w.principal("admin")

        async def boom(*args, **kwargs):
            raise RuntimeError("no version")

        before = len(await repo.list())
        monkeypatch.setattr(agents.recorder, "record", boom)
        with pytest.raises(RuntimeError):
            await agents.create(admin, AgentCreate(name="second", prompt="p", model_id=0))
        assert len(await repo.list()) == before  # no agent without a version


@pytest.mark.asyncio
async def test_recent_users_are_those_with_kept_messages_latest_first():
    async with world() as w:
        users, db = w.get(UserRepository), w.get(Database)
        agent, other_agent = await w.agent("mine"), await w.agent("other")

        async def said(user, days_ago):
            chat = await w.get(ChatRepository).ensure_default(user.id)
            await db.execute(
                "INSERT INTO messages (user_id, chat_id, content, timestamp) VALUES ($1, $4, $2, now() - make_interval(days => $3))",
                (user.id, {"type": "user", "content": "hi"}, days_ago, chat.id),
            )

        fresh, week_old, ancient, silent = [await users.insert(agent.id, n) for n in ("fresh", "week_old", "ancient", "silent")]
        foreign = await users.insert(other_agent.id, "foreign")
        await said(week_old, 6)
        await said(fresh, 1)
        await said(fresh, 0)
        await said(ancient, 8)  # older than the week: forgotten
        await said(foreign, 0)
        recent = await users.recent(agent.id, 20, 7)
        assert [(u.external_id, u.messages) for u in recent] == [("fresh", 2), ("week_old", 1)]  # latest first; nobody silent, old or foreign
        assert [u.external_id for u in await users.recent(agent.id, 1, 7)] == ["fresh"]
        assert {u.external_id for u in await users.recent(agent.id, 20, 0)} == {"fresh", "week_old", "ancient"}  # a TTL of 0 keeps everything


def test_only_coroutine_methods_are_wrapped_by_the_class_decorator():
    from core import async_logfire_class_decorator

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
    assert not inspect.iscoroutinefunction(Database.transaction)  # a context manager
    assert inspect.iscoroutinefunction(AgentRepository.get)  # the repositories' coroutines are wrapped, and still coroutines


@pytest.mark.asyncio
async def test_the_unknown_agent_of_a_rollback_is_not_found():
    async with world() as w:
        with pytest.raises(NotFound, match="^Agent not found$"):
            await w.get(VersionService).rollback(await w.principal("admin"), 99999, 1, None)
