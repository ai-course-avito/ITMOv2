import asyncpg
import json

from pathlib import Path

from pgvector.asyncpg import register_vector
from pydantic import BaseModel
from typing import List, Optional, Sequence, Tuple, TypeVar, Type, Any
from repositories.database import map_value

T = TypeVar("T", bound=BaseModel)

MIGRATIONS_DIR = Path(__file__).parent.parent / "database" / "migrations"
# Arbitrary key of the advisory lock that serialises migrations between replicas.
MIGRATION_LOCK_ID = 7340216


def list_migrations(directory: Path = MIGRATIONS_DIR) -> List[Tuple[int, Path]]:
    """Migration files named <number>.sql, in ascending order of their number."""
    found = [(int(p.stem), p) for p in directory.glob("*.sql") if p.stem.isdigit()]
    return sorted(found)


async def apply_migrations(
    connection: asyncpg.Connection, directory: Path = MIGRATIONS_DIR
) -> int:
    """Apply every migration newer than the accumulator in the `migrations` table.

    The accumulator (one row, created by migration 0) holds the number of the
    last applied migration. Migrations with a number less than or equal to it are
    skipped; the others run in order, each in its own transaction together with
    the accumulator update. Returns the resulting version.
    """
    await connection.execute("SELECT pg_advisory_lock($1)", MIGRATION_LOCK_ID)
    try:
        current = -1
        if await connection.fetchval("SELECT to_regclass('migrations') IS NOT NULL"):
            version = await connection.fetchval(
                "SELECT version FROM migrations WHERE id = 1"
            )
            current = -1 if version is None else version

        for number, path in list_migrations(directory):
            if number <= current:
                continue
            async with connection.transaction():
                await connection.execute(path.read_text(encoding="utf-8"))
                await connection.execute(
                    "UPDATE migrations SET version = $1 WHERE id = 1", number
                )
            current = number

        return current
    finally:
        await connection.execute("SELECT pg_advisory_unlock($1)", MIGRATION_LOCK_ID)


async def _init_connection(conn):
    await register_vector(conn)


class PostgresPool:
    def __init__(self, config: dict):
        self.config = config
        self.pool: Optional[asyncpg.Pool] = None

    def __str__(self):
        return f"PostgresPool({self.config['database']})"

    async def __aenter__(self):
        bootstrap = await asyncpg.connect(**self.config)
        try:
            if not await bootstrap.fetchval(
                "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')"
            ):
                raise RuntimeError("Расширение vector не установлено в БД")
        finally:
            await bootstrap.close()

        self.pool = await asyncpg.create_pool(
            **self.config,
            init=_init_connection,
            statement_cache_size=0,
        )
        await self.run_migrations()
        await self.create_initial_model()

        return self

    async def __aexit__(self, *exc):
        await self.pool.close()

    async def close(self):
        await self.pool.close()

    async def run_migrations(self) -> int:
        async with self.pool.acquire() as connection:
            return await apply_migrations(connection)

    async def execute(
        self, connection: asyncpg.Connection, query: str, values=(), transaction=False
    ) -> None:
        if transaction:
            async with connection.transaction():
                await connection.execute(query, *map(map_value, values))
        else:
            await connection.execute(query, *map(map_value, values))

    async def create_initial_model(self):
        from core import DEFAULT_MODEL  # (the seed model: Settings.default_model_body once the container owns the pool)

        async with self.pool.acquire() as connection:
            model = await self.fetch_one(
                connection,
                "SELECT * FROM models WHERE id = $1",
                (0,),
            )

            if model:
                return

            await self.execute(
                connection,
                "INSERT INTO models (id, request_json) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                (0, DEFAULT_MODEL),
            )

    async def fetch_one(
        self,
        connection: asyncpg.Connection,
        query: str,
        values=(),
        pydantic_model: Optional[Type[T]] = None,
    ) -> Optional[T]:
        row = await connection.fetchrow(query, *map(map_value, values))

        using_model = pydantic_model or dict
        return using_model(**row) if row else None

    async def fetch_all(
        self,
        connection: asyncpg.Connection,
        query: str,
        values=(),
        pydantic_model: Optional[Type[T]] = None,
    ) -> Optional[Sequence[T]]:
        rows = await connection.fetch(query, *map(map_value, values))

        using_model = pydantic_model or dict
        return [using_model(**row) for row in rows] if rows else None
