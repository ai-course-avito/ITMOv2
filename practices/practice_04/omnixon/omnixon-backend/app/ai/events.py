"""What happens while an agent answers, as the runner reports it."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence, Union

from .attachments import Attachment
from .trace import TraceStep


@dataclass(frozen=True)
class RunRequest:
    """What an agent is asked."""

    text: str
    attachments: Sequence[Attachment] = ()
    use_memo: bool = True  # give the model the previous messages of the chat (memory is the agent's tools' business)
    trace: bool = False  # also report the steps of the run
    stream: bool = True  # ask the provider for pieces (and report the text as it comes), or for whole answers
    kind: str = "request"  # for the usage rows: request | stream | agent_call


@dataclass(frozen=True)
class TextChunk:
    text: str


@dataclass
class Finished:
    """The last event: what the agent said, and the steps behind it (only if they were asked for)."""

    output: str
    trace: List[TraceStep] = field(default_factory=list)


RunEvent = Union[TextChunk, TraceStep, Finished]
