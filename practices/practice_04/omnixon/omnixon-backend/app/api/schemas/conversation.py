from typing import List, Optional

from pydantic import BaseModel, Field

from ai.attachments import Attachment
from ai.trace import TraceStep
from domain.entities import User


class MessageRequest(BaseModel):
    # The user's external id. Empty or omitted: a new user is created for the agent
    # and returned in the response.
    user_id: Optional[str] = Field(None, max_length=64)
    request: str
    # Save this exchange to the user's history.
    save_message: bool = True
    # Pass the user's previous messages to the model.
    use_memo: bool = True
    # The chat to write in (one of the user's chats, see /users/{id}/chats). Omitted: the default chat of the user, which is where the
    # clients that know nothing about chats (a bot) always are.
    chat_id: Optional[int] = None
    # Files for the model (the model must understand them: e.g. be able to see images)
    attachments: List[Attachment] = []
    # Also return the chain of calls behind the answer: each call to the model and each
    # tool it called (`trace` in the response; `event: trace` in the stream).
    trace: bool = False


class MessageResponse(BaseModel):
    response: str
    user: User
    chat_id: int  # the chat it was written in
    trace: Optional[List[TraceStep]] = None  # only when the request asked for it
