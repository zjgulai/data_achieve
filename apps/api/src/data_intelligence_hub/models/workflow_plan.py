from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
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


class _CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class WorkflowPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_plans"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_plans_tenant_id",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_workflow_plans_project_tenant",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "id", "current_version_id"],
            [
                "workflow_versions.workspace_id",
                "workflow_versions.project_id",
                "workflow_versions.workflow_plan_id",
                "workflow_versions.id",
            ],
            name="fk_workflow_plans_current_version_owner",
            use_alter=True,
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
            name="fk_workflow_plans_source_version_owner",
            use_alter=True,
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
            name="fk_workflow_plans_template_revision_tenant",
            use_alter=True,
        ),
        CheckConstraint(
            "status IN ('draft', 'previewed', 'approved', 'active', 'paused', 'archived')",
            name="status",
        ),
        CheckConstraint(
            "(source_workflow_plan_id IS NULL AND source_workflow_version_id IS NULL) "
            "OR (source_workflow_plan_id IS NOT NULL AND source_workflow_version_id IS NOT NULL)",
            name="source_version_pair",
        ),
        CheckConstraint(
            "(workflow_template_id IS NULL AND workflow_template_revision_id IS NULL) "
            "OR (workflow_template_id IS NOT NULL AND workflow_template_revision_id IS NOT NULL)",
            name="template_revision_pair",
        ),
        CheckConstraint(
            "flow_mode IN ('periodic_monitoring', 'batch_research')",
            name="flow_mode_valid",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    flow_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="previewed", nullable=False)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    source_workflow_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
    )
    source_workflow_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
    )
    workflow_template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
    )
    workflow_template_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
    )


class WorkflowVersion(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "workflow_versions"
    __table_args__ = (
        UniqueConstraint(
            "workflow_plan_id",
            "version_number",
            name="uq_workflow_versions_plan_number",
        ),
        UniqueConstraint(
            "workflow_plan_id",
            "id",
            name="uq_workflow_versions_plan_id",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_versions_tenant_id",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "workflow_plan_id",
            "id",
            name="uq_workflow_versions_tenant_plan_id",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_plan_id"],
            [
                "workflow_plans.workspace_id",
                "workflow_plans.project_id",
                "workflow_plans.id",
            ],
            name="fk_workflow_versions_plan_tenant",
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
            name="fk_workflow_versions_template_revision_tenant",
        ),
        CheckConstraint(
            "version_number >= 1",
            name="version_number_positive",
        ),
        CheckConstraint(
            "planning_status IN ('resolved', 'partially_resolved', 'held')",
            name="planning_status_valid",
        ),
        CheckConstraint(
            "(workflow_template_id IS NULL AND workflow_template_revision_id IS NULL) "
            "OR (workflow_template_id IS NOT NULL AND workflow_template_revision_id IS NOT NULL)",
            name="template_revision_pair",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_plan_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
    )
    workflow_template_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    planning_status: Mapped[str] = mapped_column(String(30), nullable=False)
    planner_contract_version: Mapped[str] = mapped_column(String(100), nullable=False)
    catalog_snapshot_id: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    mode_template_version: Mapped[str] = mapped_column(String(100), nullable=False)
    query_versions: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    fingerprint_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    normalized_input: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    plan_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    preview_fingerprint: Mapped[str] = mapped_column(String(71), nullable=False)


class MonitoringScope(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "monitoring_scopes"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "scope_key",
            name="uq_monitoring_scopes_project_key",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_monitoring_scopes_tenant_id",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_monitoring_scopes_project_tenant",
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


class WorkflowVersionScope(_CreatedAtMixin, Base):
    __tablename__ = "workflow_version_scopes"
    __table_args__ = (
        UniqueConstraint(
            "workflow_version_id",
            "ordinal",
            name="uq_workflow_version_scopes_version_ordinal",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "workflow_version_id",
            "monitoring_scope_id",
            name="uq_workflow_version_scopes_tenant_pair",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_version_id"],
            [
                "workflow_versions.workspace_id",
                "workflow_versions.project_id",
                "workflow_versions.id",
            ],
            name="fk_workflow_version_scopes_version_tenant",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "monitoring_scope_id"],
            [
                "monitoring_scopes.workspace_id",
                "monitoring_scopes.project_id",
                "monitoring_scopes.id",
            ],
            name="fk_workflow_version_scopes_scope_tenant",
        ),
        CheckConstraint("ordinal >= 0", name="ordinal_non_negative"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    monitoring_scope_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class QueryTerm(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "query_terms"
    __table_args__ = (
        UniqueConstraint(
            "workflow_version_id",
            "ordinal",
            name="uq_query_terms_version_ordinal",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_version_id", "matched_scope_id"],
            [
                "workflow_version_scopes.workspace_id",
                "workflow_version_scopes.project_id",
                "workflow_version_scopes.workflow_version_id",
                "workflow_version_scopes.monitoring_scope_id",
            ],
            name="fk_query_terms_version_scope_tenant",
        ),
        CheckConstraint("ordinal >= 0", name="ordinal_non_negative"),
        CheckConstraint(
            "status IN ('active', 'candidate', 'rejected')",
            name="status_valid",
        ),
        CheckConstraint(
            "origin IN ('canonical', 'alias', 'include', 'official_account', "
            "'seed_url', 'fixture_candidate_expansion')",
            name="origin_valid",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    term: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_term: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    conflict_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    matched_scope_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


class WorkflowPlanSaveRequest(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "workflow_plan_save_requests"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "created_by_user_id",
            "idempotency_scope",
            "idempotency_key_hash",
            name="uq_workflow_plan_save_requests_idempotency",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_plan_id"],
            [
                "workflow_plans.workspace_id",
                "workflow_plans.project_id",
                "workflow_plans.id",
            ],
            name="fk_workflow_plan_save_requests_plan_tenant",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_plan_id", "workflow_version_id"],
            [
                "workflow_versions.workspace_id",
                "workflow_versions.project_id",
                "workflow_versions.workflow_plan_id",
                "workflow_versions.id",
            ],
            name="fk_workflow_plan_save_requests_version_tenant",
        ),
        CheckConstraint(
            "outcome IN ('created', 'semantic_no_op')",
            name="outcome_valid",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    idempotency_scope: Mapped[str] = mapped_column(String(500), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    workflow_plan_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
