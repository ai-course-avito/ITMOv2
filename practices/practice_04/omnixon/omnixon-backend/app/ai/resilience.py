"""Keeping requests alive when what they depend on misbehaves.

- Failures of the model provider that are likely to pass (5xx, 429, timeouts, dropped
  connections) are retried after a pause that doubles each time.
- An MCP server that is down must not take the agent down with it: when a request
  fails because of one, the servers are probed, the dead ones are left out (and stay
  out for a while, so the next requests do not wait for them) and the request goes on
  with the rest.
"""

import asyncio
import time
from typing import Awaitable, Callable, Dict, Optional, Sequence, Set, Tuple, TypeVar

import httpx
import logfire
from mcp.shared.exceptions import McpError
from pydantic_ai.exceptions import (
    ModelAPIError,
    ModelHTTPError,
    UnexpectedModelBehavior,
)

from core import metrics
from .mcp_calls import describe_failure
from core import (
    MCP_DOWN_SECONDS,
    MCP_PROBE_TIMEOUT,
    UPSTREAM_RETRIES,
    UPSTREAM_RETRY_DELAY,
)
from core.errors import leaf_exceptions

T = TypeVar("T")

# (key of the server, the server) -- the key identifies a server by its config
ServerList = Sequence[Tuple[str, object]]

_RETRYABLE_STATUSES = {408, 409, 425, 429, 500, 502, 503, 504}

# key -> time until which the server is left out, and why
_down_until: Dict[str, float] = {}
_down_reason: Dict[str, str] = {}


def is_retryable(exc: BaseException) -> bool:
    """Would the same request probably work a moment later?"""
    for leaf in leaf_exceptions(exc):
        if isinstance(leaf, ModelHTTPError):
            if leaf.status_code in _RETRYABLE_STATUSES:
                return True
        elif isinstance(leaf, (ModelAPIError, UnexpectedModelBehavior)):
            return True  # connection problems, empty answers
        elif isinstance(leaf, (httpx.TimeoutException, httpx.TransportError)):
            return True
    return False


def is_mcp_failure(exc: BaseException) -> bool:
    """Does the failure come from talking to an MCP server?

    The model provider is reached through pydantic-ai's own exceptions; a bare httpx
    error or an MCP protocol error comes from the MCP client."""
    leaves = leaf_exceptions(exc)
    if any(isinstance(leaf, (ModelHTTPError, ModelAPIError)) for leaf in leaves):
        return False
    return any(isinstance(leaf, (httpx.HTTPError, McpError)) for leaf in leaves)


def is_down(key: str) -> bool:
    return _down_until.get(key, 0) > time.monotonic()


def mark_down(key: str, reason: str = "it could not be connected to") -> None:
    _down_until[key] = time.monotonic() + MCP_DOWN_SECONDS
    _down_reason[key] = reason


def down_reason(key: str) -> str:
    return _down_reason.get(key, "it could not be connected to")


def forget_down_servers() -> None:
    _down_until.clear()
    _down_reason.clear()


async def probe(server) -> Optional[str]:
    """None if the MCP server can be connected to, else what went wrong."""
    try:
        async with asyncio.timeout(MCP_PROBE_TIMEOUT):
            async with server:
                return None
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        return f"no answer within {MCP_PROBE_TIMEOUT:g} s"
    except BaseException as exc:  # a failed connection raises exception groups
        return describe_failure(exc)


async def find_dead_servers(servers: ServerList) -> Dict[str, str]:
    """key -> why, for the servers that cannot be connected to."""
    results = await asyncio.gather(*(probe(server) for _, server in servers))
    return {key: why for (key, _), why in zip(servers, results) if why is not None}


class Attempts:
    """The state of one request that may need several attempts."""

    def __init__(
        self, retries: int = UPSTREAM_RETRIES, delay: float = UPSTREAM_RETRY_DELAY
    ):
        self.retries = retries
        self.delay = delay
        self.retried = 0
        self.down: Set[str] = set()  # servers left out of this request
        self.reasons: Dict[str, str] = {}  # why they were

    def usable(self, key: str) -> bool:
        return key not in self.down and not is_down(key)

    def why_left_out(self, key: str) -> str:
        return self.reasons.get(key) or down_reason(key)

    async def after_failure(self, exc: BaseException, servers: ServerList) -> None:
        """Return if the request should be tried again, otherwise raise `exc`."""
        if servers and is_mcp_failure(exc):
            dead = await find_dead_servers(servers)
            fresh = set(dead) - self.down
            if fresh:
                self.down |= set(dead)
                self.reasons.update(dead)
                metrics.MCP_SERVERS_DROPPED.inc(len(fresh))
                for key, why in dead.items():
                    mark_down(key, why)
                logfire.warning(
                    "MCP server unreachable, continuing without it: {servers}",
                    servers=sorted(fresh),
                )
                return

        if self.retried >= self.retries or not is_retryable(exc):
            raise exc

        self.retried += 1
        metrics.UPSTREAM_RETRIES.inc()
        wait = self.delay * 2 ** (self.retried - 1)
        logfire.warning(
            "Retrying after a failure of the model provider ({attempt}/{total}) in {wait}s: {error}",
            attempt=self.retried,
            total=self.retries,
            wait=wait,
            error=str(exc)[:300],
        )
        await asyncio.sleep(wait)


async def run_with_attempts(
    build: Callable[[Attempts], Awaitable[Tuple[T, ServerList]]],
    call: Callable[[T], Awaitable],
    attempts: Attempts = None,
):
    """Build the agent and call it until it works or the failure is final.

    `build(attempts)` returns the agent and the MCP servers it was given."""
    attempts = attempts or Attempts()
    while True:
        agent, servers = await build(attempts)
        try:
            return await call(agent)
        except Exception as exc:
            await attempts.after_failure(exc, servers)
