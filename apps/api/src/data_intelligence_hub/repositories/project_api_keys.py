"""``project_api_keys`` 表的读写。

仓储只做查询、插入与更新，并调用 ``flush``。
事务提交权留给服务层或脚本入口。本模块不调用 ``commit``。
项目内的读写必须同时带 ``workspace_id`` 与 ``project_id``。
``find_by_hash`` 是鉴权入口。鉴权时还没有租户身份，故它不带租户条件。
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.project_api_key import ProjectApiKey


async def create_key(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    label: str,
    key_prefix: str,
    key_hash: str,
    created_by_user_id: uuid.UUID,
    tool_allowlist: Sequence[str],
    daily_collect_quota: int,
) -> ProjectApiKey:
    """插入一行密钥并 flush。明文不进入本函数。

    ``tool_allowlist`` 与 ``daily_collect_quota`` 必须由调用方给出。
    本函数不设默认值：默认值会让「忘了填」变成「允许全部」或「不限额度」。
    """
    record = ProjectApiKey(
        project_id=project_id,
        workspace_id=workspace_id,
        label=label,
        key_prefix=key_prefix,
        key_hash=key_hash,
        created_by_user_id=created_by_user_id,
        tool_allowlist=list(tool_allowlist),
        daily_collect_quota=daily_collect_quota,
    )
    session.add(record)
    await session.flush()
    return record


async def list_keys(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> list[ProjectApiKey]:
    """按工作区与项目返回密钥。结果按创建时间倒序。"""
    result = await session.execute(
        select(ProjectApiKey)
        .where(
            ProjectApiKey.workspace_id == workspace_id,
            ProjectApiKey.project_id == project_id,
        )
        .order_by(ProjectApiKey.created_at.desc(), ProjectApiKey.id)
    )
    return list(result.scalars().all())


async def revoke_key(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    revoked_at: datetime | None = None,
) -> ProjectApiKey | None:
    """撤销一把密钥。未命中时返回 None。

    ``revoked_at`` 只写一次。重复撤销不改变首次时间。
    """
    result = await session.execute(
        select(ProjectApiKey).where(
            ProjectApiKey.id == key_id,
            ProjectApiKey.workspace_id == workspace_id,
            ProjectApiKey.project_id == project_id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None
    if record.revoked_at is None:
        record.revoked_at = revoked_at or datetime.now(UTC)
        await session.flush()
    return record


async def find_by_hash(session: AsyncSession, key_hash: str) -> ProjectApiKey | None:
    """按 sha256 摘要查一行。未命中时返回 None。"""
    result = await session.execute(select(ProjectApiKey).where(ProjectApiKey.key_hash == key_hash))
    return result.scalar_one_or_none()


async def find_by_id(session: AsyncSession, key_id: uuid.UUID) -> ProjectApiKey | None:
    """按主键查一行。鉴权后按身份复核白名单与额度时使用。"""
    result = await session.execute(select(ProjectApiKey).where(ProjectApiKey.id == key_id))
    return result.scalar_one_or_none()


__all__ = ["create_key", "find_by_hash", "find_by_id", "list_keys", "revoke_key"]
