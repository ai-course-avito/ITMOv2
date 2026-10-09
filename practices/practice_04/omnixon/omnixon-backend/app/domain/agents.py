from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from .models import DEFAULT_BASE_URL


@dataclass(frozen=True)
class AgentSettings:
    """What an agent works with: its config where it says, else the defaults of the deployment."""

    tools: Tuple[str, ...]
    message_limit: int
    memo_limit: int
    rag_limit: int
    auto_memory: bool
    parallel_tool_calls: bool


@dataclass(frozen=True)
class AgentSnapshot:
    """Everything that decides how an agent behaves, as a version holds it (with copies of its model and MCP servers).

    A snapshot made before a key existed means the default of that key; `from_raw` says so, so that an old latest version does not differ
    from every new snapshot (which would record a needless version at the next change)."""

    raw: Dict[str, Any]

    _DEFAULTS = {
        "model_connection": {"base_url": DEFAULT_BASE_URL, "use_proxy": True, "own_api_token": None},
        "connections": [],
    }

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "AgentSnapshot":
        missing = {key: value for key, value in cls._DEFAULTS.items() if key not in raw}
        return cls({**raw, **missing} if missing else dict(raw))

    def diff(self, other: "AgentSnapshot") -> Dict[str, Dict[str, Any]]:
        """What differs: {key: {"from": ..., "to": ...}}."""
        keys = sorted(set(self.raw) | set(other.raw))
        return {k: {"from": self.raw.get(k), "to": other.raw.get(k)} for k in keys if self.raw.get(k) != other.raw.get(k)}
