"""Who may do what. A token has a role (regular < user < admin < owner) and an agent.

  regular  the main API: requests, users, history (what a plain client needs)
  user     plus everything about its own agent: the agent, its knowledge base, MCP servers, users, messages,
           memories, tokens for it (regular and user)
  admin    plus every agent, models, every token up to `user`, usage of all, and acting as another agent
           (`X-Act-As-Agent`)
  owner    plus tokens of any role

`require(role)` is a route dependency; `ensure_agent_access` and `can_manage_token` are the checks that
depend on what the route is about. Roles below admin never leave their own agent.
"""

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from fastapi import HTTPException, Request

from database import PostgresDB, RANK, Token

# the highest role a token of this role may hand out (and so manage)
GRANTS = {
    "regular": 0,
    "user": RANK["user"],
    "admin": RANK["user"],
    "owner": RANK["owner"],
}


@dataclass(frozen=True)
class CallChain:
    """The agents one request went through when agents called each other (tool ask_agent), and the person it
    started with. Each called agent talks to the user `agent_<caller>:<human>`, so the name never grows with depth."""

    agents: Tuple[int, ...]  # the first is the agent the request came to
    human: str  # external id of the user of that first agent


# Set by ask_agent around the run of the called agent: the code of that run (its own ask_agent) sees it
call_chain: ContextVar[Optional[CallChain]] = ContextVar(
    "agent_call_chain", default=None
)


async def may_act_as(db: PostgresDB, agent_id: int) -> bool:
    """May this request work as agent `agent_id` (X-Act-As-Agent, and an agent calling another)? An admin may work
    as any agent; otherwise the agent before it in the call chain must have a connection to it."""
    if rank_of(db) >= RANK["admin"]:
        return True
    chain = call_chain.get()
    if chain is None:
        return False
    return await db.find_agent_connection(chain.agents[-1], agent_id) is not None


def rank_of(db: PostgresDB) -> int:
    return db.context.token.rank


def forbidden(
    detail: str = "Forbidden: this token's role may not do that",
) -> HTTPException:
    return HTTPException(status_code=403, detail=detail)


def require(role: str) -> Callable:
    """A dependency that lets only tokens of `role` or a higher one through."""
    minimum = RANK[role]

    async def check(request: Request) -> None:
        db: PostgresDB = request.state.db
        if rank_of(db) < minimum:
            raise forbidden(f"Forbidden: needs the {role} role")

    return check


def ensure_agent_access(db: PostgresDB, agent_id: int) -> None:
    """admin and owner may touch any agent; the others only their own."""
    if rank_of(db) >= RANK["admin"]:
        return
    if agent_id != db.context.token.agent_id:
        raise forbidden("Forbidden: this token may only use its own agent")


def default_agent_id(db: PostgresDB, agent_id: Optional[int]) -> int:
    """The agent a route is about: the one asked for (if the token may use it), else the one in context."""
    if agent_id is None:
        return db.context.agent.id
    ensure_agent_access(db, agent_id)
    return agent_id


def may_grant(db: PostgresDB, role: str) -> bool:
    return RANK[role] <= GRANTS[db.context.token.role]


def can_manage_token(db: PostgresDB, target: Token) -> bool:
    """Make, rename or delete: only tokens up to the role the caller may hand out, on agents the caller may use."""
    caller = db.context.token
    if target.rank > GRANTS[caller.role]:
        return False
    return rank_of(db) >= RANK["admin"] or target.agent_id == caller.agent_id
