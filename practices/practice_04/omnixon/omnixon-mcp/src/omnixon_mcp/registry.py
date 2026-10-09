"""The tools: each is written by hand (name, description, arguments, what it calls), and declares the routes of the service it uses.

A tool says the lowest role that sees it; `scoped` tools work on one agent (the token's own, or for admin and owner the one in `agent_id`).
Tests check the declarations against the service's OpenAPI: a route no tool uses (and no reason for leaving it out) fails them, so this
server cannot silently fall behind the API.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
import jsonschema
from mcp import types

from .access import RANK, Identity, Route
from .api import Ctx, ToolError

AGENT_ID = "agent_id"

CONNECT_TOOL = "omnixon_connect"
CONNECT_TEXT = (
    "This MCP server needs an Omnixon API token and got {problem}. Ask the user to add the token to "
    "the connection of this MCP server, either as the header `Authorization: Bearer <token>` or in "
    "the URL as `?token=<token>`. Tokens are made on the Tokens page of the Omnixon panel. Do not "
    "ask the user to paste the token into the chat: it belongs to the connection, not to the conversation."
)

GROUPS = (
    "self",
    "agents",
    "messages",
    "users",
    "knowledge",
    "memories",
    "models",
    "mcp",
    "tokens",
    "usage",
)


# The pieces of an input schema
def i(description: str, **extra: Any) -> dict:
    return {"type": "integer", "description": description, **extra}


def s(description: str, **extra: Any) -> dict:
    return {"type": "string", "description": description, **extra}


def b(description: str) -> dict:
    return {"type": "boolean", "description": description}


def o(description: str, **extra: Any) -> dict:
    return {"type": "object", "description": description, **extra}


def a(description: str, items: dict, **extra: Any) -> dict:
    return {"type": "array", "description": description, "items": items, **extra}


Handler = Callable[..., Awaitable[Any]]


@dataclass
class Tool:
    name: str
    group: str
    role: str  # the lowest role that is offered it
    description: str
    handler: Handler
    props: dict = field(default_factory=dict)
    required: tuple[str, ...] = ()
    routes: tuple[Route, ...] = ()  # the routes of the service it calls
    admin_routes: tuple[Route, ...] = ()  # more routes it calls only when the token is an admin's
    scoped: bool = False  # works on one agent: the token's own, or `agent_id` for admin and owner
    note: Callable[[Identity], str] | None = None  # what this role should know about it
    timeout: float = 30.0

    def offered_to(self, who: Identity) -> bool:
        return who.rank >= RANK[self.role]

    def schema(self, who: Identity) -> dict:
        props = dict(self.props)
        if self.scoped and who.is_admin:
            props[AGENT_ID] = i(
                f"The agent to work on (a number from find_agents). Omitted: your own agent ({who.agent_id}).",
                minimum=1,
            )
        schema: dict[str, Any] = {"type": "object", "properties": props, "additionalProperties": False}
        if self.required:
            schema["required"] = list(self.required)
        return schema

    def describe(self, who: Identity) -> str:
        parts = [self.description.strip()]
        if self.scoped and not who.is_admin:
            parts.append(f"Works on your own agent (id {who.agent_id}).")
        if self.note:
            parts.append(self.note(who))
        return "\n\n".join(p for p in parts if p)


REGISTRY: dict[str, Tool] = {}


def tool(
    name: str,
    *,
    group: str,
    role: str,
    description: str,
    props: dict | None = None,
    required: tuple[str, ...] = (),
    routes: tuple[Route, ...] = (),
    admin_routes: tuple[Route, ...] = (),
    scoped: bool = False,
    note: Callable[[Identity], str] | None = None,
    timeout: float = 30.0,
):
    assert group in GROUPS, group
    assert name not in REGISTRY, f"two tools called {name}"

    def register(handler: Handler) -> Handler:
        REGISTRY[name] = Tool(
            name,
            group,
            role,
            description,
            handler,
            props or {},
            required,
            routes,
            admin_routes,
            scoped,
            note,
            timeout,
        )
        return handler

    return register


def tools_for(who: Identity, groups: set[str] | None = None) -> list[Tool]:
    """The tools a token sees, in the order they were written; `groups`: only these groups (and `self`, which says who the token is)."""
    return [
        t
        for t in REGISTRY.values()
        if t.offered_to(who) and (groups is None or t.group in groups or t.group == "self")
    ]


def mcp_tools(who: Identity, groups: set[str] | None = None) -> list[types.Tool]:
    return [
        types.Tool(name=t.name, description=t.describe(who), inputSchema=t.schema(who))
        for t in tools_for(who, groups)
    ]


def connect_tool(problem: str) -> types.Tool:
    return types.Tool(
        name=CONNECT_TOOL,
        description=CONNECT_TEXT.format(problem=problem) + " Call this tool to see what to tell the user.",
        inputSchema={"type": "object", "properties": {}},
    )


async def run(t: Tool, http: httpx.AsyncClient, token: str, who: Identity, args: dict) -> str:
    """Check the arguments against the schema this role was shown, run the handler, say the result as compact JSON."""
    try:
        jsonschema.validate(args, t.schema(who))
    except jsonschema.ValidationError as exc:
        where = "/".join(str(p) for p in exc.absolute_path)
        raise ToolError(
            f"Invalid arguments for {t.name}{f' ({where})' if where else ''}: {exc.message}"
        ) from None
    args = dict(args)
    agent = args.pop(AGENT_ID, None) if t.scoped else None
    ctx = Ctx(http, token, who, agent)
    result = await t.handler(ctx, **args)
    if result is None:
        return "Done."
    if isinstance(result, str):
        return result
    # compact: a model reads it as well, and every character is a token it pays for
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))
