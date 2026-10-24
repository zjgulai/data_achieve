from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IssueProjectApiKeyRequest(BaseModel):
    """签发请求。白名单必须非空；额度必须为正整数。"""

    label: str = Field(min_length=1, max_length=200)
    tool_allowlist: list[str] = Field(min_length=1)
    daily_collect_quota: int = Field(ge=1, le=100000)


class ProjectApiKeyResponse(BaseModel):
    """密钥行。永不包含明文。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    workspace_id: uuid.UUID
    label: str
    key_prefix: str
    tool_allowlist: list[str]
    daily_collect_quota: int
    quota_date: object | None = None
    quota_used: int = 0
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ProjectApiKeyPatchRequest(BaseModel):
    """PATCH 请求。两个字段均可选，但至少要给一项。

    白名单规则与签发一致：必须非空，且工具名必须已在注册表登记。
    额度范围与签发一致：1–100000。
    两者都缺省时没有可执行的更新，由处理器显式返回 400。
    """

    tool_allowlist: list[str] | None = None
    daily_collect_quota: int | None = Field(default=None, ge=1, le=100000)


class IssuedProjectApiKeyResponse(ProjectApiKeyResponse):
    """签发响应。明文只在这一次出现。"""

    plaintext: str