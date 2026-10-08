from __future__ import annotations

from .database import Database


class UnitOfWork:
    """`async with uow:` is one transaction; `await uow.lock(key)` takes an advisory lock held to its end (nested blocks are savepoints)."""

    def __init__(self, database: Database):
        self.database = database
        self._blocks: list = []

    async def __aenter__(self) -> "UnitOfWork":
        block = self.database.transaction()
        await block.__aenter__()
        self._blocks.append(block)
        return self

    async def __aexit__(self, *exc) -> bool:
        return bool(await self._blocks.pop().__aexit__(*exc))

    async def lock(self, key: str) -> None:
        await self.database.lock(key)
