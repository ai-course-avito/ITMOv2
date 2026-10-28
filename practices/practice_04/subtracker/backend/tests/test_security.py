from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app import security
from app.config import settings


def make_token(**claims) -> str:
    return jwt.encode(claims, settings.secret_key, algorithm=settings.algorithm)


def test_password_hash_roundtrip():
    hashed = security.hash_password("correct horse")
    assert hashed != "correct horse"
    assert security.verify_password("correct horse", hashed)
    assert not security.verify_password("wrong", hashed)


def test_verify_password_with_garbage_hash_is_false():
    assert not security.verify_password("x", "not-a-hash")


def test_access_token_roundtrip():
    token = security.create_token(42, "access")
    assert security.decode_token(token, "access") == 42


def test_expired_token_rejected():
    token = make_token(
        sub="1", type="access", exp=datetime.now(UTC) - timedelta(seconds=5)
    )
    with pytest.raises(jwt.PyJWTError):
        security.decode_token(token, "access")


def test_token_without_exp_rejected():
    token = make_token(sub="1", type="access")
    with pytest.raises(jwt.PyJWTError):
        security.decode_token(token, "access")


def test_wrong_token_type_rejected():
    token = security.create_token(1, "refresh")
    with pytest.raises(jwt.PyJWTError):
        security.decode_token(token, "access")


def test_wrong_signature_rejected():
    token = jwt.encode(
        {"sub": "1", "type": "access", "exp": datetime.now(UTC) + timedelta(hours=1)},
        "another-secret-another-secret-another",
        algorithm=settings.algorithm,
    )
    with pytest.raises(jwt.PyJWTError):
        security.decode_token(token, "access")
