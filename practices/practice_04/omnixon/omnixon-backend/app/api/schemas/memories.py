from typing import Annotated, Optional

from pydantic import BaseModel, StringConstraints

from domain.memory import MAX_MEMORY_CHARS

MemoryText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MEMORY_CHARS)]


class MemoryCreate(BaseModel):
    user_id: str  # the user's external id
    content: MemoryText
    agent_id: Optional[int] = None  # default: the agent in context


class MemoryUpdate(BaseModel):
    content: MemoryText
