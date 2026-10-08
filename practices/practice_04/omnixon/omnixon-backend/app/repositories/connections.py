from __future__ import annotations

from typing import List, Optional, Sequence

from domain.entities import AgentConnection
from .base import Repository


class ConnectionRepository(Repository):
    """Who may call whom: agent1 -> agent2, with a description of agent2 for agent1."""

    async def list(self, agent_id: Optional[int] = None) -> List[AgentConnection]:
        """All connections, or the ones going out of `agent_id`."""
        if agent_id is None:
            return await self.db.fetch_all("SELECT * FROM agent_connections ORDER BY id", (), AgentConnection)
        return await self.db.fetch_all("SELECT * FROM agent_connections WHERE agent1_id=$1 ORDER BY id", (agent_id,), AgentConnection)

    async def get(self, connection_id: int) -> Optional[AgentConnection]:
        return await self.db.fetch_one("SELECT * FROM agent_connections WHERE id=$1", (connection_id,), AgentConnection)

    async def find(self, agent1_id: int, agent2_id: int) -> Optional[AgentConnection]:
        return await self.db.fetch_one(
            "SELECT * FROM agent_connections WHERE agent1_id=$1 AND agent2_id=$2", (agent1_id, agent2_id), AgentConnection
        )

    async def insert(self, agent1_id: int, agent2_id: int, description: str) -> AgentConnection:
        """Raises asyncpg's UniqueViolationError for a pair that is there, ForeignKeyViolationError for an unknown agent."""
        return await self.db.fetch_one(
            "INSERT INTO agent_connections (agent1_id, agent2_id, description) VALUES ($1, $2, $3) RETURNING *",
            (agent1_id, agent2_id, description),
            AgentConnection,
        )

    async def update(self, connection_id: int, description: str) -> Optional[AgentConnection]:
        return await self.db.fetch_one(
            "UPDATE agent_connections SET description=$1 WHERE id=$2 RETURNING *", (description, connection_id), AgentConnection
        )

    async def delete(self, connection_id: int) -> Optional[AgentConnection]:
        return await self.db.fetch_one("DELETE FROM agent_connections WHERE id=$1 RETURNING *", (connection_id,), AgentConnection)

    async def callers_of(self, agent_id: int) -> List[int]:
        """The agents that have a connection to `agent_id`."""
        rows = await self.db.fetch_all("SELECT agent1_id FROM agent_connections WHERE agent2_id=$1", (agent_id,))
        return [row["agent1_id"] for row in rows]

    async def replace_of(self, agent_id: int, wanted: Sequence[dict]) -> None:
        """Make the connections going out of `agent_id` be `wanted` ([{agent2_id, description}]); one to an agent that is gone is left out."""
        await self.db.execute("DELETE FROM agent_connections WHERE agent1_id=$1", (agent_id,))
        for connection in wanted:
            await self.db.execute(
                """
                INSERT INTO agent_connections (agent1_id, agent2_id, description)
                SELECT $1, $2, $3 WHERE EXISTS (SELECT 1 FROM agents WHERE id=$2) AND $1 <> $2
                """,
                (agent_id, connection["agent2_id"], connection["description"]),
            )
