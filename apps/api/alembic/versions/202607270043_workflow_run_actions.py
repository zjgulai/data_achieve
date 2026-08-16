"""Add durable Workflow Run action ledgers and retry generations.

Revision ID: 202607270043
Revises: 202607230042
Create Date: 2026-07-27

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql.elements import conv

from alembic import op

revision: str = "202607270043"
down_revision: str | None = "202607230042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RUN_STATUSES = (
    "'draft', 'ready', 'running', 'completed', 'degraded', 'held', 'cancelled', 'empty_valid'"
)
_ACTIONS = "'retry', 'resume', 'cancel', 'budget_override', 'route_switch'"
_REQUEST_OUTCOMES = (
    "'accepted', 'accepted_pending_executor_ack', 'rejected_conflict', "
    "'rejected_authorization', 'rejected_precondition'"
)
_RECEIPT_OUTCOMES = "'accepted', 'accepted_pending_executor_ack'"


def _created_at_column() -> sa.Column[object]:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def _boundary_columns() -> tuple[sa.Column[bool], ...]:
    return tuple(
        sa.Column(name, sa.Boolean(), server_default=sa.false(), nullable=False)
        for name in (
            "provider_call_attempted",
            "credential_read_attempted",
            "execution_started",
            "production_write_allowed",
        )
    )


def _run_tenant_fk(name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["workspace_id", "project_id", "workflow_run_id"],
        [
            "workflow_runs.workspace_id",
            "workflow_runs.project_id",
            "workflow_runs.id",
        ],
        name=name,
    )


def _fixture_boundary_check(name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "NOT provider_call_attempted AND NOT credential_read_attempted "
        "AND NOT execution_started AND NOT production_write_allowed",
        name=conv(name),
    )


def upgrade() -> None:
    op.add_column(
        "step_runs",
        sa.Column(
            "retry_generation",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        conv("ck_step_runs_retry_generation"),
        "step_runs",
        "retry_generation >= 0",
    )
    op.add_column(
        "step_run_attempts",
        sa.Column(
            "retry_generation",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.drop_constraint(
        "uq_step_run_attempts_step_number",
        "step_run_attempts",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_step_run_attempts_step_number",
        "step_run_attempts",
        ["step_run_id", "retry_generation", "attempt_number"],
    )
    op.create_check_constraint(
        conv("ck_step_run_attempts_retry_generation"),
        "step_run_attempts",
        "retry_generation >= 0",
    )

    op.create_table(
        "workflow_run_action_contexts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("action_context_version", sa.Integer(), nullable=False),
        sa.Column("latest_accepted_receipt_id", sa.Uuid(), nullable=True),
        _created_at_column(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_run_action_contexts"),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_run_action_contexts_tenant_id",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "workflow_run_id",
            name="uq_workflow_run_action_contexts_run",
        ),
        _run_tenant_fk("fk_workflow_run_action_contexts_run_tenant"),
        sa.CheckConstraint(
            "action_context_version >= 1",
            name=conv("ck_workflow_run_action_contexts_version"),
        ),
    )

    op.create_table(
        "workflow_run_action_approval_receipts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("approver_user_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("approval_kind", sa.String(length=50), nullable=False),
        sa.Column("proposal_digest", sa.String(length=71), nullable=False),
        sa.Column("idempotency_scope", sa.String(length=500), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=71), nullable=False),
        sa.Column("canonical_request_hash", sa.String(length=71), nullable=False),
        sa.Column("expected_action_context_version", sa.Integer(), nullable=False),
        sa.Column("expected_run_status", sa.String(length=30), nullable=False),
        sa.Column("action_gate_digest", sa.String(length=71), nullable=False),
        sa.Column("evidence_digests", sa.JSON(), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *_boundary_columns(),
        _created_at_column(),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_workflow_run_action_approval_receipts",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_run_action_approval_receipts_tenant_id",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "approver_user_id",
            "idempotency_scope",
            "idempotency_key_hash",
            name="uq_workflow_run_action_approvals_actor_key",
        ),
        _run_tenant_fk("fk_workflow_run_action_approvals_run_tenant"),
        sa.CheckConstraint(
            "schema_version = 'workflow_action_approval_receipt.v1'",
            name=conv("ck_workflow_run_action_approval_receipts_schema_version"),
        ),
        sa.CheckConstraint(
            f"action IN ({_ACTIONS})",
            name=conv("ck_workflow_run_action_approval_receipts_action"),
        ),
        sa.CheckConstraint(
            "approval_kind IN "
            "('owner_confirmation', 'owner_policy_override', 'owner_route_override')",
            name=conv("ck_workflow_run_action_approval_receipts_approval_kind"),
        ),
        sa.CheckConstraint(
            "expected_action_context_version >= 1",
            name=conv("ck_workflow_run_action_approval_receipts_context_version"),
        ),
        sa.CheckConstraint(
            f"expected_run_status IN ({_RUN_STATUSES})",
            name=conv("ck_workflow_run_action_approval_receipts_run_status"),
        ),
        sa.CheckConstraint(
            "expires_at > issued_at",
            name=conv("ck_workflow_run_action_approval_receipts_time_order"),
        ),
        _fixture_boundary_check("ck_workflow_run_action_approval_receipts_fixture_boundaries"),
    )
    op.create_index(
        "ix_workflow_run_action_approvals_run_expiry",
        "workflow_run_action_approval_receipts",
        ["workspace_id", "project_id", "workflow_run_id", "expires_at"],
    )

    op.create_table(
        "workflow_run_action_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("idempotency_scope", sa.String(length=500), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=71), nullable=False),
        sa.Column("canonical_request_hash", sa.String(length=71), nullable=False),
        sa.Column("expected_action_context_version", sa.Integer(), nullable=False),
        sa.Column("accepted_action_context_version", sa.Integer(), nullable=True),
        sa.Column("expected_run_status", sa.String(length=30), nullable=False),
        sa.Column("observed_run_status", sa.String(length=30), nullable=False),
        sa.Column("action_gate_digest", sa.String(length=71), nullable=False),
        sa.Column("approval_receipt_id", sa.Uuid(), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("outcome", sa.String(length=50), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        _created_at_column(),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_run_action_requests"),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_run_action_requests_tenant_id",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "actor_user_id",
            "idempotency_scope",
            "idempotency_key_hash",
            name="uq_workflow_run_action_requests_actor_key",
        ),
        _run_tenant_fk("fk_workflow_run_action_requests_run_tenant"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "approval_receipt_id"],
            [
                "workflow_run_action_approval_receipts.workspace_id",
                "workflow_run_action_approval_receipts.project_id",
                "workflow_run_action_approval_receipts.id",
            ],
            name="fk_workflow_run_action_requests_approval_tenant",
        ),
        sa.CheckConstraint(
            "schema_version = 'workflow_run_action_request.v1'",
            name=conv("ck_workflow_run_action_requests_schema_version"),
        ),
        sa.CheckConstraint(
            f"action IN ({_ACTIONS})",
            name=conv("ck_workflow_run_action_requests_action"),
        ),
        sa.CheckConstraint(
            "expected_action_context_version >= 1 "
            "AND ("
            "(outcome IN ('accepted', 'accepted_pending_executor_ack') "
            "AND accepted_action_context_version IS NOT NULL "
            "AND accepted_action_context_version = expected_action_context_version + 1) "
            "OR (outcome IN ('rejected_conflict', 'rejected_authorization', "
            "'rejected_precondition') AND accepted_action_context_version IS NULL)"
            ")",
            name=conv("ck_workflow_run_action_requests_context_version"),
        ),
        sa.CheckConstraint(
            f"expected_run_status IN ({_RUN_STATUSES}) "
            f"AND observed_run_status IN ({_RUN_STATUSES})",
            name=conv("ck_workflow_run_action_requests_run_status"),
        ),
        sa.CheckConstraint(
            f"outcome IN ({_REQUEST_OUTCOMES})",
            name=conv("ck_workflow_run_action_requests_outcome"),
        ),
        sa.CheckConstraint(
            "response_status >= 200 AND response_status <= 599",
            name=conv("ck_workflow_run_action_requests_response_status"),
        ),
    )

    op.create_table(
        "workflow_run_action_receipts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("outcome", sa.String(length=50), nullable=False),
        sa.Column("before_action_context_version", sa.Integer(), nullable=False),
        sa.Column("after_action_context_version", sa.Integer(), nullable=False),
        sa.Column("before_run_status", sa.String(length=30), nullable=False),
        sa.Column("after_run_status", sa.String(length=30), nullable=False),
        sa.Column("before_step_snapshots", sa.JSON(), nullable=False),
        sa.Column("after_step_snapshots", sa.JSON(), nullable=False),
        sa.Column("decision_refs", sa.JSON(), nullable=False),
        sa.Column("state_changed", sa.Boolean(), nullable=False),
        sa.Column("database_write", sa.Boolean(), nullable=False),
        sa.Column("idempotent_replay", sa.Boolean(), nullable=False),
        sa.Column("next_action_code", sa.String(length=100), nullable=False),
        sa.Column("receipt_digest", sa.String(length=71), nullable=False),
        *_boundary_columns(),
        _created_at_column(),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_run_action_receipts"),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_run_action_receipts_tenant_id",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "request_id",
            name="uq_workflow_run_action_receipts_request",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "receipt_digest",
            name="uq_workflow_run_action_receipts_digest",
        ),
        _run_tenant_fk("fk_workflow_run_action_receipts_run_tenant"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "request_id"],
            [
                "workflow_run_action_requests.workspace_id",
                "workflow_run_action_requests.project_id",
                "workflow_run_action_requests.id",
            ],
            name="fk_workflow_run_action_receipts_request_tenant",
        ),
        sa.CheckConstraint(
            "schema_version = 'workflow_action_receipt.v1'",
            name=conv("ck_workflow_run_action_receipts_schema_version"),
        ),
        sa.CheckConstraint(
            f"action IN ({_ACTIONS})",
            name=conv("ck_workflow_run_action_receipts_action"),
        ),
        sa.CheckConstraint(
            f"outcome IN ({_RECEIPT_OUTCOMES})",
            name=conv("ck_workflow_run_action_receipts_outcome"),
        ),
        sa.CheckConstraint(
            "before_action_context_version >= 1 "
            "AND after_action_context_version = before_action_context_version + 1",
            name=conv("ck_workflow_run_action_receipts_context_version"),
        ),
        sa.CheckConstraint(
            f"before_run_status IN ({_RUN_STATUSES}) AND after_run_status IN ({_RUN_STATUSES})",
            name=conv("ck_workflow_run_action_receipts_run_status"),
        ),
        sa.CheckConstraint(
            "database_write AND NOT idempotent_replay",
            name=conv("ck_workflow_run_action_receipts_write_replay"),
        ),
        _fixture_boundary_check("ck_workflow_run_action_receipts_fixture_boundaries"),
    )

    op.create_table(
        "workflow_run_action_approval_consumptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("approval_receipt_id", sa.Uuid(), nullable=False),
        sa.Column("action_request_id", sa.Uuid(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False),
        _created_at_column(),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_workflow_run_action_approval_consumptions",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_run_action_consumptions_tenant_id",
        ),
        sa.UniqueConstraint(
            "approval_receipt_id",
            name="uq_workflow_run_action_consumptions_approval",
        ),
        sa.UniqueConstraint(
            "action_request_id",
            name="uq_workflow_run_action_consumptions_request",
        ),
        _run_tenant_fk("fk_workflow_run_action_consumptions_run_tenant"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "approval_receipt_id"],
            [
                "workflow_run_action_approval_receipts.workspace_id",
                "workflow_run_action_approval_receipts.project_id",
                "workflow_run_action_approval_receipts.id",
            ],
            name="fk_workflow_run_action_consumptions_approval_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "action_request_id"],
            [
                "workflow_run_action_requests.workspace_id",
                "workflow_run_action_requests.project_id",
                "workflow_run_action_requests.id",
            ],
            name="fk_workflow_run_action_consumptions_request_tenant",
        ),
    )

    op.create_table(
        "workflow_run_action_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("event_number", sa.Integer(), nullable=False),
        sa.Column("previous_event_digest", sa.String(length=71), nullable=True),
        sa.Column("event_digest", sa.String(length=71), nullable=False),
        sa.Column("action_request_id", sa.Uuid(), nullable=True),
        sa.Column("approval_receipt_id", sa.Uuid(), nullable=True),
        sa.Column("action_receipt_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("before_action_context_version", sa.Integer(), nullable=False),
        sa.Column("after_action_context_version", sa.Integer(), nullable=False),
        sa.Column("before_state_digest", sa.String(length=71), nullable=False),
        sa.Column("after_state_digest", sa.String(length=71), nullable=False),
        sa.Column("http_request_id", sa.String(length=200), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        *_boundary_columns(),
        _created_at_column(),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_run_action_audit_events"),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_run_action_audit_events_tenant_id",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "workflow_run_id",
            "event_number",
            name="uq_workflow_run_action_audit_events_run_number",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "workflow_run_id",
            "event_digest",
            name="uq_workflow_run_action_audit_events_run_digest",
        ),
        _run_tenant_fk("fk_workflow_run_action_audit_events_run_tenant"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "action_request_id"],
            [
                "workflow_run_action_requests.workspace_id",
                "workflow_run_action_requests.project_id",
                "workflow_run_action_requests.id",
            ],
            name="fk_workflow_run_action_audit_events_request_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "approval_receipt_id"],
            [
                "workflow_run_action_approval_receipts.workspace_id",
                "workflow_run_action_approval_receipts.project_id",
                "workflow_run_action_approval_receipts.id",
            ],
            name="fk_workflow_run_action_audit_events_approval_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "action_receipt_id"],
            [
                "workflow_run_action_receipts.workspace_id",
                "workflow_run_action_receipts.project_id",
                "workflow_run_action_receipts.id",
            ],
            name="fk_workflow_run_action_audit_events_receipt_tenant",
        ),
        sa.ForeignKeyConstraint(
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
        sa.CheckConstraint(
            "event_number >= 1",
            name=conv("ck_workflow_run_action_audit_events_event_number"),
        ),
        sa.CheckConstraint(
            "(event_number = 1 AND previous_event_digest IS NULL) "
            "OR (event_number > 1 AND previous_event_digest IS NOT NULL)",
            name=conv("ck_workflow_run_action_audit_events_predecessor"),
        ),
        sa.CheckConstraint(
            "before_action_context_version >= 1 "
            "AND after_action_context_version >= before_action_context_version",
            name=conv("ck_workflow_run_action_audit_events_context_version"),
        ),
        _fixture_boundary_check("ck_workflow_run_action_audit_events_fixture_boundaries"),
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM workflow_run_action_audit_events)
               OR EXISTS (SELECT 1 FROM workflow_run_action_approval_consumptions)
               OR EXISTS (SELECT 1 FROM workflow_run_action_receipts)
               OR EXISTS (SELECT 1 FROM workflow_run_action_requests)
               OR EXISTS (SELECT 1 FROM workflow_run_action_approval_receipts)
               OR EXISTS (SELECT 1 FROM workflow_run_action_contexts)
               OR EXISTS (SELECT 1 FROM step_runs WHERE retry_generation <> 0)
               OR EXISTS (
                    SELECT 1 FROM step_run_attempts WHERE retry_generation <> 0
               ) THEN
                RAISE EXCEPTION
                    '202607270043 downgrade refused: Workflow action evidence exists';
            END IF;
        END $$;
        """
    )
    op.drop_table("workflow_run_action_audit_events")
    op.drop_table("workflow_run_action_approval_consumptions")
    op.drop_table("workflow_run_action_receipts")
    op.drop_table("workflow_run_action_requests")
    op.drop_table("workflow_run_action_approval_receipts")
    op.drop_table("workflow_run_action_contexts")
    op.drop_constraint(
        conv("ck_step_run_attempts_retry_generation"),
        "step_run_attempts",
        type_="check",
    )
    op.drop_constraint(
        "uq_step_run_attempts_step_number",
        "step_run_attempts",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_step_run_attempts_step_number",
        "step_run_attempts",
        ["step_run_id", "attempt_number"],
    )
    op.drop_column("step_run_attempts", "retry_generation")
    op.drop_constraint(
        conv("ck_step_runs_retry_generation"),
        "step_runs",
        type_="check",
    )
    op.drop_column("step_runs", "retry_generation")
