"""unit database layer tests: Database, transactions and UnitOfWork on a scratch database"""

import asyncio

import asyncpg
import pytest
import pytest_asyncio

from repositories.database import Database
from repositories.unit_of_work import UnitOfWork
from shared import scratch_database


@pytest_asyncio.fixture
async def database():
    async with scratch_database("db_layer") as (pool, _):
        await pool.pool.execute("CREATE TABLE things (id serial primary key, name text)")
        yield Database(pool.pool)


async def names(database):
    return [r["name"] for r in await database.fetch_all("SELECT name FROM things ORDER BY id")]


@pytest.mark.asyncio
async def test_a_failed_block_rolls_back(database):
    with pytest.raises(RuntimeError):
        async with database.transaction():
            await database.execute("INSERT INTO things (name) VALUES ($1)", ("a",))
            raise RuntimeError("boom")
    assert await names(database) == []
    async with database.transaction():
        await database.execute("INSERT INTO things (name) VALUES ($1)", ("b",))
    assert await names(database) == ["b"]


@pytest.mark.asyncio
async def test_a_failed_inner_block_undoes_only_itself(database):
    async with database.transaction():
        await database.execute("INSERT INTO things (name) VALUES ($1)", ("outer",))
        with pytest.raises(RuntimeError):
            async with database.transaction():
                await database.execute("INSERT INTO things (name) VALUES ($1)", ("inner",))
                raise RuntimeError("boom")
    assert await names(database) == ["outer"]


@pytest.mark.asyncio
async def test_other_tasks_do_not_use_the_pinned_connection(database):
    """Tasks that exist before the block (an agent's tools running while another part of the request is in a transaction) keep their own."""
    go = asyncio.Event()

    async def pid():
        await go.wait()
        return (await database.fetch_one("SELECT pg_backend_pid() AS pid"))["pid"]

    waiting = [asyncio.create_task(pid()) for _ in range(3)]
    async with database.transaction():
        inside = (await database.fetch_one("SELECT pg_backend_pid() AS pid"))["pid"]
        go.set()
        others = await asyncio.gather(*waiting)
        assert (await database.fetch_one("SELECT pg_backend_pid() AS pid"))["pid"] == inside
    assert inside not in others


@pytest.mark.asyncio
async def test_lock_puts_work_in_line_and_needs_a_transaction(database):
    with pytest.raises(RuntimeError, match="needs a transaction"):
        await database.lock("k")
    order = []

    async def work(label, pause):
        uow = UnitOfWork(database)
        async with uow.transaction():
            await uow.lock("same")
            order.append(f"{label} in")
            await asyncio.sleep(pause)
            order.append(f"{label} out")

    await asyncio.gather(work("a", 0.2), work("b", 0))
    assert order in (["a in", "a out", "b in", "b out"], ["b in", "b out", "a in", "a out"])


@pytest.mark.asyncio
async def test_fetch_all_of_nothing_is_an_empty_list_and_models_are_built(database):
    assert await database.fetch_all("SELECT * FROM things") == []
    await database.execute("INSERT INTO things (name) VALUES ($1)", ("a",))
    from pydantic import BaseModel

    class Thing(BaseModel):
        id: int
        name: str

    assert await database.fetch_one("SELECT * FROM things", model=Thing) == Thing(id=1, name="a")
    assert await database.fetch_one("SELECT * FROM things WHERE id = 99") is None


@pytest.mark.asyncio
async def test_dicts_are_written_as_json(database):
    await database.execute("CREATE TABLE docs (j jsonb)")
    await database.execute("INSERT INTO docs VALUES ($1)", ({"a": [1, "é"]},))
    assert (await database.fetch_one("SELECT j::text AS j FROM docs"))["j"] == '{"a": [1, "é"]}'
