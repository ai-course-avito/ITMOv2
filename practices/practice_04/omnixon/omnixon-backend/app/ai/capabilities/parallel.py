from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pydantic_ai.capabilities import AbstractCapability

from ..deps import RunDeps

PARALLEL_INSTRUCTIONS = (
    "When you need several tools and none of them needs the result of another, call all of them in the same turn instead of one after "
    "another: they run at the same time."
)


@dataclass(kw_only=True)  # AbstractCapability is a dataclass whose first field is `id`
class ParallelCalls(AbstractCapability[RunDeps]):
    """Tells the model it may call independent tools together. pydantic-ai already runs the calls of one turn at the same time; what a model
    does not do by itself is to ask for them together, and every turn it saves is a whole context sent again. The text is the same for every
    agent (it stays in the cacheable part of the prompt)."""

    id: Optional[str] = "parallel-calls"

    def get_instructions(self) -> str:
        return PARALLEL_INSTRUCTIONS
