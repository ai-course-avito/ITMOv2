"""A call of an MCP tool never ends the agent's answer.

pydantic-ai turns a failed MCP tool call into `ModelRetry`, and after a few of those the whole run fails
("Tool ... exceeded max retries count"); a dropped connection fails it at once. Here every call goes through
`safe_tool_calls` (pydantic-ai's `process_tool_call` hook), and whatever happens the model gets a result:

- the server answered and the tool said it failed (`isError`): its text, at once. The same arguments would
  fail the same way; the model may call again with better ones.
- the call did not get through (connection, timeout, HTTP error, MCP protocol error): up to MCP_TOOL_ATTEMPTS
  attempts, the later ones over a new connection (the old one may be what broke), then a description of the
  failure (type, MCP error code, HTTP status and body) that the model can report.
"""

import asyncio
from typing import Any, Callable, Dict, List
from urllib.parse import urlsplit, urlunsplit

import httpx
import logfire
from mcp.shared.exceptions import McpError
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.mcp import MCPServer

from core import MCP_TOOL_ATTEMPTS, MCP_TOOL_RETRY_DELAY, metrics
from core.errors import leaf_exceptions


def server_label(url: str) -> str:
    """The server's URL without what may hold a secret (`?token=`, user:password@)."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def describe_failure(exc: BaseException) -> str:
    """Everything known about why a call did not get through, in one line."""
    lines: List[str] = []
    for leaf in leaf_exceptions(exc):
        if isinstance(leaf, McpError):
            line = f"MCP error {leaf.error.code}: {leaf.error.message}"
        elif isinstance(leaf, httpx.HTTPStatusError):
            body = leaf.response.text.strip()[:500]
            line = f"HTTP {leaf.response.status_code} from the MCP server" + (
                f": {body}" if body else ""
            )
        else:
            line = (
                f"{type(leaf).__name__}: {leaf}" if str(leaf) else type(leaf).__name__
            )
        if line not in lines:
            lines.append(line)
    return "; ".join(lines) or type(exc).__name__


def _refused(exc: ModelRetry) -> bool:
    """pydantic-ai raises ModelRetry both for a tool's own error and, from inside `except McpError`, for a
    protocol error (a closed connection, a timeout): only the first is an answer of the tool."""
    return not isinstance(exc.__context__, McpError)


def safe_tool_calls(
    config: Dict[str, Any], connect: Callable[[Dict[str, Any]], MCPServer]
):
    """`process_tool_call` for the MCP server made from `config`; `connect(config)` makes a new connection."""
    label = server_label(config["url"])

    async def process_tool_call(ctx, call_tool, name: str, args: Dict[str, Any]) -> Any:
        failure: BaseException = RuntimeError("no attempt was made")
        for attempt in range(1, MCP_TOOL_ATTEMPTS + 1):
            try:
                if attempt == 1:
                    return await call_tool(name, args)
                async with connect(config) as fresh:
                    return await fresh.direct_call_tool(name, args)
            except ModelRetry as exc:
                if _refused(exc):
                    metrics.MCP_TOOL_ERRORS.labels("refused").inc()
                    return f"The MCP tool `{name}` ({label}) answered with an error: {exc.message}"
                failure = exc.__context__
            except (
                Exception
            ) as exc:  # exception groups of a dropped connection are Exceptions too
                failure = exc
            logfire.warning(
                "MCP tool call failed ({attempt}/{total}): {tool} at {server}: {error}",
                attempt=attempt,
                total=MCP_TOOL_ATTEMPTS,
                tool=name,
                server=label,
                error=describe_failure(failure),
            )
            if attempt < MCP_TOOL_ATTEMPTS:
                await asyncio.sleep(MCP_TOOL_RETRY_DELAY * attempt)

        metrics.MCP_TOOL_ERRORS.labels("failed").inc()
        return (
            f"The MCP tool `{name}` ({label}) could not be called: {MCP_TOOL_ATTEMPTS} attempts failed. "
            f"Last error: {describe_failure(failure).rstrip('.')}. Go on without this tool and tell the user it failed."
        )

    return process_tool_call
