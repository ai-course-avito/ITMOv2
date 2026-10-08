from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pydantic_ai import RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.toolsets import FunctionToolset

from core import DEFAULT_RAG_LIMIT
from ..deps import Dependencies
from ..utils import get_embedding_vector

tools = FunctionToolset[Dependencies]()


@tools.tool
async def retrieve(context: RunContext[Dependencies], search_query: str) -> str:
    """Retrieve documentation sections based on a search query.

    Args:
        context: The call context.
        search_query: The search query.
    """
    db = context.deps.db
    agent = db.context.agent
    embedding = await get_embedding_vector(search_query)
    rows = await db.get_similar_rag(embedding, agent.rag_limit if agent else DEFAULT_RAG_LIMIT)
    return "\n\n".join(f'<record id="{row.id}">\n{row.content}\n</record>' for row in rows)


@dataclass
class KnowledgeBase(AbstractCapability[Dependencies]):
    """The agent can search its own knowledge base (`rag_limit` entries per search)."""

    id: Optional[str] = "knowledge-base"

    def get_toolset(self) -> FunctionToolset[Dependencies]:
        return tools
