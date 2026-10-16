"""Migration tests against a real PostgreSQL database.

Set TEST_POSTGRES_URL (e.g. postgresql+asyncpg://user@localhost/scratch_db) to a
throwaway database to run them; without it they are skipped.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL")
BACKEND_DIR = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="TEST_POSTGRES_URL is not set")


def alembic(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": POSTGRES_URL},
        capture_output=True,
        text=True,
        check=True,
    )


async def table_names() -> set[str]:
    engine = create_async_engine(POSTGRES_URL)
    try:
        async with engine.connect() as conn:
            return set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    finally:
        await engine.dispose()


async def test_upgrade_check_downgrade():
    alembic("downgrade", "base")

    alembic("upgrade", "head")
    tables = await table_names()
    assert {"users", "subscriptions"} <= tables

    alembic("upgrade", "head")  # re-running is a no-op
    alembic("check")  # no drift between models and migrations

    alembic("downgrade", "base")
    tables = await table_names()
    assert not {"users", "subscriptions"} & tables
