from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
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
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False)
    task_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_runs.id"), nullable=False)
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
