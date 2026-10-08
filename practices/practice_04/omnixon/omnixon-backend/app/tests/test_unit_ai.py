"""unit ai tests"""

import httpx
import pytest
from pydantic_ai.mcp import MCPServerSSE, MCPServerStreamableHTTP
from pydantic_ai.messages import ModelRequest, ModelResponse
from pydantic_ai.models.test import TestModel
from ai import utils as ai_utils
from ai.agent import generate_agent
from ai.deps import Dependencies
from ai.memory import build_memory_block, format_memories

from shared import (
    FakeDB,
    NOW,
    agent_row,
    memory,
)


def test_generate_model_maps_openrouter_options(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    model = ai_utils.generate_model(
        {
            "model": "a/b",
            "provider": {"order": ["x"]},
            "reasoning": {"effort": "low"},
            "not_a_setting": 1,
        }
    )
    assert model.model_name == "a/b"
    assert model.settings["openrouter_provider"] == {"order": ["x"]}
    assert model.settings["openrouter_reasoning"] == {"effort": "low"}
    assert model.settings["extra_body"] == {"not_a_setting": 1}  # sent as it is

    # the cost is always asked for (OpenRouter usage accounting), unless the model says otherwise
    assert ai_utils.generate_model({"model": "a/b"}).settings == {
        "openrouter_usage": {"include": True}
    }
    own = ai_utils.generate_model({"model": "a/b", "usage": {"include": False}})
    assert own.settings["openrouter_usage"] == {"include": False}


def test_model_settings_pass_every_key_of_the_body_on():
    settings = ai_utils.model_settings(
        {
            "model": "a/b",
            "temperature": 0.2,
            "max_tokens": 12,
            "top_p": 0.9,
            "seed": 7,
            "stop": ["END"],
            "provider": {"order": ["x"]},
            "top_k": 40,
            "min_p": 0.05,
        }
    )
    assert settings == {
        "temperature": 0.2,
        "max_tokens": 12,
        "top_p": 0.9,
        "seed": 7,
        "stop_sequences": ["END"],
        "openrouter_provider": {"order": ["x"]},
        "extra_body": {"top_k": 40, "min_p": 0.05},
    }
    assert ai_utils.model_settings({"model": "a/b"}) == {}


@pytest.mark.asyncio
async def test_http_client_only_exists_with_a_proxy(monkeypatch):
    monkeypatch.setattr(ai_utils, "_http_client", None)
    monkeypatch.setattr(ai_utils, "OPENROUTER_PROXY", None)
    assert ai_utils._get_http_client() is None

    monkeypatch.setattr(ai_utils, "OPENROUTER_PROXY", "socks5://proxy:1080")
    client = ai_utils._get_http_client()
    try:
        assert isinstance(client, httpx.AsyncClient)
        assert ai_utils._get_http_client() is client  # shared
        # not httpx's 5s default, which would cut off slow LLM answers
        assert client.timeout.read == 600 and client.timeout.connect == 5
    finally:
        await client.aclose()


def test_build_mcp_server_transports():
    server = ai_utils.build_mcp_server({"url": "http://mcp/mcp"})
    assert isinstance(server, MCPServerStreamableHTTP)
    assert server.url == "http://mcp/mcp"

    server = ai_utils.build_mcp_server(
        {"url": "http://mcp/mcp", "transport": "streamable_http"}
    )
    assert isinstance(server, MCPServerStreamableHTTP)

    server = ai_utils.build_mcp_server(
        {"url": "http://mcp/sse", "transport": "sse", "headers": {"X-Key": "1"}}
    )
    assert isinstance(server, MCPServerSSE)
    assert server.headers == {"X-Key": "1"}


def test_an_mcp_tool_that_refuses_may_be_called_again_before_the_answer_fails():
    # pydantic-ai's default of 1 failed a whole answer after one wrong call and its one retry
    assert (
        ai_utils.build_mcp_server({"url": "http://mcp/mcp"}).max_retries
        == ai_utils.MCP_TOOL_RETRIES
        == 3
    )
    assert (
        ai_utils.build_mcp_server(
            {"url": "http://mcp/mcp", "max_retries": 0}
        ).max_retries
        == 0
    )


@pytest.mark.asyncio
async def test_history_is_skipped_without_use_memo():
    from database import Message

    messages = [
        Message(
            id=1, user_id=7, content={"type": "user", "content": "hi"}, timestamp=NOW
        ),
        Message(
            id=2,
            user_id=7,
            content={"type": "assistant", "content": "hello"},
            timestamp=NOW,
        ),
    ]
    db = FakeDB(messages=messages)

    history = await ai_utils.get_conversation_history(db, "system text")
    assert [type(m) for m in history] == [ModelRequest, ModelRequest, ModelResponse]
    assert history[0].parts[0].content == "system text"
    assert (
        history[1].parts[0].content == "hi" and history[2].parts[0].content == "hello"
    )

    db.calls.clear()
    history = await ai_utils.get_conversation_history(db, "system text", use_memo=False)
    assert len(history) == 1 and history[0].parts[0].content == "system text"
    assert db.calls == []  # the history was not even read


@pytest.mark.asyncio
async def test_history_never_starts_with_an_answer():
    from database import Message

    def msg(id, kind, text):
        return Message(
            id=id, user_id=7, content={"type": kind, "content": text}, timestamp=NOW
        )

    # a window of the latest 3 messages cuts the first exchange in half
    db = FakeDB(
        messages=[
            msg(2, "assistant", "a1"),
            msg(3, "user", "q2"),
            msg(4, "assistant", "a2"),
        ]
    )
    history = await ai_utils.get_conversation_history(db, "system")
    assert [type(m) for m in history] == [ModelRequest, ModelRequest, ModelResponse]
    assert [m.parts[0].content for m in history] == ["system", "q2", "a2"]

    only_answers = FakeDB(messages=[msg(1, "assistant", "a1")])
    assert len(await ai_utils.get_conversation_history(only_answers, "system")) == 1


def test_format_memories_mentions_hidden_ones():
    shown = [memory(5, "likes tea"), memory(4, "has a cat")]
    assert format_memories(shown, total=2) == "[5] likes tea\n[4] has a cat"

    text = format_memories(shown, total=7)
    assert text.startswith("[5] likes tea\n[4] has a cat\n")
    assert "5 older memories are not shown" in text and "recall" in text


@pytest.mark.asyncio
async def test_memory_block_asks_for_at_most_the_agents_memo_limit():
    db = FakeDB(memories=[memory(2, "likes tea"), memory(1, "has a cat")], total=30)
    prompt = await build_memory_block(db)

    assert db.calls[0] == ("get_memories", 7, 3, 5, None)  # the agent's memo_limit
    assert "[2] likes tea" in prompt and "[1] has a cat" in prompt
    assert "28 older memories are not shown" in prompt
    assert prompt.startswith("<Memory>") and prompt.endswith("</Memory>")


@pytest.mark.asyncio
async def test_memory_block_when_empty_or_unscoped():
    assert "Nothing is remembered" in await build_memory_block(FakeDB())
    assert await build_memory_block(FakeDB(user=False)) == ""
    assert await build_memory_block(FakeDB(agent=False)) == ""


async def run_tools(tools, db, call_tools="all"):
    model = TestModel(call_tools=call_tools)
    agent = generate_agent(model, None, tools)
    await agent.run("hi", deps=Dependencies(db=db))
    return {tool.name for tool in model.last_model_request_parameters.function_tools}


@pytest.mark.asyncio
async def test_agent_registers_only_the_enabled_tools():
    db = FakeDB()
    assert await run_tools(["rag"], db, call_tools=[]) == {"retrieve"}
    assert await run_tools(["memory"], db, call_tools=[]) == {
        "remember",
        "recall",
        "forget",
    }
    assert await run_tools([], db, call_tools=[]) == set()
    assert await run_tools(["rag", "memory"], db, call_tools=[]) == {
        "retrieve",
        "remember",
        "recall",
        "forget",
    }


@pytest.mark.asyncio
async def test_memory_tools_act_on_the_current_user_and_agent():
    db = FakeDB(memories=[memory(1, "something else")])
    await run_tools(["memory"], db, call_tools=["remember", "recall", "forget"])

    # TestModel fills required arguments with sample data ("a", 0); `recall`'s
    # optional query stays empty, meaning "newest memories"
    assert ("create_memory", 7, 3, "a") in db.calls
    assert ("get_memories", 7, 3, 5, None) in db.calls  # no query: the newest
    # the model may only delete the current user's memories of the current agent
    assert ("delete_memory", 0, 7, 3) in db.calls


@pytest.mark.asyncio
async def test_remember_does_not_save_the_same_fact_twice():
    db = FakeDB(memories=[memory(4, "A")])  # TestModel remembers "a"
    await run_tools(["memory"], db, call_tools=["remember"])
    assert not any(
        call[0] == "create_memory" for call in db.calls
    )  # case-insensitive match

    db = FakeDB(memories=[memory(4, "something else")])
    await run_tools(["memory"], db, call_tools=["remember"])
    assert ("create_memory", 7, 3, "a") in db.calls


@pytest.mark.asyncio
async def test_memory_tools_refuse_without_a_user():
    db = FakeDB(user=False)
    await run_tools(["memory"], db, call_tools=["remember", "recall", "forget"])
    assert db.calls == []


@pytest.mark.asyncio
async def test_the_knowledge_search_returns_as_many_entries_as_the_agent_says(
    monkeypatch,
):
    async def embed(text):
        return [0.0]

    monkeypatch.setattr("ai.agent.get_embedding_vector", embed)
    db = FakeDB(rag_limit=3)
    await run_tools(["rag"], db, call_tools=["retrieve"])
    assert ("get_similar_rag", 3) in db.calls


def test_rag_limit_falls_back_to_the_default_of_8():
    assert agent_row({}).rag_limit == 8
    assert agent_row({"rag_limit": 20}).rag_limit == 20
