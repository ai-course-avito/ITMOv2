"""Which MCP servers are known to be down, so a request does not wait for one that answered nothing a moment ago.

Remembered for `down_seconds`. In the process only (`LocalHealthStore`), unless Redis is configured (`RedisHealthStore`): then every replica
of the api shares it (a server that one replica found dead is left alone by the others, and forgotten by all of them at once)."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Dict, Optional, Protocol, Tuple

import logfire
import redis.asyncio as redis


def key_of(config: dict) -> str:
    """A server is its config: the same url with other headers is another server. Only a fingerprint is kept (headers hold secrets)."""
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:24]


class HealthStore(Protocol):
    async def why_down(self, key: str) -> Optional[str]: ...
    async def mark_down(self, key: str, why: str, seconds: float) -> None: ...


class LocalHealthStore:
    def __init__(self) -> None:
        self._down: Dict[str, Tuple[float, str]] = {}  # key -> (until, why)

    async def why_down(self, key: str) -> Optional[str]:
        until, why = self._down.get(key, (0.0, ""))
        return why if until > time.monotonic() else None

    async def mark_down(self, key: str, why: str, seconds: float) -> None:
        self._down[key] = (time.monotonic() + seconds, why)


class RedisHealthStore:
    def __init__(self, client: redis.Redis):
        self.client = client

    async def why_down(self, key: str) -> Optional[str]:
        return await self.client.get(f"omnixon:mcp-down:{key}")

    async def mark_down(self, key: str, why: str, seconds: float) -> None:
        await self.client.set(f"omnixon:mcp-down:{key}", why, ex=max(1, int(seconds)))


class McpHealth:
    """The shared store when there is one (a failing Redis is logged and the process's own memory answers), else the process's own."""

    def __init__(self, down_seconds: float, shared: Optional[HealthStore] = None, local: Optional[HealthStore] = None):
        self.down_seconds = down_seconds
        self.shared = shared
        self.local = local or LocalHealthStore()

    async def why_down(self, key: str) -> Optional[str]:
        if self.shared is not None:
            try:
                return await self.shared.why_down(key)
            except redis.RedisError as error:
                logfire.warning("Redis: cannot read which MCP servers are down: {error}", error=str(error))
        return await self.local.why_down(key)

    async def mark_down(self, key: str, why: str) -> None:
        await self.local.mark_down(key, why, self.down_seconds)
        if self.shared is not None:
            try:
                await self.shared.mark_down(key, why, self.down_seconds)
            except redis.RedisError as error:
                logfire.warning("Redis: cannot remember an MCP server is down: {error}", error=str(error))
