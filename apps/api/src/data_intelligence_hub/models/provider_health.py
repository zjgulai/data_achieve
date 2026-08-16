from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin


class _CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ProviderHealthSnapshot(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "provider_health_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "scope_key",
            "snapshot_version",
            name="uq_provider_health_snapshots_scope_version",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "aggregation_key",
            name="uq_provider_health_snapshots_aggregation",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "snapshot_digest",
            name="uq_provider_health_snapshots_digest",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_provider_health_snapshots_project_tenant",
        ),
        CheckConstraint(
            "contract_version = 'provider_health_snapshot.v1'",
            name="contract_version",
        ),
        CheckConstraint("snapshot_version >= 1", name="version"),
        CheckConstraint(
            "status IN ('unknown', 'healthy', 'degraded', 'unhealthy')",
            name="status",
        ),
        CheckConstraint(
            "sample_count >= 1 AND success_count >= 0 AND timeout_count >= 0 "
            "AND rate_limited_count >= 0 AND transient_error_count >= 0 "
            "AND terminal_error_count >= 0 AND success_count + timeout_count "
            "+ rate_limited_count + transient_error_count + terminal_error_count "
            "= sample_count",
            name="counts",
        ),
        CheckConstraint(
            "success_rate_bps >= 0 AND success_rate_bps <= 10000 AND p95_latency_ms >= 0",
            name="metrics",
        ),
        CheckConstraint(
            "window_ended_at > window_started_at AND evaluated_at >= window_ended_at "
            "AND routing_valid_until > evaluated_at "
            "AND evidence_retain_until > routing_valid_until",
            name="time_order",
        ),
        CheckConstraint(
            "NOT health_probe_attempted AND NOT provider_call_attempted "
            "AND NOT credential_read_attempted AND NOT actor_run "
            "AND NOT browser_run AND NOT llm_call AND NOT raw_record_write "
            "AND NOT dataset_write AND NOT production_write_allowed",
            name="fixture_boundaries",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(100), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(71), nullable=False)
    aggregation_key: Mapped[str] = mapped_column(String(71), nullable=False)
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False)
    platform_id: Mapped[str] = mapped_column(String(200), nullable=False)
    implementation_id: Mapped[str] = mapped_column(String(200), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(200), nullable=False)
    operation: Mapped[str] = mapped_column(String(200), nullable=False)
    window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    window_ended_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False)
    timeout_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rate_limited_count: Mapped[int] = mapped_column(Integer, nullable=False)
    transient_error_count: Mapped[int] = mapped_column(Integer, nullable=False)
    terminal_error_count: Mapped[int] = mapped_column(Integer, nullable=False)
    success_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    p95_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    policy_snapshot: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False)
    observation_manifest: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    previous_snapshot_digest: Mapped[str | None] = mapped_column(
        String(71),
        nullable=True,
    )
    snapshot_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    routing_valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    evidence_retain_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    health_probe_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    provider_call_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    credential_read_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    actor_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    browser_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    llm_call: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_record_write: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dataset_write: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    production_write_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )


class ProviderHealthRouteFeedback(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "provider_health_route_feedbacks"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "route_key",
            "feedback_version",
            name="uq_provider_health_feedbacks_route_version",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "feedback_key",
            name="uq_provider_health_feedbacks_key",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "feedback_digest",
            name="uq_provider_health_feedbacks_digest",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_provider_health_feedbacks_project_tenant",
        ),
        CheckConstraint(
            "contract_version = 'provider_health_route_feedback.v1'",
            name="contract_version",
        ),
        CheckConstraint("feedback_version >= 1", name="version"),
        CheckConstraint(
            "evidence_retain_until > evaluated_at",
            name="retention",
        ),
        CheckConstraint(
            "NOT health_probe_attempted AND NOT catalog_mutation_applied "
            "AND NOT automatic_route_switch_executed "
            "AND NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT actor_run AND NOT browser_run AND NOT llm_call "
            "AND NOT raw_record_write AND NOT dataset_write "
            "AND NOT production_write_allowed",
            name="fixture_boundaries",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(100), nullable=False)
    route_key: Mapped[str] = mapped_column(String(500), nullable=False)
    feedback_key: Mapped[str] = mapped_column(String(71), nullable=False)
    feedback_version: Mapped[int] = mapped_column(Integer, nullable=False)
    platform_id: Mapped[str] = mapped_column(String(200), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(200), nullable=False)
    operation: Mapped[str] = mapped_column(String(200), nullable=False)
    original_candidate_order: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    adjusted_candidate_order: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    candidate_score_manifest: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
    )
    source_snapshot_manifest: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
    )
    ranking_changed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    previous_feedback_digest: Mapped[str | None] = mapped_column(
        String(71),
        nullable=True,
    )
    feedback_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence_retain_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    health_probe_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    catalog_mutation_applied: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    automatic_route_switch_executed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    provider_call_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    credential_read_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    actor_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    browser_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    llm_call: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_record_write: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dataset_write: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    production_write_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )


__all__ = ["ProviderHealthRouteFeedback", "ProviderHealthSnapshot"]
