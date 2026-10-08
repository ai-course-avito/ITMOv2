import base64
import mimetypes
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typing import Optional, Any, Dict, List, Literal
from datetime import date, datetime


class User(BaseModel):
    id: int
    agent_id: int
    external_id: str
    timestamp: datetime


class RecentUser(User):
    last_active: datetime  # the latest message that is still kept
    messages: int  # how many of their messages are kept


class Chat(BaseModel):
    """One conversation of a user with the agent: its own thread of messages."""

    id: int
    user_id: int
    title: str = ""  # always filled: the given title, the start of the first message, or a fallback
    is_default: bool = False  # where a request without chat_id goes
    timestamp: datetime
    updated_at: datetime  # the latest message
    messages: int = 0  # how many of its messages are still kept


class Message(BaseModel):
    id: int
    user_id: Optional[int] = None
    chat_id: Optional[int] = None
    agent_version: Optional[int] = None  # of the agent that produced it
    content: Dict[str, Any]
    timestamp: datetime


class Model(BaseModel):
    id: int
    name: str = ""  # always filled: the given name, else the model's own name
    request_json: Dict[str, Any]
    # How it is reached. base_url is always filled (OpenRouter's when the model has none of its own).
    base_url: str = "https://openrouter.ai/api/v1"
    use_proxy: bool = True  # False: the service calls it directly, not through its proxy
    has_api_token: bool = False  # whether it has a key of its own; the key is never returned
    timestamp: datetime


class Interrupted(BaseModel):
    interrupted: bool  # False: nothing was being streamed to that user
    text: str = ""  # what had been said of the answer (it is in the history now)


class Memory(BaseModel):
    id: int
    user_id: int
    agent_id: int
    content: str
    timestamp: datetime


class MCPServer(BaseModel):
    id: int
    name: str = ""  # the given name, else "MCP <id>"
    config: Dict[str, Any]
    timestamp: datetime


class AgentConnection(BaseModel):
    """agent1 may call agent2 (its built-in tools list_agents and ask_agent); the description tells agent1
    what agent2 is for."""

    id: int
    agent1_id: int
    agent2_id: int
    description: str
    timestamp: datetime


class AgentConfig(BaseModel):
    """The settings stored for an agent. A limit that is not set uses the service default."""

    tools: List[str] = ["rag", "memory"]
    message_limit: Optional[int] = None
    memo_limit: Optional[int] = None
    rag_limit: Optional[int] = None
    auto_memory: Optional[bool] = None


class AgentVersion(BaseModel):
    id: int
    agent_id: int
    number: int
    # prompt, model_id, model (a copy of its request_json), config, mcp_servers (copies)
    snapshot: Dict[str, Any]
    comment: Optional[str] = None
    created_by_token_id: Optional[int] = None
    timestamp: datetime


class Agent(BaseModel):
    id: int
    name: str = ""  # the given name, else the start of the prompt, else "Agent <id>"
    prompt: str
    model_id: int
    config: AgentConfig = AgentConfig()
    timestamp: datetime


Role = Literal["regular", "user", "admin", "owner"]
ROLES = ("regular", "user", "admin", "owner")  # from the least to the most


class Token(BaseModel):
    """A credential bound to an agent. Its secret is known only when it is made (see NewToken)."""

    id: int
    name: str
    agent_id: int
    role: Role
    # The token of the service's INITIAL_API_KEY: an owner that cannot be deleted or lowered.
    is_initial: bool = False
    timestamp: datetime


class NewToken(Token):
    """The answer to `create_token`: `token` is the secret, shown only here."""

    token: str


class UsageRow(BaseModel):
    """What one token spent on one model: counts, tokens and money (no texts). `cost` adds up what
    the provider reported."""

    token_id: Optional[int] = None  # None: the token has been deleted
    token_name: str
    model: str
    requests: int
    errors: int
    input_tokens: int
    output_tokens: int
    cost: float
    duration_ms_sum: int


class DailyUsage(UsageRow):
    day: date


class MonthlyUsage(UsageRow):
    month: date


class RAG(BaseModel):
    id: int
    agent_id: int
    content: Optional[str] = None
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = {}
    timestamp: datetime


class AgentConfigInput(BaseModel):
    """Settings of an agent to create or change. Only the keys that are set are sent,
    and a key set to None goes back to its default."""

    model_config = ConfigDict(extra="forbid")

    tools: Optional[List[str]] = None
    message_limit: Optional[int] = None
    memo_limit: Optional[int] = None
    rag_limit: Optional[int] = None
    auto_memory: Optional[bool] = None


class AgentCreate(BaseModel):
    name: str
    prompt: str
    model_id: int
    config: Optional[AgentConfigInput] = None
    comment: Optional[str] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    prompt: Optional[str] = None
    model_id: Optional[int] = None
    config: Optional[AgentConfigInput] = None
    comment: Optional[str] = None
    expected_version: Optional[int] = None


class RollbackRequest(BaseModel):
    to: int
    comment: Optional[str] = None


class VersionDiff(BaseModel):
    agent_id: int
    from_version: int
    to_version: int
    changes: Dict[str, Dict[str, Any]]  # key -> {"from": ..., "to": ...}


class ModelCreate(BaseModel):
    name: str
    request_json: dict
    base_url: Optional[str] = None  # None: OpenRouter
    use_proxy: bool = True
    api_token: Optional[str] = None  # None: the key of the service


class ModelUpdate(BaseModel):
    name: Optional[str] = None
    request_json: Optional[dict] = None
    base_url: Optional[str] = None  # "": back to OpenRouter
    use_proxy: Optional[bool] = None
    api_token: Optional[str] = None  # "": back to the key of the service


class AgentConnectionCreate(BaseModel):
    agent1_id: int
    agent2_id: int
    description: str


class AgentConnectionUpdate(BaseModel):
    description: str


class MCPServerCreate(BaseModel):
    name: str
    config: dict
    agent_id: Optional[int] = None


class MCPServerUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None


class MemoryCreate(BaseModel):
    user_id: str
    content: str
    agent_id: Optional[int] = None


class MemoryUpdate(BaseModel):
    content: str


class TokenCreate(BaseModel):
    name: str
    role: Role
    agent_id: Optional[int] = None


class TokenUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[Role] = None


class UserCreate(BaseModel):
    external_id: str


class Attachment(BaseModel):
    """A file for the model: give either `url` or `data` (base64)."""

    url: Optional[str] = None  # http(s) URL the model provider can fetch
    data: Optional[str] = None  # the file, base64-encoded
    media_type: Optional[str] = None  # image/png, application/pdf, ...
    name: Optional[str] = None  # shown in the history

    @classmethod
    def from_bytes(
        cls, data: bytes, media_type: str, name: Optional[str] = None
    ) -> "Attachment":
        return cls(
            data=base64.b64encode(data).decode("ascii"),
            media_type=media_type,
            name=name,
        )

    @classmethod
    def from_file(cls, path, media_type: Optional[str] = None) -> "Attachment":
        """Read a file; its type is guessed from its name unless given."""
        path = Path(path)
        media_type = media_type or mimetypes.guess_type(path.name)[0]
        if not media_type:
            raise ValueError(f"Cannot tell the type of {path.name}: give media_type")
        return cls.from_bytes(path.read_bytes(), media_type, path.name)

    @classmethod
    def from_url(
        cls, url: str, media_type: Optional[str] = None, name: Optional[str] = None
    ) -> "Attachment":
        return cls(url=url, media_type=media_type, name=name)


class TraceStep(BaseModel):
    """One step of the chain of calls behind an answer: a call to the model, or a tool
    (built-in or of an MCP server) that the model called."""

    step: int  # 1, 2, 3 ... in the order the steps finished
    kind: Literal["model", "tool"]
    name: str  # the model, or the tool
    args: Optional[Any] = None  # arguments of a tool call
    result: Optional[Any] = None  # what a tool returned (clipped by the service)
    text: Optional[str] = None  # what the model wrote in that call
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None  # a tool that failed, or never answered


class ChatCreate(BaseModel):
    title: Optional[str] = None  # None: named after the first message


class ChatUpdate(BaseModel):
    title: str


class MessageRequest(BaseModel):
    user_id: Optional[str] = None
    request: str
    chat_id: Optional[int] = None
    save_message: bool = True
    use_memo: bool = True
    attachments: List[Attachment] = []
    trace: bool = False


class MessageResponse(BaseModel):
    response: str
    user: User
    chat_id: int  # the chat it was written in
    trace: Optional[List[TraceStep]] = None  # only when the request asked for it


class UserUpdate(BaseModel):
    external_id: Optional[str] = None


class RAGCreate(BaseModel):
    content: str
    embedding_content: Optional[str] = None
    metadata: Optional[dict] = None


class RAGUpdate(BaseModel):
    content: str
    embedding_content: Optional[str] = None
    metadata: Optional[dict] = None
