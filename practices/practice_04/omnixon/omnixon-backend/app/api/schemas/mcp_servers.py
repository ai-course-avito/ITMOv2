from typing import Optional

from pydantic import BaseModel, field_validator

from ai.capabilities.mcp import MCP_OPTIONS
from .common import Name


def _validate_mcp_config(value: dict) -> dict:
    if not isinstance(value.get("url"), str) or not value["url"]:
        raise ValueError('config must contain a non-empty "url" string')
    if value.get("transport", "streamable_http") not in ("streamable_http", "sse"):
        raise ValueError('transport must be "streamable_http" or "sse"')
    unknown = sorted(set(value) - {"url", "transport"} - MCP_OPTIONS)
    if unknown:
        raise ValueError(f"Unknown options: {', '.join(unknown)}. Allowed: url, transport, {', '.join(sorted(MCP_OPTIONS))}")
    return value


class MCPServerCreate(BaseModel):
    name: Name  # required
    config: dict
    # Attach the new server to this agent at once. A user token always does it, to its own agent (the
    # only agent it may give one to); an admin may leave it out to make a server of nobody's.
    agent_id: Optional[int] = None

    _check = field_validator("config")(_validate_mcp_config)


class MCPServerUpdate(BaseModel):
    name: Optional[Name] = None
    config: Optional[dict] = None

    @field_validator("config")
    @classmethod
    def _check(cls, value):
        return None if value is None else _validate_mcp_config(value)
