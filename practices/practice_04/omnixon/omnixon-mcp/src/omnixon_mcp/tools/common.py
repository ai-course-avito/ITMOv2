"""Small things the tools share."""

from __future__ import annotations

import re
from typing import Any

from ..registry import a, b, i, s

SECRET = "<hidden>"


def clip(text: str | None, n: int = 120) -> str:
    flat = re.sub(r"\s+", " ", text or "").strip()
    return flat if len(flat) <= n else flat[: n - 1].rstrip() + "…"


def hide_headers(config: dict) -> dict:
    """An MCP server's config without the values of its headers (they hold secrets, and a model does not need them)."""
    headers = config.get("headers")
    if not isinstance(headers, dict):
        return config
    return {**config, "headers": {k: SECRET for k in headers}}


def mcp_brief(server: dict) -> dict:
    config = server.get("config") or {}
    extra = {k: v for k, v in hide_headers(config).items() if k not in ("url", "transport")}
    return {
        "id": server["id"],
        "name": server["name"],
        "url": config.get("url"),
        "transport": config.get("transport", "streamable_http"),
        **({"options": extra} if extra else {}),
    }


CONFIG_PROPS = {
    "tools": a(
        "Built-in tools of the agent: 'rag' (searches its knowledge base) and 'memory' (remembers facts about a person). [] = none. "
        "Omitted: unchanged (a new agent gets both).",
        {"type": "string", "enum": ["rag", "memory"]},
    ),
    "message_limit": i(
        "How many of the latest messages of a chat the model gets (0-1000; default 10).",
        minimum=0,
        maximum=1000,
    ),
    "memo_limit": i(
        "How many memories about a person the model sees at once (1-1000; default 20).",
        minimum=1,
        maximum=1000,
    ),
    "rag_limit": i(
        "How many knowledge entries one search gives the model (1-100; default 8).", minimum=1, maximum=100
    ),
    "auto_memory": b(
        "After each saved exchange a second model call extracts lasting facts about the person (default on)."
    ),
    "parallel_tool_calls": b(
        "Tools the model calls in the same turn run at the same time, and the model is told to ask for independent ones together: fewer turns, "
        "less time and fewer input tokens (default on). false: one call per turn, one after another."
    ),
}
CONFIG_KEYS = tuple(CONFIG_PROPS)


def config_from(args: dict, reset: list[str] | None = None) -> dict[str, Any] | None:
    """The `config` of a create/update: the keys that were given, and `None` for the ones to go back to the default."""
    config: dict[str, Any] = {k: args[k] for k in CONFIG_KEYS if args.get(k) is not None}
    for key in reset or []:
        config[key] = None
    return config or None


def without_none(**fields: Any) -> dict[str, Any]:
    return {k: v for k, v in fields.items() if v is not None}


def user_note(text: str):
    """A note for the roles that are below admin."""
    return lambda who: "" if who.is_admin else text


def admin_note(text: str):
    return lambda who: text if who.is_admin else ""


STRING = s
