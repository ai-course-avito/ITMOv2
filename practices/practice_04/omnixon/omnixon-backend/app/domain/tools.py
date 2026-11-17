from typing import List, Optional, Sequence

TOOL_RAG = "rag"
TOOL_MEMORY = "memory"

# Built-in tools an agent can be given through `agents.config["tools"]`
AVAILABLE_TOOLS = (TOOL_RAG, TOOL_MEMORY)
DEFAULT_TOOLS = [TOOL_RAG, TOOL_MEMORY]


def validate_tools(tools: Optional[Sequence[str]]) -> Optional[List[str]]:
    """Reject unknown tool names and drop duplicates, keeping the order."""
    if tools is None:
        return None

    unknown = sorted(set(tools) - set(AVAILABLE_TOOLS))
    if unknown:
        raise ValueError(
            f"Unknown tools: {', '.join(unknown)}. Available: {', '.join(AVAILABLE_TOOLS)}"
        )

    return list(dict.fromkeys(tools))
