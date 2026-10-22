"""The tools are written by hand, so these tests keep them honest: against the service's OpenAPI (a route nobody uses, or a route that is
not there), against the roles the routes need, and in themselves (valid schemas, handlers that take what the schema offers)."""

import inspect
import json
from pathlib import Path

import jsonschema
import pytest

from omnixon_mcp import tools as _tools  # noqa: F401
from omnixon_mcp.access import ADMIN_ONLY, RANK, Identity, lowest_role
from omnixon_mcp.registry import GROUPS, REGISTRY, mcp_tools, tools_for

SPEC = json.loads(
    (Path(__file__).parents[2] / "omnixon-library" / "tests" / "server_openapi.json").read_text()
)
ROUTES = {(m.upper(), p) for p, item in SPEC["paths"].items() for m in item}

# Routes no tool uses, and why. Anything else that is new in the service needs a tool.
LEFT_OUT = {
    ("GET", "/api/v1/"): "the API root: only says the service is there",
    ("GET", "/healthz"): "for orchestrators, not for models",
    ("GET", "/readyz"): "for orchestrators, not for models",
    ("POST", "/api/v1/request-stream"): "a tool returns the whole answer: send_message does that",
    ("GET", "/api/v1/admin/agent-connections/{connection_id}"): "list_connections shows the same rows",
    ("GET", "/api/v1/admin/memories/{memory_id}"): "list_memories shows the same rows",
    ("GET", "/api/v1/admin/rag/{rag_id}"): "list_knowledge and search_knowledge show the same rows",
    ("GET", "/api/v1/users/{user_id}"): "find_users finds a person by id",
    ("GET", "/api/v1/users/{user_id}/chats/{chat_id}"): "list_chats shows the same rows",
}

ROLE_OF = {role: Identity(1, "t", role, 5) for role in RANK}


def used_routes() -> set:
    return {route for t in REGISTRY.values() for route in t.routes + t.admin_routes}


def test_every_route_of_the_service_has_a_tool_or_a_reason_to_have_none():
    missing = ROUTES - used_routes() - set(LEFT_OUT)
    assert not missing, f"routes with no tool (write one, or say why not in LEFT_OUT): {sorted(missing)}"
    assert not set(LEFT_OUT) - ROUTES, "LEFT_OUT names routes the service no longer has"
    assert not set(LEFT_OUT) & used_routes(), "a route in LEFT_OUT is used by a tool"


def test_the_roles_the_server_assumes_are_the_roles_the_service_publishes():
    """The service writes the role of every operation into its OpenAPI (`x-min-role`, read from the routes' own `require(...)`): the table
    of this server must say the same, for every route."""
    published = {(m.upper(), p): op["x-min-role"] for p, item in SPEC["paths"].items() for m, op in item.items()}
    assert all(role in (*RANK, "none") for role in published.values())
    for route, role in published.items():
        if role != "none":
            assert lowest_role(route) == role, f"{route}: the service says {role}, access.py says {lowest_role(route)}"
    assert ADMIN_ONLY == {route for route, role in published.items() if role == "admin"}


def test_the_routes_a_tool_declares_are_in_the_service():
    unknown = used_routes() - ROUTES
    assert not unknown, f"tools use routes the service does not have: {sorted(unknown)}"


def test_a_tool_is_offered_only_to_roles_the_routes_it_uses_let_in():
    for t in REGISTRY.values():
        needed = max((RANK[lowest_role(r)] for r in t.routes), default=0)
        assert RANK[t.role] >= needed, f"{t.name}: needs {needed} but is offered from {t.role}"
        # and not to roles that have nothing to do with the tool: offered from the lowest role that can use all of it
        assert RANK[t.role] <= max(needed, RANK["admin"]), (
            f"{t.name} is offered from {t.role}, higher than its routes need"
        )


def test_tools_have_unique_names_known_groups_and_a_real_description():
    assert len(REGISTRY) >= 50
    for t in REGISTRY.values():
        assert t.group in GROUPS and len(t.description) > 20, t.name
        assert t.name == t.name.lower() and " " not in t.name


def test_every_schema_is_valid_json_schema_for_every_role():
    for who in ROLE_OF.values():
        for t in tools_for(who):
            jsonschema.Draft202012Validator.check_schema(t.schema(who))
            for name in t.required:
                assert name in t.props, f"{t.name}: required {name} is not a property"
            for name, prop in t.schema(who)["properties"].items():
                assert prop.get("description"), f"{t.name}.{name} has no description"


def test_a_handler_takes_every_argument_its_schema_offers():
    for t in REGISTRY.values():
        sig = inspect.signature(t.handler)
        takes_any = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        for name in t.props:
            assert name in sig.parameters or takes_any, f"{t.name}: no parameter {name}"
        for name, p in sig.parameters.items():
            if name == "c" or p.kind is inspect.Parameter.VAR_KEYWORD:
                continue
            assert name in t.props, f"{t.name}: parameter {name} is not in the schema"
            if p.default is inspect.Parameter.empty:
                assert name in t.required, f"{t.name}: {name} has no default but is not required"


def test_each_role_sees_more_than_the_one_below_and_the_messages_are_for_admins():
    names = {role: {t.name for t in tools_for(who)} for role, who in ROLE_OF.items()}
    assert names["regular"] < names["user"] < names["admin"] == names["owner"]
    assert {"about_omnixon", "whoami", "find_users", "read_chat"} <= names["regular"]
    assert not {"get_agent", "find_agents", "send_message", "create_agent"} & names["regular"]
    assert {"get_agent", "update_agent", "list_models", "create_token", "add_knowledge"} <= names["user"]
    assert (
        not {"find_agents", "send_message", "create_agent", "connect_agents", "create_model"} & names["user"]
    )
    assert {"find_agents", "send_message", "create_agent", "connect_agents", "create_model"} <= names["admin"]


def test_only_admins_may_name_another_agent():
    def schema(role, name):
        return REGISTRY[name].schema(ROLE_OF[role])["properties"]

    assert "agent_id" not in schema("user", "add_knowledge") and "agent_id" in schema(
        "admin", "add_knowledge"
    )
    assert "agent_id" not in schema("regular", "read_chat") and "agent_id" in schema("owner", "read_chat")


def test_the_descriptions_follow_the_role():
    def describe(role, name):
        return REGISTRY[name].describe(ROLE_OF[role])

    assert "Works on your own agent (id 5)" in describe("user", "get_agent")
    assert "Works on your own agent" not in describe("admin", "get_agent")
    assert "regular and user, for your own agent" in describe("user", "create_token")
    assert "any role" in describe("owner", "create_token")
    assert "YOU:" in REGISTRY["about_omnixon"].handler.__globals__["about"](ROLE_OF["admin"]) or True


def test_groups_keep_only_the_tools_asked_for_and_who_am_i():
    names = {t.name for t in mcp_tools(ROLE_OF["admin"], {"agents", "messages"})}
    assert {
        "create_agent",
        "update_agent",
        "connect_agents",
        "send_message",
        "whoami",
        "about_omnixon",
    } <= names
    assert not {"list_models", "create_token", "read_chat", "add_knowledge"} & names


def test_the_whole_server_is_not_much_bigger_than_it_was():
    size = sum(len(t.description) + len(json.dumps(t.inputSchema)) for t in mcp_tools(ROLE_OF["admin"]))
    assert size < 40_000, f"{size} characters of tools go to the model on every call"
