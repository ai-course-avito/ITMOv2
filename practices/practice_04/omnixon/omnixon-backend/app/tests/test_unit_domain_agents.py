"""unit domain tests: settings, snapshots and the call chain are objects with the rules in them"""

from config import AgentDefaults
from domain.agents import AgentSettings, AgentSnapshot
from domain.chain import CallChain, caller_user_id
from domain.models import ModelConnection
from shared import agent_row

DEFAULTS = AgentDefaults(message_limit=10, memo_limit=20, rag_limit=8, auto_memory=True, parallel_tool_calls=True)


def test_settings_fall_back_to_the_defaults():
    s = agent_row({"memo_limit": 3, "auto_memory": False, "tools": ["rag"]}).settings(DEFAULTS)
    assert s == AgentSettings(tools=("rag",), message_limit=10, memo_limit=3, rag_limit=8, auto_memory=False, parallel_tool_calls=True)
    assert agent_row({}).settings(AgentDefaults(rag_limit=2)).rag_limit == 2


def test_a_version_made_before_connections_existed_is_not_a_change():
    old = {"prompt": "p", "model_id": 0, "model": {}, "config": {}, "mcp_servers": []}
    snapshot = AgentSnapshot.from_raw(old)
    assert snapshot.raw["connections"] == [] and snapshot.raw["model_connection"]["use_proxy"] is True
    assert AgentSnapshot.from_raw(snapshot.raw) == snapshot


def test_a_diff_names_what_changed_and_nothing_else():
    a = AgentSnapshot.from_raw({"prompt": "a", "model_id": 0, "model": {}, "config": {}, "mcp_servers": []})
    b = AgentSnapshot.from_raw({"prompt": "b", "model_id": 0, "model": {}, "config": {}, "mcp_servers": []})
    assert a.diff(b) == {"prompt": {"from": "a", "to": "b"}}
    assert a.diff(a) == {}


def test_a_key_is_shown_by_a_fingerprint_not_by_itself():
    assert ModelConnection("https://x", True, None).fingerprint() is None
    fingerprint = ModelConnection("https://x", True, "secret-key").fingerprint()
    assert len(fingerprint) == 8 and "secret" not in fingerprint


def test_the_user_of_a_called_agent_is_the_caller_and_the_person_and_never_too_long():
    assert caller_user_id(7, "alice") == "agent_7:alice"
    long = caller_user_id(7, "x" * 64)
    assert len(long) <= 64 and long.startswith("agent_7:") and long == caller_user_id(7, "x" * 64)
    assert caller_user_id(7, "x" * 64) != caller_user_id(7, "y" * 64)


def test_a_chain_refuses_a_loop_and_a_depth_in_words():
    chain = CallChain(agents=(1, 2), human="alice")
    assert chain.then(3).agents == (1, 2, 3)
    assert chain.refusal(1, depth=3) == "Refused: agent 1 is already in this chain of calls (1 -> 2); an agent is not called twice."
    assert chain.refusal(3, depth=1) == "Refused: this request is already 1 agents deep, the most that one request may go."
    assert chain.refusal(3, depth=3) is None
