from typing import Optional, Sequence

from ..context import PostgresConnectionWithContext
from ..models import AgentConnection


class AgentConnectionMethods(PostgresConnectionWithContext):
    """Who may call whom: agent1 -> agent2, with a description of agent2 for agent1."""

    async def get_agent_connections(
        self, agent_id: Optional[int] = None
    ) -> Sequence[AgentConnection]:
        """All connections, or the ones going out of `agent_id`."""
        if agent_id is None:
            query = "SELECT * FROM agent_connections ORDER BY id"
            return (await self.fetch_all(query, (), AgentConnection)) or []
        query = "SELECT * FROM agent_connections WHERE agent1_id=$1 ORDER BY id"
        return (await self.fetch_all(query, (agent_id,), AgentConnection)) or []

    async def get_agent_connection(
        self, connection_id: int
    ) -> Optional[AgentConnection]:
        query = "SELECT * FROM agent_connections WHERE id=$1"
        return await self.fetch_one(query, (connection_id,), AgentConnection)

    async def find_agent_connection(
        self, agent1_id: int, agent2_id: int
    ) -> Optional[AgentConnection]:
        query = "SELECT * FROM agent_connections WHERE agent1_id=$1 AND agent2_id=$2"
        return await self.fetch_one(query, (agent1_id, agent2_id), AgentConnection)

    async def create_agent_connection(
        self, agent1_id: int, agent2_id: int, description: str
    ) -> AgentConnection:
        """Raises asyncpg's UniqueViolationError for a pair that is there, ForeignKeyViolationError for an unknown agent."""
        query = """
            INSERT INTO agent_connections (agent1_id, agent2_id, description)
            VALUES ($1, $2, $3)
            RETURNING *
        """
        return await self.fetch_one(
            query, (agent1_id, agent2_id, description), AgentConnection
        )

    async def update_agent_connection(
        self, connection_id: int, description: str
    ) -> Optional[AgentConnection]:
        query = "UPDATE agent_connections SET description=$1 WHERE id=$2 RETURNING *"
        return await self.fetch_one(
            query, (description, connection_id), AgentConnection
        )

    async def delete_agent_connection(
        self, connection_id: int
    ) -> Optional[AgentConnection]:
        query = "DELETE FROM agent_connections WHERE id=$1 RETURNING *"
        return await self.fetch_one(query, (connection_id,), AgentConnection)

    async def agent_ids_calling(self, agent_id: int) -> Sequence[int]:
        """The agents that have a connection to `agent_id`."""
        rows = await self.fetch_all(
            "SELECT agent1_id FROM agent_connections WHERE agent2_id=$1", (agent_id,)
        )
        return [row["agent1_id"] for row in rows or []]

    async def set_agent_connections(
        self, agent_id: int, wanted: Sequence[dict]
    ) -> None:
        """Make the connections going out of `agent_id` be `wanted` ([{agent2_id, description}]); a connection to an
        agent that is gone is left out. Used by a rollback, in its transaction."""
        await self.execute(
            "DELETE FROM agent_connections WHERE agent1_id=$1", (agent_id,)
        )
        for connection in wanted:
            await self.execute(
                """
                INSERT INTO agent_connections (agent1_id, agent2_id, description)
                SELECT $1, $2, $3 WHERE EXISTS (SELECT 1 FROM agents WHERE id=$2) AND $1 <> $2
                """,
                (agent_id, connection["agent2_id"], connection["description"]),
            )
