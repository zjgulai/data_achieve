"""run 成本账本表 ``run_ledger_entries``。

契约冻结 v1 §2.7.1 锁定八列，不得增删：
``id``、``run_id``、``step_id``、``entry_kind``、``amount_usd``、
``balance_after_usd``、``idempotency_key``、``created_at``。

上游的 provider、数量、单价等调用明细不落在这张表。
它们在 ``run_steps`` 与 ``task_runs`` 上，通过 ``step_id`` 关联。
理由：账本是金额流水，不是调用明细。两表混写会造成重复计费口径。

账本只追加。修正写负数 ``release`` 行。
金额必须用 ``Numeric(12, 6)``。不得用 float。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin

# 契约 §2.7.1 的六个取值。顺序固定。
ENTRY_KINDS: tuple[str, ...] = (
    "estimate",
    "reserve",
    "accrued",
    "settle",
    "release",
    "block",
)


class RunLedgerEntry(UUIDPrimaryKeyMixin, Base):
    """一行代表账本中的一次金额变动。

    ``step_id`` 可为空。运行级估算与运行级结算没有步骤。
    ``idempotency_key`` 唯一。估算、预留、结算与释放各用独立键。
    ``balance_after_usd`` 保存该行之后的余额快照。
    """

    __tablename__ = "run_ledger_entries"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_run_ledger_entries_idempotency_key",
        ),
        CheckConstraint(
            "entry_kind IN ('estimate', 'reserve', 'accrued', 'settle', 'release', 'block')",
            name="entry_kind",
        ),
        Index("ix_run_ledger_entries_run_id", "run_id"),
    )

    # 关联 runs.id。runs 表由 B3-01 的迁移 202610200049 创建。
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False)
    # 关联 run_steps.id。运行级记录没有步骤。
    step_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run_steps.id"))
    entry_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    balance_after_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
