from fastapi import APIRouter, Request, Query, Body, HTTPException
from typing import Optional, Sequence
from pydantic import BaseModel
from ai import get_embedding
from database import PostgresDB, RAG
from access import default_agent_id
from core import async_logfire_decorator

router = APIRouter()


class RAGCreate(BaseModel):
    content: str
    embedding_content: Optional[str] = None
    metadata: Optional[dict] = None


class RAGUpdate(BaseModel):
    content: str
    embedding_content: Optional[str] = None
    metadata: Optional[dict] = None


# RAG


@router.get(
    "/rag",
    summary="List RAG entries: all of the agent's, or the ones nearest to a query",
)
@async_logfire_decorator
async def search_rag(
    request: Request,
    query: Optional[str] = Query(
        None,
        description="Search query text. Without it the entries of the agent are listed (newest last), paged by limit/offset",
    ),
    agent_id: Optional[int] = Query(None, description="Agent ID"),
    limit: int = Query(10, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(
        0, ge=0, description="Skip entries (listing without a query only)"
    ),
    include_embedding: bool = Query(False, description="Include embedding in results"),
) -> Sequence[RAG]:
    db: PostgresDB = request.state.db
    agent_id = default_agent_id(db, agent_id)
    if not query:
        return await db.get_all_rag(limit, offset, include_embedding, agent_id)
    if limit > 100:
        raise HTTPException(
            status_code=422, detail="limit above 100 is allowed without a query only"
        )
    embedding = await get_embedding(query)
    return await db.get_similar_rag(embedding, limit, include_embedding, agent_id)


@router.post("/rag", summary="Create a RAG entry", status_code=201)
@async_logfire_decorator
async def create_rag(
    request: Request, agent_id: Optional[int] = None, data: RAGCreate = Body(...)
) -> RAG:
    db: PostgresDB = request.state.db
    agent_id = default_agent_id(db, agent_id)
    embedding = await get_embedding(data.embedding_content or data.content)
    return await db.create_rag(data.content, embedding, data.metadata, agent_id)


@router.get("/rag/{rag_id}", summary="Get a RAG entry by ID")
@async_logfire_decorator
async def get_rag(
    request: Request,
    rag_id: int,
    agent_id: Optional[int] = Query(None, description="Agent ID"),
    include_embedding: bool = Query(
        False, description="Include embedding vector in response"
    ),
) -> RAG:
    db: PostgresDB = request.state.db
    agent_id = default_agent_id(db, agent_id)
    rag = await db.get_rag_by_id(rag_id, include_embedding, agent_id)
    if not rag:
        raise HTTPException(status_code=404, detail="RAG entry not found")
    return rag


@router.patch("/rag/{rag_id}", summary="Update a RAG entry")
@async_logfire_decorator
async def update_rag(
    request: Request,
    rag_id: int,
    agent_id: Optional[int] = Query(None, description="Agent ID"),
    data: RAGUpdate = Body(...),
) -> RAG:
    db: PostgresDB = request.state.db
    agent_id = default_agent_id(db, agent_id)
    rag = await db.get_rag_by_id(rag_id, agent_id=agent_id)
    if not rag:
        raise HTTPException(status_code=404, detail="RAG entry not found")
    embedding = await get_embedding(data.embedding_content or data.content)
    rag.content = data.content
    rag.embedding = embedding
    rag.metadata = data.metadata or {}
    updated = await db.update_rag(rag, agent_id)
    if not updated:
        raise HTTPException(
            status_code=404, detail="RAG entry not found or update failed"
        )
    return updated


@router.delete("/rag/{rag_id}", summary="Delete a RAG entry")
@async_logfire_decorator
async def delete_rag(
    request: Request,
    rag_id: int,
    agent_id: Optional[int] = Query(None, description="Agent ID"),
) -> RAG:
    db: PostgresDB = request.state.db
    agent_id = default_agent_id(db, agent_id)
    rag = await db.delete_rag(rag_id, agent_id)
    if not rag:
        raise HTTPException(status_code=404, detail="RAG entry not found")
    return rag
