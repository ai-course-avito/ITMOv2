from __future__ import annotations

from typing import AsyncContextManager

from .database import Database


class UnitOfWork:
    """Several statements that stand or fall together:

        async with self.uow.transaction():
            await self.uow.lock(f"agent-versions:{agent_id}")
            ...

    A fresh block per use (the object is shared by concurrent requests, so it holds no state); nested blocks are savepoints; a lock is held
    to the end of the outermost block."""

    def __init__(self, database: Database):
        self.database = database

    def transaction(self) -> AsyncContextManager[None]:
        return self.database.transaction()

    async def lock(self, key: str) -> None:
        await self.database.lock(key)
