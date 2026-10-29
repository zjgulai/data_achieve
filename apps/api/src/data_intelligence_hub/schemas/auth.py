from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    # 最小长度 3，是用户明确要求的放宽（2026-10-29），不是疏忽。
    #
    # 注意影响范围：这条约束管的是**所有账号**的注册入口，不是某个测试
    # 账号的特例。3 位口令在 bcrypt 之外没有任何强度保护，暴力破解成本
    # 极低。恢复默认值只需把这里改回 8。
    password: str = Field(min_length=3, max_length=128)
    name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    # 与 RegisterRequest 保持同一阈值：两处不一致会出现「能注册、登不上」
    # 或反过来的死锁。同样见上文关于强度的影响说明。
    password: str = Field(min_length=3, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str
    status: str
    created_at: datetime
    updated_at: datetime


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class AuthSessionResponse(BaseModel):
    user: UserResponse
    workspace: WorkspaceResponse
