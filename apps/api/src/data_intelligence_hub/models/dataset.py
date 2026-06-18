from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data_intelligence_hub.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from data_intelligence_hub.models.project import Project
    from data_intelligence_hub.models.user import User
    from data_intelligence_hub.models.workspace import Workspace


class Dataset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "datasets"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_datasets_workspace_name"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    dataset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    workspace: Mapped[Workspace] = relationship(back_populates="datasets")
    project: Mapped[Project] = relationship(back_populates="datasets")
    versions: Mapped[list[DatasetVersion]] = relationship(back_populates="dataset")
    drift_events: Mapped[list[DatasetDriftEvent]] = relationship(back_populates="dataset")


class DatasetVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (
        UniqueConstraint("dataset_id", "version_number", name="uq_dataset_versions_number"),
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_task_run_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    selected_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    cleaning_script: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    rows: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    export_preview: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    average_completeness_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="saved", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    dataset: Mapped[Dataset] = relationship(back_populates="versions")
    workspace: Mapped[Workspace] = relationship()
    project: Mapped[Project] = relationship()
    created_by_user: Mapped[User] = relationship()
    drift_events: Mapped[list[DatasetDriftEvent]] = relationship(back_populates="dataset_version")


class DatasetDriftEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "dataset_drift_events"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), nullable=False)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dataset_versions.id"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    thresholds: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    audit_events: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    workspace: Mapped[Workspace] = relationship()
    project: Mapped[Project] = relationship()
    dataset: Mapped[Dataset] = relationship(back_populates="drift_events")
    dataset_version: Mapped[DatasetVersion] = relationship(back_populates="drift_events")
