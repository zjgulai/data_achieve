from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from data_intelligence_hub.api.deps import (
    WORKSPACE_COOKIE_NAME,
    AuthenticatedContextDep,
    SessionDep,
)
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.schemas.auth import (
    AuthSessionResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
    WorkspaceResponse,
)
from data_intelligence_hub.services.auth_service import (
    AuthSession,
    login_user,
    register_user,
)
from data_intelligence_hub.services.exceptions import (
    DuplicateEmailError,
    InvalidCredentialsError,
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
    response.delete_cookie(key=WORKSPACE_COOKIE_NAME, path="/")
    return response


@router.get("/me", response_model=AuthSessionResponse)
async def me(context: AuthenticatedContextDep) -> AuthSessionResponse:
    # 严格模式：无 token 401。工作区按 active_workspace Cookie 解析，
    # 因此切换工作区后，本接口返回新的当前工作区。
    return AuthSessionResponse(
        user=UserResponse.model_validate(context.user),
        workspace=WorkspaceResponse.model_validate(context.workspace),
    )


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
