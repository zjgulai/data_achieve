from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    # 最小长度 8。2026-10-29 曾临时放宽到 3 供测试账号使用，之后已恢复：
    # 这条约束管的是**所有账号**的注册入口，任何低于 8 的口令在 bcrypt
    # 之外都没有强度保护。
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    # 与 RegisterRequest 必须同值：两处不一致会出现「能注册、登不上」
    # 或反过来的死锁。
    password: str = Field(min_length=8, max_length=128)


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
