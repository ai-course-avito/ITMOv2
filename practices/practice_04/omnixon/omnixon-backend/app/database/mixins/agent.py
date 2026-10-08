from typing import Optional, Sequence
from core import DEFAULT_TOOLS
from ..context import PostgresConnectionWithContext
from ..models import Agent


class AgentMethods(PostgresConnectionWithContext):
    async def get_agent(self, agent_id: int) -> Optional[Agent]:
        query = "SELECT * FROM agents WHERE id=$1"
        return await self.fetch_one(query, (agent_id,), Agent)

    async def get_all_agents(self) -> Sequence[Agent]:
        query = "SELECT * FROM agents"
        return await self.fetch_all(query, (), Agent)

    async def create_agent(
        self,
        prompt: str,
        model_id: int,
        config: Optional[dict] = None,
        comment: Optional[str] = None,
        token_id: Optional[int] = None,
        name: Optional[str] = None,
    ) -> Agent:
        """`config` is merged over the default {"tools": [...]}. Version 1 is recorded."""
        settings = {"tools": list(DEFAULT_TOOLS)}
        settings.update({k: v for k, v in (config or {}).items() if v is not None})
        query = """
            INSERT INTO agents (prompt, model_id, config, name)
            VALUES ($1, $2, $3, $4)
            RETURNING *
        """
        async with self.transaction():  # the agent and its first version
            agent = await self.fetch_one(
                query, (prompt, model_id, settings, name), Agent
            )
            await self.record_agent_version(agent.id, comment or "created", token_id)
        return agent

    async def update_agent(
        self,
        agent_id: int,
        prompt: Optional[str] = None,
        model_id: Optional[int] = None,
        config: Optional[dict] = None,
        name: Optional[str] = None,
    ) -> Optional[Agent]:
        """Only what is given changes. `config` is merged into the stored JSON; a key
        set to None is removed (the setting goes back to its default)."""
        query = """
            UPDATE agents
            SET prompt=COALESCE($1, prompt),
                model_id=COALESCE($2, model_id),
                config=CASE WHEN $3::jsonb IS NULL THEN config
                            ELSE jsonb_strip_nulls(config || $3::jsonb) END,
                name=COALESCE($4, name)
            WHERE id=$5
            RETURNING *
        """
        return await self.fetch_one(
            query, (prompt, model_id, config, name, agent_id), Agent
        )

    async def delete_agent(self, id: int) -> Optional[Agent]:
        query = "DELETE FROM agents WHERE id=$1 RETURNING *"
        agent = await self.fetch_one(query, (id,), Agent)
        if agent:
            # its RAG rows are gone (cascade); the partition would stay as an empty table
            await self.execute(f"DROP TABLE IF EXISTS rag_{int(id)}")
        return agent
