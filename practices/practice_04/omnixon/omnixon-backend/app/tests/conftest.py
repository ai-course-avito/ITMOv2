"""Fixtures shared by the test files."""

import os
import pytest
import pytest_asyncio
import httpx
import asyncio
from pydantic_ai import Agent
import uuid
import asyncpg
from config import Settings

DATABASE_CONFIG = Settings.from_env().database

from shared import (
    API_URL,
    VISION_MODEL,
    generate_model,
    headers,
)


# the application is not started here, so logfire stays unconfigured; that is fine
os.environ.setdefault("LOGFIRE_IGNORE_NO_CONFIG", "1")


@pytest_asyncio.fixture(loop_scope="function")
async def evaluator_agent():
    async with httpx.AsyncClient(timeout=120.0) as http_client:
        system_prompt = (
            "You are an objective, strict evaluation system. "
            "You must analyze the provided text against the specified criteria. "
            "If ALL criteria are fully met, output exactly 'PASS'. "
            "If ANY criterion is violated, output exactly 'FAIL'. "
            "Do not output explanations, reasoning, or any other text."
        )
        yield Agent(
            generate_model(
                "google/gemini-2.5-flash-lite:google-ai-studio", http_client
            ),
            system_prompt=system_prompt,
            model_settings={"temperature": 0.0},  # a judge should be deterministic
        )


@pytest_asyncio.fixture(loop_scope="function")
async def client():
    async with httpx.AsyncClient(base_url=API_URL, headers=headers, timeout=120.0) as c:
        for _ in range(15):
            try:
                await c.get("/api/v1/")
                break
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
                await asyncio.sleep(2)
        else:
            pytest.fail("API server not reachable")
        yield c


@pytest_asyncio.fixture(loop_scope="function")
async def no_auth_client():
    """Client with no Authorization header."""
    async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as c:
        for _ in range(15):
            try:
                await c.get("/api/v1/")
                break
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
                await asyncio.sleep(2)
        yield c


@pytest_asyncio.fixture(loop_scope="function")
async def bad_auth_client():
    """Client with an invalid token."""
    async with httpx.AsyncClient(
        base_url=API_URL,
        headers={"Authorization": "Bearer totally_wrong_token_xyz"},
        timeout=30.0,
    ) as c:
        for _ in range(15):
            try:
                await c.get("/api/v1/")
                break
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
                await asyncio.sleep(2)
        yield c


@pytest_asyncio.fixture(loop_scope="function")
async def memory_tool_off(client):
    """Turn the memory tool off on the unit's agent, so that what a test says can
    only reach the model through the message history."""
    agent_id = (await client.get("/api/v1/agents/self")).json()["id"]
    res = await client.patch(
        f"/api/v1/admin/agents/{agent_id}", json={"config": {"tools": ["rag"]}}
    )
    assert res.status_code == 200
    try:
        yield
    finally:
        await client.patch(
            f"/api/v1/admin/agents/{agent_id}",
            json={"config": {"tools": ["rag", "memory"]}},
        )


@pytest_asyncio.fixture(loop_scope="function")
async def broken_model(client):
    """The unit's agent uses a model name the provider does not know."""
    agent_id = (await client.get("/api/v1/agents/self")).json()["id"]
    res = await client.post(
        "/api/v1/admin/models",
        json={"name": "test", "request_json": {"model": "no/such-model-xyz"}},
    )
    model_id = res.json()["id"]
    await client.patch(f"/api/v1/admin/agents/{agent_id}", json={"model_id": model_id})
    yield
    await client.patch(f"/api/v1/admin/agents/{agent_id}", json={"model_id": 0})
    await client.delete(f"/api/v1/admin/models/{model_id}")


@pytest_asyncio.fixture(loop_scope="function")
async def vision_model(client):
    """The unit's agent uses a model that can see images."""
    agent_id = (await client.get("/api/v1/agents/self")).json()["id"]
    res = await client.post(
        "/api/v1/admin/models",
        json={"name": "test", "request_json": {"model": VISION_MODEL}},
    )
    model_id = res.json()["id"]
    await client.patch(f"/api/v1/admin/agents/{agent_id}", json={"model_id": model_id})
    yield
    await client.patch(f"/api/v1/admin/agents/{agent_id}", json={"model_id": 0})
    await client.delete(f"/api/v1/admin/models/{model_id}")


@pytest_asyncio.fixture(loop_scope="function")
async def scratch_db():
    """A throwaway database on the test Postgres; yields a connection to it."""
    name = f"migration_test_{uuid.uuid4().hex[:8]}"
    admin = await asyncpg.connect(**DATABASE_CONFIG)
    await admin.execute(f'CREATE DATABASE "{name}"')
    connection = await asyncpg.connect(**{**DATABASE_CONFIG, "database": name})
    try:
        yield connection
    finally:
        await connection.close()
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()
