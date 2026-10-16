import pytest

from app.services import auth as auth_service


async def test_register_normalizes_email_and_hashes_password(session):
    user = await auth_service.register_user(
        session, "  Alice@Example.COM ", "password1"
    )
    assert user.email == "alice@example.com"
    assert user.hashed_password != "password1"
    assert user.plan == "free"


async def test_register_duplicate_email_different_case(session):
    await auth_service.register_user(session, "bob@example.com", "password1")
    with pytest.raises(auth_service.EmailAlreadyRegisteredError):
        await auth_service.register_user(session, "BOB@example.com", "password2")


async def test_authenticate_success(session):
    await auth_service.register_user(session, "carol@example.com", "password1")
    user = await auth_service.authenticate(session, "Carol@Example.com", "password1")
    assert user.email == "carol@example.com"


async def test_authenticate_wrong_password(session):
    await auth_service.register_user(session, "dave@example.com", "password1")
    with pytest.raises(auth_service.InvalidCredentialsError):
        await auth_service.authenticate(session, "dave@example.com", "nope-nope")


async def test_authenticate_unknown_email(session):
    with pytest.raises(auth_service.InvalidCredentialsError):
        await auth_service.authenticate(session, "ghost@example.com", "password1")
