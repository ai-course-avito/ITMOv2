from typing import Annotated

from pydantic import BaseModel, StringConstraints

Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class AgentConnectionCreate(BaseModel):
    agent1_id: int  # the one that calls
    agent2_id: int  # the one that is called
    description: Description  # what agent2 is for, as agent1 sees it in list_agents


class AgentConnectionUpdate(BaseModel):
    description: Description
