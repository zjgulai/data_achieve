"""run 证据等级结果表 ``run_evidence_grades``。

字段与 B2 的 ``RunEvidenceGrade`` dataclass 一一对应，另加 ``id`` 与 ``created_at``。
``entity_count`` / ``required_entity_count`` 服务 T4 的复合阈值。

契约冻结 v1 §1.1 把 ``run_id`` 定为逻辑主键。
表使用代理主键 ``id``，并对 ``run_id`` 加唯一约束。
一次 run 只写一行等级结果。重复写入会被唯一约束拒绝。

等级值来自契约 §2.5 的五个取值。不得写别的等级。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin


class RunEvidenceGradeRecord(UUIDPrimaryKeyMixin, Base):
    """一行代表一次 run 的证据等级计算结果。

    ``live_call`` 为 False 时等级是 L2。
    ``authorization_id`` 为空时等级最高是 L3。
    ``grade`` 只允许契约 §2.5 的五个值。
    """

    __tablename__ = "run_evidence_grades"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_run_evidence_grades_run_id"),
        CheckConstraint(
            "grade IN ('L0_unverified', 'L1_contract', 'L2_fixture_local', "
            "'L3_live_single', 'L4_authorized_live')",
            name="grade",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False)
    live_call: Mapped[bool] = mapped_column(Boolean, nullable=False)
    authorization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("authorizations.id")
    )
    sample_n: Mapped[int] = mapped_column(Integer, nullable=False)
    required_n: Mapped[int] = mapped_column(Integer, nullable=False)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    required_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    required_source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # T4 的复合阈值。其他模板为 0。
    entity_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    required_entity_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    grade: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
