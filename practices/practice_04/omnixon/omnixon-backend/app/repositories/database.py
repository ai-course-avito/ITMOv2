"""Database access: a connection per query, or one connection for a transaction.

A request spends its time waiting for the model, so by default a connection is taken from the pool for one query only; holding it
longer would limit the service to as many concurrent requests as the pool has connections, and would stop an agent's tools from running
queries at the same time. Where several statements must stand or fall together use `transaction()`: it takes one connection, keeps it for
the block (keep the block short: no model calls in it) and commits at the end or rolls back when the block raises. Only the code running in
the block (and tasks it starts) uses that connection; other tasks sharing this object keep taking their own.
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import json
from typing import Any, AsyncIterator, List, Optional, Type, TypeVar

import asyncpg
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def map_value(value: Any) -> Any:
    """What a Python value is when it is written: dicts and models as JSON."""
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, BaseModel):
        return value.model_dump_json(exclude_unset=True)
    return value


class _Pin:
    """The connection that a transaction holds, and who it belongs to."""

    def __init__(self, owner: "Database", connection: asyncpg.Connection):
        self.owner = owner
        self.connection = connection
        self.lock = asyncio.Lock()  # one connection runs one query at a time


_pinned: contextvars.ContextVar[Optional[_Pin]] = contextvars.ContextVar("pinned_connection", default=None)


class Database:
    def __init__(self, pool: Optional[asyncpg.Pool] = None):
        self.pool = pool  # the object graph is built before the service starts: the pool is bound at start-up

    def bind(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    def _pin(self) -> Optional[_Pin]:
        pin = _pinned.get()
        return pin if pin is not None and pin.owner is self else None

    @contextlib.asynccontextmanager
    async def _connection(self) -> AsyncIterator[asyncpg.Connection]:
        pin = self._pin()
        if pin is not None:
            async with pin.lock:
                yield pin.connection
        else:
            async with self.pool.acquire() as connection:
                yield connection

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        pin = self._pin()
        if pin is not None:  # a savepoint: its failure undoes only the inner block
            savepoint = pin.connection.transaction()
            async with pin.lock:
                await savepoint.start()
            try:
                yield
            except BaseException:
                async with pin.lock:
                    await savepoint.rollback()
                raise
            else:
                async with pin.lock:
                    await savepoint.commit()
            return

        async with self.pool.acquire() as connection:
            token = _pinned.set(_Pin(self, connection))
            try:
                async with connection.transaction():
                    yield
            finally:
                _pinned.reset(token)

    async def lock(self, key: str) -> None:
        """Wait for the advisory lock `key` and keep it until the end of the current transaction: whoever asks for the same key waits for it."""
        if self._pin() is None:
            raise RuntimeError("lock() needs a transaction")
        await self.fetch_one("SELECT pg_advisory_xact_lock(hashtextextended($1, 0)) AS locked", (key,))

    async def execute(self, query: str, values=()) -> None:
        async with self._connection() as connection:
            await connection.execute(query, *map(map_value, values))

    async def fetch_one(self, query: str, values=(), model: Optional[Type[T]] = None):
        async with self._connection() as connection:
            row = await connection.fetchrow(query, *map(map_value, values))
        return (model or dict)(**row) if row else None

    async def fetch_all(self, query: str, values=(), model: Optional[Type[T]] = None) -> List:
        async with self._connection() as connection:
            rows = await connection.fetch(query, *map(map_value, values))
        return [(model or dict)(**row) for row in rows]
