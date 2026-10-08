from typing import Any, Dict, Optional, Sequence
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPServer
from .deps import Dependencies
from .agent_calls import register_agent_tools
from .memory import register_memory_tools
from core import DEFAULT_RAG_LIMIT, DEFAULT_TOOLS, TOOL_MEMORY, TOOL_RAG
from .utils import get_embedding_vector


def generate_agent(
    model,
    mcp_servers: Optional[Sequence[MCPServer]] = None,
    tools: Sequence[str] = DEFAULT_TOOLS,
    instructions: Optional[str] = None,
    connected: Sequence[Dict[str, Any]] = (),
):
    """`connected`: the agents this one may call (agent_calls.connected_agents); with any, it gets list_agents and
    ask_agent."""
    agent = Agent(
        model=model,
        deps_type=Dependencies,
        retries=2,
        toolsets=list(mcp_servers) if mcp_servers else None,
        instructions=instructions,
    )

    if TOOL_RAG in tools:

        @agent.tool
        async def retrieve(context: RunContext[Dependencies], search_query: str) -> str:
            """Retrieve documentation sections based on a search query.

            Args:
                context: The call context.
                search_query: The search query.
            """
            embedding = await get_embedding_vector(search_query)
            agent = context.deps.db.context.agent
            limit = agent.rag_limit if agent else DEFAULT_RAG_LIMIT
            rows = await context.deps.db.get_similar_rag(embedding, limit)
            return "\n\n".join(
                f'<record id="{row.id}">\n{row.content}\n</record>' for row in rows
            )

    if TOOL_MEMORY in tools:
        register_memory_tools(agent)

    if connected:
        register_agent_tools(agent, connected)

    return agent
