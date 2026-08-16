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
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class _CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class _ActionBoundaryMixin:
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
    execution_started: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    production_write_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )


class WorkflowRunActionContext(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_run_action_contexts"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_run_action_contexts_tenant_id",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "workflow_run_id",
            name="uq_workflow_run_action_contexts_run",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id"],
            [
                "workflow_runs.workspace_id",
                "workflow_runs.project_id",
                "workflow_runs.id",
            ],
            name="fk_workflow_run_action_contexts_run_tenant",
        ),
        CheckConstraint("action_context_version >= 1", name="version"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action_context_version: Mapped[int] = mapped_column(Integer, nullable=False)
    latest_accepted_receipt_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )


class WorkflowRunActionApprovalReceiptRecord(
    UUIDPrimaryKeyMixin,
    _ActionBoundaryMixin,
    _CreatedAtMixin,
    Base,
):
    __tablename__ = "workflow_run_action_approval_receipts"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_run_action_approval_receipts_tenant_id",
        ),
        UniqueConstraint(
            "workspace_id",
            "approver_user_id",
            "idempotency_scope",
            "idempotency_key_hash",
            name="uq_workflow_run_action_approvals_actor_key",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id"],
            [
                "workflow_runs.workspace_id",
                "workflow_runs.project_id",
                "workflow_runs.id",
            ],
            name="fk_workflow_run_action_approvals_run_tenant",
        ),
        CheckConstraint(
            "schema_version = 'workflow_action_approval_receipt.v1'",
            name="schema_version",
        ),
        CheckConstraint(
            "action IN ('retry', 'resume', 'cancel', 'budget_override', 'route_switch')",
            name="action",
        ),
        CheckConstraint(
            "approval_kind IN "
            "('owner_confirmation', 'owner_policy_override', 'owner_route_override')",
            name="approval_kind",
        ),
        CheckConstraint("expected_action_context_version >= 1", name="context_version"),
        CheckConstraint(
            "expected_run_status IN "
            "('draft', 'ready', 'running', 'completed', 'degraded', 'held', "
            "'cancelled', 'empty_valid')",
            name="run_status",
        ),
        CheckConstraint("expires_at > issued_at", name="time_order"),
        CheckConstraint(
            "NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT execution_started AND NOT production_write_allowed",
            name="fixture_boundaries",
        ),
        Index(
            "ix_workflow_run_action_approvals_run_expiry",
            "workspace_id",
            "project_id",
            "workflow_run_id",
            "expires_at",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    approver_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    schema_version: Mapped[str] = mapped_column(
        String(100),
        default="workflow_action_approval_receipt.v1",
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    approval_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    proposal_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    idempotency_scope: Mapped[str] = mapped_column(String(500), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    canonical_request_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    expected_action_context_version: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_run_status: Mapped[str] = mapped_column(String(30), nullable=False)
    action_gate_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    evidence_digests: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowRunActionRequestRecord(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "workflow_run_action_requests"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_run_action_requests_tenant_id",
        ),
        UniqueConstraint(
            "workspace_id",
            "actor_user_id",
            "idempotency_scope",
            "idempotency_key_hash",
            name="uq_workflow_run_action_requests_actor_key",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id"],
            [
                "workflow_runs.workspace_id",
                "workflow_runs.project_id",
                "workflow_runs.id",
            ],
            name="fk_workflow_run_action_requests_run_tenant",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "approval_receipt_id"],
            [
                "workflow_run_action_approval_receipts.workspace_id",
                "workflow_run_action_approval_receipts.project_id",
                "workflow_run_action_approval_receipts.id",
            ],
            name="fk_workflow_run_action_requests_approval_tenant",
        ),
        CheckConstraint(
            "schema_version = 'workflow_run_action_request.v1'",
            name="schema_version",
        ),
        CheckConstraint(
            "action IN ('retry', 'resume', 'cancel', 'budget_override', 'route_switch')",
            name="action",
        ),
        CheckConstraint(
            "expected_action_context_version >= 1 "
            "AND ("
            "(outcome IN ('accepted', 'accepted_pending_executor_ack') "
            "AND accepted_action_context_version IS NOT NULL "
            "AND accepted_action_context_version = expected_action_context_version + 1) "
            "OR (outcome IN ('rejected_conflict', 'rejected_authorization', "
            "'rejected_precondition') AND accepted_action_context_version IS NULL)"
            ")",
            name="context_version",
        ),
        CheckConstraint(
            "expected_run_status IN "
            "('draft', 'ready', 'running', 'completed', 'degraded', 'held', "
            "'cancelled', 'empty_valid') "
            "AND observed_run_status IN "
            "('draft', 'ready', 'running', 'completed', 'degraded', 'held', "
            "'cancelled', 'empty_valid')",
            name="run_status",
        ),
        CheckConstraint(
            "outcome IN "
            "('accepted', 'accepted_pending_executor_ack', 'rejected_conflict', "
            "'rejected_authorization', 'rejected_precondition')",
            name="outcome",
        ),
        CheckConstraint(
            "response_status >= 200 AND response_status <= 599",
            name="response_status",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_scope: Mapped[str] = mapped_column(String(500), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    canonical_request_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    expected_action_context_version: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted_action_context_version: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    expected_run_status: Mapped[str] = mapped_column(String(30), nullable=False)
    observed_run_status: Mapped[str] = mapped_column(String(30), nullable=False)
    action_gate_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    approval_receipt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class WorkflowRunActionReceiptRecord(
    UUIDPrimaryKeyMixin,
    _ActionBoundaryMixin,
    _CreatedAtMixin,
    Base,
):
    __tablename__ = "workflow_run_action_receipts"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_run_action_receipts_tenant_id",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "request_id",
            name="uq_workflow_run_action_receipts_request",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "receipt_digest",
            name="uq_workflow_run_action_receipts_digest",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id"],
            [
                "workflow_runs.workspace_id",
                "workflow_runs.project_id",
                "workflow_runs.id",
            ],
            name="fk_workflow_run_action_receipts_run_tenant",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "request_id"],
            [
                "workflow_run_action_requests.workspace_id",
                "workflow_run_action_requests.project_id",
                "workflow_run_action_requests.id",
            ],
            name="fk_workflow_run_action_receipts_request_tenant",
        ),
        CheckConstraint(
            "schema_version = 'workflow_action_receipt.v1'",
            name="schema_version",
        ),
        CheckConstraint(
            "action IN ('retry', 'resume', 'cancel', 'budget_override', 'route_switch')",
            name="action",
        ),
        CheckConstraint(
            "outcome IN ('accepted', 'accepted_pending_executor_ack')",
            name="outcome",
        ),
        CheckConstraint(
            "before_action_context_version >= 1 "
            "AND after_action_context_version = before_action_context_version + 1",
            name="context_version",
        ),
        CheckConstraint(
            "before_run_status IN "
            "('draft', 'ready', 'running', 'completed', 'degraded', 'held', "
            "'cancelled', 'empty_valid') "
            "AND after_run_status IN "
            "('draft', 'ready', 'running', 'completed', 'degraded', 'held', "
            "'cancelled', 'empty_valid')",
            name="run_status",
        ),
        CheckConstraint(
            "database_write AND NOT idempotent_replay",
            name="write_replay",
        ),
        CheckConstraint(
            "NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT execution_started AND NOT production_write_allowed",
            name="fixture_boundaries",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    schema_version: Mapped[str] = mapped_column(
        String(100),
        default="workflow_action_receipt.v1",
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    before_action_context_version: Mapped[int] = mapped_column(Integer, nullable=False)
    after_action_context_version: Mapped[int] = mapped_column(Integer, nullable=False)
    before_run_status: Mapped[str] = mapped_column(String(30), nullable=False)
    after_run_status: Mapped[str] = mapped_column(String(30), nullable=False)
    before_step_snapshots: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
    )
    after_step_snapshots: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
    )
    decision_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    state_changed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    database_write: Mapped[bool] = mapped_column(Boolean, nullable=False)
    idempotent_replay: Mapped[bool] = mapped_column(Boolean, nullable=False)
    next_action_code: Mapped[str] = mapped_column(String(100), nullable=False)
    receipt_digest: Mapped[str] = mapped_column(String(71), nullable=False)


class WorkflowRunActionApprovalConsumption(
    UUIDPrimaryKeyMixin,
    _CreatedAtMixin,
    Base,
):
    __tablename__ = "workflow_run_action_approval_consumptions"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_run_action_consumptions_tenant_id",
        ),
        UniqueConstraint(
            "approval_receipt_id",
            name="uq_workflow_run_action_consumptions_approval",
        ),
        UniqueConstraint(
            "action_request_id",
            name="uq_workflow_run_action_consumptions_request",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id"],
            [
                "workflow_runs.workspace_id",
                "workflow_runs.project_id",
                "workflow_runs.id",
            ],
            name="fk_workflow_run_action_consumptions_run_tenant",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "approval_receipt_id"],
            [
                "workflow_run_action_approval_receipts.workspace_id",
                "workflow_run_action_approval_receipts.project_id",
                "workflow_run_action_approval_receipts.id",
            ],
            name="fk_workflow_run_action_consumptions_approval_tenant",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "action_request_id"],
            [
                "workflow_run_action_requests.workspace_id",
                "workflow_run_action_requests.project_id",
                "workflow_run_action_requests.id",
            ],
            name="fk_workflow_run_action_consumptions_request_tenant",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    approval_receipt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    action_request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    consumed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowRunActionAuditEvent(
    UUIDPrimaryKeyMixin,
    _ActionBoundaryMixin,
    _CreatedAtMixin,
    Base,
):
    __tablename__ = "workflow_run_action_audit_events"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_run_action_audit_events_tenant_id",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "workflow_run_id",
            "event_number",
            name="uq_workflow_run_action_audit_events_run_number",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "workflow_run_id",
            "event_digest",
            name="uq_workflow_run_action_audit_events_run_digest",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id"],
            [
                "workflow_runs.workspace_id",
                "workflow_runs.project_id",
                "workflow_runs.id",
            ],
            name="fk_workflow_run_action_audit_events_run_tenant",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "action_request_id"],
            [
                "workflow_run_action_requests.workspace_id",
                "workflow_run_action_requests.project_id",
                "workflow_run_action_requests.id",
            ],
            name="fk_workflow_run_action_audit_events_request_tenant",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "approval_receipt_id"],
            [
                "workflow_run_action_approval_receipts.workspace_id",
                "workflow_run_action_approval_receipts.project_id",
                "workflow_run_action_approval_receipts.id",
            ],
            name="fk_workflow_run_action_audit_events_approval_tenant",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "action_receipt_id"],
            [
                "workflow_run_action_receipts.workspace_id",
                "workflow_run_action_receipts.project_id",
                "workflow_run_action_receipts.id",
            ],
            name="fk_workflow_run_action_audit_events_receipt_tenant",
        ),
        ForeignKeyConstraint(
            [
                "workspace_id",
                "project_id",
                "workflow_run_id",
                "previous_event_digest",
            ],
            [
                "workflow_run_action_audit_events.workspace_id",
                "workflow_run_action_audit_events.project_id",
                "workflow_run_action_audit_events.workflow_run_id",
                "workflow_run_action_audit_events.event_digest",
            ],
            name="fk_workflow_run_action_audit_events_predecessor_tenant",
        ),
        CheckConstraint("event_number >= 1", name="event_number"),
        CheckConstraint(
            "(event_number = 1 AND previous_event_digest IS NULL) "
            "OR (event_number > 1 AND previous_event_digest IS NOT NULL)",
            name="predecessor",
        ),
        CheckConstraint(
            "before_action_context_version >= 1 "
            "AND after_action_context_version >= before_action_context_version",
            name="context_version",
        ),
        CheckConstraint(
            "NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT execution_started AND NOT production_write_allowed",
            name="fixture_boundaries",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_number: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_event_digest: Mapped[str | None] = mapped_column(String(71), nullable=True)
    event_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    action_request_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    approval_receipt_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    action_receipt_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    before_action_context_version: Mapped[int] = mapped_column(Integer, nullable=False)
    after_action_context_version: Mapped[int] = mapped_column(Integer, nullable=False)
    before_state_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    after_state_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    http_request_id: Mapped[str] = mapped_column(String(200), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


__all__ = [
    "WorkflowRunActionApprovalConsumption",
    "WorkflowRunActionApprovalReceiptRecord",
    "WorkflowRunActionAuditEvent",
    "WorkflowRunActionContext",
    "WorkflowRunActionReceiptRecord",
    "WorkflowRunActionRequestRecord",
]
