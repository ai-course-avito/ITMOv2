from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class RollbackRequest(BaseModel):
    to: int = Field(ge=1)  # the version to go back to
    comment: Optional[str] = None


class VersionDiff(BaseModel):
    agent_id: int
    from_version: int
    to_version: int
    changes: Dict[str, Dict[str, Any]]  # key -> {"from": ..., "to": ...}
