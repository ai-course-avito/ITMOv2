"""MCP servers attached to an agent, each isolated from the others and from the agent itself.

An MCP server is somebody else's service: it may be down, slow, or answer with an error. None of that may take the agent down:

- a server that cannot be reached gives the agent no tools (and a note in its instructions saying which server and why, so it can tell the
  user); it is left alone for MCP_DOWN_SECONDS (`mcp_health`, shared by all replicas with Redis);
- a call that does not get through (connection, timeout, a protocol error) is tried MCP_TOOL_ATTEMPTS times, then the model gets a FAILED tool
  result that says what the server answered (`ToolFailed`): the run goes on;
- a server that answers a call with an error of its own (the tool said it failed) is a failed result at once: the same call would fail the
  same way (`tool_error_behavior="failed"`).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import logfire
from fastmcp.client.transports import SSETransport
from pydantic_ai import ToolFailed
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.exceptions import ApprovalRequired, CallDeferred, ModelRetry
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.toolsets import AbstractToolset, CombinedToolset
from pydantic_ai.toolsets.wrapper import WrapperToolset

from core import metrics
from ..deps import RunDeps
from ..failures import describe_failure, server_label
from infrastructure.mcp_health import McpHealth, key_of

# Keys of an MCP server's config besides `url` and `transport`. Callbacks and clients cannot come from JSON.
MCP_OPTIONS = frozenset(
    {
        "headers",
        "id",
        "tool_prefix",
        "log_level",
        "timeout",
        "read_timeout",
        "max_retries",
        "cache_tools",
        "cache_resources",
        "allow_sampling",  # accepted so that old configs load; the service does not answer sampling requests
    }
)


def toolset_from_config(config: Dict[str, Any], default_retries: int = 3) -> MCPToolset:
    """The pydantic-ai toolset of an MCP server config (`url`, `transport`: streamable_http or sse, and MCP_OPTIONS)."""
    url, headers = config["url"], config.get("headers")
    client: Any = SSETransport(url, headers=headers) if config.get("transport") == "sse" else url
    options: Dict[str, Any] = {"tool_error_behavior": "failed", "max_retries": config.get("max_retries", default_retries)}
    for key, target in (("timeout", "init_timeout"), ("read_timeout", "read_timeout"), ("log_level", "log_level"), ("id", "id")):
        if key in config:
            options[target] = config[key]
    for key in ("cache_tools", "cache_resources"):
        if key in config:
            options[key] = config[key]
    if headers and not isinstance(client, SSETransport):
        options["headers"] = headers
    return MCPToolset(client, **options)


@dataclass
class ServerStatus:
    """What is known of one server in this run (shared by the copies pydantic-ai makes of a toolset)."""

    name: str
    url: str
    key: str
    down_because: Optional[str] = None

    @property
    def label(self) -> str:
        return f"{self.name} ({server_label(self.url)})"


@dataclass
class GuardedServer(WrapperToolset[RunDeps]):
    """One MCP server behind the rules above."""

    status: ServerStatus = field(default=None)  # type: ignore[assignment]
    health: McpHealth = field(default=None)  # type: ignore[assignment]
    attempts: int = 3
    retry_delay: float = 1.0

    async def _left_alone(self) -> bool:
        why = await self.health.why_down(self.status.key)
        self.status.down_because = why
        return why is not None

    async def _fail_server(self, exc: BaseException) -> None:
        why = describe_failure(exc)
        self.status.down_because = why
        await self.health.mark_down(self.status.key, why)
        metrics.MCP_SERVERS_DROPPED.inc()
        logfire.warning("MCP server unreachable, continuing without it: {server}: {why}", server=self.status.label, why=why)

    async def __aenter__(self):
        if not await self._left_alone():
            try:
                await self.wrapped.__aenter__()
            except Exception as exc:  # a failed connection raises exception groups
                await self._fail_server(exc)
        return self

    async def __aexit__(self, *args: Any):
        if self.status.down_because is None:
            return await self.wrapped.__aexit__(*args)
        return None

    async def get_tools(self, ctx):
        if await self._left_alone():
            return {}
        try:
            return await self.wrapped.get_tools(ctx)
        except Exception as exc:
            await self._fail_server(exc)
            return {}

    async def get_instructions(self, ctx):
        if self.status.down_because is None:
            return await super().get_instructions(ctx)
        return (
            f"The MCP server {self.status.label} cannot be reached right now ({self.status.down_because}), so its tools are missing from "
            "this answer. If what the user asks for needs it, say that the server is unavailable and why."
        )

    async def call_tool(self, name, tool_args, ctx, tool):
        last: BaseException = RuntimeError("no attempt was made")
        for attempt in range(1, self.attempts + 1):
            try:
                return await self.wrapped.call_tool(name, tool_args, ctx, tool)
            except (ToolFailed, ModelRetry, ApprovalRequired, CallDeferred):
                raise  # the server answered (an error of its own), or the model is to correct itself: not a failure to get through
            except Exception as exc:
                last = exc
                logfire.warning(
                    "MCP tool call failed ({attempt}/{total}): {tool} at {server}: {why}",
                    attempt=attempt,
                    total=self.attempts,
                    tool=name,
                    server=self.status.label,
                    why=describe_failure(exc),
                )
                if attempt < self.attempts:
                    await asyncio.sleep(self.retry_delay * attempt)
        metrics.MCP_TOOL_ERRORS.labels("failed").inc()
        raise ToolFailed(
            f"The MCP tool `{name}` of {self.status.label} could not be called: {self.attempts} attempts failed. "
            f"Last error: {describe_failure(last).rstrip('.')}. Go on without this tool and tell the user it failed."
        )


@dataclass(kw_only=True)  # AbstractCapability is a dataclass whose first field is `id`: positional arguments would land there
class McpServers(AbstractCapability[RunDeps]):
    """The MCP servers of an agent. `servers`: (name, config) of each."""

    servers: Sequence[tuple[str, Dict[str, Any]]] = ()
    health: McpHealth = None  # type: ignore[assignment]
    attempts: int = 3
    retry_delay: float = 1.0
    tool_retries: int = 3
    id: Optional[str] = "mcp-servers"
    guards: List[GuardedServer] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        for name, config in self.servers:
            status = ServerStatus(name, config["url"], key_of(config))
            self.guards.append(
                GuardedServer(toolset_from_config(config, self.tool_retries), status, self.health, self.attempts, self.retry_delay)
            )

    def get_toolset(self) -> Optional[AbstractToolset[RunDeps]]:
        return CombinedToolset(self.guards) if self.guards else None
