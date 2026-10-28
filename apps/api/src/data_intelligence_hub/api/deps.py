from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.core.security import decode_access_token
from data_intelligence_hub.models.abi import AccessGrant, CatalogDataset, role_rank
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.abi import (
    get_access_grant,
    get_dataset_by_slug,
)
from data_intelligence_hub.repositories.users import get_user_by_id
from data_intelligence_hub.repositories.workspaces import (
    get_default_workspace_for_user,
    get_demo_workspace,
    get_workspace_for_member,
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# 当前工作区的 Cookie 名。切换工作区时由 /api/workspaces/{id}/activate 写入。
WORKSPACE_COOKIE_NAME = "active_workspace"


def _parse_workspace_id(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


async def resolve_workspace_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    active_workspace_id: str | None = None,
) -> Workspace | None:
    """解析用户当前工作区。

    优先级：Cookie 指向且用户是成员 → Cookie 工作区；否则默认工作区。
    默认工作区在 demo 模式优先 demo，生产优先个人工作区。
    Cookie 指向非成员工作区时忽略，不报错。
    """
    workspace_id = _parse_workspace_id(active_workspace_id)
    if workspace_id is not None:
        workspace = await get_workspace_for_member(session, workspace_id, user_id)
        if workspace is not None:
            return workspace
    return await get_default_workspace_for_user(
        session,
        user_id,
        prefer_demo=get_settings().effective_demo_mode,
    )


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
    active_workspace_id: Annotated[str | None, Cookie(alias=WORKSPACE_COOKIE_NAME)] = None,
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

    workspace = await resolve_workspace_for_user(session, user.id, active_workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="workspace_not_found",
        )
    return AuthContext(user=user, workspace=workspace)


async def get_auth_context(
    session: SessionDep,
    access_token: Annotated[str | None, Cookie(alias="access_token")] = None,
    active_workspace_id: Annotated[str | None, Cookie(alias=WORKSPACE_COOKIE_NAME)] = None,
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
                workspace = await resolve_workspace_for_user(
                    session, user.id, active_workspace_id
                )
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


AuthContextDep = Annotated[AuthContext, Depends(get_auth_context)]
AuthenticatedContextDep = Annotated[AuthContext, Depends(get_authenticated_context)]


async def get_active_workspace(context: AuthContextDep) -> Workspace:
    """读接口的工作区依赖。生产无 token 时由 get_auth_context 返回 401。"""
    return context.workspace


async def get_authenticated_workspace(context: AuthenticatedContextDep) -> Workspace:
    """严格工作区依赖。无有效 token 一律 401。"""
    return context.workspace


WorkspaceDep = Annotated[Workspace, Depends(get_active_workspace)]
AuthenticatedWorkspaceDep = Annotated[Workspace, Depends(get_authenticated_workspace)]


@dataclass(frozen=True)
class DatasetAccess:
    """通过 dataset 授权校验后的上下文。

    ``grant`` 是当前用户在该 dataset 上的授权行。workspace owner 身份
    不构成 bypass：没有 access_grant 一律 403。
    """

    dataset: CatalogDataset
    grant: AccessGrant
    workspace: Workspace
    user: User


def require_dataset_role(
    min_role: str,
) -> Callable[..., Awaitable[DatasetAccess]]:
    """构造 dataset 级授权依赖。

    按 ``workspace_id + slug`` 查 dataset，再按 ``workspace_id + dataset_id
    + user_id`` 查 access_grant。角色序 viewer < editor < publisher < admin。
    admin 只表示该 dataset 的最高角色，不做 workspace 万能 bypass。
    """
    minimum = role_rank(min_role)
    if minimum < 0:
        raise ValueError(f"unknown ABI role: {min_role}")

    async def dependency(
        slug: str,
        session: SessionDep,
        context: AuthenticatedContextDep,
    ) -> DatasetAccess:
        dataset = await get_dataset_by_slug(session, context.workspace.id, slug)
        if dataset is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="dataset_not_found",
            )
        grant = await get_access_grant(
            session,
            context.workspace.id,
            dataset.id,
            context.user.id,
        )
        if grant is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="dataset_forbidden",
            )
        if role_rank(grant.role) < minimum:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="insufficient_role",
            )
        return DatasetAccess(
            dataset=dataset,
            grant=grant,
            workspace=context.workspace,
            user=context.user,
        )

    return dependency
