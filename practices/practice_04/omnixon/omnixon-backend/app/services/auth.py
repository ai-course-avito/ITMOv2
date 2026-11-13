from __future__ import annotations

from typing import Optional

from domain.access import AccessPolicy, Principal


class AuthError(Exception):
    """A request that is turned away before any route runs, with exactly the answer the service has always given for it."""

    def __init__(self, status: int, body: str, as_json: bool):
        super().__init__(body)
        self.status, self.body, self.as_json = status, body, as_json


class AuthService:
    def __init__(self, tokens, agents, connections, policy: AccessPolicy):
        self.tokens, self.agents, self.connections, self.policy = tokens, agents, connections, policy

    async def authenticate(self, secret: Optional[str], act_as: Optional[str] = None) -> Principal:
        if secret is None:
            raise AuthError(403, "Authentication failed: API token is missing", False)
        token = await self.tokens.by_secret(secret)
        if token is None:
            raise AuthError(403, "Authentication failed: wrong token", False)
        agent_id = token.agent_id
        if act_as is not None and act_as.strip():
            # an admin may work as another agent: its users, its knowledge, its answers
            try:
                agent_id = int(act_as)
            except ValueError:
                agent_id = -1
            asker = Principal(token, agent=None)  # the chain is empty here: only an admin passes
            if not self.policy.may_act_as(asker, agent_id, has_connection=False):
                raise AuthError(403, "Forbidden: X-Act-As-Agent needs the admin role", True)
        agent = await self.agents.get(agent_id)
        if agent is None:
            raise AuthError(404, "Agent not found", True)
        return Principal(token, agent)
