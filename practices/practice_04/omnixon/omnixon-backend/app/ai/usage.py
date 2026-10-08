"""Writing down what a call to the model cost: how long, how many tokens, how much money. Never the texts."""

import asyncio
import time
from dataclasses import dataclass
from typing import Iterable, Optional

import logfire
from pydantic_ai.messages import ModelMessage, ModelResponse

from core import error_response
from . import interrupt
from database import PostgresDB


@dataclass
class Spent:
    input_tokens: int = 0
    output_tokens: int = 0
    cost: Optional[float] = None  # None: the provider did not say


def spent_of(messages: Iterable[ModelMessage]) -> Spent:
    """The tokens and the money of the model's answers in `messages` (OpenRouter reports the cost when
    usage accounting is on, see generate_model)."""
    spent = Spent()
    for message in messages:
        if not isinstance(message, ModelResponse):
            continue
        spent.input_tokens += message.usage.input_tokens or 0
        spent.output_tokens += message.usage.output_tokens or 0
        cost = (message.provider_details or {}).get("cost")
        if isinstance(cost, (int, float)):
            spent.cost = (spent.cost or 0.0) + float(cost)
    return spent


class track_usage:
    """`async with track_usage(db, "request", "a/model") as usage: ...; usage.add(result.new_messages())`

    Writes one row when the block ends: ok, or what went wrong (the HTTP status the failure maps to, or
    `cancelled`). A failure to write is logged and never fails the request."""

    def __init__(self, db: PostgresDB, kind: str, model: str):
        self.db = db
        self.kind = kind
        self.model = model
        self.spent = Spent()
        self.started = 0.0

    def add(self, messages: Iterable[ModelMessage]) -> None:
        self.spent = spent_of(messages)

    async def __aenter__(self) -> "track_usage":
        self.started = time.monotonic()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if getattr(self.db.context, "token", None) is None:
            return
        if exc is None:
            status = "ok"
        elif (
            isinstance(exc, (asyncio.CancelledError, GeneratorExit))
            or type(exc).__name__ == "ClientDisconnected"
        ):
            stream = interrupt.current.get()
            status = (
                "interrupted"
                if stream is not None and stream.interrupted
                else "cancelled"
            )
        else:
            status = str(error_response(exc)[0])
        try:
            await self.db.record_usage(
                kind=self.kind,
                model=self.model,
                status=status,
                duration_ms=round((time.monotonic() - self.started) * 1000),
                input_tokens=self.spent.input_tokens,
                output_tokens=self.spent.output_tokens,
                cost=self.spent.cost,
            )
        except Exception as write_error:  # the answer matters more than its bookkeeping
            logfire.warning(
                "Could not record usage: {error}",
                error=str(write_error),
                _exc_info=write_error,
            )
