from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.core.security import decode_access_token
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.users import get_user_by_id
from data_intelligence_hub.repositories.workspaces import get_default_workspace_for_user

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@dataclass(frozen=True)
class AuthContext:
    user: User
    workspace: Workspace


async def get_current_user(
    session: SessionDep,
    access_token: Annotated[str | None, Cookie(alias="access_token")] = None,
) -> User:
    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    user_id = decode_access_token(access_token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    user = await get_user_by_id(session, user_id)
    if user is None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not active",
        )
    return user


async def get_auth_context(
    session: SessionDep,
    user: Annotated[User, Depends(get_current_user)],
) -> AuthContext:
    workspace = await get_default_workspace_for_user(session, user.id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace access not configured",
        )
    return AuthContext(user=user, workspace=workspace)
