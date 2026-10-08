from typing import Annotated, Optional

from pydantic import BaseModel, Field, StringConstraints

from database.models import NAME_MAX

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NAME_MAX)]


class UserCreate(BaseModel):
    external_id: str = Field(min_length=1, max_length=64)


class UserUpdate(BaseModel):
    external_id: Optional[str] = Field(None, min_length=1, max_length=64)


class Interrupted(BaseModel):
    interrupted: bool  # false: no answer was being streamed to this user
    text: str = ""  # what had been said of it (and is now in the history)


class ChatCreate(BaseModel):
    title: Title | None = None  # empty: named after the first message


class ChatUpdate(BaseModel):
    title: Title
