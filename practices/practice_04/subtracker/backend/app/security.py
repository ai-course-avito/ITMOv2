from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import settings

TokenType = Literal["access", "refresh"]

_hasher = PasswordHasher()
# Verified against when the email is unknown, so login timing does not reveal
# which emails are registered.
DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


def create_token(user_id: int, token_type: TokenType) -> str:
    now = datetime.now(UTC)
    if token_type == "access":
        ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    else:
        ttl = timedelta(days=settings.refresh_token_ttl_days)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str, expected_type: TokenType) -> int:
    """Return the user id from a valid token of the expected type.

    Raises jwt.PyJWTError (or ValueError/KeyError wrapped by the caller) if the
    token is invalid, expired, lacks exp/sub, or has the wrong type.
    """
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm],
        options={"require": ["exp", "sub"]},
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Wrong token type")
    try:
        return int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise jwt.InvalidTokenError("Invalid subject") from exc
