"""unit migrations tests"""

import asyncio
import json
import uuid
from pathlib import Path
import asyncpg
import pytest
from config import Settings
from infrastructure.postgres import (
    MIGRATIONS_DIR,
    apply_migrations,
    list_migrations,
)

DATABASE_CONFIG = Settings.from_env().database


def write_migrations(directory: Path, files: dict):
    for name, sql in files.items():
        (directory / name).write_text(sql)


BOOKKEEPING = """
CREATE TABLE migrations (id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1), version INTEGER NOT NULL);
INSERT INTO migrations (id, version) VALUES (1, 0);
CREATE TABLE applied (n INTEGER);
INSERT INTO applied VALUES (0);
"""


async def applied(connection):
    return [
        r["n"] for r in await connection.fetch("SELECT n FROM applied ORDER BY ctid")
    ]


def test_migration_files_are_numbered_without_gaps():
    numbers = [number for number, _ in list_migrations(MIGRATIONS_DIR)]
    assert numbers == list(range(len(numbers)))  # 0, 1, 2, ... in order


def test_list_migrations_sorts_numerically_and_ignores_other_files(tmp_path):
    write_migrations(
        tmp_path,
        {
            "10.sql": "",
            "2.sql": "",
            "0.sql": "",
            "notes.sql": "",
            "3.txt": "",
            "x1.sql": "",
        },
    )
    assert [n for n, _ in list_migrations(tmp_path)] == [0, 2, 10]


@pytest.mark.asyncio
async def test_migrations_apply_in_order_and_move_the_accumulator(scratch_db, tmp_path):
    write_migrations(
        tmp_path,
        {
            "0.sql": BOOKKEEPING,
            "1.sql": "INSERT INTO applied VALUES (1);",
            "2.sql": "INSERT INTO applied VALUES (2);",
            "10.sql": "INSERT INTO applied VALUES (10);",
        },
    )
    assert await apply_migrations(scratch_db, tmp_path) == 10
    assert await applied(scratch_db) == [0, 1, 2, 10]  # 2 before 10, not "10" < "2"
    assert await scratch_db.fetchval("SELECT version FROM migrations") == 10
    assert await scratch_db.fetchval("SELECT count(*) FROM migrations") == 1


@pytest.mark.asyncio
async def test_applied_migrations_are_not_run_again(scratch_db, tmp_path):
    write_migrations(
        tmp_path, {"0.sql": BOOKKEEPING, "1.sql": "INSERT INTO applied VALUES (1);"}
    )
    assert await apply_migrations(scratch_db, tmp_path) == 1
    assert await apply_migrations(scratch_db, tmp_path) == 1  # every start of the app
    assert await applied(scratch_db) == [0, 1]


@pytest.mark.asyncio
async def test_only_newer_migrations_run_when_files_are_added(scratch_db, tmp_path):
    write_migrations(
        tmp_path, {"0.sql": BOOKKEEPING, "1.sql": "INSERT INTO applied VALUES (1);"}
    )
    await apply_migrations(scratch_db, tmp_path)

    write_migrations(tmp_path, {"2.sql": "INSERT INTO applied VALUES (2);"})
    assert await apply_migrations(scratch_db, tmp_path) == 2
    assert await applied(scratch_db) == [0, 1, 2]


@pytest.mark.asyncio
async def test_migrations_at_or_below_the_accumulator_are_forgotten(
    scratch_db, tmp_path
):
    # a database that is already at version 5 never runs 3.sql or 5.sql
    await scratch_db.execute(BOOKKEEPING)
    await scratch_db.execute("UPDATE migrations SET version = 5")
    write_migrations(
        tmp_path,
        {
            "0.sql": "INSERT INTO applied VALUES (100);",
            "3.sql": "INSERT INTO applied VALUES (103);",
            "5.sql": "INSERT INTO applied VALUES (105);",
            "6.sql": "INSERT INTO applied VALUES (6);",
        },
    )
    assert await apply_migrations(scratch_db, tmp_path) == 6
    assert await applied(scratch_db) == [0, 6]


@pytest.mark.asyncio
async def test_failed_migration_rolls_back_and_keeps_the_accumulator(
    scratch_db, tmp_path
):
    write_migrations(
        tmp_path,
        {
            "0.sql": BOOKKEEPING,
            "1.sql": "INSERT INTO applied VALUES (1);",
            "2.sql": "INSERT INTO applied VALUES (2); SELECT * FROM no_such_table;",
            "3.sql": "INSERT INTO applied VALUES (3);",
        },
    )
    with pytest.raises(asyncpg.PostgresError):
        await apply_migrations(scratch_db, tmp_path)

    assert await scratch_db.fetchval("SELECT version FROM migrations") == 1
    assert await applied(scratch_db) == [0, 1]  # 2.sql left no trace, 3.sql never ran

    # fixed: it continues from where it stopped
    write_migrations(tmp_path, {"2.sql": "INSERT INTO applied VALUES (2);"})
    assert await apply_migrations(scratch_db, tmp_path) == 3
    assert await applied(scratch_db) == [0, 1, 2, 3]


@pytest.mark.asyncio
async def test_concurrent_starts_apply_each_migration_once(scratch_db, tmp_path):
    write_migrations(
        tmp_path,
        {
            "0.sql": BOOKKEEPING,
            "1.sql": "SELECT pg_sleep(0.5); INSERT INTO applied VALUES (1);",
        },
    )
    name = await scratch_db.fetchval("SELECT current_database()")
    others = [
        await asyncpg.connect(**{**DATABASE_CONFIG, "database": name}) for _ in range(2)
    ]
    try:
        results = await asyncio.gather(
            *(apply_migrations(c, tmp_path) for c in [scratch_db, *others])
        )
        assert results == [1, 1, 1]
        assert await applied(scratch_db) == [0, 1]
    finally:
        for c in others:
            await c.close()


@pytest.mark.asyncio
async def test_real_migrations_build_the_current_schema(scratch_db):
    last = list_migrations(MIGRATIONS_DIR)[-1][0]
    await scratch_db.execute("CREATE EXTENSION IF NOT EXISTS vector")
    assert await apply_migrations(scratch_db) == last

    tables = {
        r["tablename"]
        for r in await scratch_db.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"
        )
    }
    assert {
        "migrations",
        "models",
        "agents",
        "roles",
        "tokens",
        "usage_logs",
        "usage_monthly",
        "users",
        "messages",
        "rag",
        "mcp_servers",
        "agent_mcp_servers",
        "memories",
        "agent_versions",
    } <= tables

    columns = {
        r["column_name"]
        for r in await scratch_db.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name='agents'"
        )
    }
    assert {"config", "model_id"} <= columns
    assert not {"tools", "chat_limit", "store_history", "model"} & columns
    assert "units" not in tables  # access is a token of a role now
    assert (
        await scratch_db.fetchval(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name='agents' AND column_name='config'"
        )
        == """'{"tools": ["rag", "memory"]}'::jsonb"""
    )

    # running again, like a restart, changes nothing
    assert await apply_migrations(scratch_db) == last


@pytest.mark.asyncio
async def test_migration_4_moves_tools_and_chat_limit_into_config(scratch_db, tmp_path):
    for number, path in list_migrations(MIGRATIONS_DIR):
        if number <= 3:
            (tmp_path / path.name).write_text(path.read_text())
    await scratch_db.execute("CREATE EXTENSION IF NOT EXISTS vector")
    assert await apply_migrations(scratch_db, tmp_path) == 3

    await scratch_db.execute(
        'INSERT INTO models (id, request_json) VALUES (0, \'{"model": "a/b"}\')'
    )
    await scratch_db.execute(
        """INSERT INTO agents (prompt, model_id, chat_limit, tools) VALUES
           ('default', 0, 10, ARRAY['rag', 'memory']),
           ('custom', 0, 25, ARRAY['memory']),
           ('bare', 0, 10, ARRAY[]::text[])"""
    )

    (tmp_path / "4.sql").write_text((MIGRATIONS_DIR / "4.sql").read_text())
    assert await apply_migrations(scratch_db, tmp_path) == 4

    rows = await scratch_db.fetch("SELECT prompt, config FROM agents ORDER BY id")
    configs = {r["prompt"]: json.loads(r["config"]) for r in rows}
    assert configs == {
        "default": {"tools": ["rag", "memory"]},  # a default limit is not stored
        "custom": {"tools": ["memory"], "message_limit": 25},
        "bare": {"tools": []},
    }

    # new agents get the default config
    await scratch_db.execute("INSERT INTO agents (prompt, model_id) VALUES ('new', 0)")
    config = await scratch_db.fetchval("SELECT config FROM agents WHERE prompt='new'")
    assert json.loads(config) == {"tools": ["rag", "memory"]}


@pytest.mark.asyncio
async def test_concurrent_queries_on_one_database_object_do_not_collide():
    """Tools of an agent run concurrently: each query takes a connection of its own."""
    from repositories.database import Database
    from repositories.models import ModelRepository
    from world import world

    async with world() as w:
        models = w.get(ModelRepository)
        results = await asyncio.gather(
            *(models.list() for _ in range(40)),
            *(models.get(0) for _ in range(40)),
            *(models.insert({"model": f"a/{i}"}, f"m{i}") for i in range(20)),
        )
        assert len(results) == 100  # no "another operation is in progress"
        assert len(await models.list()) == 21  # model 0 + the 20 created


@pytest.mark.asyncio
async def test_api_database_is_at_the_latest_migration():
    last = list_migrations(MIGRATIONS_DIR)[-1][0]
    connection = await asyncpg.connect(**DATABASE_CONFIG)
    try:
        rows = await connection.fetch("SELECT version FROM migrations")
        assert [r["version"] for r in rows] == [last]
    finally:
        await connection.close()
