from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorkflowTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Project-scoped reusable scenario definition, not an execution grant."""

    __tablename__ = "workflow_templates"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_templates_tenant_id",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "template_key",
            name="uq_workflow_templates_tenant_key",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_workflow_templates_project_tenant",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "id", "current_revision_id"],
            [
                "workflow_template_revisions.workspace_id",
                "workflow_template_revisions.project_id",
                "workflow_template_revisions.workflow_template_id",
                "workflow_template_revisions.id",
            ],
            name="fk_workflow_templates_current_revision_tenant",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_workflow_templates_created_by_user",
        ),
        CheckConstraint(
            "status IN ('draft', 'previewed', 'approved', 'active', 'paused', 'archived')",
            name="status",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    template_key: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    current_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
    )
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)


class WorkflowTemplateRevision(UUIDPrimaryKeyMixin, Base):
    """Immutable, tenant-scoped PlanningInput snapshot for a template."""

    __tablename__ = "workflow_template_revisions"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_template_revisions_tenant_id",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "workflow_template_id",
            "id",
            name="uq_workflow_template_revisions_template_tenant_id",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "workflow_template_id",
            "revision_number",
            name="uq_workflow_template_revisions_tenant_number",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_template_id"],
            [
                "workflow_templates.workspace_id",
                "workflow_templates.project_id",
                "workflow_templates.id",
            ],
            name="fk_workflow_template_revisions_template_tenant",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_workflow_template_revisions_created_by_user",
        ),
        CheckConstraint(
            "revision_number >= 1",
            name="revision_number",
        ),
        CheckConstraint(
            "definition_fingerprint LIKE 'sha256:%'",
            name="definition_fingerprint",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    definition: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    definition_fingerprint: Mapped[str] = mapped_column(String(71), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class WorkflowTemplateMutationRequest(UUIDPrimaryKeyMixin, Base):
    """Idempotency ledger for Template header/revision mutations."""

    __tablename__ = "workflow_template_mutation_requests"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "created_by_user_id",
            "idempotency_scope",
            "idempotency_key_hash",
            name="uq_workflow_template_mutation_requests_idempotency",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_template_id"],
            [
                "workflow_templates.workspace_id",
                "workflow_templates.project_id",
                "workflow_templates.id",
            ],
            name="fk_workflow_template_mutation_requests_template_tenant",
        ),
        ForeignKeyConstraint(
            [
                "workspace_id",
                "project_id",
                "workflow_template_id",
                "workflow_template_revision_id",
            ],
            [
                "workflow_template_revisions.workspace_id",
                "workflow_template_revisions.project_id",
                "workflow_template_revisions.workflow_template_id",
                "workflow_template_revisions.id",
            ],
            name="fk_workflow_template_mutation_requests_revision_tenant",
        ),
        ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_workflow_template_mutation_requests_created_by_user",
        ),
        CheckConstraint(
            "operation IN ('create', 'metadata', 'revision')",
            name="operation",
        ),
        CheckConstraint(
            "outcome IN ('created', 'updated')",
            name="outcome",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    idempotency_scope: Mapped[str] = mapped_column(String(500), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    workflow_template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    workflow_template_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
    )
    operation: Mapped[str] = mapped_column(String(30), nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


__all__ = [
    "WorkflowTemplate",
    "WorkflowTemplateMutationRequest",
    "WorkflowTemplateRevision",
]
