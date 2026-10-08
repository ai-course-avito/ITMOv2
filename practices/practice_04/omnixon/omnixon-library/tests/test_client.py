import json

import httpx
import pytest

import base64

from omnixon import AgentConfigInput, AgentConnection, Chat, AgentVersion, Attachment, Client, Interrupted, MCPServer, Memory, Model, TraceStep, VersionDiff
from omnixon.exceptions import (
    Conflict,
    InvalidRequest,
    NoAccess,
    NotFound,
    StreamError,
    UpstreamError,
)

REAL_ASYNC_CLIENT = httpx.AsyncClient  # before the fixtures replace it
TS = "2026-01-01T00:00:00"
BASE = "http://omnixon.test"


def sse(*events):
    """Build an SSE body from (event, payload) tuples; event None means a plain chunk."""
    out = ""
    for event, payload in events:
        if event:
            out += f"event: {event}\n"
        out += f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    return out.encode()


@pytest.fixture
def api(monkeypatch):
    """Client wired to an in-memory handler; `api.handler` is set per test."""

    class Api:
        handler = None
        requests = []

    state = Api()

    def handle(request: httpx.Request) -> httpx.Response:
        state.requests.append(request)
        if request.method == "GET" and request.url.path == "/api/v1/":
            return httpx.Response(200, json={"status": "ok"})
        return state.handler(request)

    transport = httpx.MockTransport(handle)
    real_async, real_sync = httpx.AsyncClient, httpx.Client
    monkeypatch.setattr(
        "omnixon.main.httpx.AsyncClient",
        lambda **kw: real_async(transport=transport, **kw),
    )
    monkeypatch.setattr(
        "omnixon.main.httpx.Client", lambda **kw: real_sync(transport=transport, **kw)
    )
    state.client = Client("tok", BASE)
    state.requests.clear()
    return state


def mcp_json(id=1, url="http://mcp:9100/mcp"):
    return {"id": id, "name": "Maths", "config": {"url": url}, "timestamp": TS}


# Streaming


@pytest.mark.asyncio
async def test_stream_yields_chunks_in_order(api):
    api.handler = lambda r: httpx.Response(
        200,
        content=sse(
            (None, "Hel"),
            (None, "lo, "),
            (None, "мир"),
            ("done", {"id": 1, "agent_id": 1, "external_id": "u", "timestamp": TS}),
        ),
    )
    chunks = [c async for c in api.client.send_message_stream("u", "hi")]

    assert chunks == ["Hel", "lo, ", "мир"]
    request = api.requests[-1]
    assert request.url.path == "/api/v1/request-stream"
    assert json.loads(request.content) == {
        "user_id": "u", "request": "hi", "save_message": True, "use_memo": True,
        "attachments": [], "trace": False, "chat_id": None,
    }
    assert request.headers["authorization"] == "Bearer tok"


@pytest.mark.asyncio
async def test_stream_raises_on_error_event(api):
    api.handler = lambda r: httpx.Response(
        200, content=sse((None, "partial"), ("error", {"detail": "boom"}))
    )
    received = []
    with pytest.raises(StreamError, match="boom"):
        async for chunk in api.client.send_message_stream("u", "hi"):
            received.append(chunk)

    assert received == ["partial"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status, exc", [(403, NoAccess), (404, NotFound), (409, Conflict)]
)
async def test_stream_maps_http_errors(api, status, exc):
    api.handler = lambda r: httpx.Response(status, text="nope")
    with pytest.raises(exc):
        async for _ in api.client.send_message_stream("u", "hi"):
            pass


@pytest.mark.asyncio
async def test_stream_handles_chunks_split_across_lines(api):
    # Newlines inside a chunk are JSON-escaped, so one chunk is always one data line.
    api.handler = lambda r: httpx.Response(
        200, content=sse((None, "line1\nline2"), (None, "\n\n"))
    )
    chunks = [c async for c in api.client.send_message_stream("u", "hi")]
    assert "".join(chunks) == "line1\nline2\n\n"


# MCP servers


@pytest.mark.asyncio
async def test_mcp_server_crud(api):
    def handler(r: httpx.Request):
        path, method = r.url.path, r.method
        if path == "/api/v1/admin/mcp-servers" and method == "POST":
            assert json.loads(r.content) == {"name": "Maths", "config": {"url": "http://mcp:9100/mcp"}}
            return httpx.Response(201, json=mcp_json())
        if path == "/api/v1/admin/mcp-servers" and method == "GET":
            return httpx.Response(200, json=[mcp_json(1), mcp_json(2)])
        if path == "/api/v1/admin/mcp-servers/1" and method == "PATCH":
            return httpx.Response(200, json=mcp_json(1, json.loads(r.content)["config"]["url"]))
        if path == "/api/v1/admin/mcp-servers/1":
            return httpx.Response(200, json=mcp_json())
        return httpx.Response(404)

    api.handler = handler
    c = api.client

    created = await c.create_mcp_server("Maths", {"url": "http://mcp:9100/mcp"})
    assert isinstance(created, MCPServer) and created.id == 1
    assert [m.id for m in await c.get_mcp_servers()] == [1, 2]
    assert (await c.get_mcp_server(1)).config["url"] == "http://mcp:9100/mcp"
    assert (await c.update_mcp_server(1, {"url": "http://other/mcp"})).config == {
        "url": "http://other/mcp"
    }
    assert (await c.delete_mcp_server(1)).id == 1
    with pytest.raises(NotFound):
        await c.get_mcp_server(99)


@pytest.mark.asyncio
async def test_agent_mcp_server_association(api):
    seen = []

    def handler(r: httpx.Request):
        seen.append((r.method, r.url.path))
        if r.method == "DELETE":
            return httpx.Response(200, json=[])
        return httpx.Response(200 if r.method == "GET" else 201, json=[mcp_json(5)])

    api.handler = handler
    c = api.client

    assert [m.id for m in await c.get_agent_mcp_servers(3)] == [5]
    assert [m.id for m in await c.add_agent_mcp_server(3, 5)] == [5]
    assert await c.remove_agent_mcp_server(3, 5) == []
    assert seen == [
        ("GET", "/api/v1/admin/agents/3/mcp-servers"),
        ("POST", "/api/v1/admin/agents/3/mcp-servers/5"),
        ("DELETE", "/api/v1/admin/agents/3/mcp-servers/5"),
    ]


# Models and agents


@pytest.mark.asyncio
async def test_model_crud(api):
    model = {"id": 7, "name": "Fast", "request_json": {"model": "a/b"}, "timestamp": TS}
    api.handler = lambda r: httpx.Response(201 if r.method == "POST" else 200, json=model)
    c = api.client

    created = await c.create_model("Fast", {"model": "a/b"})
    assert isinstance(created, Model) and created.request_json == {"model": "a/b"}
    assert json.loads(api.requests[-1].content) == {"name": "Fast", "request_json": {"model": "a/b"}, "use_proxy": True}
    assert (await c.get_model(7)).id == 7
    assert (await c.update_model(7, {"model": "a/b"})).id == 7
    assert (await c.delete_model(7)).id == 7


@pytest.mark.asyncio
async def test_agent_config_is_sent_and_parsed(api):
    agent = {
        "id": 1, "name": "Helper", "prompt": "p", "model_id": 7, "timestamp": TS,
        "config": {"tools": ["memory"], "message_limit": 4},
    }
    api.handler = lambda r: httpx.Response(201 if r.method == "POST" else 200, json=agent)
    c = api.client

    created = await c.create_agent("Helper", "p", model_id=7, config={"tools": ["memory"], "message_limit": 4})
    assert created.model_id == 7
    assert created.config.tools == ["memory"] and created.config.message_limit == 4
    assert created.config.memo_limit is None
    assert json.loads(api.requests[-1].content) == {
        "name": "Helper", "prompt": "p", "model_id": 7, "config": {"tools": ["memory"], "message_limit": 4},
    }

    await c.create_agent("Helper", "p", model_id=7)  # the service default config applies
    assert json.loads(api.requests[-1].content) == {"name": "Helper", "prompt": "p", "model_id": 7}

    # a typed config works too
    await c.create_agent("Helper", "p", 7, config=AgentConfigInput(memo_limit=3))
    assert json.loads(api.requests[-1].content)["config"] == {"memo_limit": 3}
    await c.create_agent("Helper", "p", 7, config={"rag_limit": 12})  # knowledge entries per search
    assert json.loads(api.requests[-1].content)["config"] == {"rag_limit": 12}
    await c.update_agent(1, config={"rag_limit": None})  # back to the service default (8)
    assert json.loads(api.requests[-1].content)["config"] == {"rag_limit": None}


@pytest.mark.asyncio
async def test_update_agent_sends_only_the_given_changes(api):
    api.handler = lambda r: httpx.Response(
        200, json={"id": 1, "name": "Helper", "prompt": "p", "model_id": 7, "timestamp": TS}
    )
    c = api.client

    await c.update_agent(1, prompt="new")
    assert json.loads(api.requests[-1].content) == {"prompt": "new"}

    # None inside the config is kept: it tells the service to reset that key
    await c.update_agent(1, config={"memo_limit": None, "tools": []})
    assert json.loads(api.requests[-1].content)["config"] == {"memo_limit": None, "tools": []}


@pytest.mark.asyncio
async def test_agent_config_defaults_when_the_service_omits_it(api):
    agent = {"id": 1, "name": "Helper", "prompt": "p", "model_id": 7, "timestamp": TS}
    api.handler = lambda r: httpx.Response(200, json=agent)
    got = await api.client.get_agent(1)
    assert got.config.tools == ["rag", "memory"]
    assert got.config.message_limit is None and got.config.memo_limit is None


# the chain of calls


STEPS = [
    {"step": 1, "kind": "model", "name": "m", "text": "Let me check.", "input_tokens": 10, "output_tokens": 3, "duration_ms": 400},
    {"step": 2, "kind": "tool", "name": "recall", "args": {"query": "tea"}, "result": ["Likes tea."], "duration_ms": 12},
    {"step": 3, "kind": "model", "name": "m", "text": "You like tea."},
]


@pytest.mark.asyncio
async def test_send_message_can_ask_for_the_chain_of_calls(api):
    api.handler = lambda r: httpx.Response(200, json={"response": "hi", "user": USER, "chat_id": 4, "trace": STEPS})
    res = await api.client.send_message("abc", "hello", trace=True)

    assert json.loads(api.requests[-1].content)["trace"] is True
    assert [s.kind for s in res.trace] == ["model", "tool", "model"]
    assert isinstance(res.trace[1], TraceStep) and res.trace[1].args == {"query": "tea"}
    assert res.trace[0].duration_ms == 400 and res.trace[2].error is None

    api.handler = lambda r: httpx.Response(200, json={"response": "hi", "user": USER, "chat_id": 4})
    res = await api.client.send_message("abc", "hello")  # not asked: no trace, and not requested
    assert res.trace is None and json.loads(api.requests[-1].content)["trace"] is False


@pytest.mark.asyncio
async def test_a_stream_collects_the_trace_steps_while_it_runs(api):
    api.handler = lambda r: httpx.Response(
        200,
        content=sse(
            ("user", USER),
            ("trace", STEPS[0]),
            (None, "You like "),
            ("trace", STEPS[1]),
            (None, "tea."),
            ("trace", STEPS[2]),
            ("done", USER),
        ),
    )
    stream = api.client.stream_message("abc", "hi", trace=True)
    chunks = [c async for c in stream]

    assert chunks == ["You like ", "tea."]  # the steps are not text
    assert [s.step for s in stream.trace] == [1, 2, 3]
    assert json.loads(api.requests[-1].content)["trace"] is True


# finding users


@pytest.mark.asyncio
async def test_search_users_asks_for_the_start_of_an_id(api):
    api.handler = lambda r: httpx.Response(200, json=[USER, {**USER, "id": 6, "external_id": "abd"}])
    users = await api.client.search_users("ab", limit=5)

    request = api.requests[-1]
    assert request.url.path.endswith("/api/v1/users")
    assert dict(request.url.params) == {"query": "ab", "limit": "5"}
    assert [u.external_id for u in users] == ["abc", "abd"]


@pytest.mark.asyncio
async def test_search_users_with_too_short_a_query_is_refused_by_the_service(api):
    api.handler = lambda r: httpx.Response(422, json={"detail": [{"msg": "String should have at least 3 characters"}]})
    with pytest.raises(InvalidRequest):
        await api.client.search_users("ab")


# tokens, roles, usage

TOKEN = {"id": 3, "name": "Bot", "agent_id": 9, "role": "regular", "is_initial": False, "timestamp": TS}


@pytest.mark.asyncio
async def test_create_token_sends_name_role_and_agent_and_returns_the_secret_once(api):
    api.handler = lambda r: httpx.Response(201, json={**TOKEN, "role": "user", "token": "abc_secret"})
    made = await api.client.create_token("Bot", "user", agent_id=9)
    assert json.loads(api.requests[-1].content) == {"name": "Bot", "role": "user", "agent_id": 9}
    assert api.requests[-1].url.path == "/api/v1/admin/tokens"
    assert made.token == "abc_secret" and made.role == "user" and made.agent_id == 9

    await api.client.create_token("Bot", "regular")  # the agent defaults to the caller's own
    assert json.loads(api.requests[-1].content) == {"name": "Bot", "role": "regular"}


@pytest.mark.asyncio
async def test_a_token_needs_a_name_and_a_known_role(api):
    from pydantic import ValidationError

    api.handler = lambda r: httpx.Response(201, json=TOKEN)
    with pytest.raises(TypeError):
        await api.client.create_token(role="user")
    with pytest.raises(ValidationError):
        await api.client.create_token("Bot", "superuser")
    with pytest.raises(ValidationError):
        await api.client.create_token(None, "user")
    assert not api.requests


@pytest.mark.asyncio
async def test_tokens_are_listed_renamed_and_deleted_and_never_carry_a_secret(api):
    api.handler = lambda r: httpx.Response(200, json=[TOKEN, {**TOKEN, "id": 4, "role": "admin"}])
    tokens = await api.client.get_tokens()
    assert [t.role for t in tokens] == ["regular", "admin"] and not hasattr(tokens[0], "token")
    assert "agent_id" not in dict(api.requests[-1].url.params)
    await api.client.get_tokens(agent_id=9)
    assert dict(api.requests[-1].url.params) == {"agent_id": "9"}

    api.handler = lambda r: httpx.Response(200, json={**TOKEN, "name": "Renamed"})
    assert (await api.client.rename_token(3, "Renamed")).name == "Renamed"
    assert json.loads(api.requests[-1].content) == {"name": "Renamed"}
    await api.client.update_token(3, role="admin")
    assert json.loads(api.requests[-1].content) == {"role": "admin"}
    await api.client.update_token(3, name="N", role="user")
    assert json.loads(api.requests[-1].content) == {"name": "N", "role": "user"}
    assert api.requests[-1].method == "PATCH"
    assert (await api.client.delete_token(3)).id == 3 and api.requests[-1].method == "DELETE"


@pytest.mark.asyncio
async def test_what_a_token_may_not_do_is_no_access_and_what_is_protected_is_a_conflict(api):
    api.handler = lambda r: httpx.Response(403, json={"detail": "Forbidden: this token may not hand out the admin role"})
    with pytest.raises(NoAccess, match="hand out"):
        await api.client.create_token("x", "admin")
    api.handler = lambda r: httpx.Response(409, json={"detail": "The initial token cannot be deleted"})
    with pytest.raises(Conflict):
        await api.client.delete_token(1)


@pytest.mark.asyncio
async def test_self_calls_use_the_main_api_so_any_role_can_make_them(api):
    api.handler = lambda r: httpx.Response(
        200,
        json=TOKEN if r.url.path.endswith("tokens/self") else
        {"id": 9, "name": "A", "prompt": "", "model_id": 0, "timestamp": TS},
    )
    token = await api.client.get_self_token()
    assert token.role == "regular" and token.agent_id == 9
    assert (await api.client.get_self_agent()).id == 9
    assert [r.url.path for r in api.requests] == ["/api/v1/tokens/self", "/api/v1/agents/self"]


@pytest.mark.asyncio
async def test_act_as_agent_sends_the_header_on_every_call(api):
    api.handler = lambda r: httpx.Response(200, json=[])
    api.client = Client("tok", BASE, act_as_agent=7)
    api.requests.clear()
    await api.client.search_users("abc")
    await api.client.get_tokens()
    assert [r.headers.get("X-Act-As-Agent") for r in api.requests if r.url.path != "/api/v1/"] == ["7", "7"]
    # without it, no header
    plain = Client("tok", BASE)
    api.requests.clear()
    await plain.search_users("abc")
    assert all("X-Act-As-Agent" not in r.headers for r in api.requests)


ROW = {"token_id": 3, "token_name": "Bot", "model": "a/b", "requests": 2, "errors": 1,
       "input_tokens": 10, "output_tokens": 5, "cost": 0.25, "duration_ms_sum": 900}


@pytest.mark.asyncio
async def test_usage_is_read_by_day_and_by_month(api):
    api.handler = lambda r: httpx.Response(200, json=[{**ROW, "day": "2026-10-01"}])
    rows = await api.client.get_usage(days=7, token_id=3)
    assert rows[0].day.isoformat() == "2026-10-01" and rows[0].cost == 0.25 and rows[0].requests == 2
    assert dict(api.requests[-1].url.params) == {"days": "7", "token_id": "3"}
    assert api.requests[-1].url.path == "/api/v1/admin/usage"

    api.handler = lambda r: httpx.Response(200, json=[{**ROW, "token_id": None, "month": "2026-09-01"}])
    monthly = await api.client.get_usage_monthly(agent_id=9)
    assert monthly[0].token_id is None and monthly[0].month.isoformat() == "2026-09-01"  # a deleted token
    assert api.requests[-1].url.path == "/api/v1/admin/usage/monthly"
    assert dict(api.requests[-1].url.params) == {"agent_id": "9"}


@pytest.mark.asyncio
async def test_an_mcp_server_may_be_attached_to_an_agent_when_it_is_made(api):
    api.handler = lambda r: httpx.Response(201, json=mcp_json())
    await api.client.create_mcp_server("Maths", {"url": "u"}, agent_id=4)
    assert json.loads(api.requests[-1].content) == {"name": "Maths", "config": {"url": "u"}, "agent_id": 4}
    await api.client.create_mcp_server("Maths", {"url": "u"})
    assert "agent_id" not in json.loads(api.requests[-1].content)


USER = {"id": 5, "agent_id": 1, "external_id": "abc", "timestamp": TS}


@pytest.mark.asyncio
async def test_send_message_sends_flags_and_returns_user(api):
    api.handler = lambda r: httpx.Response(200, json={"response": "hi", "user": USER, "chat_id": 4})
    res = await api.client.send_message("abc", "hello", save_message=False, use_memo=False)

    assert res.response == "hi" and res.user.external_id == "abc"
    assert json.loads(api.requests[-1].content) == {
        "user_id": "abc", "request": "hello", "save_message": False, "use_memo": False,
        "attachments": [], "trace": False, "chat_id": None,
    }

    await api.client.send_message("abc", "hello")  # defaults
    body = json.loads(api.requests[-1].content)
    assert body["save_message"] is True and body["use_memo"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("user_id, sent", [(None, None), ("", ""), (123, "123")])
async def test_send_message_without_user_id_lets_the_service_create_one(api, user_id, sent):
    api.handler = lambda r: httpx.Response(
        200, json={"response": "hi", "user": {**USER, "external_id": "new"}, "chat_id": 4}
    )
    res = await api.client.send_message(user_id, "hello")
    assert json.loads(api.requests[-1].content)["user_id"] == sent
    assert res.user.external_id == "new"


@pytest.mark.asyncio
async def test_stream_message_exposes_the_user(api):
    api.handler = lambda r: httpx.Response(
        200,
        content=sse(
            ("user", {**USER, "external_id": "new"}),
            (None, "Hel"),
            (None, "lo"),
            ("done", {**USER, "external_id": "new"}),
        ),
    )
    stream = api.client.stream_message(None, "hi", save_message=False, use_memo=False)
    assert stream.user is None

    seen_user_before_first_chunk = None
    chunks = []
    async for chunk in stream:
        if seen_user_before_first_chunk is None:
            seen_user_before_first_chunk = stream.user is not None
        chunks.append(chunk)

    assert chunks == ["Hel", "lo"]
    assert seen_user_before_first_chunk is True
    assert stream.user.external_id == "new"
    assert json.loads(api.requests[-1].content) == {
        "user_id": None, "request": "hi", "save_message": False, "use_memo": False,
        "attachments": [], "trace": False, "chat_id": None,
    }


@pytest.mark.asyncio
async def test_stream_keeps_the_user_when_it_fails_midway(api):
    api.handler = lambda r: httpx.Response(
        200, content=sse(("user", USER), (None, "par"), ("error", {"detail": "boom"}))
    )
    stream = api.client.stream_message(None, "hi")
    with pytest.raises(StreamError, match="boom"):
        async for _ in stream:
            pass
    assert stream.user.external_id == "abc"


@pytest.mark.asyncio
async def test_send_message_stream_passes_flags_through(api):
    api.handler = lambda r: httpx.Response(200, content=sse((None, "x")))
    chunks = [c async for c in api.client.send_message_stream("u", "hi", use_memo=False)]
    assert chunks == ["x"]
    assert json.loads(api.requests[-1].content)["use_memo"] is False


# Memory


def memory_json(id=1, content="Likes tea."):
    return {"id": id, "user_id": 5, "agent_id": 2, "content": content, "timestamp": TS}


@pytest.mark.asyncio
async def test_memory_crud(api):
    seen = []

    def handler(r: httpx.Request):
        seen.append((r.method, r.url.path, dict(r.url.params)))
        if r.method == "GET" and r.url.path.endswith("/memories"):
            return httpx.Response(200, json=[memory_json(2, "b"), memory_json(1, "a")])
        if r.method == "POST":
            body = json.loads(r.content)
            return httpx.Response(201, json=memory_json(3, body["content"]))
        if r.method == "PATCH":
            return httpx.Response(200, json=memory_json(1, json.loads(r.content)["content"]))
        return httpx.Response(200, json=memory_json())

    api.handler = handler
    c = api.client

    listed = await c.get_memories(123, limit=5)
    assert [m.content for m in listed] == ["b", "a"] and isinstance(listed[0], Memory)
    assert seen[-1] == ("GET", "/api/v1/admin/memories", {"user_id": "123", "limit": "5"})

    await c.get_memories("u", agent_id=9)
    assert seen[-1][2]["agent_id"] == "9"

    created = await c.create_memory("u", "Has a cat.", agent_id=9)
    assert created.id == 3 and created.content == "Has a cat."
    assert json.loads(api.requests[-1].content) == {
        "user_id": "u", "content": "Has a cat.", "agent_id": 9,
    }

    assert (await c.get_memory(1)).id == 1
    assert (await c.update_memory(1, "new")).content == "new"
    assert (await c.delete_memory(1)).id == 1
    assert [m for m, *_ in seen[-3:]] == ["GET", "PATCH", "DELETE"]


# Errors carry the service's explanation


@pytest.mark.asyncio
async def test_invalid_requests_raise_with_the_service_message(api):
    api.handler = lambda r: httpx.Response(
        422, json={"detail": [{"msg": "Value error, Unknown tools: teleport"}]}
    )
    with pytest.raises(InvalidRequest, match="Unknown tools: teleport") as info:
        await api.client.create_agent("Helper", "p", 0, config={"tools": ["teleport"]})
    assert info.value.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status, exc, detail",
    [
        (404, NotFound, "User not found"),
        (409, Conflict, "Model is used by an agent"),
        (403, NoAccess, "Forbidden: Admin access required"),
    ],
)
async def test_errors_use_the_service_detail(api, status, exc, detail):
    api.handler = lambda r: httpx.Response(status, json={"detail": detail})
    with pytest.raises(exc, match=detail):
        await api.client.get_memories("u")


@pytest.mark.asyncio
async def test_errors_without_a_detail_keep_the_default_message(api):
    api.handler = lambda r: httpx.Response(404)
    with pytest.raises(NotFound, match="Resource not found"):
        await api.client.get_memory(1)


@pytest.mark.asyncio
async def test_stream_http_errors_carry_the_detail(api):
    api.handler = lambda r: httpx.Response(422, json={"detail": [{"msg": "too long"}]})
    with pytest.raises(InvalidRequest, match="too long"):
        async for _ in api.client.send_message_stream("u" * 100, "hi"):
            pass


@pytest.mark.asyncio
async def test_update_user_only_sends_external_id(api):
    user = {"id": 1, "agent_id": 1, "external_id": "new", "timestamp": TS}
    api.handler = lambda r: httpx.Response(200, json=user)
    await api.client.update_user("old", external_id="new")
    assert json.loads(api.requests[-1].content) == {"external_id": "new"}


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [502, 504])
async def test_provider_and_mcp_failures_are_upstream_errors(api, status):
    api.handler = lambda r: httpx.Response(
        status, json={"detail": "Model provider error: no/such-model is not a valid model ID"}
    )
    with pytest.raises(UpstreamError, match="not a valid model ID") as info:
        await api.client.send_message("u", "hi")
    assert info.value.status_code == status

    with pytest.raises(UpstreamError):  # also before a stream starts
        async for _ in api.client.send_message_stream("u", "hi"):
            pass


# Attachments


PNG = b"\x89PNG\r\n\x1a\nnot really a picture"


def test_attachment_helpers(tmp_path):
    a = Attachment.from_bytes(PNG, "image/png", "p.png")
    assert base64.b64decode(a.data) == PNG and a.media_type == "image/png" and a.name == "p.png"

    path = tmp_path / "scan.pdf"
    path.write_bytes(b"%PDF-1.4")
    b = Attachment.from_file(path)
    assert (b.media_type, b.name, base64.b64decode(b.data)) == ("application/pdf", "scan.pdf", b"%PDF-1.4")

    unknown = tmp_path / "blob.zzz"
    unknown.write_bytes(b"x")
    with pytest.raises(ValueError, match="media_type"):
        Attachment.from_file(unknown)
    assert Attachment.from_file(unknown, media_type="text/plain").media_type == "text/plain"

    c = Attachment.from_url("https://example.com/cat.png")
    assert c.url == "https://example.com/cat.png" and c.data is None


@pytest.mark.asyncio
async def test_attachments_are_sent_with_a_message_and_a_stream(api):
    api.handler = lambda r: httpx.Response(200, json={"response": "red", "user": USER, "chat_id": 4})
    files = [Attachment.from_bytes(PNG, "image/png", "p.png"), {"url": "https://x.test/a.png"}]
    await api.client.send_message("u", "what colour?", attachments=files)

    body = json.loads(api.requests[-1].content)
    assert [sorted(k for k, v in a.items() if v is not None) for a in body["attachments"]] == [
        ["data", "media_type", "name"],
        ["url"],
    ]
    assert body["attachments"][0]["data"] == base64.b64encode(PNG).decode()

    api.handler = lambda r: httpx.Response(200, content=sse((None, "red")))
    chunks = [c async for c in api.client.send_message_stream("u", "what colour?", attachments=files[:1])]
    assert chunks == ["red"]
    assert len(json.loads(api.requests[-1].content)["attachments"]) == 1

    stream = api.client.stream_message("u", "x", attachments=files[:1])
    async for _ in stream:
        pass
    assert json.loads(api.requests[-1].content)["attachments"][0]["media_type"] == "image/png"


# Agent versions


def version_json(number=1, comment="created", **snapshot):
    return {
        "id": number, "agent_id": 3, "number": number, "comment": comment, "created_by_token_id": 1,
        "snapshot": {"prompt": "p", "model_id": 0, **snapshot}, "timestamp": TS,
    }


@pytest.mark.asyncio
async def test_agent_versions(api):
    seen = []

    def handler(r: httpx.Request):
        seen.append((r.method, r.url.path, dict(r.url.params)))
        if r.url.path.endswith("/versions"):
            return httpx.Response(200, json=[version_json(2, "updated"), version_json(1)])
        if r.url.path.endswith("/diff"):
            return httpx.Response(200, json={
                "agent_id": 3, "from_version": 1, "to_version": 2,
                "changes": {"prompt": {"from": "a", "to": "b"}},
            })
        if r.url.path.endswith("/rollback"):
            return httpx.Response(200, json=version_json(3, "rolled back to version 1"))
        return httpx.Response(200, json=version_json(1))

    api.handler = handler
    c = api.client

    versions = await c.get_agent_versions(3)
    assert [v.number for v in versions] == [2, 1] and isinstance(versions[0], AgentVersion)
    assert (await c.get_agent_version(3, 1)).snapshot["prompt"] == "p"

    diff = await c.diff_agent_versions(3, 1)
    assert isinstance(diff, VersionDiff) and diff.changes["prompt"] == {"from": "a", "to": "b"}
    assert seen[-1] == ("GET", "/api/v1/admin/agents/3/versions/1/diff", {})
    await c.diff_agent_versions(3, 1, to=2)
    assert seen[-1][2] == {"to": "2"}

    restored = await c.rollback_agent(3, to=1, comment="oops")
    assert restored.number == 3
    assert seen[-1][:2] == ("POST", "/api/v1/admin/agents/3/rollback")
    assert json.loads(api.requests[-1].content) == {"to": 1, "comment": "oops"}
    await c.rollback_agent(3, to=1)
    assert json.loads(api.requests[-1].content) == {"to": 1}


@pytest.mark.asyncio
async def test_agent_comment_expected_version_and_auto_memory(api):
    agent = {"id": 1, "name": "Helper", "prompt": "p", "model_id": 7, "timestamp": TS, "config": {"auto_memory": True}}
    api.handler = lambda r: httpx.Response(201 if r.method == "POST" else 200, json=agent)
    c = api.client

    created = await c.create_agent("Helper", "p", 7, config={"auto_memory": True}, comment="first")
    assert created.config.auto_memory is True
    assert json.loads(api.requests[-1].content) == {
        "name": "Helper", "prompt": "p", "model_id": 7, "config": {"auto_memory": True}, "comment": "first",
    }

    await c.update_agent(1, prompt="new", comment="reworded", expected_version=4)
    assert json.loads(api.requests[-1].content) == {"prompt": "new", "comment": "reworded", "expected_version": 4}

    api.handler = lambda r: httpx.Response(409, json={"detail": "The agent is at version 5, not 4"})
    with pytest.raises(Conflict, match="version 5"):
        await c.update_agent(1, prompt="x", expected_version=4)


@pytest.mark.asyncio
async def test_messages_carry_the_agent_version(api):
    api.handler = lambda r: httpx.Response(200, json=[
        {"id": 1, "user_id": 5, "content": {"type": "user"}, "timestamp": TS, "agent_version": 3},
        {"id": 2, "user_id": 5, "content": {"type": "assistant"}, "timestamp": TS},
    ])
    history = await api.client.get_history("u")
    assert [m.agent_version for m in history] == [3, None]


@pytest.mark.asyncio
async def test_memories_can_be_searched_by_meaning(api):
    api.handler = lambda r: httpx.Response(200, json=[memory_json(1, "The dog is Rex.")])
    found = await api.client.get_memories("u", query="my pet")
    assert found[0].content == "The dog is Rex."
    assert api.requests[-1].url.params["query"] == "my pet"

    await api.client.get_memories("u")
    assert "query" not in api.requests[-1].url.params


@pytest.mark.asyncio
async def test_ready_asks_the_service_without_a_token(api, monkeypatch):
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200 if request.url.path == "/readyz" else 404, json={"status": "ok"})

    monkeypatch.setattr(
        "omnixon.main.httpx.AsyncClient",
        lambda **kw: REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handle), **kw),
    )
    assert await api.client.ready() is True
    assert calls[-1].url.path == "/readyz" and "authorization" not in calls[-1].headers

    def down(request):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(
        "omnixon.main.httpx.AsyncClient",
        lambda **kw: REAL_ASYNC_CLIENT(transport=httpx.MockTransport(down), **kw),
    )
    assert await api.client.ready() is False


# One connection pool for many calls


@pytest.fixture
def counting(monkeypatch):
    """Like `api`, but counts the httpx clients that get created."""
    created = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path.endswith("request-stream"):
            return httpx.Response(200, content=sse((None, "x")))
        if request.url.path.endswith("/request"):
            return httpx.Response(200, json={"response": "hi", "user": USER, "chat_id": 4})
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handle)
    real_async, real_sync = httpx.AsyncClient, httpx.Client

    def make(**kw):
        client = real_async(transport=transport, **kw)
        created.append(client)
        return client

    monkeypatch.setattr("omnixon.main.httpx.AsyncClient", make)
    monkeypatch.setattr("omnixon.main.httpx.Client", lambda **kw: real_sync(transport=transport, **kw))
    return Client("tok", BASE), created


@pytest.mark.asyncio
async def test_every_call_opens_its_own_connection_by_default(counting):
    client, created = counting
    for _ in range(3):
        await client.get_agents()
    assert len(created) == 3 and all(c.is_closed for c in created)


@pytest.mark.asyncio
async def test_async_with_shares_one_connection_pool(counting):
    client, created = counting
    async with client as shared:
        assert shared is client
        await client.get_agents()
        await client.get_models()
        await client.send_message("u", "hi")
        assert [c async for c in client.send_message_stream("u", "hi")] == ["x"]
        assert len(created) == 1 and not created[0].is_closed  # one pool, still open
    assert created[0].is_closed  # closed on leaving the block

    await client.get_agents()  # still usable afterwards, on a connection of its own
    assert len(created) == 2 and created[1].is_closed


@pytest.mark.asyncio
async def test_aclose_is_safe_to_call_twice(counting):
    client, created = counting
    await client.aclose()  # nothing open
    async with client:
        pass
    await client.aclose()
    assert len(created) == 1 and created[0].is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize("shared", [False, True])
async def test_calls_keep_their_own_timeouts_with_or_without_a_shared_pool(api, shared):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen[request.url.path.rsplit("/", 1)[-1]] = request.extensions["timeout"]["read"]
        if request.url.path.endswith("/request"):
            return httpx.Response(200, json={"response": "hi", "user": USER, "chat_id": 4})
        return httpx.Response(200, json=[])

    api.handler = handler
    if shared:
        async with api.client as client:
            await client.get_agents()
            await client.send_message("u", "hi")
    else:
        await api.client.get_agents()
        await api.client.send_message("u", "hi")

    assert seen["agents"] == 5.0  # plain calls: httpx's default
    assert seen["request"] == 120.0  # what waits for a model


# names

@pytest.mark.asyncio
async def test_names_are_required_on_create_and_optional_on_update(api):
    from pydantic import ValidationError

    api.handler = lambda r: httpx.Response(200, json=mcp_json())
    for call in (
        lambda c: c.create_model(request_json={"model": "a/b"}),
        lambda c: c.create_mcp_server(config={"url": "u"}),
        lambda c: c.create_agent(prompt="p", model_id=0),
        lambda c: c.create_token(role="user"),
    ):
        with pytest.raises(TypeError):
            await call(api.client)
    with pytest.raises(ValidationError):
        await api.client.create_model(None, {"model": "a/b"})
    assert not api.requests  # nothing was sent

    api.handler = lambda r: httpx.Response(200, json=mcp_json())
    await api.client.update_mcp_server(1, name="Renamed")
    assert json.loads(api.requests[-1].content) == {"name": "Renamed", "config": None}
    api.handler = lambda r: httpx.Response(
        200, json={"id": 1, "name": "Renamed", "request_json": {"model": "a/b"}, "timestamp": TS}
    )
    assert (await api.client.update_model(1, name="Renamed")).name == "Renamed"


@pytest.mark.asyncio
async def test_list_rag_lists_without_a_query_and_pages(api):
    entry = {"id": 1, "agent_id": 2, "content": "a", "timestamp": TS}
    api.handler = lambda r: httpx.Response(200, json=[entry])
    assert [e.content for e in await api.client.list_rag(limit=500, offset=1000, agent_id=2)] == ["a"]
    req = api.requests[-1]
    assert req.url.path == "/api/v1/admin/rag"
    assert dict(req.url.params) == {"limit": "500", "offset": "1000", "agent_id": "2"}
    assert "query" not in req.url.params


# the connection of a model


@pytest.mark.asyncio
async def test_a_model_has_a_connection_and_never_a_key(api):
    row = {"id": 7, "name": "Local", "request_json": {"model": "a/b"}, "timestamp": TS,
           "base_url": "http://llm:8000/v1", "use_proxy": False, "has_api_token": True}
    api.handler = lambda r: httpx.Response(201 if r.method == "POST" else 200, json=row)
    c = api.client

    created = await c.create_model("Local", {"model": "a/b"}, base_url="http://llm:8000/v1", use_proxy=False, api_token="sk-1")
    assert (created.base_url, created.use_proxy, created.has_api_token) == ("http://llm:8000/v1", False, True)
    assert not hasattr(created, "api_token")
    assert json.loads(api.requests[-1].content) == {
        "name": "Local", "request_json": {"model": "a/b"}, "base_url": "http://llm:8000/v1", "use_proxy": False, "api_token": "sk-1",
    }

    # only what is given is sent when it changes; "" clears
    await c.update_model(7, use_proxy=True)
    assert {k: v for k, v in json.loads(api.requests[-1].content).items() if v is not None} == {"use_proxy": True}
    await c.update_model(7, base_url="", api_token="")
    assert {k: v for k, v in json.loads(api.requests[-1].content).items() if v is not None} == {"base_url": "", "api_token": ""}

    # a model of an older service has none of the fields: the defaults
    api.handler = lambda r: httpx.Response(200, json={"id": 1, "name": "Old", "request_json": {"model": "a/b"}, "timestamp": TS})
    old = await c.get_model(1)
    assert (old.base_url, old.use_proxy, old.has_api_token) == ("https://openrouter.ai/api/v1", True, False)


# interrupting


@pytest.mark.asyncio
async def test_interrupt_stops_the_stream_of_a_user(api):
    api.handler = lambda r: httpx.Response(200, json={"interrupted": True, "text": "one two"})
    res = await api.client.interrupt("u1")
    assert isinstance(res, Interrupted) and res.interrupted is True and res.text == "one two"
    request = api.requests[-1]
    assert (request.method, request.url.path) == ("POST", "/api/v1/users/u1/interrupt")

    api.handler = lambda r: httpx.Response(200, json={"interrupted": False, "text": ""})
    assert (await api.client.interrupt("u1")).interrupted is False


@pytest.mark.asyncio
async def test_interrupt_maps_errors(api):
    api.handler = lambda r: httpx.Response(404, json={"detail": "User not found"})
    with pytest.raises(NotFound, match="User not found"):
        await api.client.interrupt("nobody")
    api.handler = lambda r: httpx.Response(403, json={"detail": "no"})
    with pytest.raises(NoAccess):
        await api.client.interrupt("u1")


@pytest.mark.asyncio
async def test_a_stream_that_was_cut_ends_cleanly_and_says_so(api):
    api.handler = lambda r: httpx.Response(
        200,
        content=sse(
            ("user", USER),
            (None, "one "),
            (None, "two"),
            ("interrupted", {**USER, "external_id": "u"}),
        ),
    )
    stream = api.client.stream_message("u", "count")
    assert stream.interrupted is False
    chunks = [c async for c in stream]
    assert chunks == ["one ", "two"]
    assert stream.interrupted is True and stream.user.external_id == "u"


@pytest.mark.asyncio
async def test_a_stream_that_finished_is_not_interrupted(api):
    api.handler = lambda r: httpx.Response(200, content=sse((None, "hi"), ("done", USER)))
    stream = api.client.stream_message("u", "hi")
    assert [c async for c in stream] == ["hi"]
    assert stream.interrupted is False


@pytest.mark.asyncio
async def test_recent_users_come_with_their_last_activity(api):
    row = {"id": 1, "agent_id": 2, "external_id": "ann", "timestamp": TS, "last_active": TS, "messages": 4}
    api.handler = lambda r: httpx.Response(200, json=[row, {**row, "id": 2, "external_id": "bob", "messages": 1}])
    users = await api.client.get_recent_users(limit=5)
    assert [(u.external_id, u.messages) for u in users] == [("ann", 4), ("bob", 1)] and users[0].last_active
    request = api.requests[-1]
    assert request.url.path == "/api/v1/users/recent" and dict(request.url.params) == {"limit": "5"}


# chats

CHAT = {"id": 4, "user_id": 1, "title": "Prices", "is_default": False, "timestamp": TS, "updated_at": TS, "messages": 2}


@pytest.mark.asyncio
async def test_chats_are_listed_made_renamed_read_and_deleted(api):
    c = api.client
    api.handler = lambda r: httpx.Response(200, json=[CHAT, {**CHAT, "id": 5, "title": "Default chat", "is_default": True}])
    chats = await c.get_chats("u 1")
    assert [(x.id, x.title, x.is_default, x.messages) for x in chats] == [(4, "Prices", False, 2), (5, "Default chat", True, 2)]
    assert isinstance(chats[0], Chat)
    assert (api.requests[-1].method, api.requests[-1].url.path) == ("GET", "/api/v1/users/u 1/chats")

    api.handler = lambda r: httpx.Response(201, json=CHAT)
    made = await c.create_chat("u", "Prices")
    assert made.id == 4 and json.loads(api.requests[-1].content) == {"title": "Prices"}
    await c.create_chat("u")  # named after the first message
    assert json.loads(api.requests[-1].content) == {"title": None}

    api.handler = lambda r: httpx.Response(200, json={**CHAT, "title": "Plans"})
    assert (await c.rename_chat("u", 4, "Plans")).title == "Plans"
    request = api.requests[-1]
    assert (request.method, request.url.path, json.loads(request.content)) == ("PATCH", "/api/v1/users/u/chats/4", {"title": "Plans"})
    assert (await c.get_chat("u", 4)).id == 4 and api.requests[-1].url.path == "/api/v1/users/u/chats/4"
    assert (await c.delete_chat("u", 4)).id == 4 and api.requests[-1].method == "DELETE"


@pytest.mark.asyncio
async def test_the_history_of_a_chat_is_read_and_cleared(api):
    c = api.client
    api.handler = lambda r: httpx.Response(200, json=[{"id": 1, "user_id": 1, "chat_id": 4, "content": {"type": "user", "content": "hi"}, "timestamp": TS}])
    history = await c.get_chat_history("u", 4)
    assert history[0].chat_id == 4 and history[0].content["content"] == "hi"
    assert api.requests[-1].url.path == "/api/v1/users/u/chats/4/history"
    api.handler = lambda r: httpx.Response(204)
    await c.clear_chat_history("u", 4)
    assert (api.requests[-1].method, api.requests[-1].url.path) == ("DELETE", "/api/v1/users/u/chats/4/history")


@pytest.mark.asyncio
async def test_a_message_goes_to_the_chat_it_is_given_and_the_answer_says_where_it_was_written(api):
    api.handler = lambda r: httpx.Response(200, json={"response": "hi", "user": USER, "chat_id": 9})
    res = await api.client.send_message("u", "hello", chat_id=9)
    assert res.chat_id == 9 and json.loads(api.requests[-1].content)["chat_id"] == 9
    await api.client.send_message("u", "hello")  # no chat: the default one of the user
    assert json.loads(api.requests[-1].content)["chat_id"] is None

    api.handler = lambda r: httpx.Response(200, content=sse((None, "a"), ("done", USER)))
    assert [c async for c in api.client.send_message_stream("u", "hi", chat_id=9)] == ["a"]
    assert json.loads(api.requests[-1].content)["chat_id"] == 9
    stream = api.client.stream_message("u", "hi", chat_id=3)
    [c async for c in stream]
    assert json.loads(api.requests[-1].content)["chat_id"] == 3


@pytest.mark.asyncio
async def test_a_chat_that_is_not_the_users_is_not_found(api):
    api.handler = lambda r: httpx.Response(404, json={"detail": "Chat not found"})
    with pytest.raises(NotFound, match="Chat not found"):
        await api.client.send_message("u", "hi", chat_id=99)
    with pytest.raises(NotFound):
        await api.client.get_chat("u", 99)


@pytest.mark.asyncio
async def test_an_external_id_with_odd_characters_stays_one_part_of_the_path(api):
    api.handler = lambda r: httpx.Response(200, json=[])
    await api.client.get_chats("a/b?c#d")
    assert api.requests[-1].url.raw_path.decode().startswith("/api/v1/users/a%2Fb%3Fc%23d/chats")


@pytest.mark.asyncio
async def test_agent_connections_crud(api):
    conn = {"id": 3, "agent1_id": 1, "agent2_id": 2, "description": "knows prices", "timestamp": "2026-01-01T00:00:00"}

    def handler(r: httpx.Request):
        path, method = r.url.path, r.method
        if path == "/api/v1/admin/agent-connections" and method == "POST":
            assert json.loads(r.content) == {"agent1_id": 1, "agent2_id": 2, "description": "knows prices"}
            return httpx.Response(201, json=conn)
        if path == "/api/v1/admin/agent-connections" and method == "GET":
            return httpx.Response(200, json=[conn] if r.url.params.get("agent_id") == "1" else [conn, {**conn, "id": 4}])
        if path == "/api/v1/admin/agent-connections/3" and method == "PATCH":
            assert json.loads(r.content) == {"description": "knows stock"}
            return httpx.Response(200, json={**conn, "description": "knows stock"})
        if path == "/api/v1/admin/agent-connections/3":
            return httpx.Response(200, json=conn)
        if path == "/api/v1/admin/agent-connections/9":
            return httpx.Response(409, json={"detail": "Agent 1 is already connected to agent 2"})
        return httpx.Response(404, json={"detail": "Agent connection not found"})

    api.handler = handler
    c = api.client
    made = await c.create_agent_connection(1, 2, "knows prices")
    assert isinstance(made, AgentConnection) and made.agent2_id == 2
    assert [x.id for x in await c.get_agent_connections()] == [3, 4]
    assert [x.id for x in await c.get_agent_connections(agent_id=1)] == [3]
    assert (await c.get_agent_connection(3)).description == "knows prices"
    assert (await c.update_agent_connection(3, "knows stock")).description == "knows stock"
    assert (await c.delete_agent_connection(3)).id == 3
    with pytest.raises(NotFound):
        await c.get_agent_connection(5)
    with pytest.raises(Conflict):
        await c.get_agent_connection(9)
