"""Agents that call each other: the built-in tools `list_agents` and `ask_agent`.

An agent gets them when it has connections (`agent_connections`, agent1 -> agent2). `ask_agent` runs the called
agent in this process, like a request to it would (`agent_run`): with its own prompt, model, tools and history, as
the user `agent_<caller>:<human>`, so every person who talks to the caller has a thread of their own with it. The
called agent gets the request text only, not what the caller was discussing.

The chain of agents of one request is in `access.call_chain`: an agent already in it may not be called again, and
it is at most AGENT_CALL_DEPTH agents long after the first. Who may be called is decided like X-Act-As-Agent
(`access.may_act_as`): a connection from the agent before, or an admin token. A call that fails or is refused
gives the caller the reason as the tool's result; it never ends the caller's answer.
"""

import hashlib
import json
from typing import Any, Dict, List, Sequence

import logfire
from pydantic_ai import Agent, RunContext

from access import CallChain, call_chain, may_act_as
from core import AGENT_CALL_DEPTH, error_response
from database import Context, PostgresDB

from .deps import Dependencies

USER_ID_MAX = 64  # users.external_id


def caller_user_id(caller_agent_id: int, human: str) -> str:
    """The user a called agent talks to: one per (calling agent, person). A person's id that does not fit is
    replaced by a short fingerprint of it, which is still one per person."""
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
            found.append(
                {
                    "id": agent.id,
                    "name": agent.name,
                    "description": connection.description,
                }
            )
    return found


async def ask(db: PostgresDB, agent_id: int, request: str) -> str:
    """Run agent `agent_id` on `request` for the agent of `db`; the answer, or why there is none."""
    caller = db.context.agent
    chain = call_chain.get() or CallChain(
        agents=(caller.id,),
        human=db.context.user.external_id if db.context.user else "anonymous",
    )
    if agent_id in chain.agents:
        path = " -> ".join(str(a) for a in chain.agents)
        return f"Refused: agent {agent_id} is already in this chain of calls ({path}); an agent is not called twice."
    if len(chain.agents) - 1 >= AGENT_CALL_DEPTH:
        return f"Refused: this request is already {AGENT_CALL_DEPTH} agents deep, the most that one request may go."

    token = call_chain.set(chain)  # may_act_as looks at the agent before: the caller
    try:
        if not await may_act_as(db, agent_id):
            return f"Refused: agent {caller.id} has no connection to agent {agent_id}. Call list_agents to see which it has."
    finally:
        call_chain.reset(token)
    target = await db.get_agent(agent_id)
    if target is None:
        return f"Refused: there is no agent {agent_id}."

    called = PostgresDB(
        db.foundation, Context(agent=target, token=db.context.token, user=None)
    )
    await called.insure_user(caller_user_id(caller.id, chain.human))
    called.context.chat = await called.ensure_default_chat()

    from .endpoint import agent_run  # endpoint builds agents with these tools

    token = call_chain.set(
        CallChain(agents=chain.agents + (agent_id,), human=chain.human)
    )
    try:
        run = await agent_run(called, request, kind="agent_call")
        return run.output
    except Exception as exc:  # the caller goes on without this answer
        status, detail = error_response(exc)
        logfire.warning(
            "Agent {caller} could not ask agent {agent}: {detail}",
            caller=caller.id,
            agent=agent_id,
            detail=detail,
        )
        return f"Agent {agent_id} could not answer (HTTP {status}): {detail}"
    finally:
        call_chain.reset(token)


def register_agent_tools(agent: Agent, connected: Sequence[Dict[str, Any]]) -> None:
    """`list_agents` and `ask_agent` for an agent with connections (`connected`: from `connected_agents`)."""
    listing = json.dumps(list(connected), ensure_ascii=False)

    @agent.tool
    async def list_agents(context: RunContext[Dependencies]) -> str:
        """The other agents you may ask for help: their id, name and what they are for.

        Args:
            context: The call context.
        """
        return listing

    @agent.tool
    async def ask_agent(
        context: RunContext[Dependencies], agent_id: int, request: str
    ) -> str:
        """Ask another agent (one from list_agents) and get its answer as text. It sees only this request, not
        your conversation: put everything it needs into the request.

        Args:
            context: The call context.
            agent_id: The id of the agent, from list_agents.
            request: What to ask it, complete in itself.
        """
        return await ask(context.deps.db, agent_id, request)
