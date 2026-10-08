"""unit core tests"""

import pytest
from core import (
    DEFAULT_MEMO_LIMIT,
    DEFAULT_MESSAGE_LIMIT,
    DEFAULT_TOOLS,
    validate_tools,
)
from database import models as database_models
from database.models import Token, token_hash

from shared import (
    NOW,
    agent_row,
)


def test_only_the_token_of_initial_api_key_is_initial(monkeypatch):
    monkeypatch.setattr(database_models, "INITIAL_API_KEY", "the-initial-key")
    row = dict(id=1, name="t", agent_id=1, role="owner", timestamp=NOW)
    assert Token(token_sha256=token_hash("the-initial-key"), **row).is_initial is True
    assert Token(token_sha256=token_hash("another-key"), **row).is_initial is False
    assert (
        Token(token_sha256=token_hash("the-initial-key"), **row).model_dump()[
            "is_initial"
        ]
        is True
    )

    # without a key nobody is initial (an empty token must not match an empty key)
    monkeypatch.setattr(database_models, "INITIAL_API_KEY", None)
    assert Token(token_sha256=token_hash(""), **row).is_initial is False
    monkeypatch.setattr(database_models, "INITIAL_API_KEY", "")
    assert Token(token_sha256=token_hash(""), **row).is_initial is False


def test_a_token_never_carries_its_hash_out():
    token = Token(
        id=1,
        name="t",
        agent_id=1,
        role="user",
        token_sha256=token_hash("secret"),
        timestamp=NOW,
    )
    assert "token_sha256" not in token.model_dump()
    assert "secret" not in token.model_dump_json()
    assert token_hash("secret") not in token.model_dump_json()
    assert token.rank == 2


def test_unused_metric_series_expire_after_the_ttl():
    from prometheus_client import CollectorRegistry, Counter, generate_latest
    from core.metrics import Expiring

    registry = CollectorRegistry()
    now = [0.0]
    requests = Expiring(
        Counter("t_requests_total", "x", ["path"], registry=registry),
        clock=lambda: now[0],
    )
    week = 7 * 86400

    requests.labels("/old").inc()
    now[0] = 6 * 86400
    requests.labels("/busy").inc()
    now[0] = week + 1  # /old was last used more than a week ago, /busy one day ago
    assert requests.expire(week) == 1
    page = generate_latest(registry).decode()
    assert 'path="/old"' not in page and 'path="/busy"' in page

    # using a series again keeps it; a series that comes back is a fresh one
    requests.labels("/busy").inc()
    now[0] = 2 * week + 2
    assert requests.expire(week) == 1  # /busy was used at week+1, which is now old too
    requests.labels("/busy").inc()
    assert 't_requests_total{path="/busy"} 1.0' in generate_latest(registry).decode()

    # a ttl of 0 keeps everything
    now[0] = 100 * week
    assert (
        requests.expire(0) == 0 and 'path="/busy"' in generate_latest(registry).decode()
    )


def test_the_metrics_page_drops_stale_series(monkeypatch):
    from core import metrics

    clock = [1000.0]
    monkeypatch.setattr(metrics.HTTP_REQUESTS, "clock", lambda: clock[0])
    metrics.HTTP_REQUESTS.labels("GET", "/ttl-probe", "200").inc()
    assert b"/ttl-probe" in metrics.render()[0]
    clock[0] += 8 * 86400
    assert b"/ttl-probe" not in metrics.render()[0]
    monkeypatch.setattr(metrics.HTTP_REQUESTS, "clock", __import__("time").monotonic)


def test_default_tools_are_rag_and_memory():
    assert DEFAULT_TOOLS == ["rag", "memory"]


def test_validate_tools():
    assert validate_tools(None) is None
    assert validate_tools([]) == []
    assert validate_tools(["memory", "rag", "memory"]) == ["memory", "rag"]
    with pytest.raises(ValueError, match="teleport"):
        validate_tools(["rag", "teleport"])


def test_agent_config_defaults_and_limits():
    agent = agent_row({})  # nothing stored
    assert agent.tools == DEFAULT_TOOLS
    assert agent.message_limit == DEFAULT_MESSAGE_LIMIT
    assert agent.memo_limit == DEFAULT_MEMO_LIMIT

    agent = agent_row({"tools": ["rag"], "message_limit": 3, "memo_limit": 4})
    assert (agent.tools, agent.message_limit, agent.memo_limit) == (["rag"], 3, 4)
    assert agent_row({"message_limit": 0}).message_limit == 0  # 0 is a real value


def test_agent_config_is_decoded_from_json_text_and_serialized_as_stored():
    # asyncpg hands jsonb over as text
    agent = agent_row('{"tools": ["memory"], "memo_limit": 2}')
    assert agent.tools == ["memory"] and agent.memo_limit == 2
    assert agent.model_dump()["config"] == {"tools": ["memory"], "memo_limit": 2}

    assert agent_row(None).model_dump()["config"] == {"tools": DEFAULT_TOOLS}
    assert agent_row("not json").tools == DEFAULT_TOOLS


def test_default_limits_are_sane():
    assert DEFAULT_MESSAGE_LIMIT >= 0 and DEFAULT_MEMO_LIMIT >= 1
