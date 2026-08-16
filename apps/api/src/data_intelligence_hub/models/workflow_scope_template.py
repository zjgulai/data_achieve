from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin


class MonitoringScopeTemplate(UUIDPrimaryKeyMixin, Base):
    """Editable Scope copy that keeps canonical MonitoringScope rows immutable."""

    __tablename__ = "monitoring_scope_templates"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_monitoring_scope_templates_tenant_id",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_monitoring_scope_templates_project_tenant",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "source_scope_id"],
            [
                "monitoring_scopes.workspace_id",
                "monitoring_scopes.project_id",
                "monitoring_scopes.id",
            ],
            name="fk_monitoring_scope_templates_source_scope_tenant",
        ),
        ForeignKeyConstraint(
            [
                "workspace_id",
                "project_id",
                "source_workflow_plan_id",
                "source_workflow_version_id",
            ],
            [
                "workflow_versions.workspace_id",
                "workflow_versions.project_id",
                "workflow_versions.workflow_plan_id",
                "workflow_versions.id",
            ],
            name="fk_monitoring_scope_templates_source_version_tenant",
        ),
        ForeignKeyConstraint(
            [
                "workspace_id",
                "project_id",
                "source_workflow_version_id",
                "source_scope_id",
            ],
            [
                "workflow_version_scopes.workspace_id",
                "workflow_version_scopes.project_id",
                "workflow_version_scopes.workflow_version_id",
                "workflow_version_scopes.monitoring_scope_id",
            ],
            name="fk_monitoring_scope_templates_source_association_tenant",
        ),
        CheckConstraint(
            "scope_type IN ('brand', 'category', 'competitor', 'topic', 'campaign')",
            name="scope_type_valid",
        ),
        CheckConstraint(
            "match_mode IN ('exact', 'phrase', 'semantic', 'hybrid')",
            name="match_mode_valid",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    source_scope_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_workflow_plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    source_workflow_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    scope_key: Mapped[str] = mapped_column(String(71), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(30), nullable=False)
    canonical_term: Mapped[str | None] = mapped_column(Text)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    include_terms: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    exclude_terms: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    official_accounts: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    seed_urls: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    effective_languages: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    effective_regions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    effective_platforms: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    match_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


__all__ = ["MonitoringScopeTemplate"]
