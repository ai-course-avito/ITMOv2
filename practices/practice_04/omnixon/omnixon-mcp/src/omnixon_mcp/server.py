"""The MCP server: streamable HTTP at /mcp, every request answered for the token it came with.

The token is the `Authorization: Bearer` header or `?token=` in the URL, set once in the client's
connection, so a model never sees or repeats it. Its role (asked from the service) decides which
tools are listed and what their descriptions say. Stateless: each HTTP request stands alone, so a
token whose role changed gets the new set of tools at the next listing.
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import time
from typing import Any

import httpx
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.shared.exceptions import McpError
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.types import Receive, Scope, Send

from . import tools as _tools  # noqa: F401  (importing it registers the tools)
from .access import Identity
from .api import ToolError
from .registry import CONNECT_TEXT, CONNECT_TOOL, GROUPS, REGISTRY, connect_tool, mcp_tools, run

log = logging.getLogger("omnixon_mcp")

OMNIXON_URL = os.environ.get("OMNIXON_URL", "http://localhost:8083").rstrip("/")
IDENTITY_SECONDS = float(
    os.environ.get("OMNIXON_MCP_IDENTITY_SECONDS", "30")
)  # how long a token's role is trusted

INSTRUCTIONS = (
    "Omnixon runs LLM agents (a prompt, a model, settings, a knowledge base, memory, MCP servers) for bots and sites. These tools "
    "manage them: agents and their versions, connections between agents, models, MCP servers, knowledge, memories, people and chats, "
    "tokens and usage, and send a message to an agent to try it. What you get depends on the role of the token this server was "
    "connected with. If you do not know the service, call about_omnixon first; whoami says who you are."
)


class Backend:
    """The service: who a token is (from /tokens/self)."""

    def __init__(self, http: httpx.AsyncClient):
        self.http = http
        self._identities: dict[str, tuple[float, Identity | None]] = {}

    async def identify(self, token: str) -> Identity | None:
        """None: the service does not know the token. Raises httpx.HTTPError when it cannot be asked."""
        key = hashlib.sha256(token.encode()).hexdigest()  # never keep the secret itself
        cached = self._identities.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        res = await self.http.get(
            "/api/v1/tokens/self", headers={"Authorization": f"Bearer {token}"}, timeout=10
        )
        if res.status_code in (401, 403):
            who = None
        else:
            res.raise_for_status()
            data = res.json()
            who = Identity(
                token_id=data["id"], name=data["name"], role=data["role"], agent_id=data["agent_id"]
            )
        self._identities[key] = (time.monotonic() + IDENTITY_SECONDS, who)
        return who


def token_of(request: Request | None) -> str | None:
    if request is None:
        return None
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer ") and header[7:].strip():
        return header[7:].strip()
    return request.query_params.get("token") or None


KNOWN_GROUPS = sorted(GROUPS)


def groups_of(request: Request | None) -> set[str] | None:
    """`?groups=agents,messages` keeps only those tools (fewer tools = fewer tokens on every model call)."""
    raw = request.query_params.get("groups") if request is not None else None
    if not raw:
        return None
    groups = {g.strip() for g in raw.split(",") if g.strip()}
    unknown = groups - set(KNOWN_GROUPS)
    if unknown:
        raise McpError(
            types.ErrorData(
                code=types.INVALID_PARAMS,
                message=f"Unknown tool groups in ?groups=: {', '.join(sorted(unknown))}. Known: {', '.join(KNOWN_GROUPS)}",
            )
        )
    return groups


def make_server(backend: Backend) -> Server:
    server: Server = Server("omnixon", instructions=INSTRUCTIONS)

    async def caller() -> tuple[str | None, Identity | None, str]:
        """(token, identity, what is wrong when there is no identity)"""
        token = token_of(server.request_context.request)
        if not token:
            return None, None, "no token"
        try:
            who = await backend.identify(token)
        except httpx.HTTPError as exc:
            log.warning("cannot ask the service who a token is: %s", type(exc).__name__)
            return token, None, "no answer from the Omnixon service, so the token could not be checked"
        return token, who, "" if who else "a token the service does not accept"

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        _, who, problem = await caller()
        if who is None:
            return [connect_tool(problem)]
        return mcp_tools(who, groups_of(server.request_context.request))

    @server.call_tool(validate_input=False)  # validated per role in tools.build_request
    async def call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        token, who, problem = await caller()
        if who is None or token is None:
            return _result(CONNECT_TEXT.format(problem=problem), error=name != CONNECT_TOOL)
        groups = groups_of(server.request_context.request)
        tool = REGISTRY.get(name)
        if (
            tool is None
            or not tool.offered_to(who)
            or (groups is not None and tool.group not in groups | {"self"})
        ):
            return _result(f"Unknown tool {name!r} for a token of role {who.role}.", error=True)
        try:
            return _result(await run(tool, backend.http, token, who, arguments or {}))
        except ToolError as exc:
            return _result(str(exc), error=True)

    return server


def _result(text: str, error: bool = False) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)], isError=error)


class App:
    """ASGI: /mcp is the MCP endpoint, /healthz says the process is up; nothing else."""

    def __init__(self) -> None:
        self.http = httpx.AsyncClient(base_url=OMNIXON_URL)
        self.backend = Backend(self.http)
        self.sessions = StreamableHTTPSessionManager(app=make_server(self.backend), stateless=True)

    @contextlib.asynccontextmanager
    async def lifespan(self):
        async with self.sessions.run():
            yield
        await self.http.aclose()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._lifespan(receive, send)
            return
        path = scope.get("path", "")
        if path in ("/mcp", "/mcp/"):
            await self.sessions.handle_request(scope, receive, send)
        elif path == "/healthz":
            await JSONResponse({"status": "ok"})(scope, receive, send)
        else:
            await PlainTextResponse("Not found: the MCP endpoint is /mcp", status_code=404)(
                scope, receive, send
            )

    async def _lifespan(self, receive: Receive, send: Send) -> None:
        message = await receive()
        assert message["type"] == "lifespan.startup"
        async with self.lifespan():
            await send({"type": "lifespan.startup.complete"})
            message = await receive()
            assert message["type"] == "lifespan.shutdown"
        await send({"type": "lifespan.shutdown.complete"})
