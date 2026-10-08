from __future__ import annotations

from typing import List, Optional

from database.models import RAG
from domain.access import AccessPolicy, Conversation, Principal
from domain.errors import Invalid, NotFound
from infrastructure.llm import Embedder
from repositories.data import KnowledgeRepository


class KnowledgeService:
    """The knowledge base of an agent: entries of text found by meaning."""

    def __init__(self, knowledge: KnowledgeRepository, embedder: Embedder, policy: AccessPolicy):
        self.knowledge, self.embedder, self.policy = knowledge, embedder, policy

    async def search(
        self, principal: Principal, query: Optional[str], agent_id: Optional[int], limit: int, offset: int, include_embedding: bool
    ) -> List[RAG]:
        agent_id = self.policy.agent_scope(principal, agent_id)
        if not query:
            return await self.knowledge.list(agent_id, limit, offset, include_embedding)
        if limit > 100:
            raise Invalid("limit above 100 is allowed without a query only")
        return await self.knowledge.nearest(agent_id, await self.embedder.embed(query), limit, include_embedding)

    async def create(self, principal: Principal, agent_id: Optional[int], data) -> RAG:
        agent_id = self.policy.agent_scope(principal, agent_id)
        embedding = await self.embedder.embed(data.embedding_content or data.content)
        return await self.knowledge.insert(agent_id, data.content, embedding, data.metadata)

    async def get(self, principal: Principal, rag_id: int, agent_id: Optional[int], include_embedding: bool) -> RAG:
        agent_id = self.policy.agent_scope(principal, agent_id)
        rag = await self.knowledge.get(agent_id, rag_id, include_embedding)
        if not rag:
            raise NotFound("RAG entry not found")
        return rag

    async def update(self, principal: Principal, rag_id: int, agent_id: Optional[int], data) -> RAG:
        agent_id = self.policy.agent_scope(principal, agent_id)
        rag = await self.knowledge.get(agent_id, rag_id)
        if not rag:
            raise NotFound("RAG entry not found")
        rag.content = data.content
        rag.embedding = await self.embedder.embed(data.embedding_content or data.content)
        rag.metadata = data.metadata or {}
        updated = await self.knowledge.update(agent_id, rag)
        if not updated:
            raise NotFound("RAG entry not found or update failed")
        return updated

    async def delete(self, principal: Principal, rag_id: int, agent_id: Optional[int]) -> RAG:
        agent_id = self.policy.agent_scope(principal, agent_id)
        rag = await self.knowledge.delete(agent_id, rag_id)
        if not rag:
            raise NotFound("RAG entry not found")
        return rag

    async def retrieve(self, conversation: Conversation, search_query: str) -> str:
        """What the agent's `retrieve` tool answers: the entries nearest to the query, `rag_limit` of them."""
        rows = await self.knowledge.nearest(conversation.agent.id, await self.embedder.embed(search_query), conversation.settings.rag_limit)
        return "\n\n".join(f'<record id="{row.id}">\n{row.content}\n</record>' for row in rows)
