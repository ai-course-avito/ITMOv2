"""The old module-level constants, now read from `config.Settings` (kept until every user takes its settings from the container)."""

from config import Settings

settings = Settings.from_env()

APP_NAME = settings.app_name
OPENROUTER_TOKEN = settings.openrouter_token
OPENROUTER_PROXY = settings.openrouter_proxy
INITIAL_API_KEY = settings.initial_api_key
LOG_LEVEL = settings.log_level.lower()
REQUEST_TIMEOUT_SECONDS = settings.request_timeout_seconds
UPSTREAM_RETRIES = settings.upstream_retries
UPSTREAM_RETRY_DELAY = settings.upstream_retry_delay
MCP_DOWN_SECONDS = settings.mcp_down_seconds
MCP_TOOL_ATTEMPTS = settings.mcp_tool_attempts
MCP_TOOL_RETRY_DELAY = settings.mcp_tool_retry_delay
MCP_TOOL_RETRIES = settings.mcp_tool_retries
MESSAGE_TTL_DAYS = settings.message_ttl_days
MESSAGE_CLEANUP_INTERVAL_SECONDS = settings.message_cleanup_interval_seconds
USAGE_TTL_DAYS = settings.usage_ttl_days
USAGE_COMPACT_INTERVAL_SECONDS = settings.usage_compact_interval_seconds
METRICS_TTL_DAYS = settings.metrics_ttl_days
DEFAULT_MESSAGE_LIMIT = settings.default_message_limit
DEFAULT_MEMO_LIMIT = settings.default_memo_limit
REDIS_URL = settings.redis_url
AGENT_CALL_DEPTH = settings.agent_call_depth
DEFAULT_RAG_LIMIT = settings.default_rag_limit
DEFAULT_PARALLEL_TOOL_CALLS = settings.default_parallel_tool_calls
DEFAULT_AUTO_MEMORY = settings.default_auto_memory
DEFAULT_MODEL = settings.default_model_body
DATABASE_CONFIG = settings.database
