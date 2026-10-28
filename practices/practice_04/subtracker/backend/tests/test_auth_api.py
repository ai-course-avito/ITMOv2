from datetime import UTC, datetime, timedelta

import jwt

from app import security
from app.config import settings
from app.models import User

CREDS = {"email": "user@example.com", "password": "password123"}


async def register_and_login(client) -> dict:
    resp = await client.post("/api/auth/register", json=CREDS)
    assert resp.status_code == 201
    resp = await client.post("/api/auth/login", json=CREDS)
    assert resp.status_code == 200
    return resp.json()


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_register_returns_user_without_secrets(client):
    resp = await client.post("/api/auth/register", json=CREDS)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == CREDS["email"]
    assert body["plan"] == "free"
    assert "password" not in body and "hashed_password" not in body


async def test_register_duplicate_email_is_409(client):
    await client.post("/api/auth/register", json=CREDS)
    resp = await client.post(
        "/api/auth/register", json={**CREDS, "email": "USER@example.com"}
    )
    assert resp.status_code == 409


async def test_register_invalid_input_is_422(client):
    bad_email = await client.post(
        "/api/auth/register", json={"email": "nope", "password": "password123"}
    )
    short_pw = await client.post(
        "/api/auth/register", json={"email": "a@example.com", "password": "short"}
    )
    assert bad_email.status_code == 422
    assert short_pw.status_code == 422


async def test_login_returns_tokens(client):
    tokens = await register_and_login(client)
    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"] and tokens["refresh_token"]


async def test_login_wrong_credentials_same_message(client):
    await client.post("/api/auth/register", json=CREDS)
    wrong_pw = await client.post(
        "/api/auth/login", json={**CREDS, "password": "wrong-password"}
    )
    unknown = await client.post(
        "/api/auth/login", json={"email": "x@example.com", "password": "whatever1"}
    )
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()


async def test_refresh_returns_new_access_token(client):
    tokens = await register_and_login(client)
    resp = await client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 200
    me = await client.get("/api/auth/me", headers=bearer(resp.json()["access_token"]))
    assert me.status_code == 200


async def test_refresh_rejects_access_token(client):
    tokens = await register_and_login(client)
    resp = await client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )
    assert resp.status_code == 401


async def test_refresh_token_not_accepted_as_access(client):
    tokens = await register_and_login(client)
    resp = await client.get(
        "/api/stats/summary", headers=bearer(tokens["refresh_token"])
    )
    assert resp.status_code == 401


async def test_stats_with_real_token_and_without(client):
    tokens = await register_and_login(client)
    ok = await client.get("/api/stats/summary", headers=bearer(tokens["access_token"]))
    assert ok.status_code == 200
    assert ok.json()["monthly_total"] == "0.00"

    missing = await client.get("/api/stats/summary")
    assert missing.status_code == 401


async def test_expired_access_token_is_401(client):
    await client.post("/api/auth/register", json=CREDS)
    token = jwt.encode(
        {"sub": "1", "type": "access", "exp": datetime.now(UTC) - timedelta(minutes=1)},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    resp = await client.get("/api/auth/me", headers=bearer(token))
    assert resp.status_code == 401


async def test_token_for_deleted_user_is_401(client):
    ghost = security.create_token(9999, "access")
    resp = await client.get("/api/auth/me", headers=bearer(ghost))
    assert resp.status_code == 401


async def test_me_free_and_pro(client, session):
    tokens = await register_and_login(client)
    me = await client.get("/api/auth/me", headers=bearer(tokens["access_token"]))
    assert me.status_code == 200
    assert me.json()["plan"] == "free"
    assert me.json()["default_currency"] == "USD"

    user = await session.get(User, me.json()["id"])
    user.plan = "pro"
    await session.commit()
    me = await client.get("/api/auth/me", headers=bearer(tokens["access_token"]))
    assert me.json()["plan"] == "pro"


async def test_me_requires_authentication(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_register_password_over_128_chars_is_422(client):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "long@example.com", "password": "x" * 129},
    )
    assert resp.status_code == 422


async def test_login_email_case_and_spaces_insensitive(client):
    await client.post("/api/auth/register", json=CREDS)
    resp = await client.post(
        "/api/auth/login",
        json={"email": "  USER@Example.com ", "password": CREDS["password"]},
    )
    assert resp.status_code == 200
