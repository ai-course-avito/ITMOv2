from typing import Optional, Sequence, List
from ..context import PostgresConnectionWithContext
from ..models import RAG


class RAGMethods(PostgresConnectionWithContext):
    async def ensure_rag_partition(self, agent_id: Optional[int] = None) -> None:
        agent_id = agent_id or self.context.agent.id
        partition_name = f"rag_{agent_id}"
        query = f"""
            CREATE TABLE IF NOT EXISTS {partition_name}
            PARTITION OF rag FOR VALUES IN ({agent_id})
        """
        await self.execute(query, ())

    async def create_rag(
        self,
        content: str,
        embedding: List[float],
        metadata: Optional[dict] = None,
        agent_id: Optional[int] = None,
    ) -> RAG:
        agent_id = agent_id or self.context.agent.id
        await self.ensure_rag_partition(agent_id)

        query = """
            INSERT INTO rag (agent_id, content, embedding, metadata)
            VALUES ($1, $2, $3, $4)
            RETURNING id, agent_id, content, embedding, metadata, timestamp
        """

        return await self.fetch_one(
            query, (agent_id, content, embedding, metadata), RAG
        )

    async def get_rag_by_id(
        self,
        rag_id: int,
        include_embedding: bool = False,
        agent_id: Optional[int] = None,
    ) -> Optional[RAG]:
        agent_id = agent_id or self.context.agent.id
        await self.ensure_rag_partition(agent_id)

        query = f"""
            SELECT
                id,
                agent_id,
                content,
                {"NULL::vector AS" if not include_embedding else ""} embedding,
                metadata,
                timestamp
            FROM rag
            WHERE agent_id=$1
            AND id=$2
        """
        return await self.fetch_one(query, (agent_id, rag_id), RAG)

    async def get_similar_rag(
        self,
        embedding: List[float],
        limit: int = 10,
        include_embedding: bool = False,
        agent_id: Optional[int] = None,
    ) -> Sequence[RAG]:
        agent_id = agent_id or self.context.agent.id
        await self.ensure_rag_partition(agent_id)

        query = f"""
            SELECT
                id,
                agent_id,
                content,
                {"NULL::vector AS" if not include_embedding else ""} embedding,
                metadata,
                timestamp
            FROM rag
            WHERE agent_id=$1
            ORDER BY embedding <=> $2  -- cosine, what rag_embedding_idx is built for
            LIMIT $3
        """
        return (await self.fetch_all(query, (agent_id, embedding, limit), RAG)) or []

    async def get_all_rag(
        self,
        limit: int = 100,
        offset: int = 0,
        include_embedding: bool = False,
        agent_id: Optional[int] = None,
    ) -> Sequence[RAG]:
        """The entries of an agent in the order they were made (a stable order for paging)."""
        agent_id = agent_id or self.context.agent.id
        await self.ensure_rag_partition(agent_id)

        query = f"""
            SELECT
                id,
                agent_id,
                content,
                {"NULL::vector AS" if not include_embedding else ""} embedding,
                metadata,
                timestamp
            FROM rag
            WHERE agent_id=$1
            ORDER BY id ASC
            LIMIT $2 OFFSET $3
        """
        return (await self.fetch_all(query, (agent_id, limit, offset), RAG)) or []

    async def update_rag(
        self, rag: RAG, agent_id: Optional[int] = None
    ) -> Optional[RAG]:
        agent_id = agent_id or self.context.agent.id
        await self.ensure_rag_partition(agent_id)

        query = """
            UPDATE rag
            SET content = COALESCE($1, content),
                embedding = COALESCE($2, embedding),
                metadata = COALESCE($3, metadata)
            WHERE agent_id = $4
            AND id = $5
            RETURNING id, agent_id, content, embedding, metadata, timestamp
        """
        return await self.fetch_one(
            query,
            (
                rag.content,
                rag.embedding,
                rag.metadata,
                agent_id,
                rag.id,
            ),
            RAG,
        )

    async def delete_rag(
        self, rag_id: int, agent_id: Optional[int] = None
    ) -> Optional[RAG]:
        agent_id = agent_id or self.context.agent.id
        await self.ensure_rag_partition(agent_id)

        query = "DELETE FROM rag WHERE agent_id=$1 AND id=$2 RETURNING id, agent_id, content, embedding, metadata, timestamp"
        return await self.fetch_one(query, (agent_id, rag_id), RAG)
