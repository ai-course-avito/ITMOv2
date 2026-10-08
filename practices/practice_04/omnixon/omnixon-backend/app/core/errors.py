"""What to tell the client when a request fails."""

import asyncio
from typing import List, Tuple

import httpx
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior


def leaf_exceptions(exc: BaseException) -> List[BaseException]:
    """The exceptions inside (nested) exception groups, e.g. from anyio task groups."""
    if isinstance(exc, BaseExceptionGroup):
        return [leaf for inner in exc.exceptions for leaf in leaf_exceptions(inner)]
    return [exc]


def error_response(exc: BaseException) -> Tuple[int, str]:
    """(HTTP status, message) for an exception raised while handling a request.

    Failures of what the service talks to (the model provider, an MCP server) are
    502, or 504 for timeouts, rather than a bare 500: the service itself works.
    """
    leaves = leaf_exceptions(exc)

    for leaf in leaves:
        if isinstance(leaf, httpx.TimeoutException):
            return 504, f"Upstream request timed out ({type(leaf).__name__})"
        if isinstance(leaf, asyncio.TimeoutError):
            return 504, "The request timed out"

    for leaf in leaves:
        if isinstance(leaf, (ModelHTTPError, UnexpectedModelBehavior)):
            return 502, f"Model provider error: {leaf}"
        if isinstance(leaf, httpx.HTTPError):
            return 502, f"Upstream request failed ({type(leaf).__name__}): {leaf}"

    return 500, str(leaves[0]) if leaves else str(exc)
