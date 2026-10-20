"""项目级 API 密钥的签发与鉴权。

明文只在签发时返回一次。库里只存 sha256 摘要。
随机数来自 ``secrets`` 模块。本模块不用 ``random``。
签发只 flush，不 commit。调用方负责提交事务。
"""

from __future__ import annotations

import dataclasses
import hashlib
import secrets
import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.project_api_key import ProjectApiKey
from data_intelligence_hub.repositories.project_api_keys import create_key, find_by_hash

KEY_MARKER = "dih_"
PREFIX_HEX_BYTES = 4
SECRET_HEX_BYTES = 16


@dataclasses.dataclass(frozen=True, slots=True)
class IssuedProjectApiKey:
    """签发结果。``plaintext`` 只在此处出现一次，且不进入 repr。"""

    plaintext: str = dataclasses.field(repr=False)
    record: ProjectApiKey = dataclasses.field(repr=False)


@dataclasses.dataclass(frozen=True, slots=True)
class ProjectApiKeyIdentity:
    """一次成功鉴权得到的调用身份。它不含明文。"""

    key_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    key_prefix: str
    label: str
    tool_allowlist: tuple[str, ...]
    daily_collect_quota: int

    def allows_tool(self, tool_name: str) -> bool:
        """白名单外的工具必须返回 403 tool_not_allowed。"""
        return tool_name in self.tool_allowlist


def hash_key(plaintext: str) -> str:
    """返回明文的 sha256 十六进制摘要。"""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def generate_plaintext() -> tuple[str, str]:
    """生成明文与可读前缀。

    格式：``dih_<8位前缀>_<32位随机>``。
    前缀与随机段都用 ``secrets.token_hex``。输出只含十六进制字符。
    """
    prefix = secrets.token_hex(PREFIX_HEX_BYTES)
    secret = secrets.token_hex(SECRET_HEX_BYTES)
    key_prefix = f"{KEY_MARKER}{prefix}"
    return f"{key_prefix}_{secret}", key_prefix


async def issue_key(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    label: str,
    created_by_user_id: uuid.UUID,
    tool_allowlist: Sequence[str],
    daily_collect_quota: int,
) -> IssuedProjectApiKey:
    """签发一把密钥，并返回一次明文。

    标签必须非空，白名单必须非空，额度必须为正整数。
    白名单为空会让密钥无法调用任何工具；额度为零会让它立即超额。
    两者都按配置错误拒绝，不静默放行。
    本函数只 flush，调用方负责 commit。
    """
    normalized_label = label.strip()
    if not normalized_label:
        raise ValueError("project_api_key_label_required")
    normalized_allowlist = tuple(item.strip() for item in tool_allowlist if item.strip())
    if not normalized_allowlist:
        raise ValueError("project_api_key_allowlist_required")
    if daily_collect_quota < 1:
        raise ValueError("project_api_key_quota_must_be_positive")
    plaintext, key_prefix = generate_plaintext()
    record = await create_key(
        session,
        project_id=project_id,
        workspace_id=workspace_id,
        label=normalized_label,
        key_prefix=key_prefix,
        key_hash=hash_key(plaintext),
        created_by_user_id=created_by_user_id,
        tool_allowlist=normalized_allowlist,
        daily_collect_quota=daily_collect_quota,
    )
    return IssuedProjectApiKey(plaintext=plaintext, record=record)


async def authenticate_key(
    session: AsyncSession,
    plaintext: str,
) -> ProjectApiKeyIdentity | None:
    """按明文鉴权。未命中或已撤销时返回 None。"""
    if not plaintext:
        return None
    record = await find_by_hash(session, hash_key(plaintext))
    if record is None or record.revoked_at is not None:
        return None
    return ProjectApiKeyIdentity(
        key_id=record.id,
        workspace_id=record.workspace_id,
        project_id=record.project_id,
        key_prefix=record.key_prefix,
        label=record.label,
        tool_allowlist=tuple(record.tool_allowlist or ()),
        daily_collect_quota=record.daily_collect_quota,
    )


__all__ = [
    "KEY_MARKER",
    "IssuedProjectApiKey",
    "ProjectApiKeyIdentity",
    "authenticate_key",
    "generate_plaintext",
    "hash_key",
    "issue_key",
]
