import os
from collections.abc import AsyncGenerator
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("SECRET_KEY", "test-secret-key-with-sufficient-length-32b")

from app.auth import get_current_user
from app.db import Base, get_db_session
from app.dependencies import get_today
from app.main import app


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as db_session:
        yield db_session

    await engine.dispose()


@pytest.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_db_session] = override_get_db_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_today, None)


PINNED_TODAY = date(2026, 10, 16)


@pytest.fixture
def pinned_today() -> date:
    app.dependency_overrides[get_today] = lambda: PINNED_TODAY
    return PINNED_TODAY


@pytest.fixture
def make_headers(client: AsyncClient):
    """Register a user through the real API and return Bearer headers."""

    async def _make(email: str) -> dict[str, str]:
        creds = {"email": email, "password": "password123"}
        assert (await client.post("/api/auth/register", json=creds)).status_code == 201
        resp = await client.post("/api/auth/login", json=creds)
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return _make


def authenticate_as(user) -> None:
    app.dependency_overrides[get_current_user] = lambda: user
