import json
import os

APP_NAME = os.getenv("APP_NAME")
OPENROUTER_TOKEN = os.getenv("OPENROUTER_TOKEN")
OPENROUTER_PROXY = os.getenv("OPENROUTER_PROXY")
INITIAL_API_KEY = os.getenv("INITIAL_API_KEY")
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").lower()
# A request that takes longer than this is cancelled (504)
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "600"))
# Failures of the model provider (5xx, 429, timeouts) are retried this many more times,
# waiting UPSTREAM_RETRY_DELAY seconds, then twice as long, ...
UPSTREAM_RETRIES = int(os.getenv("UPSTREAM_RETRIES", "2"))
UPSTREAM_RETRY_DELAY = float(os.getenv("UPSTREAM_RETRY_DELAY", "1"))
# An MCP server that does not answer within MCP_PROBE_TIMEOUT seconds is left out of
# the requests for MCP_DOWN_SECONDS
MCP_PROBE_TIMEOUT = float(os.getenv("MCP_PROBE_TIMEOUT", "5"))
MCP_DOWN_SECONDS = float(os.getenv("MCP_DOWN_SECONDS", "30"))
# A call of an MCP tool that does not get through (connection, timeout, HTTP or protocol error) is tried this
# many times in all, waiting MCP_TOOL_RETRY_DELAY seconds, then twice as long, ...; then the model gets the
# error as the tool's result and the answer goes on (ai/mcp_calls.py)
MCP_TOOL_ATTEMPTS = max(1, int(os.getenv("MCP_TOOL_ATTEMPTS", "3")))
MCP_TOOL_RETRY_DELAY = float(os.getenv("MCP_TOOL_RETRY_DELAY", "1"))
# pydantic-ai's retries of an MCP tool whose arguments the model wrote badly (not valid JSON, an unknown
# tool); its default 1 failed whole answers. A server's own `max_retries` wins.
MCP_TOOL_RETRIES = int(os.getenv("MCP_TOOL_RETRIES", "3"))
# Messages older than this many days are no longer used and are deleted (0: keep forever)
MESSAGE_TTL_DAYS = float(os.getenv("MESSAGE_TTL_DAYS", "7"))
# How often expired messages are deleted
MESSAGE_CLEANUP_INTERVAL_SECONDS = float(
    os.getenv("MESSAGE_CLEANUP_INTERVAL_SECONDS", "3600")
)
# Usage rows (what a token spent on the models) older than this many days are folded into one row per
# token, month and model, which then stays (0: never fold)
USAGE_TTL_DAYS = float(os.getenv("USAGE_TTL_DAYS", "30"))
USAGE_COMPACT_INTERVAL_SECONDS = float(
    os.getenv("USAGE_COMPACT_INTERVAL_SECONDS", "3600")
)
# A labelled metric series (e.g. one route and status) that nothing has touched for this
# many days is dropped from /metrics (0: keep forever)
METRICS_TTL_DAYS = float(os.getenv("METRICS_TTL_DAYS", "7"))
# Defaults for agents whose `config` does not set them
DEFAULT_MESSAGE_LIMIT = int(os.getenv("DEFAULT_MESSAGE_LIMIT", "10"))
DEFAULT_MEMO_LIMIT = int(os.getenv("DEFAULT_MEMO_LIMIT", "20"))
# Redis, for the replicas of the api to reach each other's streams (Stop). Unset: one process, nothing shared.
REDIS_URL = os.getenv("REDIS_URL", "").strip()
# How many agents deep one request may go when agents call each other (ask_agent): agent -> 1 -> 2 -> 3
AGENT_CALL_DEPTH = int(os.getenv("AGENT_CALL_DEPTH", "3"))
DEFAULT_RAG_LIMIT = int(
    os.getenv("DEFAULT_RAG_LIMIT", "8")
)  # knowledge entries one `retrieve` call returns
DEFAULT_AUTO_MEMORY = os.getenv("DEFAULT_AUTO_MEMORY", "true").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
    "",
)


def _parse_default_model(raw: str) -> dict:
    """DEFAULT_MODEL is an OpenRouter request body as JSON, or a bare model name."""
    raw = raw.strip()
    if raw.startswith("{"):
        return json.loads(raw)
    return {"model": raw}


DEFAULT_MODEL = _parse_default_model(
    os.getenv(
        "DEFAULT_MODEL",
        '{"model": "z-ai/glm-5.3-20260816", "provider": {"order": ["decart"], "quantizations": ["fp4"]}}',
    )
)

DATABASE_CONFIG = {
    "host": os.getenv("POSTGRES_HOST"),
    "port": int(os.getenv("POSTGRES_PORT")),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "database": os.getenv("POSTGRES_DB"),
}
