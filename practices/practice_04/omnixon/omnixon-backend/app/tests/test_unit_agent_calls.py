"""unit agent calls tests: connections between agents, their versions, who may act as whom, and list_agents /
ask_agent run end to end with a scripted model (pydantic-ai's FunctionModel) on a scratch database"""

import json

import pytest
from pydantic_ai.messages import (
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import FunctionModel

from access import CallChain, call_chain, may_act_as
from ai import agent_calls
from ai.agent_calls import caller_user_id, connected_agents
from ai.endpoint import agent_run
from database.mixins.agent_version import normal

from shared import scratch_database

NO_TOOLS = {"tools": [], "auto_memory": False}


def scripted(_messages, info):
    """A model whose behaviour is its system prompt: `call <id>` asks agent <id> and repeats what it said, `list`
    repeats list_agents, anything else answers with the prompt itself."""
    prompt = next(
        part.content
        for m in _messages
        for part in getattr(m, "parts", [])
        if isinstance(part, SystemPromptPart)
    )
    returned = [
        p
        for m in _messages
        for p in getattr(m, "parts", [])
        if isinstance(p, ToolReturnPart)
    ]
    if returned:
        return ModelResponse(
            parts=[TextPart(f"[{prompt}] heard: {returned[-1].content}")]
        )
    if prompt.startswith("call "):
        target = int(prompt.split()[1])
        return ModelResponse(
            parts=[
                ToolCallPart(
                    "ask_agent", {"agent_id": target, "request": "hello from " + prompt}
                )
            ]
        )
    if prompt == "list":
        return ModelResponse(parts=[ToolCallPart("list_agents", {})])
    return ModelResponse(parts=[TextPart(f"I am {prompt}")])


@pytest.fixture
def fake_model(monkeypatch):
    monkeypatch.setattr(
        "ai.endpoint.generate_model", lambda *args, **kwargs: FunctionModel(scripted)
    )


def test_the_user_of_a_called_agent_is_the_caller_and_the_person_and_never_too_long():
    assert caller_user_id(7, "alice") == "agent_7:alice"
    long = caller_user_id(7, "x" * 64)
    assert (
        len(long) <= 64
        and long.startswith("agent_7:")
        and long == caller_user_id(7, "x" * 64)
    )
    assert caller_user_id(7, "x" * 64) != caller_user_id(7, "y" * 64)


@pytest.mark.asyncio
async def test_connections_are_part_of_the_callers_versions_and_come_back_with_a_rollback():
    async with scratch_database("conn_versions") as (pool, db):
        a = db.context.agent
        b = await db.create_agent("b", 0, name="b")
        await db.record_agent_version(a.id)
        before = await db.get_latest_version_number(a.id)

        connection = await db.create_agent_connection(a.id, b.id, "knows prices")
        version = await db.record_agent_version(a.id, "connected")
        assert version.number == before + 1
        assert version.snapshot["connections"] == [
            {"agent2_id": b.id, "description": "knows prices"}
        ]
        assert await db.agent_ids_calling(b.id) == [a.id]

        await db.update_agent_connection(connection.id, "knows prices and stock")
        assert (await db.record_agent_version(a.id)).snapshot["connections"][0][
            "description"
        ] == "knows prices and stock"

        await db.delete_agent_connection(connection.id)
        await db.record_agent_version(a.id)
        assert await db.get_agent_connections(a.id) == []

        await db.rollback_agent(a.id, before + 1)  # the version with the connection
        back = await db.get_agent_connections(a.id)
        assert [(c.agent2_id, c.description) for c in back] == [(b.id, "knows prices")]


def test_a_version_made_before_connections_existed_is_not_a_change():
    old = {"prompt": "p", "model_id": 0, "model": {}, "config": {}, "mcp_servers": []}
    assert normal(old)["connections"] == []
    assert normal(normal(old)) == normal(old)


@pytest.mark.asyncio
async def test_a_rollback_skips_a_connection_to_an_agent_that_is_gone():
    async with scratch_database("conn_gone") as (pool, db):
        a = db.context.agent
        b = await db.create_agent("b", 0, name="b")
        await db.create_agent_connection(a.id, b.id, "b")
        number = (await db.record_agent_version(a.id)).number
        await db.delete_agent(b.id)  # the connection goes with it (cascade)
        assert await db.get_agent_connections(a.id) == []
        await db.rollback_agent(a.id, number)
        assert await db.get_agent_connections(a.id) == []


@pytest.mark.asyncio
async def test_a_token_below_admin_may_act_as_an_agent_only_through_a_connection():
    async with scratch_database("conn_access") as (pool, db):
        a, owner = db.context.agent, db.context.token
        b = await db.create_agent("b", 0, name="b")
        c = await db.create_agent("c", 0, name="c")
        await db.create_agent_connection(a.id, b.id, "b")
        assert await may_act_as(db, c.id)  # the owner may act as any agent

        regular = await db.create_token("plain", a.id, "regular")
        db.context.token = await db.get_token_by_secret(regular.token)
        assert not await may_act_as(
            db, b.id
        )  # no chain: the same as X-Act-As-Agent from a client
        reset = call_chain.set(CallChain(agents=(a.id,), human="alice"))
        try:
            assert await may_act_as(db, b.id)  # a -> b
            assert not await may_act_as(db, c.id)  # no a -> c
        finally:
            call_chain.reset(reset)
        db.context.token = owner


@pytest.mark.asyncio
async def test_an_agent_asks_a_connected_one_as_its_caller_and_its_person_and_hears_the_answer(
    fake_model,
):
    async with scratch_database("conn_ask") as (pool, db):
        b = await db.create_agent("I answer", 0, name="Answerer", config=NO_TOOLS)
        a = await db.create_agent(f"call {b.id}", 0, name="Caller", config=NO_TOOLS)
        await db.create_agent_connection(a.id, b.id, "answers questions")
        db.context.agent = a
        db.context.chat = await db.ensure_default_chat()  # tx_user's chat with a

        run = await agent_run(db, "hi")
        assert run.output == f"[call {b.id}] heard: I am I answer"

        # b was asked by "agent_<a>:tx_user", in a chat of its own, and remembers it
        db.context.agent = b
        asked = await db.get_user(f"agent_{a.id}:tx_user")
        assert asked is not None and asked.agent_id == b.id
        db.context.user = asked
        db.context.chat = await db.ensure_default_chat()
        history = [m.content["content"] for m in await db.get_all_messages()]
        assert history == [f"hello from call {b.id}", "I am I answer"]

        usage = await pool.pool.fetch("SELECT kind FROM usage_logs ORDER BY id")
        assert [row["kind"] for row in usage] == [
            "agent_call",
            "request",
        ]  # b finished first
        assert call_chain.get() is None  # nothing is left behind


@pytest.mark.asyncio
async def test_list_agents_shows_the_connected_agents_with_the_description_of_the_connection(
    fake_model,
):
    async with scratch_database("conn_list") as (pool, db):
        b = await db.create_agent("x", 0, name="Prices", config=NO_TOOLS)
        a = await db.create_agent("list", 0, name="Lister", config=NO_TOOLS)
        await db.create_agent_connection(a.id, b.id, "knows the prices")
        db.context.agent = a
        assert await connected_agents(db) == [
            {"id": b.id, "name": "Prices", "description": "knows the prices"}
        ]
        db.context.chat = await db.ensure_default_chat()
        run = await agent_run(db, "who is there?")
        listed = json.loads(run.output.split("heard: ", 1)[1])
        assert listed == [
            {"id": b.id, "name": "Prices", "description": "knows the prices"}
        ]


@pytest.mark.asyncio
async def test_a_chain_never_calls_an_agent_twice_and_never_goes_deeper_than_the_limit(
    fake_model, monkeypatch
):
    async with scratch_database("conn_chain") as (pool, db):
        # a -> b -> a: b may not call a back in the same request
        a = await db.create_agent("placeholder", 0, name="a", config=NO_TOOLS)
        b = await db.create_agent(f"call {a.id}", 0, name="b", config=NO_TOOLS)
        await db.update_agent(a.id, prompt=f"call {b.id}")
        await db.create_agent_connection(a.id, b.id, "b")
        await db.create_agent_connection(b.id, a.id, "a")
        db.context.agent = await db.get_agent(a.id)
        db.context.chat = await db.ensure_default_chat()
        output = (await agent_run(db, "go")).output
        assert (
            f"Refused: agent {a.id} is already in this chain of calls ({a.id} -> {b.id})"
            in output
        )

        # a chain of 5 agents with a depth of 2: the third call is refused
        monkeypatch.setattr(agent_calls, "AGENT_CALL_DEPTH", 2)
        ids = [
            (await db.create_agent("placeholder", 0, name=f"n{i}", config=NO_TOOLS)).id
            for i in range(4)
        ]
        for here, there in zip(ids, ids[1:]):
            await db.update_agent(here, prompt=f"call {there}")
            await db.create_agent_connection(here, there, "next")
        db.context.agent = await db.get_agent(ids[0])
        db.context.chat = await db.ensure_default_chat()
        output = (await agent_run(db, "go")).output
        assert "Refused: this request is already 2 agents deep" in output


@pytest.mark.asyncio
async def test_asking_an_agent_that_is_not_there_or_not_connected_is_refused_in_words(
    fake_model,
):
    async with scratch_database("conn_refused") as (pool, db):
        a = db.context.agent
        assert (await agent_calls.ask(db, 999999, "hi")).startswith(
            "Refused: there is no agent 999999"
        )

        c = await db.create_agent("x", 0, name="c", config=NO_TOOLS)
        regular = await db.create_token("plain", a.id, "regular")
        db.context.token = await db.get_token_by_secret(regular.token)
        answer = await agent_calls.ask(db, c.id, "hi")
        assert (
            answer
            == f"Refused: agent {a.id} has no connection to agent {c.id}. Call list_agents to see which it has."
        )
