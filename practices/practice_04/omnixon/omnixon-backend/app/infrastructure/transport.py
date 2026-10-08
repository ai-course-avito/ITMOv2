"""Retries of the HTTP request to a model provider, where they belong: under the model client, so a run never notices them.

A request that did not reach the provider (a connection that failed or timed out) or that the provider answered with a status that passes (408,
425, 429, 5xx) is sent again after a pause (the provider's `Retry-After` if it gave one, else doubling), up to UPSTREAM_RETRIES more times. The
last answer is handed on as it is, so the client still sees the provider's own status and reason. A response that is streaming is not touched once
it has started: what was already said cannot be unsaid.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import httpx2
import logfire

from core import UPSTREAM_RETRIES, UPSTREAM_RETRY_DELAY  # (the defaults; the gateway passes its own)

RETRYABLE_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
MAX_WAIT_SECONDS = 60.0


def retry_after(response: httpx2.Response) -> Optional[float]:
    """The pause the provider asked for (`Retry-After`: seconds, or a date), or None."""
    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        return max(0.0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return None


class RetryingTransport(httpx2.AsyncBaseTransport):
    def __init__(
        self,
        wrapped: httpx2.AsyncBaseTransport,
        retries: Optional[int] = None,
        delay: Optional[float] = None,
    ):
        self.wrapped = wrapped
        self.retries = UPSTREAM_RETRIES if retries is None else retries
        self.delay = UPSTREAM_RETRY_DELAY if delay is None else delay

    def _pause(self, attempt: int, response: Optional[httpx2.Response]) -> float:
        asked = retry_after(response) if response is not None else None
        return min(MAX_WAIT_SECONDS, asked if asked is not None else self.delay * 2 ** (attempt - 1))

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        attempt = 0
        while True:
            attempt += 1
            last = attempt > self.retries
            try:
                response = await self.wrapped.handle_async_request(request)
            except (httpx2.TransportError, OSError) as error:
                if last:
                    raise
                reason, response = type(error).__name__, None
            else:
                if last or response.status_code not in RETRYABLE_STATUSES:
                    return response
                reason = f"HTTP {response.status_code}"
                await response.aclose()
            wait = self._pause(attempt, response)
            logfire.warning(
                "Retrying a request to the model provider ({attempt}/{total}) in {wait}s: {reason}",
                attempt=attempt,
                total=self.retries,
                wait=wait,
                reason=reason,
            )
            await asyncio.sleep(wait)

    async def aclose(self) -> None:
        await self.wrapped.aclose()
