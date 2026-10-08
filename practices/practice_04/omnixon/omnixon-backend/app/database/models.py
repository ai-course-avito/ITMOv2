import json
import hashlib
import secrets

from datetime import datetime
from typing import Optional, Any, Dict, List
from core import (
    INITIAL_API_KEY,
    DEFAULT_AUTO_MEMORY,
    DEFAULT_PARALLEL_TOOL_CALLS,
    DEFAULT_MEMO_LIMIT,
    DEFAULT_RAG_LIMIT,
    DEFAULT_MESSAGE_LIMIT,
    DEFAULT_TOOLS,
)
from pydantic import (
    BaseModel,
    Field,
    computed_field,
    field_validator,
    field_serializer,
    model_validator,
)

NAME_MAX = 120


def prompt_title(prompt: str, limit: int = 60) -> str:
    """The start of a system prompt: its first non-empty line, cut to `limit` characters."""
    for line in (prompt or "").splitlines():
        line = line.strip()
        if line:
            return line if len(line) <= limit else line[: limit - 1].rstrip() + "…"
    return ""


class Named(BaseModel):
    """A row whose name may be NULL (made before names existed): it reads as "" and the
    subclass puts its fallback in (`fallback_name`)."""

    @field_validator("name", mode="before", check_fields=False)
    @classmethod
    def no_null_name(cls, v):
        return "" if v is None else v


from domain.agents import AgentSettings  # noqa: E402
from domain.roles import Role  # noqa: E402
from domain.models import DEFAULT_BASE_URL  # noqa: E402


def fingerprint(secret: Optional[str]) -> Optional[str]:
    """Eight characters of the hash of a secret: enough to see that it changed (versions record it), not enough to find it."""
    return hashlib.sha256(secret.encode()).hexdigest()[:8] if secret else None


class Model(Named):
    id: int
    # Always filled in the answer: the stored name, else the model's own name.
    name: str = ""
    request_json: Dict[str, Any]
    # How it is reached (see migration 12). The answer always has a base_url (OpenRouter's when none is set).
    base_url: str = DEFAULT_BASE_URL
    use_proxy: bool = True
    api_token: Optional[str] = Field(None, exclude=True)  # a secret: never in an answer
    timestamp: datetime

    @field_validator("base_url", mode="before")
    @classmethod
    def default_base_url(cls, v):
        return DEFAULT_BASE_URL if not v else str(v).rstrip("/")

    @computed_field
    @property
    def has_api_token(self) -> bool:
        """Whether the model has a key of its own (the key itself is never shown)."""
        return bool(self.api_token)

    @property
    def connection(self) -> Dict[str, Any]:
        """What generate_model needs besides the body."""
        return {
            "base_url": self.base_url,
            "use_proxy": self.use_proxy,
            "api_token": self.api_token,
        }

    @model_validator(mode="after")
    def fallback_name(self):
        if not (self.name or "").strip():
            model = self.request_json.get("model")
            self.name = (
                model if isinstance(model, str) and model else f"Model {self.id}"
            )
        return self

    @field_validator("request_json", mode="before")
    @classmethod
    def decode_json(cls, v) -> Dict[str, Any]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        elif v is None:
            return {}

        return v


class MCPServer(Named):
    id: int
    name: str = ""  # always filled in the answer: stored name, else "MCP <id>"
    config: Dict[str, Any]
    timestamp: datetime

    @model_validator(mode="after")
    def fallback_name(self):
        if not (self.name or "").strip():
            self.name = f"MCP {self.id}"
        return self

    @field_validator("config", mode="before")
    @classmethod
    def decode_json(cls, v) -> Dict[str, Any]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        elif v is None:
            return {}

        return v


class Memory(BaseModel):
    id: int
    user_id: int
    agent_id: int
    content: str
    timestamp: datetime


class AgentConfig(BaseModel):
    """The JSON in agents.config. A limit that is not set uses the DEFAULT_* env value."""

    tools: List[str] = Field(default_factory=lambda: list(DEFAULT_TOOLS))
    message_limit: Optional[int] = None  # latest messages given to the model
    memo_limit: Optional[int] = None  # memories shown to the model at once
    rag_limit: Optional[int] = None  # knowledge entries one `retrieve` call returns
    auto_memory: Optional[bool] = (
        None  # learn from every exchange (default: DEFAULT_AUTO_MEMORY)
    )
    parallel_tool_calls: Optional[bool] = (
        None  # tools the model calls in one turn run together (default: DEFAULT_PARALLEL_TOOL_CALLS)
    )


class AgentConnection(BaseModel):
    """agent1 may call agent2 (tools list_agents / ask_agent); the description tells agent1 what agent2 is for."""

    id: int
    agent1_id: int
    agent2_id: int
    description: str
    timestamp: datetime


class AgentVersion(BaseModel):
    id: int
    agent_id: int
    number: int
    # prompt, model_id, model (a copy of its request_json), config, mcp_servers
    # (copies of their configs), connections (agents it may call): what is needed to restore the behaviour
    snapshot: Dict[str, Any]
    comment: Optional[str] = None
    created_by_token_id: Optional[int] = None
    timestamp: datetime

    @field_validator("snapshot", mode="before")
    @classmethod
    def decode_json(cls, v) -> Dict[str, Any]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return {} if v is None else v


class Agent(Named):
    id: int
    # Always filled in the answer: the stored name, else the start of the prompt, else "Agent <id>".
    name: str = ""
    prompt: str
    model_id: int
    config: AgentConfig = Field(default_factory=AgentConfig)
    timestamp: datetime

    @field_validator("config", mode="before")
    @classmethod
    def decode_json(cls, v) -> Any:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return {} if v is None else v

    @model_validator(mode="after")
    def fallback_name(self):
        if not (self.name or "").strip():
            self.name = prompt_title(self.prompt) or f"Agent {self.id}"
        return self

    @field_serializer("config")
    def serialize_config(self, config: AgentConfig) -> Dict[str, Any]:
        return config.model_dump(exclude_none=True)  # only what is stored

    def settings(self, defaults) -> AgentSettings:
        """What this agent works with: its config where it says, else `defaults` (a `config.AgentDefaults`)."""
        c = self.config
        pick = lambda value, default: default if value is None else value  # noqa: E731
        return AgentSettings(
            tools=tuple(c.tools),
            message_limit=pick(c.message_limit, defaults.message_limit),
            memo_limit=pick(c.memo_limit, defaults.memo_limit),
            rag_limit=pick(c.rag_limit, defaults.rag_limit),
            auto_memory=pick(c.auto_memory, defaults.auto_memory),
            parallel_tool_calls=pick(c.parallel_tool_calls, defaults.parallel_tool_calls),
        )

    @property
    def tools(self) -> List[str]:
        return self.config.tools

    @property
    def message_limit(self) -> int:
        limit = self.config.message_limit
        return DEFAULT_MESSAGE_LIMIT if limit is None else limit

    @property
    def auto_memory(self) -> bool:
        setting = self.config.auto_memory
        return DEFAULT_AUTO_MEMORY if setting is None else setting

    @property
    def parallel_tool_calls(self) -> bool:
        setting = self.config.parallel_tool_calls
        return DEFAULT_PARALLEL_TOOL_CALLS if setting is None else setting

    @property
    def memo_limit(self) -> int:
        limit = self.config.memo_limit
        return DEFAULT_MEMO_LIMIT if limit is None else limit

    @property
    def rag_limit(self) -> int:
        limit = self.config.rag_limit
        return DEFAULT_RAG_LIMIT if limit is None else limit


# Roles, from the least to the most: what a token may do (see access.py for the rules)
ROLES = ("regular", "user", "admin", "owner")
RANK = {name: i + 1 for i, name in enumerate(ROLES)}


def token_hash(secret: str) -> str:
    """What is stored of a token: the sha256 of the secret (a long random string, so no salt)."""
    return hashlib.sha256(secret.encode()).hexdigest()


class Token(BaseModel):
    """A credential bound to an agent. The secret itself is never stored or returned again."""

    id: int
    name: str
    agent_id: int
    role: str
    token_sha256: str = Field("", exclude=True)  # never in an answer
    timestamp: datetime

    @computed_field
    @property
    def is_initial(self) -> bool:
        """The token of INITIAL_API_KEY: an owner that cannot be deleted or lowered."""
        return bool(INITIAL_API_KEY) and secrets.compare_digest(
            self.token_sha256, token_hash(INITIAL_API_KEY)
        )

    @property
    def rank(self) -> int:
        return RANK[self.role]

    @property
    def as_role(self) -> Role:
        return Role(self.role)

    def may_manage(self, other: "Token") -> bool:
        """Make, rename or delete: only tokens up to the role this one hands out, on agents it may use."""
        if other.rank > self.as_role.grants:
            return False
        return self.as_role.at_least(Role.ADMIN) or other.agent_id == self.agent_id


class NewToken(Token):
    """The answer to making a token: the only time the secret is shown."""

    token: str


class User(BaseModel):
    id: int
    agent_id: int
    external_id: str
    timestamp: datetime


class RecentUser(User):
    last_active: datetime  # the time of the user's latest message that is still kept
    messages: int  # how many of their messages are kept


class Chat(BaseModel):
    """One conversation of a user with the agent. Its messages are its own thread: the model sees only them."""

    id: int
    user_id: int
    # Always filled in the answer: the given (or first-message) title, else a fallback.
    title: str = ""
    is_default: bool = False  # where a request without chat_id goes
    timestamp: datetime
    updated_at: datetime  # the latest message
    messages: int = 0  # how many of its messages are still kept (filled in the list)

    @field_validator("title", mode="before")
    @classmethod
    def no_title_yet(cls, v):
        return v or ""

    @model_validator(mode="after")
    def fallback_title(self):
        if not (self.title or "").strip():
            self.title = "Default chat" if self.is_default else f"Chat {self.id}"
        return self


class Message(BaseModel):
    id: int
    user_id: Optional[int] = None
    chat_id: Optional[int] = None
    agent_version: Optional[int] = None  # of the agent that produced it
    content: Dict[str, Any]
    timestamp: datetime

    @field_validator("content", mode="before")
    @classmethod
    def decode_json(cls, v) -> Dict[str, Any]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return v


class RAG(BaseModel):
    id: int
    agent_id: int
    content: Optional[str] = None
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = {}
    timestamp: datetime

    @field_validator("metadata", mode="before")
    @classmethod
    def decode_json(cls, v) -> Dict[str, Any]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        elif v is None:
            return {}

        return v
