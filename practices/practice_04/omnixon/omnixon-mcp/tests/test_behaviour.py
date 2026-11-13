"""What the tools send to the service and what they give back, against a service that is only a table of answers."""

import json

import httpx
import pytest

from omnixon_mcp import tools as _tools  # noqa: F401
from omnixon_mcp.access import Identity
from omnixon_mcp.api import ToolError
from omnixon_mcp.registry import REGISTRY, run
from omnixon_mcp.server import Backend, token_of


class Service:
    """Answers by `METHOD /path`; a value is a json body, a (status, body) pair, or a function of the request. Remembers what it was asked."""

    def __init__(self, **answers):
        self.answers = dict(answers)
        self.requests: list[httpx.Request] = []

    def on(self, key: str, value):
        self.answers[key] = value
        return self

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = f"{request.method} {request.url.path}"
        if key not in self.answers:
            return httpx.Response(404, json={"detail": f"nothing for {key} in the test"})
        value = self.answers[key]
        value = value(request) if callable(value) else value
        if isinstance(value, httpx.Response):
            return value
        status, body = value if isinstance(value, tuple) else (200, value)
        return httpx.Response(status, json=body) if body is not None else httpx.Response(status)

    def last(self, method: str, path: str) -> httpx.Request:
        return [r for r in self.requests if r.method == method and r.url.path == path][-1]

    def body(self, method: str, path: str):
        return json.loads(self.last(method, path).content)

    def paths(self) -> list[str]:
        return [f"{r.method} {r.url.path}" for r in self.requests]


def who(role="admin", agent=5) -> Identity:
    return Identity(token_id=1, name="boss", role=role, agent_id=agent)


async def call(service: Service, name: str, args: dict | None = None, role="admin", agent=5):
    http = httpx.AsyncClient(transport=httpx.MockTransport(service), base_url="http://omnixon")
    return await run(REGISTRY[name], http, "secret-token", who(role, agent), args or {})


def parsed(text: str):
    return json.loads(text)


AGENT = {
    "id": 5,
    "name": "Boss",
    "prompt": "You manage agents.",
    "model_id": 0,
    "config": {"tools": []},
    "timestamp": "t",
}


@pytest.mark.asyncio
async def test_whoami_says_the_role_the_agent_and_what_may_be_handed_out():
    service = Service()
    service.on(
        "GET /api/v1/tokens/self",
        {"id": 1, "name": "boss", "role": "user", "agent_id": 5, "is_initial": False, "timestamp": "t"},
    )
    service.on("GET /api/v1/agents/self", AGENT)
    result = parsed(await call(service, "whoami", role="user"))
    assert result["token"]["role"] == "user" and result["agent"]["name"] == "Boss"
    assert "own agent" in result["may_hand_out_tokens"]


@pytest.mark.asyncio
async def test_about_omnixon_explains_the_service_and_this_token():
    text = await call(Service(), "about_omnixon", role="owner")
    assert (
        "VERSION" in text
        and "Connection (agent A -> agent B)" in text
        and "role owner, agent 5" in text
        and "any role" in text
    )


@pytest.mark.asyncio
async def test_get_agent_is_one_call_for_everything_and_a_user_token_asks_only_what_it_may():
    service = Service()
    service.on("GET /api/v1/admin/agents/5", AGENT)
    service.on("GET /api/v1/admin/agents/5/versions", [{"number": 7}, {"number": 6}])
    service.on(
        "GET /api/v1/admin/agents/5/mcp-servers",
        [
            {
                "id": 3,
                "name": "Maths",
                "config": {"url": "http://m/mcp", "headers": {"Authorization": "Bearer xyz"}, "timeout": 5},
            }
        ],
    )
    service.on("GET /api/v1/admin/models", [{"id": 0, "name": "glm"}])
    result = parsed(await call(service, "get_agent", role="user"))
    assert result["latest_version"] == 7 and result["model"] == {"id": 0, "name": "glm"}
    assert result["defaults_of_unset_config"]["rag_limit"] == 8
    assert result["mcp_servers"] == [
        {
            "id": 3,
            "name": "Maths",
            "url": "http://m/mcp",
            "transport": "streamable_http",
            "options": {"headers": {"Authorization": "<hidden>"}, "timeout": 5},
        }
    ]
    assert "xyz" not in json.dumps(result)  # a secret in a header is not given to a model
    assert "may_call" not in result and not any(
        "agent-connections" in p for p in service.paths()
    )  # a user token may not read them


@pytest.mark.asyncio
async def test_get_agent_of_an_admin_names_who_it_may_call_and_who_calls_it():
    service = Service()
    service.on("GET /api/v1/admin/agents/9", {**AGENT, "id": 9, "name": "Mid"})
    service.on("GET /api/v1/admin/agents/9/versions", [])
    service.on("GET /api/v1/admin/agents/9/mcp-servers", [])
    service.on("GET /api/v1/admin/models", [])
    service.on(
        "GET /api/v1/admin/agents",
        [{"id": 5, "name": "Boss"}, {"id": 9, "name": "Mid"}, {"id": 2, "name": "Prices"}],
    )
    service.on(
        "GET /api/v1/admin/agent-connections",
        [
            {"id": 1, "agent1_id": 9, "agent2_id": 2, "description": "knows prices"},
            {"id": 2, "agent1_id": 5, "agent2_id": 9, "description": "does the work"},
        ],
    )
    result = parsed(await call(service, "get_agent", {"agent_id": 9}))
    assert result["may_call"] == [{"agent_id": 2, "name": "Prices", "description": "knows prices"}]
    assert result["called_by"] == [{"agent_id": 5, "name": "Boss"}]


@pytest.mark.asyncio
async def test_create_agent_sends_only_what_was_given_and_update_can_reset_a_setting():
    service = Service()
    service.on("POST /api/v1/admin/agents", (201, AGENT))
    await call(
        service,
        "create_agent",
        {"name": "Boss", "prompt": "p", "model_id": 0, "tools": [], "rag_limit": 12, "comment": "first"},
    )
    assert service.body("POST", "/api/v1/admin/agents") == {
        "name": "Boss",
        "prompt": "p",
        "model_id": 0,
        "config": {"tools": [], "rag_limit": 12},
        "comment": "first",
    }

    service.on("PATCH /api/v1/admin/agents/5", AGENT)
    await call(
        service,
        "update_agent",
        {"memo_limit": 3, "reset_config": ["rag_limit"], "comment": "less memory", "expected_version": 4},
    )
    assert service.body("PATCH", "/api/v1/admin/agents/5") == {
        "config": {"memo_limit": 3, "rag_limit": None},
        "comment": "less memory",
        "expected_version": 4,
    }

    with pytest.raises(ToolError, match="Nothing to change"):
        await call(service, "update_agent", {"comment": "only a comment"})


@pytest.mark.asyncio
async def test_the_arguments_are_checked_against_the_schema_this_role_was_shown():
    service = Service()
    with pytest.raises(ToolError, match="'prompt' is a required property"):
        await call(service, "create_agent", {"name": "x", "model_id": 0})
    with pytest.raises(ToolError, match="Additional properties"):  # a user token was not offered agent_id
        await call(service, "get_agent", {"agent_id": 9}, role="user")
    with pytest.raises(ToolError, match="is not one of"):
        await call(service, "create_agent", {"name": "x", "prompt": "p", "model_id": 0, "tools": ["web"]})
    assert service.requests == []  # none of it reached the service


@pytest.mark.asyncio
async def test_send_message_is_always_from_the_mcp_user_never_to_itself_and_can_show_the_work():
    service = Service()
    service.on(
        "POST /api/v1/request",
        {
            "response": "Bonjour",
            "user": {"id": 1},
            "chat_id": 4,
            "trace": [
                {"step": 1, "kind": "model", "name": "m", "text": "x" * 500, "duration_ms": 12},
                {"step": 2, "kind": "tool", "name": "retrieve", "args": {"q": "hi"}, "result": "r" * 900},
            ],
        },
    )
    result = parsed(await call(service, "send_message", {"agent_id": 7, "text": "Hello", "trace": True}))
    sent = service.last("POST", "/api/v1/request")
    assert json.loads(sent.content) == {"request": "Hello", "user_id": "agentmcp_5", "trace": True}
    assert sent.headers["x-act-as-agent"] == "7" and sent.headers["authorization"] == "Bearer secret-token"
    assert result["answer"] == "Bonjour" and result["as_user"] == "agentmcp_5" and result["chat_id"] == 4
    assert len(result["trace"][0]["text"]) <= 300 and result["trace"][1]["name"] == "retrieve"

    with pytest.raises(ToolError, match="may not message itself"):
        await call(service, "send_message", {"agent_id": 5, "text": "me"})
    with pytest.raises(ToolError, match="Additional properties"):  # cannot write as somebody else
        await call(service, "send_message", {"agent_id": 7, "text": "hi", "user_id": "alice"})


@pytest.mark.asyncio
async def test_connections_are_named_by_the_agents_not_by_the_id_of_the_connection():
    service = Service()
    rows = [{"id": 11, "agent1_id": 1, "agent2_id": 2, "description": "old"}]
    service.on("GET /api/v1/admin/agent-connections", rows)
    service.on("GET /api/v1/admin/agents", [{"id": 1, "name": "Boss"}, {"id": 2, "name": "Prices"}])
    service.on(
        "POST /api/v1/admin/agent-connections",
        (201, {"id": 12, "agent1_id": 2, "agent2_id": 1, "description": "d"}),
    )
    service.on("PATCH /api/v1/admin/agent-connections/11", {"id": 11, "description": "new"})
    service.on("DELETE /api/v1/admin/agent-connections/11", rows[0])

    made = parsed(await call(service, "connect_agents", {"caller": 2, "called": 1, "description": "d"}))
    assert made["connected"] == "Prices (2) may now call Boss (1)"
    assert service.body("POST", "/api/v1/admin/agent-connections") == {
        "agent1_id": 2,
        "agent2_id": 1,
        "description": "d",
    }

    assert parsed(
        await call(service, "change_connection", {"caller": 1, "called": 2, "description": "new"})
    ) == {"description": "new"}
    assert service.body("PATCH", "/api/v1/admin/agent-connections/11") == {"description": "new"}
    await call(service, "disconnect_agents", {"caller": 1, "called": 2})
    assert "DELETE /api/v1/admin/agent-connections/11" in service.paths()

    with pytest.raises(ToolError, match="Agent 2 is not connected to agent 1"):
        await call(service, "change_connection", {"caller": 2, "called": 1, "description": "x"})
    listed = parsed(await call(service, "list_connections"))
    assert listed == [
        {"caller": {"id": 1, "name": "Boss"}, "called": {"id": 2, "name": "Prices"}, "description": "old"}
    ]


@pytest.mark.asyncio
async def test_an_mcp_server_is_added_to_the_own_agent_and_edited_without_losing_its_headers():
    service = Service()
    stored = {
        "id": 3,
        "name": "Maths",
        "config": {"url": "http://m/mcp", "headers": {"Authorization": "Bearer xyz"}, "timeout": 5},
    }
    service.on("POST /api/v1/admin/mcp-servers", (201, stored))
    added = parsed(
        await call(
            service,
            "add_mcp_server",
            {
                "name": "Maths",
                "url": "http://m/mcp",
                "headers": {"Authorization": "Bearer xyz"},
                "options": {"timeout": 5},
            },
            role="user",
        )
    )
    assert service.body("POST", "/api/v1/admin/mcp-servers") == {
        "name": "Maths",
        "config": {"timeout": 5, "url": "http://m/mcp", "headers": {"Authorization": "Bearer xyz"}},
        "agent_id": 5,
    }
    assert "xyz" not in json.dumps(added)

    service.on("GET /api/v1/admin/mcp-servers/3", stored)
    service.on(
        "PATCH /api/v1/admin/mcp-servers/3",
        {**stored, "config": {**stored["config"], "url": "http://m2/mcp"}},
    )
    await call(service, "edit_mcp_server", {"mcp_server_id": 3, "url": "http://m2/mcp"}, role="user")
    assert service.body("PATCH", "/api/v1/admin/mcp-servers/3") == {
        "config": {"url": "http://m2/mcp", "headers": {"Authorization": "Bearer xyz"}, "timeout": 5}
    }
    await call(service, "edit_mcp_server", {"mcp_server_id": 3, "name": "Calc"}, role="user")
    assert service.body("PATCH", "/api/v1/admin/mcp-servers/3") == {
        "name": "Calc"
    }  # the config is not sent when it did not change


@pytest.mark.asyncio
async def test_knowledge_goes_to_the_own_agent_or_the_one_an_admin_names_and_comes_back_without_vectors():
    service = Service()
    entry = {
        "id": 1,
        "agent_id": 5,
        "content": "open 8-22",
        "embedding": [0.1] * 1536,
        "metadata": {},
        "timestamp": "t",
    }
    service.on("POST /api/v1/admin/rag", (201, entry))
    added = await call(
        service, "add_knowledge", {"text": "open 8-22", "search_text": "when open?"}, role="user"
    )
    assert json.loads(added) == {"added": {"id": 1, "text": "open 8-22"}} and len(added) < 80
    sent = service.last("POST", "/api/v1/admin/rag")
    assert sent.url.params["agent_id"] == "5" and json.loads(sent.content) == {
        "content": "open 8-22",
        "embedding_content": "when open?",
    }

    service.on("GET /api/v1/admin/rag", [entry])
    await call(service, "search_knowledge", {"query": "hours", "agent_id": 9, "limit": 3})
    params = service.last("GET", "/api/v1/admin/rag").url.params
    assert (params["agent_id"], params["query"], params["limit"]) == ("9", "hours", "3")
    assert (
        "x-act-as-agent" not in service.last("GET", "/api/v1/admin/rag").headers
    )  # the admin API takes the agent as a parameter


@pytest.mark.asyncio
async def test_people_and_chats_of_another_agent_are_asked_with_act_as_and_ids_are_quoted():
    service = Service()
    service.on(
        "GET /api/v1/users/a/b c/history",
        [
            {"id": 1, "chat_id": 1, "timestamp": "t1", "content": {"type": "user", "content": "hi"}},
            {
                "id": 2,
                "chat_id": 1,
                "timestamp": "t2",
                "content": {"type": "assistant", "content": "hello", "interrupted": True},
            },
        ],
    )
    history = parsed(await call(service, "read_chat", {"user_id": "a/b c", "agent_id": 9}))
    assert history == [
        {"who": "user", "text": "hi", "at": "t1"},
        {"who": "assistant", "text": "hello", "at": "t2", "interrupted": True},
    ]
    sent = service.requests[-1]
    assert (
        sent.url.raw_path.decode() == "/api/v1/users/a%2Fb%20c/history"
        and sent.headers["x-act-as-agent"] == "9"
    )

    service.on("GET /api/v1/users/u/chats/4/history", [])
    await call(service, "read_chat", {"user_id": "u", "chat_id": 4})
    assert "x-act-as-agent" not in service.requests[-1].headers  # the own agent: no header


@pytest.mark.asyncio
async def test_an_admin_who_forgot_agent_id_is_told_where_it_looked():
    service = Service()
    service.on("GET /api/v1/users/agentmcp_1/history", (404, {"detail": "User not found"}))
    with pytest.raises(
        ToolError,
        match=r"User not found. Users, chats and messages belong to an agent: this looked in your own agent \(5\); give agent_id",
    ):
        await call(service, "read_chat", {"user_id": "agentmcp_1"})
    with pytest.raises(ToolError) as error:
        await call(service, "read_chat", {"user_id": "agentmcp_1", "agent_id": 9})
    assert "give agent_id" not in str(error.value)  # it was given


@pytest.mark.asyncio
async def test_the_service_errors_are_said_plainly():
    service = Service()
    service.on(
        "PATCH /api/v1/admin/agents/5",
        (
            422,
            {
                "detail": [
                    {
                        "loc": ["body", "config", "rag_limit"],
                        "msg": "Input should be less than or equal to 100",
                    }
                ]
            },
        ),
    )
    with pytest.raises(
        ToolError, match=r"HTTP 422: config.rag_limit: Input should be less than or equal to 100"
    ):
        await call(service, "update_agent", {"rag_limit": 100})
    service.on("DELETE /api/v1/admin/agents/9", (409, {"detail": "Agent still has tokens"}))
    with pytest.raises(ToolError, match="HTTP 409: Agent still has tokens"):
        await call(service, "delete_agent", {"agent_id": 9})


@pytest.mark.asyncio
async def test_a_new_token_gives_its_secret_once_and_nowhere_else():
    service = Service()
    made = {
        "id": 8,
        "name": "bot",
        "role": "regular",
        "agent_id": 5,
        "timestamp": "t",
        "is_initial": False,
        "token": "abc_" + "x" * 60,
    }
    service.on("POST /api/v1/admin/tokens", (201, made))
    service.on("GET /api/v1/admin/tokens", [{k: v for k, v in made.items() if k != "token"}])
    result = parsed(await call(service, "create_token", {"name": "bot", "role": "regular"}, role="user"))
    assert result["secret"] == made["token"] and service.body("POST", "/api/v1/admin/tokens") == {
        "name": "bot",
        "role": "regular",
        "agent_id": 5,
    }
    assert "secret" not in (await call(service, "list_tokens", role="user"))


@pytest.mark.asyncio
async def test_usage_is_totalled_by_model_token_and_day():
    service = Service()
    row = lambda model, token, day, n, cost: {
        "model": model,
        "token_name": token,
        "day": day,
        "requests": n,
        "errors": 0,
        "input_tokens": 100 * n,
        "output_tokens": 10 * n,
        "cost": cost,
    }  # noqa: E731
    service.on(
        "GET /api/v1/admin/usage",
        [
            row("a/x", "bot", "2026-10-01", 2, 0.5),
            row("a/x", "bot", "2026-10-02", 1, 0.25),
            row("b/y", "boss", "2026-10-02", 4, 1.0),
        ],
    )
    result = parsed(await call(service, "usage_report", {"days": 7}))
    assert result["total"] == {
        "requests": 7,
        "errors": 0,
        "input_tokens": 700,
        "output_tokens": 70,
        "cost": 1.75,
    }
    assert [m["model"] for m in result["by_model"]] == ["b/y", "a/x"]  # the dearest first
    assert [d["day"] for d in result["by_day"]] == ["2026-10-01", "2026-10-02"]


@pytest.mark.asyncio
async def test_a_model_is_made_and_changed_in_the_services_shape():
    service = Service()
    stored = {
        "id": 2,
        "name": "flash",
        "request_json": {"model": "google/gemini-2.5-flash", "temperature": 0.2},
        "base_url": "https://openrouter.ai/api/v1",
        "use_proxy": True,
        "has_api_token": False,
    }
    service.on("POST /api/v1/admin/models", (201, stored))
    await call(
        service,
        "create_model",
        {"name": "flash", "model": "google/gemini-2.5-flash", "options": {"temperature": 0.2}},
    )
    assert service.body("POST", "/api/v1/admin/models") == {
        "name": "flash",
        "request_json": {"model": "google/gemini-2.5-flash", "temperature": 0.2},
    }
    service.on("GET /api/v1/admin/models/2", stored)
    service.on("PATCH /api/v1/admin/models/2", stored)
    await call(service, "edit_model", {"model_id": 2, "options": {"temperature": 0.9}})
    assert service.body("PATCH", "/api/v1/admin/models/2") == {
        "request_json": {"model": "google/gemini-2.5-flash", "temperature": 0.9}
    }


@pytest.mark.asyncio
async def test_the_role_comes_from_the_service_and_an_unknown_token_is_none():
    service = Service()
    service.answers["GET /api/v1/tokens/self"] = lambda r: (
        (403, {"detail": "wrong"})
        if r.headers["authorization"].endswith("bad")
        else (200, {"id": 1, "name": "boss", "role": r.headers["authorization"].split()[-1], "agent_id": 5})
    )
    backend = Backend(httpx.AsyncClient(transport=httpx.MockTransport(service), base_url="http://omnixon"))
    assert (await backend.identify("owner")).role == "owner"
    assert await backend.identify("bad") is None
    asked = len(service.requests)
    await backend.identify("owner")
    assert len(service.requests) == asked  # cached


def test_the_token_is_read_from_the_header_or_the_url():
    from starlette.requests import Request

    def request(headers=(), query=b""):
        return Request({"type": "http", "headers": list(headers), "query_string": query})

    assert token_of(request([(b"authorization", b"Bearer abc")])) == "abc"
    assert token_of(request(query=b"token=xyz")) == "xyz"
    assert token_of(request()) is None
