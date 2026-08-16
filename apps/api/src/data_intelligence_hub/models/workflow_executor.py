from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
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


class _ExecutorLineageMixin:
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_step_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    attempt_generation: Mapped[int] = mapped_column(Integer, nullable=False)


def _tenant_id_constraint(table: str) -> UniqueConstraint:
    return UniqueConstraint(
        "workspace_id",
        "project_id",
        "id",
        name=f"uq_{table}_tenant_id",
    )


def _run_lineage_constraint(table: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["workspace_id", "project_id", "workflow_run_id"],
        ["workflow_runs.workspace_id", "workflow_runs.project_id", "workflow_runs.id"],
        name=f"fk_{table}_run_tenant",
    )


def _step_lineage_constraint(table: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
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
        name=f"fk_{table}_step_tenant",
    )


def _dispatch_lineage_constraint(table: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["workspace_id", "project_id", "dispatch_id"],
        [
            "workflow_execution_dispatches.workspace_id",
            "workflow_execution_dispatches.project_id",
            "workflow_execution_dispatches.id",
        ],
        name=f"fk_{table}_dispatch_tenant",
    )


def _lineage_constraints(table: str) -> tuple[object, ...]:
    return (
        _tenant_id_constraint(table),
        _run_lineage_constraint(table),
        _step_lineage_constraint(table),
        CheckConstraint("attempt_generation >= 0", name="attempt_generation"),
    )


class WorkflowExecutionDispatchRecord(
    UUIDPrimaryKeyMixin,
    _ExecutorLineageMixin,
    _CreatedAtMixin,
    Base,
):
    __tablename__ = "workflow_execution_dispatches"
    __table_args__ = (
        *_lineage_constraints(__tablename__),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "dispatch_key",
            name="uq_workflow_execution_dispatches_semantic_key",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "source_action_request_id"],
            [
                "workflow_run_action_requests.workspace_id",
                "workflow_run_action_requests.project_id",
                "workflow_run_action_requests.id",
            ],
            name="fk_workflow_execution_dispatches_action_request_tenant",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "source_action_receipt_id"],
            [
                "workflow_run_action_receipts.workspace_id",
                "workflow_run_action_receipts.project_id",
                "workflow_run_action_receipts.id",
            ],
            name="fk_workflow_execution_dispatches_action_receipt_tenant",
        ),
        CheckConstraint(
            "(source_action_request_id IS NULL AND source_action_receipt_id IS NULL) OR "
            "(source_action_request_id IS NOT NULL AND source_action_receipt_id IS NOT NULL)",
            name="action_lineage_pair",
        ),
        CheckConstraint(
            "state IN ('pending', 'claimable', 'terminal')",
            name="state",
        ),
        CheckConstraint(
            "NOT database_write AND NOT credential_read_attempted AND NOT provider_call "
            "AND NOT network_call AND NOT production_write_allowed",
            name="local_boundaries",
        ),
    )

    workflow_plan_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_action_request_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    source_action_receipt_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    workflow_version_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    execution_policy_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    dispatch_key: Mapped[str] = mapped_column(String(71), nullable=False)
    provider_side_effect_key: Mapped[str] = mapped_column(String(71), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    database_write: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    credential_read_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    provider_call: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    network_call: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    production_write_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )


class WorkflowExecutionLeaseRecord(
    UUIDPrimaryKeyMixin,
    _ExecutorLineageMixin,
    TimestampMixin,
    Base,
):
    __tablename__ = "workflow_execution_leases"
    __table_args__ = (
        *_lineage_constraints(__tablename__),
        _dispatch_lineage_constraint(__tablename__),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "dispatch_id",
            name="uq_workflow_execution_leases_dispatch_head",
        ),
        CheckConstraint("fencing_token >= 1", name="fencing_token"),
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint(
            "claimed_at <= heartbeat_at AND heartbeat_at < expires_at",
            name="time_order",
        ),
        CheckConstraint(
            "state IN ('active', 'released', 'expired', 'superseded', 'terminal')",
            name="state",
        ),
    )

    dispatch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    worker_id: Mapped[str] = mapped_column(String(128), nullable=False)
    fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)


class WorkflowExecutionEventRecord(
    UUIDPrimaryKeyMixin,
    _ExecutorLineageMixin,
    _CreatedAtMixin,
    Base,
):
    __tablename__ = "workflow_execution_events"
    __table_args__ = (
        *_lineage_constraints(__tablename__),
        _dispatch_lineage_constraint(__tablename__),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "dispatch_id",
            "sequence",
            name="uq_workflow_execution_events_dispatch_sequence",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "dispatch_id",
            "event_digest",
            name="uq_workflow_execution_events_dispatch_digest",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "dispatch_id", "previous_event_digest"],
            [
                "workflow_execution_events.workspace_id",
                "workflow_execution_events.project_id",
                "workflow_execution_events.dispatch_id",
                "workflow_execution_events.event_digest",
            ],
            name="fk_workflow_execution_events_previous_digest",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "lease_id"],
            [
                "workflow_execution_leases.workspace_id",
                "workflow_execution_leases.project_id",
                "workflow_execution_leases.id",
            ],
            name="fk_workflow_execution_events_lease_tenant",
        ),
        CheckConstraint("sequence >= 1", name="sequence"),
        CheckConstraint(
            "(sequence = 1 AND previous_event_digest IS NULL) OR "
            "(sequence > 1 AND previous_event_digest IS NOT NULL)",
            name="chain",
        ),
        CheckConstraint(
            "(lease_id IS NULL AND fencing_token IS NULL) OR "
            "(lease_id IS NOT NULL AND fencing_token >= 1)",
            name="lease_pair",
        ),
    )

    dispatch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    lease_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    fencing_token: Mapped[int | None] = mapped_column(Integer, nullable=True)
    previous_event_digest: Mapped[str | None] = mapped_column(String(71), nullable=True)
    event_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class _PermitMixin(_ExecutorLineageMixin):
    dispatch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(128), nullable=False)
    operation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def _permit_constraints(table: str) -> tuple[object, ...]:
    return (
        *_lineage_constraints(table),
        _dispatch_lineage_constraint(table),
        CheckConstraint(
            "environment IN ('local', 'test', 'staging', 'production')",
            name="environment",
        ),
        CheckConstraint("expires_at > issued_at", name="expiry"),
        CheckConstraint(
            "consumed_at IS NULL OR (consumed_at >= issued_at AND consumed_at < expires_at)",
            name="consumed_time",
        ),
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= issued_at",
            name="revoked_time",
        ),
        CheckConstraint(
            "consumed_at IS NULL OR revoked_at IS NULL",
            name="single_terminal_state",
        ),
    )


class WorkflowCredentialResolutionPermitRecord(
    UUIDPrimaryKeyMixin,
    _PermitMixin,
    _CreatedAtMixin,
    Base,
):
    __tablename__ = "workflow_credential_resolution_permits"
    __table_args__ = _permit_constraints(__tablename__)

    purpose: Mapped[str] = mapped_column(String(128), nullable=False)
    credential_reference_fingerprint: Mapped[str] = mapped_column(
        String(71),
        nullable=False,
    )


class WorkflowProviderCallPermitRecord(
    UUIDPrimaryKeyMixin,
    _PermitMixin,
    _CreatedAtMixin,
    Base,
):
    __tablename__ = "workflow_provider_call_permits"
    __table_args__ = (
        *_permit_constraints(__tablename__),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "dispatch_id",
            "preflight_id",
            "side_effect_key",
            name="uq_workflow_provider_call_permits_authority",
        ),
        CheckConstraint("max_cost_usd >= 0", name="max_cost"),
        CheckConstraint("max_quota_units >= 0", name="max_quota"),
    )

    preflight_id: Mapped[str] = mapped_column(String(71), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    side_effect_key: Mapped[str] = mapped_column(String(71), nullable=False)
    max_cost_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    max_quota_units: Mapped[int] = mapped_column(Integer, nullable=False)


class WorkflowProviderCallAuditRecord(
    UUIDPrimaryKeyMixin,
    _ExecutorLineageMixin,
    _CreatedAtMixin,
    Base,
):
    __tablename__ = "workflow_provider_call_audits"
    __table_args__ = (
        *_lineage_constraints(__tablename__),
        _dispatch_lineage_constraint(__tablename__),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "lease_id"],
            [
                "workflow_execution_leases.workspace_id",
                "workflow_execution_leases.project_id",
                "workflow_execution_leases.id",
            ],
            name="fk_workflow_provider_call_audits_lease_tenant",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "dispatch_id",
            "attempt_ordinal",
            name="uq_workflow_provider_call_audits_dispatch_ordinal",
        ),
        CheckConstraint("fencing_token >= 1", name="fencing_token"),
        CheckConstraint("attempt_ordinal >= 1", name="attempt_ordinal"),
        CheckConstraint(
            "environment IN ('local', 'test', 'staging', 'production')",
            name="environment",
        ),
        CheckConstraint(
            "(transport_state = 'not_attempted' AND started_at IS NULL "
            "AND finished_at IS NULL AND outcome_code IS NULL) OR "
            "(transport_state = 'attempting' AND started_at IS NOT NULL "
            "AND finished_at IS NULL AND outcome_code IS NULL) OR "
            "(transport_state IN ('succeeded', 'failed', 'uncertain') "
            "AND started_at IS NOT NULL AND finished_at >= started_at "
            "AND outcome_code IS NOT NULL)",
            name="transport_state",
        ),
    )

    dispatch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    lease_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_id: Mapped[str] = mapped_column(String(128), nullable=False)
    operation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    preflight_id: Mapped[str] = mapped_column(String(71), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    side_effect_key: Mapped[str] = mapped_column(String(71), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    attempt_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    transport_state: Mapped[str] = mapped_column(String(20), nullable=False)
    outcome_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkflowCancellationRequestRecord(
    UUIDPrimaryKeyMixin,
    _ExecutorLineageMixin,
    _CreatedAtMixin,
    Base,
):
    __tablename__ = "workflow_cancellation_requests"
    __table_args__ = (
        *_lineage_constraints(__tablename__),
        _dispatch_lineage_constraint(__tablename__),
        ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name="fk_workflow_cancellation_requests_requested_by_user",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "request_key",
            name="uq_workflow_cancellation_requests_semantic_key",
        ),
    )

    dispatch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    request_key: Mapped[str] = mapped_column(String(71), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowCancellationAcknowledgementRecord(
    UUIDPrimaryKeyMixin,
    _ExecutorLineageMixin,
    _CreatedAtMixin,
    Base,
):
    __tablename__ = "workflow_cancellation_acknowledgements"
    __table_args__ = (
        *_lineage_constraints(__tablename__),
        _dispatch_lineage_constraint(__tablename__),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "request_id"],
            [
                "workflow_cancellation_requests.workspace_id",
                "workflow_cancellation_requests.project_id",
                "workflow_cancellation_requests.id",
            ],
            name="fk_workflow_cancellation_acknowledgements_request_tenant",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "lease_id"],
            [
                "workflow_execution_leases.workspace_id",
                "workflow_execution_leases.project_id",
                "workflow_execution_leases.id",
            ],
            name="fk_workflow_cancellation_acknowledgements_lease_tenant",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "request_id",
            name="uq_workflow_cancellation_acknowledgements_request",
        ),
        CheckConstraint("fencing_token >= 1", name="fencing_token"),
        CheckConstraint(
            "outcome IN ('cancelled_before_effect', 'cancelled_after_current_effect', "
            "'cancel_pending_external_outcome')",
            name="outcome",
        ),
    )

    request_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dispatch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    lease_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    safe_point: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


__all__ = [
    "WorkflowCancellationAcknowledgementRecord",
    "WorkflowCancellationRequestRecord",
    "WorkflowCredentialResolutionPermitRecord",
    "WorkflowExecutionDispatchRecord",
    "WorkflowExecutionEventRecord",
    "WorkflowExecutionLeaseRecord",
    "WorkflowProviderCallAuditRecord",
    "WorkflowProviderCallPermitRecord",
]
