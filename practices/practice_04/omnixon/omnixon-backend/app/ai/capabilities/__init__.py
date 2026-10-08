"""What an agent can have, one capability each (a bundle of tools, instructions and behaviour, see pydantic-ai's capabilities).

`build_capabilities` reads the agent of a request and returns the capabilities it has: that is the whole of "what is this agent made of"."""

from __future__ import annotations

from typing import List

from pydantic_ai.capabilities import AbstractCapability

from core import DEFAULT_PARALLEL_TOOL_CALLS, DEFAULT_TOOLS, TOOL_MEMORY, TOOL_RAG
from database import PostgresDB
from .agent_calls import Answer, AgentCalls, connected_agents
from .knowledge import KnowledgeBase
from .mcp import McpServers
from .parallel import ParallelCalls
from .memory import Memory
from .tool_failures import ToolFailures

__all__ = ["build_capabilities", "AgentCalls", "KnowledgeBase", "McpServers", "Memory", "ParallelCalls", "ToolFailures"]


async def build_capabilities(db: PostgresDB, answer: Answer) -> List[AbstractCapability]:
    """The capabilities of the agent of `db`. `answer` is how an agent it may call is run (see AgentCalls)."""
    agent = db.context.agent
    tools = agent.tools if agent else DEFAULT_TOOLS
    capabilities: List[AbstractCapability] = [ToolFailures()]  # first: what the others raise, it turns into a failed result
    if TOOL_RAG in tools:
        capabilities.append(KnowledgeBase())
    if TOOL_MEMORY in tools:
        capabilities.append(Memory())
    if connected := await connected_agents(db):
        capabilities.append(AgentCalls(agents=connected, answer=answer))
    if agent and (servers := await db.get_agent_mcp_servers(agent.id)):
        capabilities.append(McpServers(servers=[(server.name, server.config) for server in servers]))
    parallel = agent.parallel_tool_calls if agent else DEFAULT_PARALLEL_TOOL_CALLS
    if parallel and len(capabilities) > 1:  # there are tools to call together
        capabilities.append(ParallelCalls())
    return capabilities
