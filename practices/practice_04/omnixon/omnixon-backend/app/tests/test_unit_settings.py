"""unit settings tests: the one place that reads the environment"""

import pytest

from config import AgentDefaults, Settings


def make(**env):
    return Settings(_env_file=None, **env)


def test_defaults_are_todays(monkeypatch):
    for name in ("REQUEST_TIMEOUT_SECONDS", "UPSTREAM_RETRIES", "MCP_TOOL_ATTEMPTS", "MESSAGE_TTL_DAYS", "REDIS_URL", "AGENT_CALL_DEPTH"):
        monkeypatch.delenv(name, raising=False)
    s = Settings.from_env()
    assert (s.request_timeout_seconds, s.upstream_retries, s.upstream_retry_delay) == (600, 2, 1)
    assert (s.mcp_down_seconds, s.mcp_tool_attempts, s.mcp_tool_retry_delay, s.mcp_tool_retries) == (30, 3, 1, 3)
    assert (s.message_ttl_days, s.usage_ttl_days, s.metrics_ttl_days) == (7, 30, 7)
    assert s.redis_url == "" and s.agent_call_depth == 3


@pytest.mark.parametrize("raw", ["0", "false", "no", "off", "", "FALSE", " Off "])
def test_booleans_read_like_today(raw):
    assert Settings(default_auto_memory=raw, default_parallel_tool_calls=raw).agent_defaults.auto_memory is False
    assert Settings(default_parallel_tool_calls=raw).agent_defaults.parallel_tool_calls is False


def test_default_model_accepts_a_name_or_a_json_body():
    assert Settings(default_model="a/b").default_model_body == {"model": "a/b"}
    assert Settings(default_model='{"model": "a/b", "temperature": 0}').default_model_body == {"model": "a/b", "temperature": 0}


def test_agent_defaults_come_from_the_settings():
    d = Settings(default_message_limit=4, default_memo_limit=5, default_rag_limit=6).agent_defaults
    assert d == AgentDefaults(message_limit=4, memo_limit=5, rag_limit=6, auto_memory=True, parallel_tool_calls=True, tools=("rag", "memory"))


def test_a_tool_attempt_count_is_at_least_one():
    assert Settings(mcp_tool_attempts=0).mcp_tool_attempts == 1


def test_database_is_the_asyncpg_arguments(monkeypatch):
    s = Settings(postgres_host="h", postgres_port=5, postgres_user="u", postgres_password="p", postgres_db="d")
    assert s.database == {"host": "h", "port": 5, "user": "u", "password": "p", "database": "d"}
