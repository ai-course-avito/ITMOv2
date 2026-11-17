from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from domain.tools import validate_tools
from .common import Name


class AgentConfigInput(BaseModel):
    """Settings of an agent (agents.config). On update only the given keys change,
    and a key set to null goes back to its default."""

    model_config = ConfigDict(extra="forbid")

    tools: Optional[List[str]] = None  # default: ["rag", "memory"]
    message_limit: Optional[int] = Field(None, ge=0, le=1000)
    memo_limit: Optional[int] = Field(None, ge=1, le=1000)
    rag_limit: Optional[int] = Field(None, ge=1, le=100)  # default: DEFAULT_RAG_LIMIT (8)
    auto_memory: Optional[bool] = None  # default: on (DEFAULT_AUTO_MEMORY)
    parallel_tool_calls: Optional[bool] = None  # default: on (DEFAULT_PARALLEL_TOOL_CALLS)

    _check_tools = field_validator("tools")(validate_tools)

    def changes(self) -> dict:
        """What was given, `null` included (a null removes the key)."""
        return self.model_dump(exclude_unset=True)


class AgentCreate(BaseModel):
    name: Name  # required
    prompt: str
    model_id: int
    config: Optional[AgentConfigInput] = None
    comment: Optional[str] = None  # shown in the history of the agent


class AgentUpdate(BaseModel):
    name: Optional[Name] = None
    prompt: Optional[str] = None
    model_id: Optional[int] = None
    config: Optional[AgentConfigInput] = None
    comment: Optional[str] = None  # shown in the history of the agent
    # Optimistic locking: the number of the version this change is based on. If the
    # agent has moved on since, nothing changes and the answer is 409.
    expected_version: Optional[int] = Field(None, ge=1)
