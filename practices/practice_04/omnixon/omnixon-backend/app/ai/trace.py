"""A readable chain of what happened during one request: every call to the model and
every tool the model called (the built-in ones, memory and the knowledge base, and the
tools of MCP servers), in order, with arguments, results, tokens and times.

Built from the messages of the run, so it costs nothing extra. It is only sent to the
client that asks for it (`trace: true`)."""

import json
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Sequence

from pydantic import BaseModel
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_core import to_jsonable_python

# a tool may return a whole document; the trace keeps a readable part of it
MAX_CHARS = 4000


class TraceStep(BaseModel):
    step: int  # 1, 2, 3 ... in the order the steps finished
    kind: Literal["model", "tool"]
    name: str  # the model, or the tool
    args: Optional[Any] = None  # arguments of a tool call
    result: Optional[Any] = None  # what a tool returned
    text: Optional[str] = None  # what the model wrote in that call
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None  # a tool that failed or was asked again


def clip(value: Any) -> Any:
    """JSON-safe and not huge: long values become a truncated string."""
    plain = to_jsonable_python(value, fallback=str)
    text = plain if isinstance(plain, str) else json.dumps(plain, ensure_ascii=False)
    if len(text) <= MAX_CHARS:
        return plain
    return text[:MAX_CHARS] + f"… ({len(text) - MAX_CHARS} more characters)"


def _ms(start: Optional[datetime], end: datetime) -> Optional[int]:
    if start is None:
        return None
    return max(0, round((end - start).total_seconds() * 1000))


class Tracer:
    """Turns the messages of a run into steps. Call `feed` with the messages so far
    (it remembers how far it got) and `finish` at the end."""

    def __init__(self) -> None:
        self._seen = 0
        self._count = 0
        self._last: Optional[datetime] = None  # when the model was last asked
        self._calls: Dict[str, tuple] = {}  # tool_call_id -> (name, args, called_at)

    def _step(self, **fields: Any) -> TraceStep:
        self._count += 1
        return TraceStep(step=self._count, **fields)

    def feed(self, messages: Sequence[ModelMessage]) -> List[TraceStep]:
        steps: List[TraceStep] = []
        for message in messages[self._seen :]:
            if isinstance(message, ModelRequest):
                for part in message.parts:
                    self._last = max(filter(None, (self._last, part.timestamp)), default=None)
                    if isinstance(part, (ToolReturnPart, RetryPromptPart)) and part.tool_call_id in self._calls:
                        name, args, called_at = self._calls.pop(part.tool_call_id)
                        failed = isinstance(part, RetryPromptPart)
                        steps.append(
                            self._step(
                                kind="tool",
                                name=name,
                                args=args,
                                result=None if failed else clip(part.content),
                                error=clip(part.content) if failed else None,
                                duration_ms=_ms(called_at, part.timestamp),
                            )
                        )
            elif isinstance(message, ModelResponse):
                text = "".join(p.content for p in message.parts if isinstance(p, TextPart))
                steps.append(
                    self._step(
                        kind="model",
                        name=message.model_name or "model",
                        text=text.strip() or None,
                        input_tokens=message.usage.input_tokens or None,
                        output_tokens=message.usage.output_tokens or None,
                        duration_ms=_ms(self._last, message.timestamp),
                    )
                )
                self._last = message.timestamp
                for part in message.parts:
                    if isinstance(part, ToolCallPart):
                        self._calls[part.tool_call_id] = (
                            part.tool_name,
                            clip(part.args_as_dict()),
                            message.timestamp,
                        )
        self._seen = len(messages)
        return steps

    def rewind(self, seen: int) -> None:
        """Forget messages after the first `seen`: they were dropped (an answer of the model whose tool calls never got their results)."""
        self._seen = min(self._seen, seen)

    def finish(self) -> List[TraceStep]:
        """Tool calls that never got an answer (the run ended first)."""
        steps = [
            self._step(kind="tool", name=name, args=args, error="no result")
            for name, args, _ in self._calls.values()
        ]
        self._calls.clear()
        return steps
