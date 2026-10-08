from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.toolsets import FunctionToolset

from ..deps import Dependencies
from ..memory import MEMORY_INSTRUCTIONS, memory_tools


@dataclass
class Memory(AbstractCapability[Dependencies]):
    """The agent can remember, recall and forget facts about a person. The instructions are the same for every user (so they can be cached);
    what is remembered about this user goes in front of their message instead (see `runner.user_prompt`)."""

    id: Optional[str] = "memory"

    def get_toolset(self) -> FunctionToolset[Dependencies]:
        return memory_tools

    def get_instructions(self) -> str:
        return MEMORY_INSTRUCTIONS
