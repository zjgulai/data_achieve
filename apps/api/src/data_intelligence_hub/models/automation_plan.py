from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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
