from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from domain.entities import RAG, Memory
from .base import Repository

# Everything but the embedding, which is not part of a Memory
MEMORY_COLUMNS = "id, user_id, agent_id, content, timestamp"


class MemoryRepository(Repository):
    """Facts an agent remembers about a user, scoped by (user_id, agent_id)."""

    async def newest(self, user_id: int, agent_id: int, limit: Optional[int] = None, query: Optional[str] = None) -> List[Memory]:
        """Newest first. `query` keeps only memories containing it (case-insensitive)."""
        return await self.db.fetch_all(
            f"""
            SELECT {MEMORY_COLUMNS} FROM memories
            WHERE user_id=$1 AND agent_id=$2
            AND ($3::text IS NULL OR position(lower($3) in lower(content)) > 0)
            ORDER BY id DESC
            LIMIT $4
            """,
            (user_id, agent_id, query or None, limit),
            Memory,
        )

    async def nearest(
        self, user_id: int, agent_id: int, embedding: List[float], limit: int, max_distance: Optional[float] = None
    ) -> List[Tuple[Memory, float]]:
        """The memories closest in meaning to `embedding`, with their cosine distance, nearest first (those without an embedding are not found)."""
        rows = await self.db.fetch_all(
            f"""
            SELECT {MEMORY_COLUMNS}, embedding <=> $3 AS distance FROM memories
            WHERE user_id=$1 AND agent_id=$2 AND embedding IS NOT NULL
            AND ($4::float8 IS NULL OR embedding <=> $3 <= $4)
            ORDER BY embedding <=> $3
            LIMIT $5
            """,
            (user_id, agent_id, embedding, max_distance, limit),
        )
        return [(Memory(**{k: v for k, v in row.items() if k != "distance"}), row["distance"]) for row in rows]

    async def count(self, user_id: int, agent_id: int) -> int:
        row = await self.db.fetch_one("SELECT count(*) AS n FROM memories WHERE user_id=$1 AND agent_id=$2", (user_id, agent_id))
        return row["n"]

    async def get(self, memory_id: int) -> Optional[Memory]:
        return await self.db.fetch_one(f"SELECT {MEMORY_COLUMNS} FROM memories WHERE id=$1", (memory_id,), Memory)

    async def insert(self, user_id: int, agent_id: int, content: str, embedding: Optional[List[float]] = None) -> Memory:
        return await self.db.fetch_one(
            f"INSERT INTO memories (user_id, agent_id, content, embedding) VALUES ($1, $2, $3, $4) RETURNING {MEMORY_COLUMNS}",
            (user_id, agent_id, content, embedding),
            Memory,
        )

    async def update(self, memory_id: int, content: str, embedding: Optional[List[float]] = None) -> Optional[Memory]:
        """The embedding always follows the content: without a new one it is cleared."""
        return await self.db.fetch_one(
            f"UPDATE memories SET content=$1, embedding=$2 WHERE id=$3 RETURNING {MEMORY_COLUMNS}", (content, embedding, memory_id), Memory
        )

    async def delete(self, memory_id: int, user_id: Optional[int] = None, agent_id: Optional[int] = None) -> Optional[Memory]:
        """Delete by id; `user_id` / `agent_id` restrict it to one user's / agent's memories."""
        return await self.db.fetch_one(
            f"""
            DELETE FROM memories
            WHERE id=$1 AND ($2::bigint IS NULL OR user_id=$2) AND ($3::bigint IS NULL OR agent_id=$3)
            RETURNING {MEMORY_COLUMNS}
            """,
            (memory_id, user_id, agent_id),
            Memory,
        )

    async def without_embedding(self, limit: int) -> List[Memory]:
        return await self.db.fetch_all(
            f"SELECT {MEMORY_COLUMNS} FROM memories WHERE embedding IS NULL ORDER BY id LIMIT $1", (limit,), Memory
        )

    async def set_embedding(self, memory_id: int, embedding: List[float]) -> None:
        await self.db.execute("UPDATE memories SET embedding=$1 WHERE id=$2", (embedding, memory_id))


_RAG_COLUMNS = "id, agent_id, content, {embedding} embedding, metadata, timestamp"


def _columns(include_embedding: bool) -> str:
    return _RAG_COLUMNS.format(embedding="" if include_embedding else "NULL::vector AS")


class KnowledgeRepository(Repository):
    """The knowledge base of an agent: a table partitioned by agent (`rag_<agent_id>`, made when first needed)."""

    async def ensure_partition(self, agent_id: int) -> None:
        await self.db.execute(f"CREATE TABLE IF NOT EXISTS rag_{int(agent_id)} PARTITION OF rag FOR VALUES IN ({int(agent_id)})")

    async def insert(self, agent_id: int, content: str, embedding: List[float], metadata: Optional[dict] = None) -> RAG:
        await self.ensure_partition(agent_id)
        return await self.db.fetch_one(
            "INSERT INTO rag (agent_id, content, embedding, metadata) VALUES ($1, $2, $3, $4) "
            "RETURNING id, agent_id, content, embedding, metadata, timestamp",
            (agent_id, content, embedding, metadata),
            RAG,
        )

    async def get(self, agent_id: int, rag_id: int, include_embedding: bool = False) -> Optional[RAG]:
        await self.ensure_partition(agent_id)
        return await self.db.fetch_one(
            f"SELECT {_columns(include_embedding)} FROM rag WHERE agent_id=$1 AND id=$2", (agent_id, rag_id), RAG
        )

    async def nearest(self, agent_id: int, embedding: List[float], limit: int = 10, include_embedding: bool = False) -> List[RAG]:
        await self.ensure_partition(agent_id)
        return await self.db.fetch_all(
            f"""
            SELECT {_columns(include_embedding)} FROM rag
            WHERE agent_id=$1
            ORDER BY embedding <=> $2  -- cosine, what rag_embedding_idx is built for
            LIMIT $3
            """,
            (agent_id, embedding, limit),
            RAG,
        )

    async def list(self, agent_id: int, limit: int = 100, offset: int = 0, include_embedding: bool = False) -> List[RAG]:
        """The entries in the order they were made (a stable order for paging)."""
        await self.ensure_partition(agent_id)
        return await self.db.fetch_all(
            f"SELECT {_columns(include_embedding)} FROM rag WHERE agent_id=$1 ORDER BY id ASC LIMIT $2 OFFSET $3",
            (agent_id, limit, offset),
            RAG,
        )

    async def update(self, agent_id: int, rag: RAG) -> Optional[RAG]:
        await self.ensure_partition(agent_id)
        return await self.db.fetch_one(
            """
            UPDATE rag
            SET content = COALESCE($1, content), embedding = COALESCE($2, embedding), metadata = COALESCE($3, metadata)
            WHERE agent_id = $4 AND id = $5
            RETURNING id, agent_id, content, embedding, metadata, timestamp
            """,
            (rag.content, rag.embedding, rag.metadata, agent_id, rag.id),
            RAG,
        )

    async def delete(self, agent_id: int, rag_id: int) -> Optional[RAG]:
        await self.ensure_partition(agent_id)
        return await self.db.fetch_one(
            "DELETE FROM rag WHERE agent_id=$1 AND id=$2 RETURNING id, agent_id, content, embedding, metadata, timestamp",
            (agent_id, rag_id),
            RAG,
        )


def _plain(row: Dict[str, Any]) -> Dict[str, Any]:
    """JSON-friendly: money and sums come out of Postgres as Decimal, dates as date."""
    out = {}
    for key, value in row.items():
        if hasattr(value, "is_finite"):  # Decimal
            value = float(value)
        elif isinstance(value, date):
            value = value.isoformat()
        out[key] = value
    return out


class UsageRepository(Repository):
    async def record(
        self,
        *,
        token_id: int,
        token_name: str,
        agent_id: Optional[int],
        kind: str,
        model: str,
        status: str,
        duration_ms: int,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: Optional[float] = None,
    ) -> None:
        """One call to the model, written on the token that made the request. No texts: only that it happened and what it cost."""
        await self.db.execute(
            """
            INSERT INTO usage_logs (token_id, token_name, agent_id, model, kind, status, duration_ms, input_tokens, output_tokens, cost)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            (token_id, token_name, agent_id, model, kind, status, duration_ms, input_tokens, output_tokens, cost),
        )

    async def daily(
        self, since: date, until: date, token_id: Optional[int] = None, agent_id: Optional[int] = None, own_agent_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """The recent rows (not folded yet), summed by day, token and model. `own_agent_id` limits it to the tokens of one agent."""
        rows = await self.db.fetch_all(
            """
            SELECT l.timestamp::date AS day, l.token_id, l.token_name, l.model,
                   count(*) AS requests,
                   count(*) FILTER (WHERE l.status NOT IN ('ok', 'interrupted')) AS errors,
                   COALESCE(sum(l.input_tokens), 0) AS input_tokens,
                   COALESCE(sum(l.output_tokens), 0) AS output_tokens,
                   COALESCE(sum(l.cost), 0) AS cost,
                   COALESCE(sum(l.duration_ms), 0) AS duration_ms_sum
            FROM usage_logs l
            LEFT JOIN tokens t ON t.id = l.token_id
            WHERE l.timestamp >= $1 AND l.timestamp < $2::date + 1
              AND ($3::bigint IS NULL OR l.token_id = $3)
              AND ($4::bigint IS NULL OR t.agent_id = $4)
              AND ($5::bigint IS NULL OR t.agent_id = $5)
            GROUP BY 1, 2, 3, 4
            ORDER BY 1, 3, 4
            """,
            (since, until, token_id, agent_id, own_agent_id),
        )
        return [_plain(r) for r in rows]

    async def monthly(
        self, token_id: Optional[int] = None, agent_id: Optional[int] = None, own_agent_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        rows = await self.db.fetch_all(
            """
            SELECT m.month, m.token_id, m.token_name, m.model, m.requests, m.errors,
                   m.input_tokens, m.output_tokens, m.cost, m.duration_ms_sum
            FROM usage_monthly m
            LEFT JOIN tokens t ON t.id = m.token_id
            WHERE ($1::bigint IS NULL OR m.token_id = $1)
              AND ($2::bigint IS NULL OR t.agent_id = $2)
              AND ($3::bigint IS NULL OR t.agent_id = $3)
            ORDER BY m.month, m.token_name, m.model
            """,
            (token_id, agent_id, own_agent_id),
        )
        return [_plain(r) for r in rows]
