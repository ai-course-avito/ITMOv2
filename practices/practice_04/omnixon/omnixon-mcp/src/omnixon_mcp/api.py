"""The call of the service for one tool call: the token's identity, the agent it works on, and errors a model can act on."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx

from .access import Identity

REQUEST_TIMEOUT = (
    600.0  # an answer of an agent waits for the model (and its tools); the service's own limit is the same
)
TIMEOUT = 30.0
ACT_AS_HEADER = "X-Act-As-Agent"


class ToolError(Exception):
    """A call that is refused before it reaches the service, or that the service refused."""


def detail(answer: Any) -> str:
    """FastAPI's 422 detail is a list of {loc, msg}: say it as `config.tools: <msg>`."""
    if isinstance(answer, list) and all(isinstance(e, dict) and "msg" in e for e in answer):
        lines = []
        for e in answer:
            where = ".".join(str(p) for p in e.get("loc", []) if p not in ("body", "query", "path"))
            lines.append(f"{where}: {e['msg']}" if where else e["msg"])
        return "; ".join(lines)
    return answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)


def without_embeddings(value: Any) -> Any:
    """The service returns a knowledge entry's vector on create/update: 1536 numbers no model needs."""
    if isinstance(value, dict):
        return {k: without_embeddings(v) for k, v in value.items() if k != "embedding"}
    if isinstance(value, list):
        return [without_embeddings(v) for v in value]
    return value


def q(value: Any) -> str:
    """A value in a path (a user id may hold / ? #)."""
    return quote(str(value), safe="")


class Ctx:
    """What a tool handler works with: `get/post/patch/delete` go to the service as the token, on the agent `agent` (the token's own unless an
    admin asked for another one: then main-API calls carry X-Act-As-Agent)."""

    def __init__(self, http: httpx.AsyncClient, token: str, who: Identity, agent: int | None = None):
        self.http = http
        self.token = token
        self.who = who
        self.agent = agent if agent is not None else who.agent_id

    @property
    def other_agent(self) -> bool:
        return self.agent != self.who.agent_id

    async def call(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: Any = None,
        acting: bool = False,
        timeout: float = TIMEOUT,
        name: str = "the service",
    ) -> Any:
        """`acting`: a main-API route (users, chats, messages): it is about the agent in X-Act-As-Agent."""
        headers = {"Authorization": f"Bearer {self.token}"}
        if acting and self.other_agent:
            headers[ACT_AS_HEADER] = str(self.agent)
        params = {k: v for k, v in (params or {}).items() if v is not None}
        try:
            res = await self.http.request(
                method, path, params=params or None, json=json_body, headers=headers, timeout=timeout
            )
        except httpx.TimeoutException:
            raise ToolError(f"{name} did not answer in time") from None
        except httpx.HTTPError as exc:
            raise ToolError(f"{name} cannot be reached ({type(exc).__name__})") from None
        if res.status_code >= 400:
            raise ToolError(self._refusal(res, acting))
        if res.status_code == 204 or not res.content:
            return None
        try:
            return without_embeddings(res.json())
        except ValueError:
            return res.text

    def _refusal(self, res: httpx.Response, acting: bool) -> str:
        try:
            answer = res.json()
            text = detail(answer.get("detail", answer) if isinstance(answer, dict) else answer)
        except ValueError:
            text = res.text
        message = f"The service refused: HTTP {res.status_code}: {text}"
        if res.status_code == 404 and acting and self.who.is_admin and not self.other_agent:
            message += (
                f". Users, chats and messages belong to an agent: this looked in your own agent ({self.who.agent_id}); "
                "give agent_id to look in another one."
            )
        return message

    async def get(self, path: str, **kw: Any) -> Any:
        return await self.call("GET", path, **kw)

    async def post(self, path: str, **kw: Any) -> Any:
        return await self.call("POST", path, **kw)

    async def patch(self, path: str, **kw: Any) -> Any:
        return await self.call("PATCH", path, **kw)

    async def delete(self, path: str, **kw: Any) -> Any:
        return await self.call("DELETE", path, **kw)
