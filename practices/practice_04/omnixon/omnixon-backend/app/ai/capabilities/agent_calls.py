"""Agents that call each other.

An agent that has connections (`agent_connections`, agent1 -> agent2) gets two tools: `list_agents` (the agents it may call, with what each is
for, as the connection says) and `ask_agent` (ask one of them, and get its answer as text).

What happens when one is asked (who may be called, the chain, the user the called agent talks to, running it) is the business of whoever
implements `AgentAsker` (the conversation service): this capability only offers the tools, so it does not depend on the thing that runs agents.
A call that is refused, or fails, is the tool's answer (its words, for the model to read); it never ends the caller's run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, Sequence

from pydantic_ai import RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.toolsets import FunctionToolset

from domain.access import Conversation
from ..deps import RunDeps


class AgentAsker(Protocol):
    async def ask_as_agent(self, conversation: Conversation, agent_id: int, request: str) -> str: ...


@dataclass(kw_only=True)  # AbstractCapability is a dataclass whose first field is `id`: positional arguments would land there
class AgentCalls(AbstractCapability[RunDeps]):
    """`list_agents` and `ask_agent` for an agent with connections (`agents`: id, name and description of each it may call)."""

    agents: Sequence[Dict[str, Any]] = ()
    asker: Optional[AgentAsker] = None
    id: Optional[str] = "agent-calls"

    def __post_init__(self) -> None:
        listing = json.dumps(list(self.agents), ensure_ascii=False)
        asker = self.asker
        tools = FunctionToolset[RunDeps]()

        @tools.tool
        async def list_agents(context: RunContext[RunDeps]) -> str:
            """The other agents you may ask for help: their id, name and what they are for.

            Args:
                context: The call context.
            """
            return listing

        @tools.tool
        async def ask_agent(context: RunContext[RunDeps], agent_id: int, request: str) -> str:
            """Ask another agent (one from list_agents) and get its answer as text. It sees only this request, not your conversation: put
            everything it needs into the request.

            Args:
                context: The call context.
                agent_id: The id of the agent, from list_agents.
                request: What to ask it, complete in itself.
            """
            return await asker.ask_as_agent(context.deps.conversation, agent_id, request)

        self._tools = tools

    def get_toolset(self) -> FunctionToolset[RunDeps]:
        return self._tools
