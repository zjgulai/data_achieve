from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr

from data_intelligence_hub.schemas.auth import UserResponse, WorkspaceResponse


class WorkspaceMembershipResponse(WorkspaceResponse):
    """工作区与当前用户在该工作区的角色。"""

    role: str


class WorkspaceMemberResponse(BaseModel):
    """工作区成员：用户资料加角色。"""

    user: UserResponse
    role: str


class AddWorkspaceMemberRequest(BaseModel):
    """按邮箱添加成员。MVP 只支持 member 角色。"""

    email: EmailStr
    role: Literal["member"] = "member"
