from __future__ import annotations

from typing import List, Optional

from domain.entities import Agent
from .base import Repository


class AgentRepository(Repository):
    async def get(self, agent_id: int) -> Optional[Agent]:
        return await self.db.fetch_one("SELECT * FROM agents WHERE id=$1", (agent_id,), Agent)

    async def list(self) -> List[Agent]:
        return await self.db.fetch_all("SELECT * FROM agents", (), Agent)

    async def insert(self, name: Optional[str], prompt: str, model_id: int, config: dict) -> Agent:
        return await self.db.fetch_one(
            "INSERT INTO agents (prompt, model_id, config, name) VALUES ($1, $2, $3, $4) RETURNING *",
            (prompt, model_id, config, name),
            Agent,
        )

    async def update(
        self,
        agent_id: int,
        *,
        name: Optional[str] = None,
        prompt: Optional[str] = None,
        model_id: Optional[int] = None,
        config_changes: Optional[dict] = None,
    ) -> Optional[Agent]:
        """Only what is given changes. `config_changes` is merged into the stored JSON; a key set to None is removed (back to its default)."""
        return await self.db.fetch_one(
            """
            UPDATE agents
            SET prompt=COALESCE($1, prompt),
                model_id=COALESCE($2, model_id),
                config=CASE WHEN $3::jsonb IS NULL THEN config
                            ELSE jsonb_strip_nulls(config || $3::jsonb) END,
                name=COALESCE($4, name)
            WHERE id=$5
            RETURNING *
            """,
            (prompt, model_id, config_changes, name, agent_id),
            Agent,
        )

    async def set_behaviour(self, agent_id: int, prompt: str, model_id: int, config: dict) -> None:
        """Make the agent be what a version says (a rollback): the whole config is replaced."""
        await self.db.fetch_one(
            "UPDATE agents SET prompt=$1, model_id=$2, config=$3 WHERE id=$4 RETURNING id", (prompt, model_id, config, agent_id)
        )

    async def delete(self, agent_id: int) -> Optional[Agent]:
        agent = await self.db.fetch_one("DELETE FROM agents WHERE id=$1 RETURNING *", (agent_id,), Agent)
        if agent:  # its knowledge rows are gone (cascade); the partition would stay as an empty table
            await self.db.execute(f"DROP TABLE IF EXISTS rag_{int(agent_id)}")
        return agent

    async def ids_using_model(self, model_id: int) -> List[int]:
        return [row["id"] for row in await self.db.fetch_all("SELECT id FROM agents WHERE model_id=$1", (model_id,))]
