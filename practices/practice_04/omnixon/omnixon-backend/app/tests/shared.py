"""Helpers, constants and fake objects the test files have in common (the fixtures are in conftest.py)."""

import os
import base64
import json
import time
import pytest
import httpx
import asyncio
import contextlib
from types import SimpleNamespace
from typing import Optional
from database import Agent
from pydantic_ai.models.openrouter import OpenRouterModel, OpenRouterProvider
import math
import uuid
from datetime import datetime
import asyncpg
from core import DATABASE_CONFIG
from database import Memory


API_URL = os.getenv("API_URL", "http://api:80/")
# a second replica of the api on the same database and Redis (the test stack has one; empty elsewhere)
API_URL_2 = os.getenv("API_URL_2", "")


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")


INITIAL_API_KEY = os.getenv("INITIAL_API_KEY", "")


MCP_CALCULATOR_URL = os.getenv("MCP_CALCULATOR_URL", "http://mcp-calculator:9100/mcp")


FAKE_LLM_URL = os.getenv(
    "FAKE_LLM_URL", "http://fake-llm:8000/v1"
)  # docker/fake-llm: an OpenAI-compatible server without a provider


headers = {"Authorization": f"Bearer {INITIAL_API_KEY}"}


def generate_model(model_name: str, http_client: httpx.AsyncClient):
    return OpenRouterModel(
        model_name,
        provider=OpenRouterProvider(
            api_key=OPENROUTER_API_KEY, http_client=http_client
        ),
    )


async def collect_sse(client, user_id: str, text: str, **flags) -> dict:
    """POST to /request-stream and parse the SSE stream into its events."""
    chunks, done, error, user, trace = [], None, None, None, []
    async with client.stream(
        "POST",
        "/api/v1/request-stream",
        json={"user_id": user_id, "request": text, **flags},
    ) as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")

        event = "message"
        async for line in res.aiter_lines():
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                payload = json.loads(line[len("data:") :].strip())
                if event == "done":
                    done = payload
                elif event == "error":
                    error = payload
                elif event == "user":
                    user = payload
                elif event == "trace":
                    trace.append(payload)
                else:
                    chunks.append(payload)
            elif line == "":
                event = "message"

    return {
        "chunks": chunks,
        "done": done,
        "error": error,
        "user": user,
        "trace": trace,
    }


async def make_agent(client, **extra) -> dict:
    """An agent of its own (empty prompt, the default model); tokens made for it work as that agent."""
    res = await client.post(
        "/api/v1/admin/agents",
        json={"name": "test agent", "prompt": "", "model_id": 0, **extra},
    )
    assert res.status_code == 201, res.text
    return res.json()


async def make_token(
    client, agent_id: int, role: str, name: str = "test token"
) -> dict:
    """A token of `role` for the agent. The answer has the secret in `token`."""
    res = await client.post(
        "/api/v1/admin/tokens", json={"name": name, "role": role, "agent_id": agent_id}
    )
    assert res.status_code == 201, res.text
    return res.json()


def as_token(
    secret: str, act_as: Optional[int] = None, timeout: float = 120.0
) -> httpx.AsyncClient:
    """A client that signs in with `secret` (and acts as another agent when `act_as` is given). Use `async with`."""
    extra = {"X-Act-As-Agent": str(act_as)} if act_as is not None else {}
    return httpx.AsyncClient(
        base_url=API_URL,
        headers={"Authorization": f"Bearer {secret}", **extra},
        timeout=timeout,
    )


async def drop_agent(client, agent: dict) -> None:
    """Delete an agent (its tokens must be gone first)."""
    await client.delete(f"/api/v1/admin/agents/{agent['id']}")


CALC_QUESTION = (
    "Use the calculate tool to compute 123456 * 654321. "
    "Reply with only the resulting number."
)


CALC_ANSWER = str(123456 * 654321)


def digits_only(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


async def history_of(client, user_id: str) -> list:
    res = await client.get(f"/api/v1/users/{user_id}/history")
    assert res.status_code == 200
    return res.json()


async def make_user(client, external_id: str) -> dict:
    res = await client.post("/api/v1/users", json={"external_id": external_id})
    assert res.status_code == 201
    return res.json()


async def versions_of(client, agent_id: int) -> list:
    res = await client.get(f"/api/v1/admin/agents/{agent_id}/versions")
    assert res.status_code == 200
    return res.json()  # newest first


VISION_MODEL = "google/gemini-2.5-flash-lite"


ROLES = ("regular", "user", "admin", "owner")


RANK = {role: i + 1 for i, role in enumerate(ROLES)}


@contextlib.asynccontextmanager
async def role_clients(client):
    """Two agents, A and B, and a token of every role on A: `ctx.clients[role]` signs in with it."""
    a = await make_agent(client, name="agent A")
    b = await make_agent(client, name="agent B")
    tokens = {
        role: await make_token(client, a["id"], role, name=f"{role} token")
        for role in ROLES
    }
    async with contextlib.AsyncExitStack() as stack:
        clients = {
            role: await stack.enter_async_context(as_token(t["token"]))
            for role, t in tokens.items()
        }
        try:
            yield SimpleNamespace(a=a, b=b, tokens=tokens, clients=clients)
        finally:
            for t in tokens.values():
                await client.delete(f"/api/v1/admin/tokens/{t['id']}")
            for agent in (a, b):
                for t in (
                    await client.get(
                        "/api/v1/admin/tokens", params={"agent_id": agent["id"]}
                    )
                ).json():
                    await client.delete(f"/api/v1/admin/tokens/{t['id']}")
                await drop_agent(client, agent)


def spent(rows, token_id):
    mine = [r for r in rows if r["token_id"] == token_id]
    return SimpleNamespace(
        requests=sum(r["requests"] for r in mine),
        errors=sum(r["errors"] for r in mine),
        input=sum(r["input_tokens"] for r in mine),
        output=sum(r["output_tokens"] for r in mine),
        cost=sum(r["cost"] for r in mine),
    )


def fake_log(model: str) -> list:
    """What the fake LLM server got for this model (the names are unique per test)."""
    res = httpx.get(
        FAKE_LLM_URL.rsplit("/v1", 1)[0] + "/log", params={"model": model}, timeout=10
    )
    return res.json()


async def fake_model(client, name: str, **connection) -> dict:
    res = await client.post(
        "/api/v1/admin/models",
        json={
            "name": name,
            "request_json": {"model": name},
            "base_url": FAKE_LLM_URL,
            **connection,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


@contextlib.asynccontextmanager
async def agent_on(client, model: dict, **config):
    """An agent that uses `model` with a regular token; yields (agent, a client signed in with that token)."""
    agent = await make_agent(
        client,
        model_id=model["id"],
        config={"tools": [], "auto_memory": False, **config},
    )
    token = await make_token(client, agent["id"], "regular")
    try:
        async with as_token(token["token"]) as c:
            yield agent, c
    finally:
        await client.delete(f"/api/v1/admin/tokens/{token['id']}")
        await drop_agent(client, agent)
        await client.delete(f"/api/v1/admin/models/{model['id']}")


async def slow_stream(c, user_id: str, text: str = "Count slowly.") -> dict:
    """Runs /request-stream to its end in the background; the result has the events, filled as they come."""
    seen = {"chunks": [], "events": [], "status": None}

    async def run():
        async with c.stream(
            "POST", "/api/v1/request-stream", json={"request": text, "user_id": user_id}
        ) as res:
            seen["status"] = res.status_code
            event = "message"
            async for line in res.aiter_lines():
                if line.startswith("event:"):
                    event = line[6:].strip()
                    seen["events"].append(event)
                elif line.startswith("data:") and event == "message":
                    seen["chunks"].append(json.loads(line[5:].strip()))
                elif line == "":
                    event = "message"

    seen["task"] = asyncio.create_task(run())
    return seen


async def until(predicate, seconds: float = 20.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if predicate():
            return
        await asyncio.sleep(0.05)
    pytest.fail("the condition did not come true in time")


NOW = datetime(2026, 1, 1)


def agent_row(config):
    return Agent(id=1, prompt="p", model_id=0, config=config, timestamp=NOW)


class FakeDB:
    """Just enough of PostgresDB for the prompt and memory tools."""

    def __init__(
        self,
        memories=(),
        total=None,
        user=True,
        agent=True,
        messages=(),
        memo_limit=5,
        rag_limit=8,
        vectors=None,
        auto_memory=False,
        parallel_tool_calls=True,
        tools=("rag", "memory"),
    ):
        self.context = SimpleNamespace(
            user=SimpleNamespace(id=7) if user else None,
            agent=(
                SimpleNamespace(
                    id=3,
                    prompt="Be helpful.",
                    message_limit=10,
                    memo_limit=memo_limit,
                    rag_limit=rag_limit,
                    auto_memory=auto_memory,
                    parallel_tool_calls=parallel_tool_calls,
                    tools=list(tools),
                    model_id=0,
                )
                if agent
                else None
            ),
        )
        self.memories = list(memories)
        self.vectors = dict(vectors or {})  # memory id -> embedding
        self.total = len(self.memories) if total is None else total
        self.messages = list(messages)
        self.calls = []
        self.next_id = 99

    async def get_agent_connections(self, agent_id=None):
        return []  # no agents to call: no list_agents / ask_agent

    async def get_similar_rag(self, embedding, limit=10):
        self.calls.append(("get_similar_rag", limit))
        return []

    async def get_memories(self, user_id, agent_id, limit=None, query=None):
        self.calls.append(("get_memories", user_id, agent_id, limit, query))
        found = [
            m for m in self.memories if not query or query.lower() in m.content.lower()
        ]
        return found[:limit]

    async def search_memories(
        self, user_id, agent_id, embedding, limit, max_distance=None
    ):
        self.calls.append(("search_memories", limit, max_distance))
        found = []
        for m in self.memories:
            vector = self.vectors.get(m.id)
            if vector is None:
                continue
            dot = sum(x * y for x, y in zip(vector, embedding))
            norm = math.sqrt(sum(x * x for x in vector)) * math.sqrt(
                sum(y * y for y in embedding)
            )
            distance = 1 - dot / norm
            if max_distance is None or distance <= max_distance:
                found.append((m, distance))
        return sorted(found, key=lambda pair: pair[1])[:limit]

    async def count_memories(self, user_id, agent_id):
        return self.total

    async def create_memory(self, user_id, agent_id, content, embedding=None):
        self.calls.append(("create_memory", user_id, agent_id, content))
        created = Memory(
            id=self.next_id,
            user_id=user_id,
            agent_id=agent_id,
            content=content,
            timestamp=NOW,
        )
        self.next_id += 1
        self.memories.insert(0, created)  # newest first
        if embedding is not None:
            self.vectors[created.id] = embedding
        return created

    async def delete_memory(self, memory_id, user_id=None, agent_id=None):
        self.calls.append(("delete_memory", memory_id, user_id, agent_id))
        return self.memories[0] if self.memories else None

    async def get_all_messages(self):
        self.calls.append(("get_all_messages",))
        return self.messages

    async def get_model(self, model_id):
        return SimpleNamespace(request_json={"model": "a/b"}, connection={})

    async def get_agent_mcp_servers(self, agent_id):
        return []

    async def create_message(self, content):
        self.stored = getattr(self, "stored", []) + [content]

    async def create_messages(self, contents):
        for content in contents:
            await self.create_message(content)

    @contextlib.asynccontextmanager
    async def transaction(self):
        yield

    async def lock(self, key):
        self.calls.append(("lock", key))


def memory(id: int, content: str) -> Memory:
    return Memory(id=id, user_id=7, agent_id=3, content=content, timestamp=NOW)


async def scratch_pool(name):
    admin = await asyncpg.connect(**DATABASE_CONFIG)
    await admin.execute(f'CREATE DATABASE "{name}"')
    scratch = await asyncpg.connect(**{**DATABASE_CONFIG, "database": name})
    await scratch.execute("CREATE EXTENSION IF NOT EXISTS vector")
    await scratch.close()
    return admin


async def stored(db):
    rows = await db.fetch_all("SELECT content FROM messages ORDER BY id") or []
    return [json.loads(r["content"])["content"] for r in rows]


PNG_B64 = base64.b64encode(b"\x89PNG\r\n\x1a\nnot really a picture").decode()


@contextlib.asynccontextmanager
async def scratch_database(prefix="tx_test"):
    """(pool, db): a database object with a token, an agent, a user and its default chat, on a scratch database."""
    from core import INITIAL_API_KEY
    from database import Context, PostgresDB, PostgresPool

    name = f"{prefix}_{uuid.uuid4().hex[:8]}"
    admin = await scratch_pool(name)
    try:
        async with PostgresPool({**DATABASE_CONFIG, "database": name}) as pool:
            db = PostgresDB(pool, Context(agent=None, token=None, user=None))
            db.context.token = await db.ensure_initial_token(INITIAL_API_KEY)
            db.context.agent = await db.create_agent("first", 0, name="a")
            db.context.user = await db.create_user("tx_user")
            db.context.chat = await db.ensure_default_chat()
            yield pool, db
    finally:
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()
