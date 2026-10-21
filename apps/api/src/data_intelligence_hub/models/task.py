from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data_intelligence_hub.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from data_intelligence_hub.models.project import Project
    from data_intelligence_hub.models.raw_record import RawRecord
    from data_intelligence_hub.models.source import Source
    from data_intelligence_hub.models.workspace import Workspace


class CollectionTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "collection_tasks"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id"),
        nullable=False,
        unique=True,
    )
    collector_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    schedule_cron: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    workspace: Mapped[Workspace] = relationship(back_populates="collection_tasks")
    project: Mapped[Project] = relationship(back_populates="collection_tasks")
    source: Mapped[Source] = relationship(back_populates="collection_task")
    runs: Mapped[list[TaskRun]] = relationship(back_populates="task")


class TaskRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "task_runs"
    __table_args__ = (
        # 同一任务下，同一个幂等键只能有一个运行。
        # 幂等键可为空：手动触发且未带 key 的运行不受约束，
        # Postgres 与 SQLite 都允许多行 NULL，符合预期。
        # 应用层先查后插仍是主路径；本索引兜住并发下的重复插入。
        Index(
            "uq_task_runs_task_idempotency",
            "task_id",
            "idempotency_key_hash",
            unique=True,
        ),
        # 按 run 反查该运行的采集调用记录。
        Index("ix_task_runs_run_id", "run_id"),
    )

    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collection_tasks.id"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    entities_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    error_traceback: Mapped[str | None] = mapped_column(Text)
    logs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # 幂等键摘要。空值表示该运行没有携带幂等键。
    # 历史上该值只存在 logs 里，列是后加的；
    # 读取时先看列，为空再回退解析 logs，保留一个发布周期。
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64))

    # 以下列由 B3-02 按契约冻结 v1 §1.3 补齐。
    # 全部可空，存量行读取为 None。
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    # 关联 runs.id。runs 表由 B3-01 的迁移 202610200049 创建。
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id"))
    step_index: Mapped[int | None] = mapped_column(Integer)
    unit: Mapped[str | None] = mapped_column(String(20))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    total_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    # 契约规定字段名不加 _usd 后缀。PRD R6 直接读这个列名。
    remaining_budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    provider: Mapped[str | None] = mapped_column(String(40))
    provider_run_id: Mapped[str | None] = mapped_column(String(120))
    endpoint_type: Mapped[str | None] = mapped_column(String(80))
    evidence_grade: Mapped[str | None] = mapped_column(String(30))
    schema_version: Mapped[str | None] = mapped_column(String(20))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    task: Mapped[CollectionTask] = relationship(back_populates="runs")
    raw_records: Mapped[list[RawRecord]] = relationship(back_populates="task_run")
