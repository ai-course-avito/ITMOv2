from typing import Literal, Optional

from pydantic import BaseModel, model_validator

from .common import Name

RoleName = Literal["regular", "user", "admin", "owner"]


class TokenCreate(BaseModel):
    name: Name  # required
    role: RoleName
    # The agent the token gives access to. Default: the agent in context. A user token may only
    # name its own agent.
    agent_id: Optional[int] = None


class TokenUpdate(BaseModel):
    name: Optional[Name] = None
    role: Optional[RoleName] = None  # the role may be changed up to what the caller may hand out

    @model_validator(mode="after")
    def something_to_change(self):
        if self.name is None and self.role is None:
            raise ValueError("give a name, a role, or both")
        return self
