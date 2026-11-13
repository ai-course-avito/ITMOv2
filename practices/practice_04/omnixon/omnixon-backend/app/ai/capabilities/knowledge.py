from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pydantic_ai import RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.toolsets import FunctionToolset

from ..deps import RunDeps

tools = FunctionToolset[RunDeps]()


@tools.tool
async def retrieve(context: RunContext[RunDeps], search_query: str) -> str:
    """Retrieve documentation sections based on a search query.

    Args:
        context: The call context.
        search_query: The search query.
    """
    return await context.deps.knowledge.retrieve(context.deps.conversation, search_query)


@dataclass
class KnowledgeBase(AbstractCapability[RunDeps]):
    """The agent can search its own knowledge base (`rag_limit` entries per search)."""

    id: Optional[str] = "knowledge-base"

    def get_toolset(self) -> FunctionToolset[RunDeps]:
        return tools
