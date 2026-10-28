from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 业务域闭集。前端 `/domain/[domain]` 有 7 个域，这里必须同源，
# 否则「Agent 生态 / 平台采集 / 合规边界」三个域建项目会被 422 拒绝，
# 域页永远只有空壳。`mixed` 是跨域项目的兜底值。
#
# Project.domain 列是 String(30)，没有 DB CHECK，扩取值不需要迁移。
ProjectDomain = Literal[
    "osint",
    "ecommerce",
    "social",
    "competitor",
    "agent",
    "platform",
    "governance",
    "mixed",
]
ProjectStatus = Literal["active", "archived"]


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    domain: ProjectDomain


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    domain: ProjectDomain | None = None
    status: ProjectStatus | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None
    domain: str
    status: str
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
