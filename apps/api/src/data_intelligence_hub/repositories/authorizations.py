"""``authorizations`` 表的读写。

凭证类查询必须带 ``workspace_id``。跨工作区的行查不到，也改不了。
仓储只做查询、插入与更新，并调用 ``flush``。
事务提交权留给服务层或脚本入口。本模块不调用 ``commit``。

金额使用 ``Decimal``。传入 float 会直接报错，不得静默转换。
PRD 5.4.2：``expires_at`` 过期的授权不得用于新 run。
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.authorization import Authorization

GATE_STATUSES: frozenset[str] = frozenset(
    {"pending", "pass", "fail", "blocked", "expired"}
)


def _as_decimal(value: Decimal | int | str, field_name: str) -> Decimal:
    """把金额转成 Decimal。float 与 bool 一律拒绝。"""
    if isinstance(value, (bool, float)):
        raise TypeError(f"{field_name} 必须用 Decimal，不得用 float")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, str)):
        return Decimal(value)
    raise TypeError(f"{field_name} 必须是 Decimal、int 或 str")


async def create_authorization(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    scope: Mapping[str, Any],
    max_cost_usd: Decimal | int | str,
    approver: uuid.UUID,
    expires_at: datetime,
    granted_at: datetime | None = None,
    plan_id: uuid.UUID | None = None,
    plan_version_id: uuid.UUID | None = None,
    gate_id: str = "G-Plan",
    gate_status: str = "pending",
    allowed_risk_levels: Sequence[str] | None = None,
    idempotency_key_hash: str | None = None,
) -> Authorization:
    """写入一行授权并 flush。

    ``expires_at`` 必须由调用方给出。授权没有永久有效这一说。
    ``scope`` 必须是字典。它不能是自由文本。
    """
    if gate_status not in GATE_STATUSES:
        raise ValueError(f"未知的 gate_status：{gate_status}")
    record = Authorization(
        workspace_id=workspace_id,
        project_id=project_id,
        plan_id=plan_id,
        plan_version_id=plan_version_id,
        gate_id=gate_id,
        gate_status=gate_status,
        scope=dict(scope),
        allowed_risk_levels=None if allowed_risk_levels is None else list(allowed_risk_levels),
        max_cost_usd=_as_decimal(max_cost_usd, "max_cost_usd"),
        approver=approver,
        granted_at=granted_at or datetime.now(UTC),
        expires_at=expires_at,
        idempotency_key_hash=idempotency_key_hash,
    )
    session.add(record)
    await session.flush()
    return record


async def get_authorization(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    authorization_id: uuid.UUID,
) -> Authorization | None:
    """按工作区取一行授权。跨工作区返回 None。"""
    result = await session.execute(
        select(Authorization).where(
            Authorization.id == authorization_id,
            Authorization.workspace_id == workspace_id,
        )
    )
    return result.scalar_one_or_none()


async def list_authorizations(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
) -> list[Authorization]:
    """按工作区列出授权。可再按项目过滤。结果按批准时间倒序。"""
    statement = select(Authorization).where(Authorization.workspace_id == workspace_id)
    if project_id is not None:
        statement = statement.where(Authorization.project_id == project_id)
    result = await session.execute(
        statement.order_by(Authorization.granted_at.desc(), Authorization.id)
    )
    return list(result.scalars().all())


async def revoke_authorization(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    authorization_id: uuid.UUID,
    revoked_at: datetime | None = None,
) -> Authorization | None:
    """撤销一行授权。未命中或跨工作区时返回 None。

    ``revoked_at`` 只写一次。重复撤销不改变首次时间。
    """
    record = await get_authorization(
        session,
        workspace_id=workspace_id,
        authorization_id=authorization_id,
    )
    if record is None:
        return None
    if record.revoked_at is None:
        record.revoked_at = revoked_at or datetime.now(UTC)
        await session.flush()
    return record


__all__ = [
    "GATE_STATUSES",
    "create_authorization",
    "get_authorization",
    "list_authorizations",
    "revoke_authorization",
]
