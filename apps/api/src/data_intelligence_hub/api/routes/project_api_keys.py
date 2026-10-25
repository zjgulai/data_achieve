"""项目 API 密钥的签发、列表与撤销。

每个项目最多一把未撤销的密钥。轮换必须先撤销、再签发。
签发响应只在这一次返回明文；此后只能看到前缀。

鉴权：登录会话（严格模式）。工作区所有者或项目所有者可管理密钥。
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from data_intelligence_hub.api.deps import AuthenticatedContextDep, SessionDep
from data_intelligence_hub.mcp_runtime.tool_registry import TOOL_POLICIES
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.project_api_key import ProjectApiKey
from data_intelligence_hub.repositories.project_api_keys import (
    list_keys,
    revoke_key,
)
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.schemas.project_api_key import (
    IssuedProjectApiKeyResponse,
    IssueProjectApiKeyRequest,
    ProjectApiKeyPatchRequest,
    ProjectApiKeyResponse,
)
from data_intelligence_hub.services.project_api_keys import issue_key

router = APIRouter(tags=["project-api-keys"])


async def _project_or_404(
    session: SessionDep,
    context: AuthenticatedContextDep,
    project_id: uuid.UUID,
) -> Project:
    project = await get_project(session, context.workspace.id, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="project_not_found",
        )
    if (
        context.workspace.owner_id != context.user.id
        and project.owner_id != context.user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="project_key_management_forbidden",
        )
    return project


@router.post(
    "/{project_id}/api-keys",
    response_model=IssuedProjectApiKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def issue_project_api_key(
    project_id: uuid.UUID,
    payload: IssueProjectApiKeyRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> IssuedProjectApiKeyResponse:
    """签发一把项目密钥。

    白名单规则与 PATCH 一致：工具名必须已在注册表登记，且不允许为空。
    schema 的 min_length 已挡住空列表，这里再挡一道，两条路径共用同一组
    错误码，客户端不必按接口分别处理。
    """
    await _project_or_404(session, context, project_id)
    unknown = [t for t in payload.tool_allowlist if t not in TOOL_POLICIES]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unknown_tool_in_allowlist",
        )
    if not payload.tool_allowlist:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_api_key_allowlist_required",
        )
    try:
        issued = await issue_key(
            session,
            project_id=project_id,
            workspace_id=context.workspace.id,
            label=payload.label,
            created_by_user_id=context.user.id,
            tool_allowlist=payload.tool_allowlist,
            daily_collect_quota=payload.daily_collect_quota,
        )
        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        # 部分唯一索引在 flush 时就报错：项目已有一把未撤销的密钥。
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="project_api_key_active_exists",
        ) from exc
    await session.refresh(issued.record)
    return IssuedProjectApiKeyResponse(
        **ProjectApiKeyResponse.model_validate(issued.record).model_dump(),
        plaintext=issued.plaintext,
    )


@router.get(
    "/{project_id}/api-keys",
    response_model=list[ProjectApiKeyResponse],
)
async def list_project_api_keys(
    project_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> list[ProjectApiKeyResponse]:
    await _project_or_404(session, context, project_id)
    rows = await list_keys(
        session,
        workspace_id=context.workspace.id,
        project_id=project_id,
    )
    return [ProjectApiKeyResponse.model_validate(row) for row in rows]


@router.patch(
    "/{project_id}/api-keys/{key_id}",
    response_model=ProjectApiKeyResponse,
)
async def patch_project_api_key(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    payload: ProjectApiKeyPatchRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> ProjectApiKeyResponse:
    """原地更新密钥的白名单与日额度。

    仅所有者（工作区所有者或项目所有者）可改；key 必须同时命中
    workspace+project 复合归属。白名单规则与签发一致：工具名必须
    已在注册表登记，且不允许为空。两者都缺省时显式拒绝。
    """
    await _project_or_404(session, context, project_id)
    record = await session.get(ProjectApiKey, key_id)
    if (
        record is None
        or record.workspace_id != context.workspace.id
        or record.project_id != project_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="project_api_key_not_found",
        )
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no_fields_to_update",
        )
    if "tool_allowlist" in updates:
        unknown = [t for t in updates["tool_allowlist"] if t not in TOOL_POLICIES]
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="unknown_tool_in_allowlist",
            )
        if not updates["tool_allowlist"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="project_api_key_allowlist_required",
            )
        record.tool_allowlist = updates["tool_allowlist"]
    if "daily_collect_quota" in updates:
        record.daily_collect_quota = updates["daily_collect_quota"]
    await session.commit()
    await session.refresh(record)
    return ProjectApiKeyResponse.model_validate(record)


@router.delete(
    "/{project_id}/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_project_api_key(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> None:
    await _project_or_404(session, context, project_id)
    record = await revoke_key(
        session,
        workspace_id=context.workspace.id,
        project_id=project_id,
        key_id=key_id,
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="project_api_key_not_found",
        )
    await session.commit()