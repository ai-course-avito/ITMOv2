"""What to tell the client when a request fails."""

import asyncio
from typing import List, Tuple

import httpx
import httpx2
from pydantic_ai.exceptions import ModelHTTPError, ModelAPIError, UnexpectedModelBehavior

# pydantic-ai 2, the OpenAI SDK and FastMCP talk through httpx2; httpx is what the rest of Python uses
TIMEOUTS = (httpx.TimeoutException, httpx2.TimeoutException)
HTTP_ERRORS = (httpx.HTTPError, httpx2.HTTPError)


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
        if isinstance(leaf, TIMEOUTS):
            return 504, f"Upstream request timed out ({type(leaf).__name__})"
        if isinstance(leaf, asyncio.TimeoutError):
            return 504, "The request timed out"

    for leaf in leaves:
        if isinstance(leaf, (ModelHTTPError, ModelAPIError, UnexpectedModelBehavior)):
            return 502, f"Model provider error: {leaf}"
        if isinstance(leaf, HTTP_ERRORS):
            return 502, f"Upstream request failed ({type(leaf).__name__}): {leaf}"

    return 500, str(leaves[0]) if leaves else str(exc)
