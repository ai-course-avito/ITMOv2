"""Saying what went wrong, for a model to read: the type, the code the server gave, the status and the body."""

from __future__ import annotations

from typing import List
from urllib.parse import urlsplit, urlunsplit

import httpx
import httpx2
from mcp.shared.exceptions import McpError

from core.errors import leaf_exceptions


def server_label(url: str) -> str:
    """The server's URL without what may hold a secret (`?token=`, user:password@)."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def describe_failure(exc: BaseException) -> str:
    """Everything known about why a call failed, in one line (the leaves of an exception group, each once)."""
    lines: List[str] = []
    for leaf in leaf_exceptions(exc):
        if isinstance(leaf, McpError):
            line = f"MCP error {leaf.error.code}: {leaf.error.message}"
        elif isinstance(leaf, (httpx.HTTPStatusError, httpx2.HTTPStatusError)):
            body = leaf.response.text.strip()[:500]
            line = f"HTTP {leaf.response.status_code} from the server" + (f": {body}" if body else "")
        else:
            line = f"{type(leaf).__name__}: {leaf}" if str(leaf) else type(leaf).__name__
        if line not in lines:
            lines.append(line)
    return "; ".join(lines) or type(exc).__name__
