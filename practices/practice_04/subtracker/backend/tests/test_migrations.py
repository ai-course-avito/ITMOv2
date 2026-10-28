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


async def test_subscription_constraints_migration_keeps_data_and_enforces_rules():
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    alembic("downgrade", "base")
    alembic("upgrade", "c42cf1c11196")  # schema before the constraints revision

    engine = create_async_engine(POSTGRES_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO users (email, hashed_password, default_currency, plan)"
                    " VALUES ('m@example.com', 'x', 'USD', 'free')"
                )
            )
            await conn.execute(
                text(
                    "INSERT INTO subscriptions (owner_id, name, amount, billing_cycle,"
                    " custom_interval_days, is_active)"
                    " SELECT id, 'Old', 9.99, 'monthly', NULL, true FROM users"
                )
            )

        alembic("upgrade", "head")
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text("SELECT start_date, next_billing_date FROM subscriptions")
                )
            ).one()
        assert row.start_date is not None and row.next_billing_date is not None

        bad_rows = [
            "0, 'monthly', NULL",
            "5, 'daily', NULL",
            "5, 'monthly', 30",
            "5, 'custom_days', NULL",
            "5, 'custom_days', 3651",
        ]
        for values in bad_rows:
            with pytest.raises(IntegrityError):
                async with engine.begin() as conn:
                    await conn.execute(
                        text(
                            "INSERT INTO subscriptions (owner_id, name, amount,"
                            " billing_cycle, custom_interval_days, is_active,"
                            " start_date, next_billing_date)"
                            f" SELECT id, 'Bad', {values}, true, CURRENT_DATE,"
                            " CURRENT_DATE FROM users"
                        )
                    )

        async with engine.begin() as conn:  # date bounds (revision d3f5a9b2c6e1)
            with_bad_date = (
                "INSERT INTO subscriptions (owner_id, name, amount, billing_cycle,"
                " is_active, start_date, next_billing_date)"
                " SELECT id, 'Bad', 5, 'monthly', true, DATE '1999-12-31', CURRENT_DATE"
                " FROM users"
            )
        with pytest.raises(IntegrityError):
            async with engine.begin() as conn:
                await conn.execute(text(with_bad_date))

        alembic("downgrade", "-2")  # reversible, data stays
        async with engine.connect() as conn:
            count = (
                await conn.execute(text("SELECT count(*) FROM subscriptions"))
            ).scalar()
        assert count == 1
    finally:
        await engine.dispose()
        alembic("downgrade", "base")
