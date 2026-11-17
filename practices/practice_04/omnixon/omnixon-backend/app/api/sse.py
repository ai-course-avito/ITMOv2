"""Server-sent events: `event: user` with the user, then one `data:` event per text chunk (a JSON string), then `event: done` with the user, or
`event: error` with `{"detail": ...}`. With `trace`, `event: trace` events (one step of the chain of calls each) come in between, as the steps
finish. A stream that is stopped ends with `event: interrupted` (the user) instead of `done`."""

from __future__ import annotations

import json
from typing import AsyncIterator

from ai.events import TextChunk
from ai.trace import TraceStep
from services.conversations import DoneEvent, ErrorEvent, InterruptedEvent, StreamEvent, UserEvent


class SseStream:
    @staticmethod
    def line(event: str, payload: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    @classmethod
    def encode(cls, event: StreamEvent) -> str:
        if isinstance(event, TextChunk):
            return f"data: {json.dumps(event.text, ensure_ascii=False)}\n\n"
        if isinstance(event, TraceStep):
            return cls.line("trace", event.model_dump(exclude_none=True))
        if isinstance(event, UserEvent):
            return cls.line("user", json.loads(event.user.model_dump_json()))
        if isinstance(event, DoneEvent):
            return cls.line("done", json.loads(event.user.model_dump_json()))
        if isinstance(event, InterruptedEvent):
            return cls.line("interrupted", json.loads(event.user.model_dump_json()))
        if isinstance(event, ErrorEvent):
            return cls.line("error", {"detail": event.detail})
        raise TypeError(f"not a stream event: {event!r}")

    @classmethod
    async def lines(cls, events: AsyncIterator[StreamEvent]) -> AsyncIterator[str]:
        async for event in events:
            yield cls.encode(event)
