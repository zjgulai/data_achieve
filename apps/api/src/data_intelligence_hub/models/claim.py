"""主张表 ``claims`` 与主张证据关联表 ``claim_evidence``。

契约冻结 v1 §1.1 锁定表名与主键。
``claims`` 的主键是 ``id``。
``claim_evidence`` 的主键只有 ``claim_id`` 与 ``evidence_id``。
``role`` 是普通列，不进主键。

``ClaimState`` 只有契约 §2.6 的五个取值。
显示别名（Verified、Supported 等）只用于界面文案，不得写进合同。
``EvidenceRole`` 只有 PRD 5.4.1 的四个取值。

反证保证：

- 每条 claim 必须至少有一条 ``role='counter'`` 或 ``role='gap'`` 的关联。
- 若一条 claim 只有 ``gap`` 或 ``context``，状态只能是 ``hypothesis`` 或
  ``blocked``。PRD 5.4.1 如此要求。
- 这两条规则由服务层 ``create_claim_with_evidence`` 保证。
- 数据库约束无法表达「至少一行关联」。模型层只写注释，不假装能拦住。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin


class ClaimState(StrEnum):
    """``claims.state`` 的五个取值。

    取值来自契约冻结 v1 §2.6。
    ``verified`` 与 ``supported`` 是显示别名，不得写进枚举。
    """

    CONFIRMED = "confirmed"
    DIRECTIONAL = "directional"
    HYPOTHESIS = "hypothesis"
    EVIDENCE_GAP = "evidence_gap"
    BLOCKED = "blocked"


class EvidenceRole(StrEnum):
    """``claim_evidence.role`` 的四个取值。

    ``counter`` 与 ``gap`` 是反证。服务层要求每条 claim 至少有一条。
    """

    SUPPORT = "support"
    COUNTER = "counter"
    CONTEXT = "context"
    GAP = "gap"


_CLAIM_STATE_CHECK = (
    "state IN ('confirmed', 'directional', 'hypothesis', 'evidence_gap', 'blocked')"
)
_CLAIM_GRADE_CHECK = (
    "evidence_grade IS NULL OR evidence_grade IN ('L0_unverified', 'L1_contract', "
    "'L2_fixture_local', 'L3_live_single', 'L4_authorized_live')"
)
_CLAIM_CONFIDENCE_CHECK = "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)"
_ROLE_CHECK = "role IN ('support', 'counter', 'context', 'gap')"


class Claim(UUIDPrimaryKeyMixin, Base):
    """一行代表一条可被反驳的主张。

    命名对照。表内 ``state`` 对应 PRD 5.4.1 与报告合同的 ``claim_status``。
    表内 ``claim_text`` 对应同一来源的 ``text``。表内命名保持不变。
    读合同字段时按这份对照映射，不要把 ``claim_status`` 写进表。

    ``run_id`` 可空。它指向提供输入的那次运行。
    ``state`` 默认 ``hypothesis``。PRD 5.4.1 的回填规则如此。
    ``evidence_grade`` 可空。它取契约 §2.5 的五个等级。
    ``confidence`` 可空。取值范围是 0 到 1。

    报告合同字段。以下五列全部可空，存量行保持 None：

    - ``owner``：责任人。
    - ``scope_market``：适用市场。
    - ``scope_window_days``：适用时间窗，单位是天。
    - ``scope_sample_n``：适用样本量。
    - ``counterevidence_text``：反证说明。合同要求非空字符串。

    CHECK 约束名与迁移 052 逐字一致。``conv`` 阻止命名约定再加前缀。
    """

    __tablename__ = "claims"
    __table_args__ = (
        CheckConstraint(_CLAIM_STATE_CHECK, name=conv("ck_claims_state")),
        CheckConstraint(_CLAIM_GRADE_CHECK, name=conv("ck_claims_evidence_grade")),
        CheckConstraint(
            _CLAIM_CONFIDENCE_CHECK,
            name=conv("ck_claims_confidence_range"),
        ),
        Index("ix_claims_workspace_project", "workspace_id", "project_id"),
        Index("ix_claims_run_id", "run_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id"))
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(
        String(20),
        default=ClaimState.HYPOTHESIS.value,
        nullable=False,
    )
    evidence_grade: Mapped[str | None] = mapped_column(String(30))
    confidence: Mapped[float | None] = mapped_column(Float)
    owner: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    scope_market: Mapped[str | None] = mapped_column(String(40))
    scope_window_days: Mapped[int | None] = mapped_column(Integer)
    scope_sample_n: Mapped[int | None] = mapped_column(Integer)
    counterevidence_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ClaimEvidence(Base):
    """一行代表 claim 与 evidence 的一条关联。

    主键只有 ``claim_id`` 与 ``evidence_id`` 两列。
    ``role`` 是普通列。同一条证据对同一条 claim 只保留一个角色。
    服务层在创建 claim 时保证至少一条 ``counter`` 或 ``gap`` 关联。
    """

    __tablename__ = "claim_evidence"
    __table_args__ = (
        CheckConstraint(_ROLE_CHECK, name=conv("ck_claim_evidence_role")),
        Index("ix_claim_evidence_evidence_id", "evidence_id"),
    )

    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claims.id"),
        primary_key=True,
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidences.id"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


__all__ = ["Claim", "ClaimEvidence", "ClaimState", "EvidenceRole"]
