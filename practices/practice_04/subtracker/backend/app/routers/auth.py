from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db_session
from app.models import User
from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    body: RegisterRequest, session: AsyncSession = Depends(get_db_session)
) -> User:
    try:
        return await auth_service.register_user(session, body.email, body.password)
    except auth_service.EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        ) from exc


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, session: AsyncSession = Depends(get_db_session)
) -> TokenResponse:
    try:
        user = await auth_service.authenticate(session, body.email, body.password)
    except auth_service.InvalidCredentialsError as exc:
        raise _unauthorized("Incorrect email or password") from exc
    return auth_service.issue_tokens(user)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    body: RefreshRequest, session: AsyncSession = Depends(get_db_session)
) -> AccessTokenResponse:
    try:
        return await auth_service.refresh_access_token(session, body.refresh_token)
    except auth_service.InvalidCredentialsError as exc:
        raise _unauthorized("Invalid refresh token") from exc


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
