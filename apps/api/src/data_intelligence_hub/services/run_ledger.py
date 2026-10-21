"""run 成本账本的写入与汇总。

金额全程使用 ``Decimal``。任何 float 输入都会报错。
本模块只调用 ``flush``。它不调用 ``commit``。

``sum_cost`` 的语义是「这个 run 的实际已结算成本」。
它累加 ``settle`` 与 ``release`` 行。修正行用负数 ``release`` 表达。
``estimate``、``reserve``、``accrued``、``block`` 不是实际成本，不参与汇总。
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.run_ledger import ENTRY_KINDS, RunLedgerEntry
from data_intelligence_hub.repositories.run_ledger import add_entry, sum_amounts

# 计入实际成本的账本行。release 用负数修正 settle。
COST_ENTRY_KINDS: tuple[str, ...] = ("settle", "release")


def _as_decimal(value: Decimal | int | str, field_name: str) -> Decimal:
    """把金额转成 Decimal。float 与 bool 一律拒绝。"""
    if isinstance(value, (bool, float)):
        raise TypeError(f"{field_name} 必须用 Decimal，不得用 float")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, str)):
        return Decimal(value)
    raise TypeError(f"{field_name} 必须是 Decimal、int 或 str")


async def record_entry(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    entry_kind: str,
    amount_usd: Decimal | int | str,
    balance_after_usd: Decimal | int | str,
    idempotency_key: str,
    step_id: uuid.UUID | None = None,
) -> RunLedgerEntry:
    """写入一行账本并 flush。

    ``entry_kind`` 必须是契约 §2.7.1 的六个取值之一。
    金额必须是 Decimal。float 会被拒绝。
    """
    if entry_kind not in ENTRY_KINDS:
        raise ValueError(f"未知的 entry_kind：{entry_kind}")
    return await add_entry(
        session,
        run_id=run_id,
        step_id=step_id,
        entry_kind=entry_kind,
        amount_usd=_as_decimal(amount_usd, "amount_usd"),
        balance_after_usd=_as_decimal(balance_after_usd, "balance_after_usd"),
        idempotency_key=idempotency_key,
    )


async def sum_cost(session: AsyncSession, run_id: uuid.UUID) -> Decimal:
    """汇总一个 run 的实际已结算成本。

    结果类型是 Decimal。没有行时返回 ``Decimal("0")``。
    """
    return await sum_amounts(
        session,
        run_id=run_id,
        entry_kinds=COST_ENTRY_KINDS,
    )


async def remaining_budget(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    max_cost_usd: Decimal | int | str,
) -> Decimal:
    """计算剩余额度。公式是授权上限减已结算成本。

    结果可以为负。负数表示已经超出授权上限。
    本函数不回落到 0，调用方必须处理超额。
    """
    limit = _as_decimal(max_cost_usd, "max_cost_usd")
    return limit - await sum_cost(session, run_id)


__all__ = ["COST_ENTRY_KINDS", "record_entry", "remaining_budget", "sum_cost"]
