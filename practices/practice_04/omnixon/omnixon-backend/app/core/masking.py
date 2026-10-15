"""Keeps secrets out of the logs.

Three layers, all used by the JSON log exporter and the debug logging of calls:
- values under a sensitive name (token, password, api_key, ...) are masked;
- the secrets of this deployment (from the environment) are masked wherever they
  appear in a text;
- texts that look like a secret (Bearer credentials, tokens, OpenRouter keys)
  are masked as well.
"""

import inspect
import os
import re
from typing import Any, Callable, Dict, Mapping

from pydantic import BaseModel

MASK = "***"

_SENSITIVE_NAME = re.compile(
    r"token|secret|passw(or)?d|api[_-]?key|authorization|credential|cookie", re.I
)
_BEARER = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}")
_UNIT_TOKEN = re.compile(
    r"\b[0-9A-Za-z]{3}_[0-9A-Za-z]{60}\b"
)  # core's create_api_token
_PROVIDER_KEY = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}")
_URL_PASSWORD = re.compile(r"(?<=://)([^/\s:@]+):[^/\s@]+@")  # user:password@host

# Environment variables holding secrets of this deployment
SECRET_ENV_VARS = (
    "OPENROUTER_API_KEY",
    "OPENROUTER_TOKEN",
    "INITIAL_API_KEY",
    "LOGFIRE_TOKEN",
    "POSTGRES_PASSWORD",
    "OPENROUTER_PROXY",
)
_MIN_SECRET_LENGTH = 6  # shorter values would also match ordinary words


def is_sensitive_name(name: Any) -> bool:
    return isinstance(name, str) and _SENSITIVE_NAME.search(name) is not None


def _known_secrets() -> list:
    values = (os.environ.get(name) for name in SECRET_ENV_VARS)
    # longest first, so a secret that contains another one is masked as a whole
    return sorted(
        {v for v in values if v and len(v) >= _MIN_SECRET_LENGTH}, key=len, reverse=True
    )


def mask_text(text: str) -> str:
    """Mask secrets inside free text (log messages, stack traces, JSON strings)."""
    for secret in _known_secrets():
        text = text.replace(secret, MASK)
    text = _BEARER.sub(lambda m: f"{m.group(1)} {MASK}", text)
    text = _UNIT_TOKEN.sub(MASK, text)
    text = _PROVIDER_KEY.sub(MASK, text)
    return _URL_PASSWORD.sub(rf"\1:{MASK}@", text)


def mask_value(value: Any, name: Any = None) -> Any:
    """A copy of `value` that is safe to log: plain data with secrets masked.

    `name` is the key or parameter the value belongs to. Objects that are not plain
    data are replaced by their type, because their repr could hold anything.
    """
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if is_sensitive_name(name):
        return MASK
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, BaseModel):
        return mask_value(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        return {str(k): mask_value(v, k) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [mask_value(item) for item in value]
    return f"<{type(value).__name__}>"


def mask_arguments(
    func: Callable, args: tuple, kwargs: Dict[str, Any]
) -> Dict[str, Any]:
    """The arguments of a call by parameter name (so `token` is recognised as one),
    masked. `self` is left out."""
    try:
        bound = inspect.signature(func).bind_partial(*args, **kwargs).arguments
    except (TypeError, ValueError):
        bound = {f"arg{i}": value for i, value in enumerate(args)} | kwargs
    return {
        name: mask_value(value, name) for name, value in bound.items() if name != "self"
    }
