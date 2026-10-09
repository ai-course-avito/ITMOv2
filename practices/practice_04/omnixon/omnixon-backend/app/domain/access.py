"""Who is asking and what they may do.

A token has a role (regular < user < admin < owner) and an agent:

  regular  the main API: requests, users, history
  user     plus everything about its own agent: the agent, its knowledge base, MCP servers, users, memories, tokens for it
  admin    plus every agent, models, every token up to `user`, usage of all, and acting as another agent (`X-Act-As-Agent`)
  owner    plus tokens of any role

`AccessPolicy` is the one place that decides; the services ask it and it raises `Forbidden` with the text the API has always sent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, Optional

from .agents import AgentSettings
from .chain import CallChain
from .errors import Forbidden
from .roles import Role

if TYPE_CHECKING:  # the entities live with the row models until they are moved here
    from domain.entities import Agent, Chat, Token, User


@dataclass(frozen=True)
class Principal:
    """The request: the token that asks, the agent it is about (the token's own, or the one an admin acts as), and — for an agent that
    another agent is asking — how the request got here."""

    token: "Token"
    agent: "Agent"
    chain: Optional[CallChain] = None

    @property
    def role(self) -> Role:
        return self.token.as_role

    @property
    def is_admin(self) -> bool:
        return self.role.at_least(Role.ADMIN)

    def continued_as(self, agent: "Agent", chain: CallChain) -> "Principal":
        """The same token, asking on as `agent` (an agent calling another one)."""
        return Principal(self.token, agent, chain)


@dataclass(frozen=True)
class Conversation:
    """One request's conversation: who asks, which user of the agent they talk as, in which chat, and with which settings."""

    principal: Principal
    user: "User"
    chat: "Chat"
    settings: AgentSettings

    @property
    def agent(self) -> "Agent":
        return self.principal.agent


class AccessPolicy:
    def require(self, principal: Principal, role: Role) -> None:
        if not principal.role.at_least(role):
            raise Forbidden(f"Forbidden: needs the {role.value} role")

    def ensure_agent(self, principal: Principal, agent_id: int) -> None:
        """admin and owner may touch any agent; the others only their own."""
        if principal.is_admin:
            return
        if agent_id != principal.token.agent_id:
            raise Forbidden("Forbidden: this token may only use its own agent")

    def agent_scope(self, principal: Principal, agent_id: Optional[int]) -> int:
        """The agent a call is about: the one asked for (if the token may use it), else the one in context."""
        if agent_id is None:
            return principal.agent.id
        self.ensure_agent(principal, agent_id)
        return agent_id

    def may_act_as(self, principal: Principal, agent_id: int, has_connection: bool) -> bool:
        """May this request work as agent `agent_id` (X-Act-As-Agent, and an agent asking another)? An admin may work as any agent;
        otherwise the agent that is asking must have a connection to it (`has_connection`)."""
        return principal.is_admin or (principal.chain is not None and has_connection)

    def ensure_may_hand_out(self, principal: Principal, role: Role) -> None:
        if not principal.role.may_hand_out(role):
            raise Forbidden(f"Forbidden: this token may not hand out the {role.value} role")

    def ensure_may_manage(self, principal: Principal, token: "Token") -> None:
        if not principal.token.may_manage(token):
            raise Forbidden("Forbidden: this token may not manage a token of that role or agent")

    def ensure_mcp_use(self, principal: Principal, agents_using: Iterable[int], change: bool) -> None:
        """Below admin a token sees the servers of its own agent, and changes only those that nothing else uses (a server shared with
        another agent would change that agent too)."""
        if principal.is_admin:
            return
        agents = set(agents_using)
        own = principal.token.agent_id
        if own not in agents:
            raise Forbidden("Forbidden: this MCP server is not attached to the token's agent")
        if change and agents != {own}:
            raise Forbidden("Forbidden: this MCP server is shared with another agent, so it cannot be changed here")
