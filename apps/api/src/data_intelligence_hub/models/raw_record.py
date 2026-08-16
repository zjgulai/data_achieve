from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from data_intelligence_hub.models.entity import EntitySnapshot
    from data_intelligence_hub.models.project import Project
    from data_intelligence_hub.models.source import Source
    from data_intelligence_hub.models.task import TaskRun
    from data_intelligence_hub.models.workspace import Workspace


class RawRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "raw_records"
    __table_args__ = (
        UniqueConstraint("source_id", "content_hash", name="uq_raw_records_source_content_hash"),
        UniqueConstraint(
            "workflow_step_run_id",
            "content_hash",
            name="uq_raw_records_workflow_step_content_hash",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id"],
            ["workflow_runs.workspace_id", "workflow_runs.project_id", "workflow_runs.id"],
            name="fk_raw_records_workflow_run_tenant",
        ),
        ForeignKeyConstraint(
            [
                "workspace_id",
                "project_id",
                "workflow_run_id",
                "workflow_step_run_id",
            ],
            [
                "step_runs.workspace_id",
                "step_runs.project_id",
                "step_runs.workflow_run_id",
                "step_runs.id",
            ],
            name="fk_raw_records_workflow_step_tenant",
        ),
        CheckConstraint(
            "(task_run_id IS NOT NULL AND source_id IS NOT NULL "
            "AND workflow_run_id IS NULL AND workflow_step_run_id IS NULL) "
            "OR (task_run_id IS NULL AND source_id IS NULL "
            "AND workflow_run_id IS NOT NULL AND workflow_step_run_id IS NOT NULL)",
            name="source_provenance",
        ),
        CheckConstraint(
            "(workflow_run_id IS NULL AND workflow_step_run_id IS NULL "
            "AND workflow_lineage_contract_version IS NULL) "
            "OR (workflow_run_id IS NOT NULL AND workflow_step_run_id IS NOT NULL "
            "AND workflow_lineage_contract_version IS NOT NULL "
            "AND workflow_lineage_contract_version = 'workflow_raw_record.v1')",
            name="workflow_lineage_contract",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id"))
    task_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("task_runs.id"))
    workflow_run_id: Mapped[uuid.UUID | None]
    workflow_step_run_id: Mapped[uuid.UUID | None]
    workflow_lineage_contract_version: Mapped[str | None] = mapped_column(String(100))
    record_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    content: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    screenshot_url: Mapped[str | None] = mapped_column(Text)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    workspace: Mapped[Workspace] = relationship(back_populates="raw_records")
    project: Mapped[Project] = relationship(back_populates="raw_records")
    source: Mapped[Source] = relationship(back_populates="raw_records")
    task_run: Mapped[TaskRun] = relationship(back_populates="raw_records")
    entity_snapshots: Mapped[list[EntitySnapshot]] = relationship(back_populates="raw_record")
