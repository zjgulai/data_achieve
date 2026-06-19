from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
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
    export_jobs: Mapped[list[DatasetExportJob]] = relationship(back_populates="dataset")


class CleaningPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cleaning_plans"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "name",
            "version_number",
            name="uq_cleaning_plans_workspace_name_version",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    target: Mapped[str] = mapped_column(String(50), nullable=False)
    selected_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    source_task_run_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    rules: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    cleaning_script: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    dry_run_preview: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)

    workspace: Mapped[Workspace] = relationship()
    project: Mapped[Project] = relationship()
    created_by_user: Mapped[User] = relationship()
    dataset_versions: Mapped[list[DatasetVersion]] = relationship(back_populates="cleaning_plan")


class DatasetVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (
        UniqueConstraint("dataset_id", "version_number", name="uq_dataset_versions_number"),
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    cleaning_plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cleaning_plans.id"))
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
    cleaning_plan: Mapped[CleaningPlan | None] = relationship(back_populates="dataset_versions")
    drift_events: Mapped[list[DatasetDriftEvent]] = relationship(back_populates="dataset_version")
    export_jobs: Mapped[list[DatasetExportJob]] = relationship(back_populates="dataset_version")


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


class DatasetExportJob(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "dataset_export_jobs"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), nullable=False)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dataset_versions.id"),
        nullable=False,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    export_format: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    artifact_path: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    audit_events: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    workspace: Mapped[Workspace] = relationship()
    project: Mapped[Project] = relationship()
    dataset: Mapped[Dataset] = relationship(back_populates="export_jobs")
    dataset_version: Mapped[DatasetVersion] = relationship(back_populates="export_jobs")
    created_by_user: Mapped[User] = relationship()
