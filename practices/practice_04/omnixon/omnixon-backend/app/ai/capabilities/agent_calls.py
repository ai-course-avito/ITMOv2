"""Agents that call each other.

An agent that has connections (`agent_connections`, agent1 -> agent2) gets two tools: `list_agents` (the agents it may call, with what each is
for, as the connection says) and `ask_agent` (ask one of them, and get its answer as text).

The called agent is run like any request to it would be, in this process, with its own prompt, model, tools and history, as the user
`agent_<caller>:<person>`: every person who talks to the caller has a thread of their own with it, and a person's id (however long) does not
make the name grow with depth. It is given the text of the request only, not what the caller was discussing.

The agents a request went through are the `chain` of its context (`database.CallChain`), carried by the database handle each agent is run with:
an agent already in the chain is not called again, the chain is at most AGENT_CALL_DEPTH agents long after the first, and who may be called is
decided like X-Act-As-Agent (`access.may_act_as`): an admin token may call anyone, else the agent that asks needs a connection to it. A call that
is refused, or fails, is the tool's answer (its words, for the model to read); it never ends the caller's run.

How an agent is run is not known here: `answer` is given (by `runner`) so that this module does not depend on the thing that builds it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence

import logfire
from pydantic_ai import RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.toolsets import FunctionToolset

from access import may_act_as
from core import AGENT_CALL_DEPTH, error_response
from database import CallChain, PostgresDB
from ..deps import Dependencies

USER_ID_MAX = 64  # users.external_id

# Runs the agent of a database handle on a request and returns what it said.
Answer = Callable[[PostgresDB, str], Awaitable[str]]


def caller_user_id(caller_agent_id: int, human: str) -> str:
    """The user a called agent talks to: one per (calling agent, person). A person's id that does not fit is replaced by a short fingerprint
    of it, which is still one per person."""
    user_id = f"agent_{caller_agent_id}:{human}"
    if len(user_id) <= USER_ID_MAX:
        return user_id
    return f"agent_{caller_agent_id}:{hashlib.sha256(human.encode()).hexdigest()[:16]}"


async def connected_agents(db: PostgresDB) -> List[Dict[str, Any]]:
    """The agents the agent of `db` may call: id, name and the description of the connection."""
    if db.context.agent is None:
        return []
    found = []
    for connection in await db.get_agent_connections(db.context.agent.id):
        agent = await db.get_agent(connection.agent2_id)
        if agent is not None:
            found.append({"id": agent.id, "name": agent.name, "description": connection.description})
    return found


def chain_of(db: PostgresDB) -> CallChain:
    """How this request got here: the chain it is in, or the start of one (the agent of this request, and the person who wrote to it)."""
    return db.context.chain or CallChain(
        agents=(db.context.agent.id,), human=db.context.user.external_id if db.context.user else "anonymous"
    )


def refusal(chain: CallChain, agent_id: int) -> Optional[str]:
    """Why the chain may not go on to `agent_id` (a loop, or too deep), in the tool's words; None if it may."""
    if agent_id in chain.agents:
        path = " -> ".join(str(a) for a in chain.agents)
        return f"Refused: agent {agent_id} is already in this chain of calls ({path}); an agent is not called twice."
    if len(chain.agents) - 1 >= AGENT_CALL_DEPTH:
        return f"Refused: this request is already {AGENT_CALL_DEPTH} agents deep, the most that one request may go."
    return None


async def ask(db: PostgresDB, agent_id: int, request: str, answer: Answer) -> str:
    """Ask agent `agent_id` for the agent of `db`: its answer, or why there is none."""
    caller = db.context.agent
    chain = chain_of(db)
    if (why := refusal(chain, agent_id)) is not None:
        return why
    if not await may_act_as(db.with_context(chain=chain), agent_id):
        return f"Refused: agent {caller.id} has no connection to agent {agent_id}. Call list_agents to see which it has."
    target = await db.get_agent(agent_id)
    if target is None:
        return f"Refused: there is no agent {agent_id}."

    called = db.with_context(agent=target, user=None, chat=None, chain=chain.then(agent_id))
    try:
        await called.insure_user(caller_user_id(caller.id, chain.human))
        called.context.chat = await called.ensure_default_chat()
        return await answer(called, request)
    except Exception as exc:  # the caller goes on without this answer
        status, detail = error_response(exc)
        logfire.warning("Agent {caller} could not ask agent {agent}: {detail}", caller=caller.id, agent=agent_id, detail=detail)
        return f"Agent {agent_id} could not answer (HTTP {status}): {detail}"


@dataclass(kw_only=True)  # AbstractCapability is a dataclass whose first field is `id`: positional arguments would land there
class AgentCalls(AbstractCapability[Dependencies]):
    """`list_agents` and `ask_agent` for an agent with connections (`agents`: from `connected_agents`)."""

    agents: Sequence[Dict[str, Any]] = ()
    answer: Optional[Answer] = None
    id: Optional[str] = "agent-calls"

    def __post_init__(self) -> None:
        listing = json.dumps(list(self.agents), ensure_ascii=False)
        answer = self.answer
        tools = FunctionToolset[Dependencies]()

        @tools.tool
        async def list_agents(context: RunContext[Dependencies]) -> str:
            """The other agents you may ask for help: their id, name and what they are for.

            Args:
                context: The call context.
            """
            return listing

        @tools.tool
        async def ask_agent(context: RunContext[Dependencies], agent_id: int, request: str) -> str:
            """Ask another agent (one from list_agents) and get its answer as text. It sees only this request, not your conversation: put
            everything it needs into the request.

            Args:
                context: The call context.
                agent_id: The id of the agent, from list_agents.
                request: What to ask it, complete in itself.
            """
            return await ask(context.deps.db, agent_id, request, answer)

        self._tools = tools

    def get_toolset(self) -> FunctionToolset[Dependencies]:
        return self._tools
