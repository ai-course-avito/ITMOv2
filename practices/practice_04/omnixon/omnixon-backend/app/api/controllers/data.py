from typing import List, Optional, Sequence

from fastapi import Body, Depends, Query

from api.controller import Controller, current_principal, endpoint
from api.schemas.knowledge import RAGCreate, RAGUpdate
from api.schemas.memories import MemoryCreate, MemoryUpdate
from api.schemas.usage import DailyUsage, MonthlyUsage
from database.models import RAG, Memory
from domain.access import Principal
from services.knowledge import KnowledgeService
from services.memories import MemoryService
from services.usage import UsageService


class MemoryController(Controller):
    prefix = "/api/v1/admin"
    tags = ["Admin API"]
    default_role = "user"

    def __init__(self, memories: MemoryService):
        self.memories = memories
        super().__init__()

    @endpoint.get("/memories", summary="List the memories of a user (newest first)")
    async def get_memories(
        self,
        user_id: str = Query(..., description="The user's external id"),
        agent_id: Optional[int] = Query(None, description="Agent ID"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
        query: Optional[str] = Query(
            None, description="Search by meaning (and by the words it contains) instead of listing the newest; the closest first"
        ),
        principal: Principal = Depends(current_principal),
    ) -> Sequence[Memory]:
        return await self.memories.list(principal, user_id, agent_id, limit, query)

    @endpoint.post("/memories", summary="Create a memory", status_code=201)
    async def create_memory(self, data: MemoryCreate = Body(...), principal: Principal = Depends(current_principal)) -> Memory:
        return await self.memories.create(principal, data)

    @endpoint.get("/memories/{memory_id}", summary="Get a memory by ID")
    async def get_memory(self, memory_id: int, principal: Principal = Depends(current_principal)) -> Memory:
        return await self.memories.get(principal, memory_id)

    @endpoint.patch("/memories/{memory_id}", summary="Update a memory")
    async def update_memory(self, memory_id: int, data: MemoryUpdate = Body(...), principal: Principal = Depends(current_principal)) -> Memory:
        return await self.memories.update(principal, memory_id, data.content)

    @endpoint.delete("/memories/{memory_id}", summary="Delete a memory")
    async def delete_memory(self, memory_id: int, principal: Principal = Depends(current_principal)) -> Memory:
        return await self.memories.delete(principal, memory_id)


class KnowledgeController(Controller):
    prefix = "/api/v1/admin"
    tags = ["Admin API"]
    default_role = "user"

    def __init__(self, knowledge: KnowledgeService):
        self.knowledge = knowledge
        super().__init__()

    @endpoint.get("/rag", summary="List RAG entries: all of the agent's, or the ones nearest to a query")
    async def search_rag(
        self,
        query: Optional[str] = Query(
            None,
            description="Search query text. Without it the entries of the agent are listed (newest last), paged by limit/offset",
        ),
        agent_id: Optional[int] = Query(None, description="Agent ID"),
        limit: int = Query(10, ge=1, le=1000, description="Maximum number of results"),
        offset: int = Query(0, ge=0, description="Skip entries (listing without a query only)"),
        include_embedding: bool = Query(False, description="Include embedding in results"),
        principal: Principal = Depends(current_principal),
    ) -> Sequence[RAG]:
        return await self.knowledge.search(principal, query, agent_id, limit, offset, include_embedding)

    @endpoint.post("/rag", summary="Create a RAG entry", status_code=201)
    async def create_rag(
        self, agent_id: Optional[int] = None, data: RAGCreate = Body(...), principal: Principal = Depends(current_principal)
    ) -> RAG:
        return await self.knowledge.create(principal, agent_id, data)

    @endpoint.get("/rag/{rag_id}", summary="Get a RAG entry by ID")
    async def get_rag(
        self,
        rag_id: int,
        agent_id: Optional[int] = Query(None, description="Agent ID"),
        include_embedding: bool = Query(False, description="Include embedding vector in response"),
        principal: Principal = Depends(current_principal),
    ) -> RAG:
        return await self.knowledge.get(principal, rag_id, agent_id, include_embedding)

    @endpoint.patch("/rag/{rag_id}", summary="Update a RAG entry")
    async def update_rag(
        self,
        rag_id: int,
        agent_id: Optional[int] = Query(None, description="Agent ID"),
        data: RAGUpdate = Body(...),
        principal: Principal = Depends(current_principal),
    ) -> RAG:
        return await self.knowledge.update(principal, rag_id, agent_id, data)

    @endpoint.delete("/rag/{rag_id}", summary="Delete a RAG entry")
    async def delete_rag(
        self, rag_id: int, agent_id: Optional[int] = Query(None, description="Agent ID"), principal: Principal = Depends(current_principal)
    ) -> RAG:
        return await self.knowledge.delete(principal, rag_id, agent_id)


class UsageController(Controller):
    """Usage of the models (no texts are kept)."""

    prefix = "/api/v1/admin"
    tags = ["Admin API"]
    default_role = "user"

    def __init__(self, usage: UsageService):
        self.usage = usage
        super().__init__()

    @endpoint.get("/usage", summary="Recent usage by day, token and model (the last USAGE_TTL_DAYS days are in detail)")
    async def get_usage(
        self,
        days: int = Query(30, ge=1, le=366, description="How many days back, counting today"),
        token_id: Optional[int] = Query(None, description="Only this token"),
        agent_id: Optional[int] = Query(None, description="Only the tokens of this agent"),
        principal: Principal = Depends(current_principal),
    ) -> List[DailyUsage]:
        return [DailyUsage(**row) for row in await self.usage.daily(principal, days, token_id, agent_id)]

    @endpoint.get("/usage/monthly", summary="Older usage, folded into one row per token, month and model")
    async def get_usage_monthly(
        self,
        token_id: Optional[int] = Query(None, description="Only this token"),
        agent_id: Optional[int] = Query(None, description="Only the tokens of this agent"),
        principal: Principal = Depends(current_principal),
    ) -> List[MonthlyUsage]:
        return [MonthlyUsage(**row) for row in await self.usage.monthly(principal, token_id, agent_id)]
