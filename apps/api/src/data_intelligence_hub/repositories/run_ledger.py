"""``run_ledger_entries`` 表的读写。

账本只追加。本模块不更新行，也不删除行。
仓储只调用 ``flush``。本模块不调用 ``commit``。

金额使用 ``Numeric(12, 6)`` 与 ``Decimal``。
传入 float 会直接报错，不得静默转换。
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.run_ledger import ENTRY_KINDS, RunLedgerEntry


def _as_decimal(value: Decimal | int | str, field_name: str) -> Decimal:
    """把金额转成 Decimal。float 与 bool 一律拒绝。"""
    if isinstance(value, (bool, float)):
        raise TypeError(f"{field_name} 必须用 Decimal，不得用 float")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, str)):
        return Decimal(value)
    raise TypeError(f"{field_name} 必须是 Decimal、int 或 str")


def _decimal_from_sql(value: object) -> Decimal:
    """把 SQL 聚合结果转成 Decimal。SQLite 可能返回 float。"""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


async def add_entry(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    entry_kind: str,
    amount_usd: Decimal | int | str,
    balance_after_usd: Decimal | int | str,
    idempotency_key: str,
    step_id: uuid.UUID | None = None,
) -> RunLedgerEntry:
    """追加一行账本并 flush。

    ``entry_kind`` 必须是契约 §2.7.1 的六个取值之一。
    ``idempotency_key`` 不能为空。唯一约束挡住重复写入。
    """
    if entry_kind not in ENTRY_KINDS:
        raise ValueError(f"未知的 entry_kind：{entry_kind}")
    if not idempotency_key:
        raise ValueError("idempotency_key 不能为空")
    record = RunLedgerEntry(
        run_id=run_id,
        step_id=step_id,
        entry_kind=entry_kind,
        amount_usd=_as_decimal(amount_usd, "amount_usd"),
        balance_after_usd=_as_decimal(balance_after_usd, "balance_after_usd"),
        idempotency_key=idempotency_key,
    )
    session.add(record)
    await session.flush()
    return record


async def list_entries(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
) -> list[RunLedgerEntry]:
    """按 run 列出账本行。结果按创建时间正序。"""
    result = await session.execute(
        select(RunLedgerEntry)
        .where(RunLedgerEntry.run_id == run_id)
        .order_by(RunLedgerEntry.created_at, RunLedgerEntry.id)
    )
    return list(result.scalars().all())


async def get_by_idempotency_key(
    session: AsyncSession,
    *,
    idempotency_key: str,
) -> RunLedgerEntry | None:
    """按幂等键取一行。未命中返回 None。"""
    result = await session.execute(
        select(RunLedgerEntry).where(RunLedgerEntry.idempotency_key == idempotency_key)
    )
    return result.scalar_one_or_none()


async def sum_amounts(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    entry_kinds: Sequence[str],
) -> Decimal:
    """按 run 与 entry_kind 汇总金额。无行时返回 Decimal("0")。"""
    unknown = set(entry_kinds) - set(ENTRY_KINDS)
    if unknown:
        raise ValueError(f"未知的 entry_kind：{sorted(unknown)}")
    result = await session.execute(
        select(func.coalesce(func.sum(RunLedgerEntry.amount_usd), 0)).where(
            RunLedgerEntry.run_id == run_id,
            RunLedgerEntry.entry_kind.in_(tuple(entry_kinds)),
        )
    )
    return _decimal_from_sql(result.scalar_one())


__all__ = [
    "add_entry",
    "get_by_idempotency_key",
    "list_entries",
    "sum_amounts",
]
