import asyncio
import contextlib
import contextvars
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple, Type, TypeVar

import asyncpg
from pydantic import BaseModel

from .foundation import PostgresPool
from domain.chain import CallChain
from .models import Agent, Chat, Token, User

T = TypeVar("T", bound=BaseModel)


class Context(BaseModel):
    agent: Optional[Agent]  # the agent the request is about: the token's, or the one an admin acts as
    token: Optional[Token]  # who asks
    user: Optional[User]
    chat: Optional[Chat] = None  # the conversation the request is in
    chain: Optional[CallChain] = None  # set for an agent that another agent is asking: how the request got here


class _Pin:
    """The connection that a transaction holds, and who it belongs to."""

    def __init__(
        self, owner: "PostgresConnectionWithContext", connection: asyncpg.Connection
    ):
        self.owner = owner
        self.connection = connection
        self.lock = asyncio.Lock()  # one connection runs one query at a time


# What the current task is pinned to. A context variable, so a transaction is seen
# only by the code that runs inside its `async with` (and tasks started there), not by
# other tasks that use the same database object at the same time, e.g. the tools of an
# agent.
_pinned: contextvars.ContextVar[Optional[_Pin]] = contextvars.ContextVar(
    "pinned_connection", default=None
)


class PostgresConnectionWithContext:
    """Database access of one request, with the token, agent and user it is about.

    By default a connection is taken from the pool for the duration of one query
    only. A request spends most of its time waiting for the model, and holding a
    connection for that long would limit the service to as many concurrent requests
    as the pool has connections. It also lets the tools of an agent run queries
    concurrently.

    Where several statements must succeed or fail together, use a transaction:

        async with db.transaction():
            await db.update_agent(...)
            await db.record_agent_version(...)

    It takes one connection, keeps it for the block (keep the block short: no model
    calls in it) and commits at the end or rolls back when the block raises. Queries
    of the block run on that connection, in order; transactions nest (an inner one is
    a savepoint). Locks taken with `lock()` last until the outermost block ends.
    """

    def __init__(self, foundation: PostgresPool, context: Context):
        self.foundation = foundation
        self.context = context

    def with_context(self, **changes):
        """Database access for the same pool with a context that differs in `changes`: how a request goes on as another agent, user or chat
        (the context of this one is left as it is)."""
        return type(self)(self.foundation, self.context.model_copy(update=changes))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    @contextlib.asynccontextmanager
    async def transaction(self):
        pin = _pinned.get()
        if pin is not None and pin.owner is self:
            # a savepoint: its failure undoes only the inner block
            savepoint = pin.connection.transaction()
            async with pin.lock:  # the connection is not used by a query meanwhile
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

        async with self.foundation.pool.acquire() as connection:
            token = _pinned.set(_Pin(self, connection))
            try:
                async with connection.transaction():
                    yield
            finally:
                _pinned.reset(token)

    async def lock(self, key: str) -> None:
        """Wait for the advisory lock `key` and keep it until the end of the current
        transaction. Whoever asks for the same key waits for it: this puts work on the
        same thing (one user's messages, one agent's versions) in line. Needs a
        transaction."""
        pin = _pinned.get()
        if pin is None or pin.owner is not self:
            raise RuntimeError("lock() needs `async with db.transaction():`")
        await self.fetch_one(
            "SELECT pg_advisory_xact_lock(hashtextextended($1, 0)) AS locked", (key,)
        )

    @contextlib.asynccontextmanager
    async def _connection(self):
        pin = _pinned.get()
        if pin is not None and pin.owner is self:
            async with pin.lock:
                yield pin.connection
        else:
            async with self.foundation.pool.acquire() as connection:
                yield connection

    async def execute(self, query: str, values=(), transaction=False):
        async with self._connection() as connection:
            return await self.foundation.execute(connection, query, values, transaction)

    async def fetch_one(
        self,
        query: str,
        values=(),
        pydantic_model: Optional[Type[T]] = None,
    ) -> Optional[T]:
        async with self._connection() as connection:
            return await self.foundation.fetch_one(
                connection, query, values, pydantic_model
            )

    async def fetch_all(
        self,
        query: str,
        values=(),
        pydantic_model: Optional[Type[T]] = None,
    ) -> Optional[Sequence[T]]:
        async with self._connection() as connection:
            return await self.foundation.fetch_all(
                connection, query, values, pydantic_model
            )
