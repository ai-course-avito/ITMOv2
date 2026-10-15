from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pydantic_ai import RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.toolsets import FunctionToolset

from services.memories import MEMORY_INSTRUCTIONS
from ..deps import RunDeps

memory_tools = FunctionToolset[RunDeps]()  # remember / recall / forget


@memory_tools.tool
async def remember(context: RunContext[RunDeps], fact: str) -> str:
    """Save a lasting fact about the user so it can be recalled in later conversations.

    Args:
        context: The call context.
        fact: One short, self-contained fact, e.g. "Prefers answers in Russian".
    """
    return await context.deps.memory.remember(context.deps.conversation, fact)


@memory_tools.tool
async def recall(context: RunContext[RunDeps], query: str = "") -> str:
    """Search the memories saved about the user, by meaning.

    Args:
        context: The call context.
        query: What to look for, in a few words. Leave empty to list the newest memories.
    """
    return await context.deps.memory.recall_text(context.deps.conversation, query)


@memory_tools.tool
async def forget(context: RunContext[RunDeps], memory_id: int) -> str:
    """Delete a memory that is outdated or wrong.

    Args:
        context: The call context.
        memory_id: The id shown in brackets next to the memory.
    """
    return await context.deps.memory.forget(context.deps.conversation, memory_id)


@dataclass
class Memory(AbstractCapability[RunDeps]):
    """The agent can remember, recall and forget facts about a person. The instructions are the same for every user (so they can be cached);
    what is remembered about this user goes in front of their message instead (see `PromptBuilder`)."""

    id: Optional[str] = "memory"

    def get_toolset(self) -> FunctionToolset[RunDeps]:
        return memory_tools

    def get_instructions(self) -> str:
        return MEMORY_INSTRUCTIONS
