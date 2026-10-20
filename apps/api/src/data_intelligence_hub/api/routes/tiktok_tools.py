"""REST surface for the sixteen TikTok content tools."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from data_intelligence_hub.api.deps import SessionDep, get_current_user
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.services.tiktok_tools import TOOL_SPECS, run_tiktok_tool

router = APIRouter(tags=["tiktok-tools"])


class TikTokToolRequest(BaseModel):
    project_id: uuid.UUID
    params: dict[str, Any] = Field(default_factory=dict)


async def _require_project_access(
    session: SessionDep,
    user: User,
    project_id: uuid.UUID,
) -> Project:
    """项目必须属于当前用户的某个工作区。

    鉴权用 get_current_user，不用 get_auth_context。
    后者在无 token 时回退 demo workspace，无法阻止匿名调用。
    """
    workspace_ids = {membership.workspace_id for membership in user.workspace_memberships}
    for workspace_id in workspace_ids:
        project = await get_project(session, workspace_id, project_id)
        if project is not None:
            return project
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="project_not_found",
    )


@router.get("")
async def list_tiktok_tools(
    user: Annotated[User, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    del user
    return [{"tool_id": tool_id, **spec} for tool_id, spec in TOOL_SPECS.items()]


@router.post("/{tool_id}")
async def run_tiktok_tool_route(
    tool_id: str,
    body: TikTokToolRequest,
    session: SessionDep,
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    if tool_id not in TOOL_SPECS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown_tiktok_tool: {tool_id}",
        )
    await _require_project_access(session, user, body.project_id)
    result = await run_tiktok_tool(tool_id, body.project_id, body.params)
    return result.as_dict()
