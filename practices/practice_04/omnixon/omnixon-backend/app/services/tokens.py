from __future__ import annotations

from typing import List, Optional

from domain.entities import NewToken, Token
from domain.access import AccessPolicy, Principal
from domain.errors import Conflict, NotFound
from domain.roles import Role
from repositories.agents import AgentRepository
from repositories.people import TokenRepository
from repositories.unit_of_work import UnitOfWork
from .versions import VersionRecorder


class TokenService:
    def __init__(self, tokens: TokenRepository, agents: AgentRepository, recorder: VersionRecorder, policy: AccessPolicy, uow: UnitOfWork):
        self.tokens, self.agents, self.recorder, self.policy, self.uow = tokens, agents, recorder, policy, uow

    async def self_token(self, principal: Principal) -> Token:
        token = await self.tokens.get(principal.token.id)
        if not token:
            raise NotFound("Token not found")
        return token

    async def list(self, principal: Principal, agent_id: Optional[int] = None) -> List[Token]:
        if agent_id is None and principal.is_admin:
            return await self.tokens.list()
        return await self.tokens.list(self.policy.agent_scope(principal, agent_id))

    async def create(self, principal: Principal, data) -> NewToken:
        self.policy.ensure_may_hand_out(principal, Role(data.role))
        agent_id = self.policy.agent_scope(principal, data.agent_id)
        if not await self.agents.get(agent_id):
            raise NotFound("Agent not found")
        return await self.tokens.insert(data.name, agent_id, data.role)

    async def _managed(self, principal: Principal, token_id: int) -> Token:
        target = await self.tokens.get(token_id)
        if not target:
            raise NotFound("Token not found")
        self.policy.ensure_may_manage(principal, target)
        return target

    async def update(self, principal: Principal, token_id: int, data) -> Token:
        target = await self._managed(principal, token_id)
        if data.role is not None and data.role != target.role:
            self.policy.ensure_may_hand_out(principal, Role(data.role))
            if target.id == principal.token.id:
                raise Conflict("The token in use cannot change its own role")
            if target.is_initial:
                raise Conflict("The role of the initial token cannot be changed")
        return await self.tokens.update(token_id, data.name, data.role)

    async def delete(self, principal: Principal, token_id: int) -> Token:
        target = await self._managed(principal, token_id)
        if target.id == principal.token.id:
            raise Conflict("The token in use cannot delete itself")
        if target.is_initial:
            raise Conflict("The initial token cannot be deleted")
        return await self.tokens.delete(token_id)

    async def ensure_initial(self, secret: str) -> Token:
        """The token of INITIAL_API_KEY is an owner, made at start if it is not there (with an agent of its own), and made an owner again
        if someone lowered it by hand. Replicas start together: the first one makes the token, the others find it."""
        existing = await self.tokens.by_secret(secret)
        if existing:
            return existing if existing.role == "owner" else await self.tokens.update(existing.id, role="owner")
        async with self.uow.transaction():
            await self.uow.lock("initial-token")
            existing = await self.tokens.by_secret(secret)
            if existing:
                return existing
            agent = await self.agents.insert("Default agent", "", 0, {"tools": ["rag", "memory"]})
            await self.recorder.record(agent.id, "created", None)
            created = await self.tokens.insert("initial", agent.id, "owner", secret)
        return await self.tokens.get(created.id)
