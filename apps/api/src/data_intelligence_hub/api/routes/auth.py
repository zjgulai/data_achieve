from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from data_intelligence_hub.api.deps import SessionDep, get_current_user
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.models.user import User
from data_intelligence_hub.schemas.auth import AuthSessionResponse, LoginRequest, RegisterRequest
from data_intelligence_hub.services.auth_service import (
    AuthSession,
    get_session_for_user,
    login_user,
    register_user,
)
from data_intelligence_hub.services.exceptions import (
    DuplicateEmailError,
    InvalidCredentialsError,
    WorkspaceNotFoundError,
)

router = APIRouter(tags=["auth"])


@router.post("/register", response_model=AuthSessionResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    response: Response,
    session: SessionDep,
) -> AuthSessionResponse:
    try:
        auth_session = await register_user(session, payload)
    except DuplicateEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DuplicateEmailError.message,
        ) from exc

    _set_auth_cookie(response, auth_session)
    return AuthSessionResponse(user=auth_session.user, workspace=auth_session.workspace)


@router.post("/login", response_model=AuthSessionResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    session: SessionDep,
) -> AuthSessionResponse:
    try:
        auth_session = await login_user(session, payload)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=InvalidCredentialsError.message,
        ) from exc

    _set_auth_cookie(response, auth_session)
    return AuthSessionResponse(user=auth_session.user, workspace=auth_session.workspace)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    settings = get_settings()
    response.delete_cookie(key=settings.auth_cookie_name, path="/")
    return response


@router.get("/me", response_model=AuthSessionResponse)
async def me(
    session: SessionDep,
    user: Annotated[User, Depends(get_current_user)],
) -> AuthSessionResponse:
    try:
        auth_session = await get_session_for_user(session, user)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=WorkspaceNotFoundError.message,
        ) from exc
    return AuthSessionResponse(user=auth_session.user, workspace=auth_session.workspace)


def _set_auth_cookie(response: Response, auth_session: AuthSession) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=auth_session.access_token,
        max_age=settings.jwt_expires_minutes * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
