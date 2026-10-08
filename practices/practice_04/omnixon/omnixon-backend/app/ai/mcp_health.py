"""Which MCP servers are known to be down, so a request does not wait for one that answered nothing a moment ago.

Remembered for MCP_DOWN_SECONDS. In the process only, unless Redis is configured: then every replica of the api shares it (a server that one
replica found dead is left alone by the others, and forgotten by all of them at once)."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Dict, Optional, Tuple

import logfire
import redis.asyncio as redis

from core import MCP_DOWN_SECONDS


def key_of(config: dict) -> str:
    """A server is its config: the same url with other headers is another server. Only a fingerprint is kept (headers hold secrets)."""
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:24]


class McpHealth:
    def __init__(self) -> None:
        self._local: Dict[str, Tuple[float, str]] = {}  # key -> (until, why)
        self.client_of = lambda: None  # () -> a Redis client or None; set by the application at start

    def _redis(self) -> Optional[redis.Redis]:
        return self.client_of()

    async def why_down(self, key: str) -> Optional[str]:
        """Why the server is left alone for now, or None if it may be tried."""
        client = self._redis()
        if client is not None:
            try:
                return await client.get(f"omnixon:mcp-down:{key}")
            except redis.RedisError as error:
                logfire.warning("Redis: cannot read which MCP servers are down: {error}", error=str(error))
        until, why = self._local.get(key, (0.0, ""))
        return why if until > time.monotonic() else None

    async def mark_down(self, key: str, why: str) -> None:
        self._local[key] = (time.monotonic() + MCP_DOWN_SECONDS, why)
        client = self._redis()
        if client is not None:
            try:
                await client.set(f"omnixon:mcp-down:{key}", why, ex=max(1, int(MCP_DOWN_SECONDS)))
            except redis.RedisError as error:
                logfire.warning("Redis: cannot remember an MCP server is down: {error}", error=str(error))

    async def forget_all(self) -> None:
        self._local.clear()


health = McpHealth()
