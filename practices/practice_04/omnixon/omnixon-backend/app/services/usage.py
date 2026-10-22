from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from domain.access import AccessPolicy, Principal
from repositories.data import UsageRepository


class UsageService:
    def __init__(self, usage: UsageRepository, policy: AccessPolicy):
        self.usage, self.policy = usage, policy

    def _scope(self, principal: Principal, agent_id: Optional[int]) -> Dict[str, Optional[int]]:
        """Below admin the statistics are those of the tokens of the own agent; an admin sees all, or one agent's."""
        if principal.is_admin:
            if agent_id is not None:
                self.policy.ensure_agent(principal, agent_id)
            return {"agent_id": agent_id, "own_agent_id": None}
        return {"agent_id": None, "own_agent_id": self.policy.agent_scope(principal, agent_id)}

    async def daily(self, principal: Principal, days: int, token_id: Optional[int], agent_id: Optional[int]) -> List[Dict[str, Any]]:
        today = date.today()
        return await self.usage.daily(today - timedelta(days=days - 1), today, token_id=token_id, **self._scope(principal, agent_id))

    async def monthly(self, principal: Principal, token_id: Optional[int], agent_id: Optional[int]) -> List[Dict[str, Any]]:
        return await self.usage.monthly(token_id=token_id, **self._scope(principal, agent_id))
