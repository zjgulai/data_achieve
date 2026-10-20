from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.core.security import decode_access_token
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.users import get_user_by_id
from data_intelligence_hub.repositories.workspaces import (
    get_default_workspace_for_user,
    get_demo_workspace,
)

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


async def get_authenticated_context(
    session: SessionDep,
    access_token: Annotated[str | None, Cookie(alias="access_token")] = None,
) -> AuthContext:
    """严格鉴权。无有效 token 一律 401。

    这是 fail-closed 依赖。写接口应当用它。
    与 get_auth_context 的区别：它从不回退到 demo workspace，
    不受 DEMO_MODE 影响。

    为什么单列一个函数而不是改 get_auth_context：
    get_auth_context 被 149 个端点使用，其中读接口在开发环境依赖 demo 回退。
    迁移是分批的（B1-08 起把写接口逐个切过来）。
    一次改掉会让读接口在本地与测试环境全部 401。
    """
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

    workspace = await get_default_workspace_for_user(session, user.id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="workspace_not_found",
        )
    return AuthContext(user=user, workspace=workspace)


async def get_auth_context(
    session: SessionDep,
    access_token: Annotated[str | None, Cookie(alias="access_token")] = None,
) -> AuthContext:
    """带 demo 回退的鉴权。

    有有效 token 时按 token 解析。
    无 token 时，只有 effective_demo_mode 为真才回退 demo workspace。
    生产环境 effective_demo_mode 默认为假，因此生产是 fail-closed。

    回退开关见 core/config.py 的 demo_mode 与 effective_demo_mode。
    """
    if access_token is not None:
        user_id = decode_access_token(access_token)
        if user_id is not None:
            user = await get_user_by_id(session, user_id)
            if user is not None and user.status == "active":
                workspace = await get_default_workspace_for_user(session, user.id)
                if workspace is not None:
                    return AuthContext(user=user, workspace=workspace)

    if not get_settings().effective_demo_mode:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    workspace = await get_demo_workspace(session)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_workspace_unavailable",
        )
    owner = await get_user_by_id(session, workspace.owner_id)
    if owner is None or owner.status != "active":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_workspace_owner_unavailable",
        )
    return AuthContext(user=owner, workspace=workspace)
