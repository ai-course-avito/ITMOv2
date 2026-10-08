from typing import List, Optional, Sequence, Tuple

from ..context import PostgresConnectionWithContext
from ..models import Memory

# Everything but the embedding, which is not part of a Memory
COLUMNS = "id, user_id, agent_id, content, timestamp"


class MemoryMethods(PostgresConnectionWithContext):
    """Facts an agent remembers about a user. Scoped by (user_id, agent_id)."""

    async def get_memories(
        self,
        user_id: int,
        agent_id: int,
        limit: Optional[int] = None,
        query: Optional[str] = None,
    ) -> Sequence[Memory]:
        """Newest first. `query` keeps only memories containing it (case-insensitive)."""
        sql = f"""
            SELECT {COLUMNS} FROM memories
            WHERE user_id=$1 AND agent_id=$2
            AND ($3::text IS NULL OR position(lower($3) in lower(content)) > 0)
            ORDER BY id DESC
            LIMIT $4
        """
        return (
            await self.fetch_all(sql, (user_id, agent_id, query or None, limit), Memory)
        ) or []

    async def search_memories(
        self,
        user_id: int,
        agent_id: int,
        embedding: List[float],
        limit: int,
        max_distance: Optional[float] = None,
    ) -> List[Tuple[Memory, float]]:
        """The memories closest in meaning to `embedding`, with their cosine distance
        (0 is the same meaning, 2 the opposite), nearest first. Memories without an
        embedding are not found this way."""
        sql = f"""
            SELECT {COLUMNS}, embedding <=> $3 AS distance FROM memories
            WHERE user_id=$1 AND agent_id=$2 AND embedding IS NOT NULL
            AND ($4::float8 IS NULL OR embedding <=> $3 <= $4)
            ORDER BY embedding <=> $3
            LIMIT $5
        """
        rows = await self.fetch_all(
            sql, (user_id, agent_id, embedding, max_distance, limit)
        )
        return [
            (
                Memory(**{key: row[key] for key in row if key != "distance"}),
                row["distance"],
            )
            for row in rows or []
        ]

    async def count_memories(self, user_id: int, agent_id: int) -> int:
        row = await self.fetch_one(
            "SELECT count(*) AS n FROM memories WHERE user_id=$1 AND agent_id=$2",
            (user_id, agent_id),
        )
        return row["n"]

    async def get_memory(self, memory_id: int) -> Optional[Memory]:
        query = f"SELECT {COLUMNS} FROM memories WHERE id=$1"
        return await self.fetch_one(query, (memory_id,), Memory)

    async def create_memory(
        self,
        user_id: int,
        agent_id: int,
        content: str,
        embedding: Optional[List[float]] = None,
    ) -> Memory:
        query = f"""
            INSERT INTO memories (user_id, agent_id, content, embedding)
            VALUES ($1, $2, $3, $4)
            RETURNING {COLUMNS}
        """
        return await self.fetch_one(
            query, (user_id, agent_id, content, embedding), Memory
        )

    async def update_memory(
        self,
        memory_id: int,
        content: str,
        embedding: Optional[List[float]] = None,
    ) -> Optional[Memory]:
        """The embedding always follows the content: without a new one it is cleared."""
        query = f"UPDATE memories SET content=$1, embedding=$2 WHERE id=$3 RETURNING {COLUMNS}"
        return await self.fetch_one(query, (content, embedding, memory_id), Memory)

    async def delete_memory(
        self,
        memory_id: int,
        user_id: Optional[int] = None,
        agent_id: Optional[int] = None,
    ) -> Optional[Memory]:
        """Delete by id; `user_id` / `agent_id` restrict it to one user's / agent's memories."""
        query = f"""
            DELETE FROM memories
            WHERE id=$1
            AND ($2::bigint IS NULL OR user_id=$2)
            AND ($3::bigint IS NULL OR agent_id=$3)
            RETURNING {COLUMNS}
        """
        return await self.fetch_one(query, (memory_id, user_id, agent_id), Memory)

    async def memories_without_embedding(self, limit: int) -> Sequence[Memory]:
        query = f"SELECT {COLUMNS} FROM memories WHERE embedding IS NULL ORDER BY id LIMIT $1"
        return (await self.fetch_all(query, (limit,), Memory)) or []

    async def set_memory_embedding(
        self, memory_id: int, embedding: List[float]
    ) -> None:
        await self.execute(
            "UPDATE memories SET embedding=$1 WHERE id=$2", (embedding, memory_id)
        )
