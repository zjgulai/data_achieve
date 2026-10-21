"""执行运行与运行步骤的持久化模型。

``runs`` 是一次执行运行。它不存七槽位任务单。
``run_steps`` 是一次执行中的一个步骤。它不存计划正文。
三组状态枚举在模型层定义。测试可以直接断言取值。
契约冻结 v1 §2.1-2.3 是唯一事实源。

``runs.status`` 不得出现 ``degraded`` 与 ``held``。
``runs.outcome`` 与 ``run_steps.outcome`` 不得出现 ``partial``。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin


class RunStatus(StrEnum):
    """``runs.status`` 的五个取值。

    ``degraded`` 属于 health_status。``held`` 属于 workflow_plans。
    """

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunStepStatus(StrEnum):
    """``run_steps.status`` 的七个取值。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    EMPTY = "empty"
    CONFIG_GATED = "config_gated"
    FAILED = "failed"
    SKIPPED = "skipped"


class RunOutcome(StrEnum):
    """``runs.outcome`` 与 ``run_steps.outcome`` 的四个取值。

    部分成功用 status=success 加 outcome=success 加 records_count>0 表达。
    """

    SUCCESS = "success"
    EMPTY = "empty"
    CONFIG_GATED = "config_gated"
    FAILED = "failed"


_RUN_STATUS_CHECK = "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')"
_STEP_STATUS_CHECK = (
    "status IN ('pending', 'running', 'success', 'empty', 'config_gated', 'failed', 'skipped')"
)
_OUTCOME_CHECK = "outcome IS NULL OR outcome IN ('success', 'empty', 'config_gated', 'failed')"


class Run(UUIDPrimaryKeyMixin, Base):
    """一行代表一次执行运行。

    ``task_id`` 可空。它指向单次采集任务。
    ``workflow_version_id`` 可空。它指向计划版本。
    ``lease_expires_at`` 供持久队列扫描与租约续期使用。
    """

    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint(_RUN_STATUS_CHECK, name="status"),
        CheckConstraint(_OUTCOME_CHECK, name="outcome"),
        # 列表页按工作区与项目过滤。
        Index("ix_runs_workspace_project", "workspace_id", "project_id"),
        # 持久队列按状态与租约到期时间扫描。
        Index("ix_runs_status_lease", "status", "lease_expires_at"),
        # 同一工作区下，同一个幂等键只能有一行。
        # 幂等键可为空：不带 key 的运行不受约束。
        Index(
            "uq_runs_workspace_idempotency",
            "workspace_id",
            "idempotency_key_hash",
            unique=True,
            postgresql_where=text("idempotency_key_hash IS NOT NULL"),
            sqlite_where=text("idempotency_key_hash IS NOT NULL"),
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("collection_tasks.id"))
    workflow_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_versions.id")
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=RunStatus.QUEUED.value,
        nullable=False,
    )
    outcome: Mapped[str | None] = mapped_column(String(20))
    # 执行模式：live 表示真实调用，fixture 表示夹具回放。
    execution_mode: Mapped[str] = mapped_column(
        String(30),
        default="live",
        nullable=False,
    )
    # 触发来源：manual、schedule 或 api。
    trigger: Mapped[str] = mapped_column(String(30), default="manual", nullable=False)
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64))
    evidence_grade: Mapped[str | None] = mapped_column(String(30))
    records_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 契约 §4.1：total_cost_usd 必须同时出现在 run_steps、task_runs 与 runs。
    total_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class RunStep(UUIDPrimaryKeyMixin, Base):
    """一行代表运行中的一个步骤。

    同一个运行内，``step_index`` 唯一。
    ``task_run_id`` 可空。它指向该步骤对应的单次采集记录。
    """

    __tablename__ = "run_steps"
    __table_args__ = (
        UniqueConstraint("run_id", "step_index", name="uq_run_steps_run_step_index"),
        CheckConstraint(_STEP_STATUS_CHECK, name="status"),
        CheckConstraint(_OUTCOME_CHECK, name="outcome"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    endpoint_type: Mapped[str] = mapped_column(String(80), nullable=False)
    collector_type: Mapped[str] = mapped_column(String(50), nullable=False)
    task_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("task_runs.id"))
    status: Mapped[str] = mapped_column(
        String(20),
        default=RunStepStatus.PENDING.value,
        nullable=False,
    )
    outcome: Mapped[str | None] = mapped_column(String(20))
    records_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 契约 §4.1 的成本三字段中，run_steps 必须有 unit_price 与 total_cost_usd。
    # unit 与 quantity 是计量口径，与单价乘出总价。
    # 金额一律 Numeric(12, 6)，不得用 float。
    unit: Mapped[str | None] = mapped_column(String(20))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    total_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = [
    "Run",
    "RunOutcome",
    "RunStatus",
    "RunStep",
    "RunStepStatus",
]
