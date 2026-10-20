"""工作区与成员接口。

切换工作区写 active_workspace Cookie。后续请求按该 Cookie 解析工作区。
成员管理只允许工作区所有者操作。MVP 只支持添加 member 角色。
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response, status

from data_intelligence_hub.api.deps import (
    WORKSPACE_COOKIE_NAME,
    AuthenticatedContextDep,
    SessionDep,
)
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.repositories.users import get_user_by_email
from data_intelligence_hub.repositories.workspaces import (
    get_workspace_for_member,
    list_workspace_members,
    list_workspaces_for_user,
    user_belongs_to_workspace,
)
from data_intelligence_hub.schemas.auth import (
    AuthSessionResponse,
    UserResponse,
    WorkspaceResponse,
)
from data_intelligence_hub.schemas.workspace import (
    AddWorkspaceMemberRequest,
    WorkspaceMemberResponse,
    WorkspaceMembershipResponse,
)
from data_intelligence_hub.services.workspace_service import (
    add_member,
    remove_member,
)

router = APIRouter(tags=["workspaces"])


def _require_owner(context: AuthenticatedContextDep) -> None:
    if context.workspace.owner_id != context.user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="workspace_owner_required",
        )


@router.get("", response_model=list[WorkspaceMembershipResponse])
async def list_workspaces_item(
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> list[WorkspaceMembershipResponse]:
    rows = await list_workspaces_for_user(session, context.user.id)
    return [
        WorkspaceMembershipResponse(
            **WorkspaceResponse.model_validate(workspace).model_dump(),
            role=role,
        )
        for workspace, role in rows
    ]


@router.post("/{workspace_id}/activate", response_model=AuthSessionResponse)
async def activate_workspace_item(
    workspace_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
    response: Response,
) -> AuthSessionResponse:
    workspace = await get_workspace_for_member(session, workspace_id, context.user.id)
    if workspace is None:
        # 非成员与不存在的工作区返回同一个响应，避免探测工作区是否存在。
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="workspace_membership_required",
        )
    settings = get_settings()
    response.set_cookie(
        key=WORKSPACE_COOKIE_NAME,
        value=str(workspace.id),
        max_age=settings.jwt_expires_minutes * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    return AuthSessionResponse(
        user=UserResponse.model_validate(context.user),
        workspace=WorkspaceResponse.model_validate(workspace),
    )


@router.get("/current/members", response_model=list[WorkspaceMemberResponse])
async def list_current_workspace_members(
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> list[WorkspaceMemberResponse]:
    rows = await list_workspace_members(session, context.workspace.id)
    return [
        WorkspaceMemberResponse(user=UserResponse.model_validate(user), role=member.role)
        for member, user in rows
    ]


@router.post(
    "/current/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_current_workspace_member(
    payload: AddWorkspaceMemberRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> WorkspaceMemberResponse:
    _require_owner(context)
    user = await get_user_by_email(session, str(payload.email))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user_not_found",
        )
    if await user_belongs_to_workspace(session, user.id, context.workspace.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="workspace_member_exists",
        )
    member = await add_member(
        session, context.workspace.id, user.id, payload.role
    )
    return WorkspaceMemberResponse(
        user=UserResponse.model_validate(user), role=member.role
    )


@router.delete(
    "/current/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_current_workspace_member(
    user_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> None:
    # 所有者可移除任何非所有者成员；成员可以移除自己（离开工作区）。
    if user_id != context.user.id:
        _require_owner(context)
    if user_id == context.workspace.owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="workspace_owner_immovable",
        )
    removed = await remove_member(session, context.workspace.id, user_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="workspace_member_not_found",
        )
