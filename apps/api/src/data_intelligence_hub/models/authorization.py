"""人工授权表 ``authorizations``。

契约冻结 v1 §1.1 锁定表名。门禁决定也写这张表，不另建门禁表（§2.7）。
PRD 5.4.2 的字段映射如下：
``id``、``approver``、``scope``、``max_cost_usd``、``granted_at``、``expires_at``。

补充列：
``workspace_id`` 与 ``project_id`` 用于租户隔离。
``gate_status`` 保存门禁状态。取值来自契约 §2.7。
``revoked_at`` 支持撤销。撤销后授权不得用于新 run。
``plan_id`` 与 ``plan_version_id`` 关联计划与计划版本。
``idempotency_key_hash`` 支持幂等签发。

金额必须用 ``Numeric(12, 6)``。不得用 float。
``expires_at`` 过期后授权回落到 L3。判断函数是 B2 的 ``authorization_is_usable``。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin


class Authorization(UUIDPrimaryKeyMixin, Base):
    """一行代表一次人工批准。

    ``scope`` 保存模板、市场与时间窗。它是 JSON，不是自由文本。
    ``gate_status`` 取 ``pending`` / ``pass`` / ``fail`` / ``blocked`` / ``expired``。
    ``expires_at`` 为空不允许。授权必须有过期时间。
    """

    __tablename__ = "authorizations"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "approver",
            "idempotency_key_hash",
            name="uq_authorizations_workspace_approver_idempotency",
        ),
        CheckConstraint(
            "gate_status IN ('pending', 'pass', 'fail', 'blocked', 'expired')",
            name="gate_status",
        ),
        CheckConstraint("max_cost_usd >= 0", name="max_cost_usd_non_negative"),
        Index(
            "ix_authorizations_workspace_project",
            "workspace_id",
            "project_id",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workflow_plans.id"),
    )
    plan_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workflow_versions.id"),
    )
    # 门禁 ID 来自契约 §2.8：G-Plan / G-Cost / G-Evidence / G-Claim / G-Publish。
    gate_id: Mapped[str] = mapped_column(String(20), default="G-Plan", nullable=False)
    # 门禁状态来自契约 §2.7。不另建门禁表。
    gate_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    # 批准范围：模板 + 市场 + 时间窗，可带工具范围。
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    allowed_risk_levels: Mapped[list[str] | None] = mapped_column(JSON)
    # 批准的成本上限。Decimal 是唯一允许的金额类型。
    max_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    # 批准人。PRD 5.4.2 的字段名是 approver。
    approver: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    # 授权必须有过期时间。过期后不得用于新 run。
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 签发幂等。空值表示该授权没有携带幂等键。
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64))
