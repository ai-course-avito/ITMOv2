"""Settings: the one place that reads the environment. Everything else is given what it needs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Annotated, Any, Optional, Tuple

from pydantic import BeforeValidator, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_MODEL_BODY = '{"model": "z-ai/glm-5.3-20260816", "provider": {"order": ["decart"], "quantizations": ["fp4"]}}'


def _flag(value: Any) -> bool:
    """The way the service has always read a switch: "0", "false", "no", "off" and "" are off, anything else is on."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in ("0", "false", "no", "off", "")


Flag = Annotated[bool, BeforeValidator(_flag)]


@dataclass(frozen=True)
class AgentDefaults:
    """What an agent whose `config` does not say gets."""

    message_limit: int = 10
    memo_limit: int = 20
    rag_limit: int = 8
    auto_memory: bool = True
    parallel_tool_calls: bool = True
    tools: Tuple[str, ...] = ("rag", "memory")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, extra="ignore", case_sensitive=False)

    app_name: Optional[str] = None
    openrouter_token: Optional[str] = None
    openrouter_proxy: Optional[str] = None
    initial_api_key: Optional[str] = None
    log_level: str = "info"
    redis_url: str = ""

    postgres_host: Optional[str] = None
    postgres_port: int = 5432
    postgres_user: Optional[str] = None
    postgres_password: Optional[str] = None
    postgres_db: Optional[str] = None

    # A request that takes longer than this is cancelled (504)
    request_timeout_seconds: float = 600
    # Failures of the model provider (5xx, 429, timeouts) are retried this many more times, waiting this long, then twice as long, ...
    upstream_retries: int = 2
    upstream_retry_delay: float = 1
    # An MCP server that could not be connected to is left alone for this long
    mcp_down_seconds: float = 30
    # A call of an MCP tool that does not get through is tried this many times in all (waiting mcp_tool_retry_delay, doubling)
    mcp_tool_attempts: int = 3
    mcp_tool_retry_delay: float = 1
    # pydantic-ai's retries of a tool whose arguments the model wrote badly; a server's own `max_retries` wins
    mcp_tool_retries: int = 3
    # Messages older than this many days are no longer used and are deleted (0: keep forever)
    message_ttl_days: float = 7
    message_cleanup_interval_seconds: float = 3600
    # Usage rows older than this are folded into one row per token, month and model (0: never fold)
    usage_ttl_days: float = 30
    usage_compact_interval_seconds: float = 3600
    # A labelled metric series untouched for this many days is dropped from /metrics (0: keep forever)
    metrics_ttl_days: float = 7
    # How many agents deep one request may go when agents call each other
    agent_call_depth: int = 3

    default_message_limit: int = 10
    default_memo_limit: int = 20
    default_rag_limit: int = 8
    default_auto_memory: Flag = True
    default_parallel_tool_calls: Flag = True
    default_model: str = DEFAULT_MODEL_BODY

    @field_validator("mcp_tool_attempts")
    @classmethod
    def _at_least_one(cls, value: int) -> int:
        return max(1, value)

    @field_validator("redis_url")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()

    @property
    def database(self) -> dict:
        """The arguments of asyncpg's connect."""
        return {
            "host": self.postgres_host,
            "port": self.postgres_port,
            "user": self.postgres_user,
            "password": self.postgres_password,
            "database": self.postgres_db,
        }

    @property
    def default_model_body(self) -> dict:
        """DEFAULT_MODEL is an OpenRouter request body as JSON, or a bare model name."""
        raw = self.default_model.strip()
        return json.loads(raw) if raw.startswith("{") else {"model": raw}

    @property
    def agent_defaults(self) -> AgentDefaults:
        return AgentDefaults(
            message_limit=self.default_message_limit,
            memo_limit=self.default_memo_limit,
            rag_limit=self.default_rag_limit,
            auto_memory=self.default_auto_memory,
            parallel_tool_calls=self.default_parallel_tool_calls,
        )
