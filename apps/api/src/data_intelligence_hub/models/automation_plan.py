from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data_intelligence_hub.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SiteAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "site_analyses"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    requested_url: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    authorization_confirmed: Mapped[bool] = mapped_column(nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    platform_profile: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    page_structure: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    field_candidates: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    tool_recommendations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    cleaning_plan: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    source_draft: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    blocked_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    extraction_plans: Mapped[list[ExtractionPlan]] = relationship(
        back_populates="site_analysis",
        cascade="all, delete-orphan",
    )
    browser_diagnostic_runs: Mapped[list[BrowserDiagnosticRun]] = relationship(
        back_populates="site_analysis",
        cascade="all, delete-orphan",
    )
    browser_diagnostic_jobs: Mapped[list[BrowserDiagnosticJob]] = relationship(
        back_populates="site_analysis",
        cascade="all, delete-orphan",
    )


class BrowserDiagnosticRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "browser_diagnostic_runs"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    site_analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("site_analyses.id"),
        nullable=True,
    )
    requested_url: Mapped[str] = mapped_column(Text, nullable=False)
    final_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    authorization_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    recommended_path: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    field_stability: Mapped[str | None] = mapped_column(String(30))
    evidence_source: Mapped[str] = mapped_column(String(120), nullable=False)
    screenshot_path: Mapped[str | None] = mapped_column(Text)
    run_policy: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    page_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    network_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    accessibility_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    risk_flags: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    extraction_strategy: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    diagnostic_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    blocked_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    run_started: Mapped[bool] = mapped_column(Boolean, nullable=False)

    site_analysis: Mapped[SiteAnalysis | None] = relationship(
        back_populates="browser_diagnostic_runs"
    )
    browser_diagnostic_jobs: Mapped[list[BrowserDiagnosticJob]] = relationship(
        back_populates="browser_diagnostic_run",
        cascade="all, delete-orphan",
    )
    browser_diagnostic_job_runs: Mapped[list[BrowserDiagnosticJobRun]] = relationship(
        back_populates="browser_diagnostic_run",
        cascade="all, delete-orphan",
    )


class BrowserDiagnosticJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "browser_diagnostic_jobs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "request_fingerprint",
            name="uq_browser_diagnostic_jobs_workspace_fingerprint",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    site_analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("site_analyses.id"),
        nullable=False,
    )
    extraction_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("extraction_plans.id"),
        nullable=False,
    )
    browser_diagnostic_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("browser_diagnostic_runs.id"),
        nullable=False,
    )
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_url: Mapped[str] = mapped_column(Text, nullable=False)
    final_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    authorization_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    runner: Mapped[str] = mapped_column(String(80), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(80), nullable=False)
    selector_scope: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    wait_policy: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    network_observation_policy: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    artifact_policy: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    safety_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    dry_run_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    executable_spec_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    blocked_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    audit_events: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    run_started: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    site_analysis: Mapped[SiteAnalysis] = relationship(back_populates="browser_diagnostic_jobs")
    extraction_plan: Mapped[ExtractionPlan] = relationship(
        back_populates="browser_diagnostic_jobs"
    )
    browser_diagnostic_run: Mapped[BrowserDiagnosticRun] = relationship(
        back_populates="browser_diagnostic_jobs"
    )
    local_runs: Mapped[list[BrowserDiagnosticJobRun]] = relationship(
        back_populates="browser_diagnostic_job",
        cascade="all, delete-orphan",
    )


class BrowserDiagnosticJobRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "browser_diagnostic_job_runs"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    browser_diagnostic_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("browser_diagnostic_jobs.id"),
        nullable=False,
    )
    site_analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("site_analyses.id"),
        nullable=False,
    )
    extraction_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("extraction_plans.id"),
        nullable=False,
    )
    browser_diagnostic_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("browser_diagnostic_runs.id"),
        nullable=False,
    )
    requested_url: Mapped[str] = mapped_column(Text, nullable=False)
    final_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    runner: Mapped[str] = mapped_column(String(80), nullable=False)
    run_mode: Mapped[str] = mapped_column(String(80), nullable=False)
    contract_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    artifact_manifest: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    selector_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    preview_rows: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    network_observation_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    error_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    blocked_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    audit_events: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    execution_started: Mapped[bool] = mapped_column(Boolean, nullable=False)
    browser_started: Mapped[bool] = mapped_column(Boolean, nullable=False)
    files_written: Mapped[bool] = mapped_column(Boolean, nullable=False)
    collection_resources_written: Mapped[bool] = mapped_column(Boolean, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    browser_diagnostic_job: Mapped[BrowserDiagnosticJob] = relationship(
        back_populates="local_runs"
    )
    browser_diagnostic_run: Mapped[BrowserDiagnosticRun] = relationship(
        back_populates="browser_diagnostic_job_runs"
    )


class ExtractionPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "extraction_plans"
    __table_args__ = (
        UniqueConstraint(
            "site_analysis_id",
            "version_number",
            name="uq_extraction_plans_site_analysis_version",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    site_analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("site_analyses.id"),
        nullable=False,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    collector_type: Mapped[str] = mapped_column(String(80), nullable=False)
    selected_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    source_draft: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    schedule_cron: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(30), nullable=False)
    audit_events: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)

    site_analysis: Mapped[SiteAnalysis] = relationship(back_populates="extraction_plans")
    browser_diagnostic_jobs: Mapped[list[BrowserDiagnosticJob]] = relationship(
        back_populates="extraction_plan",
        cascade="all, delete-orphan",
    )
