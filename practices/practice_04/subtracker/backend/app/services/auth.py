import asyncio

import jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import security
from app.models import User
from app.schemas.auth import AccessTokenResponse, TokenResponse


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == normalize_email(email))
    return (await session.execute(stmt)).scalar_one_or_none()


async def register_user(session: AsyncSession, email: str, password: str) -> User:
    email = normalize_email(email)
    if await get_user_by_email(session, email) is not None:
        raise EmailAlreadyRegisteredError
    hashed = await asyncio.to_thread(security.hash_password, password)
    user = User(email=email, hashed_password=hashed)
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:  # concurrent registration of the same email
        await session.rollback()
        raise EmailAlreadyRegisteredError from exc
    await session.refresh(user)
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(session, email)
    hashed = user.hashed_password if user else security.DUMMY_HASH
    ok = await asyncio.to_thread(security.verify_password, password, hashed)
    if user is None or not ok:
        raise InvalidCredentialsError
    return user


def issue_tokens(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=security.create_token(user.id, "access"),
        refresh_token=security.create_token(user.id, "refresh"),
    )


async def refresh_access_token(
    session: AsyncSession, refresh_token: str
) -> AccessTokenResponse:
    try:
        user_id = security.decode_token(refresh_token, "refresh")
    except jwt.PyJWTError as exc:
        raise InvalidCredentialsError from exc
    user = await session.get(User, user_id)
    if user is None:
        raise InvalidCredentialsError
    return AccessTokenResponse(access_token=security.create_token(user.id, "access"))
