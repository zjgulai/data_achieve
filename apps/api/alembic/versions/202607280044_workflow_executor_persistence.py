"""Add durable local Workflow Executor persistence contracts.

Revision ID: 202607280044
Revises: 202607270043
Create Date: 2026-07-28

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql.elements import conv

from alembic import op

revision: str = "202607280044"
down_revision: str | None = "202607270043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "workflow_execution_dispatches",
    "workflow_execution_leases",
    "workflow_execution_events",
    "workflow_credential_resolution_permits",
    "workflow_provider_call_permits",
    "workflow_provider_call_audits",
    "workflow_cancellation_requests",
    "workflow_cancellation_acknowledgements",
)


def _lineage_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_step_run_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_generation", sa.Integer(), nullable=False),
    )


def _created_at_column() -> sa.Column[object]:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def _lineage_constraints(table: str) -> tuple[sa.Constraint, ...]:
    return (
        sa.PrimaryKeyConstraint("id", name=conv(f"pk_{table}")),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name=conv(f"uq_{table}_tenant_id"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id"],
            ["workflow_runs.workspace_id", "workflow_runs.project_id", "workflow_runs.id"],
            name=conv(f"fk_{table}_run_tenant"),
        ),
        sa.ForeignKeyConstraint(
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
            name=conv(f"fk_{table}_step_tenant"),
        ),
        sa.CheckConstraint(
            "attempt_generation >= 0",
            name=conv(f"ck_{table}_attempt_generation"),
        ),
    )


def _dispatch_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["workspace_id", "project_id", "dispatch_id"],
        [
            "workflow_execution_dispatches.workspace_id",
            "workflow_execution_dispatches.project_id",
            "workflow_execution_dispatches.id",
        ],
        name=conv(f"fk_{table}_dispatch_tenant"),
    )


def _permit_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("dispatch_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column("operation_id", sa.String(length=128), nullable=False),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )


def _permit_constraints(table: str) -> tuple[sa.Constraint, ...]:
    return (
        *_lineage_constraints(table),
        _dispatch_fk(table),
        sa.CheckConstraint(
            "environment IN ('local', 'test', 'staging', 'production')",
            name=conv(f"ck_{table}_environment"),
        ),
        sa.CheckConstraint(
            "expires_at > issued_at",
            name=conv(f"ck_{table}_expiry"),
        ),
        sa.CheckConstraint(
            "consumed_at IS NULL OR (consumed_at >= issued_at AND consumed_at < expires_at)",
            name=conv(f"ck_{table}_consumed_time"),
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= issued_at",
            name=conv(f"ck_{table}_revoked_time"),
        ),
        sa.CheckConstraint(
            "consumed_at IS NULL OR revoked_at IS NULL",
            name=conv(f"ck_{table}_single_terminal_state"),
        ),
    )


def upgrade() -> None:
    op.create_table(
        "workflow_execution_dispatches",
        *_lineage_columns(),
        sa.Column("workflow_plan_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_action_request_id", sa.Uuid(), nullable=True),
        sa.Column("source_action_receipt_id", sa.Uuid(), nullable=True),
        sa.Column("workflow_version_digest", sa.String(length=71), nullable=False),
        sa.Column("execution_policy_digest", sa.String(length=71), nullable=False),
        sa.Column("dispatch_key", sa.String(length=71), nullable=False),
        sa.Column("provider_side_effect_key", sa.String(length=71), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("database_write", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "credential_read_attempted",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("provider_call", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("network_call", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "production_write_allowed",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        _created_at_column(),
        *_lineage_constraints("workflow_execution_dispatches"),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "dispatch_key",
            name=conv("uq_workflow_execution_dispatches_semantic_key"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "source_action_request_id"],
            [
                "workflow_run_action_requests.workspace_id",
                "workflow_run_action_requests.project_id",
                "workflow_run_action_requests.id",
            ],
            name=conv("fk_workflow_execution_dispatches_action_request_tenant"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "source_action_receipt_id"],
            [
                "workflow_run_action_receipts.workspace_id",
                "workflow_run_action_receipts.project_id",
                "workflow_run_action_receipts.id",
            ],
            name=conv("fk_workflow_execution_dispatches_action_receipt_tenant"),
        ),
        sa.CheckConstraint(
            "(source_action_request_id IS NULL AND source_action_receipt_id IS NULL) OR "
            "(source_action_request_id IS NOT NULL AND source_action_receipt_id IS NOT NULL)",
            name=conv("ck_workflow_execution_dispatches_action_lineage_pair"),
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'claimable', 'terminal')",
            name=conv("ck_workflow_execution_dispatches_state"),
        ),
        sa.CheckConstraint(
            "NOT database_write AND NOT credential_read_attempted AND NOT provider_call "
            "AND NOT network_call AND NOT production_write_allowed",
            name=conv("ck_workflow_execution_dispatches_local_boundaries"),
        ),
    )

    op.create_table(
        "workflow_execution_leases",
        *_lineage_columns(),
        sa.Column("dispatch_id", sa.Uuid(), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column("fencing_token", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        _created_at_column(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        *_lineage_constraints("workflow_execution_leases"),
        _dispatch_fk("workflow_execution_leases"),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "dispatch_id",
            name=conv("uq_workflow_execution_leases_dispatch_head"),
        ),
        sa.CheckConstraint(
            "fencing_token >= 1",
            name=conv("ck_workflow_execution_leases_fencing_token"),
        ),
        sa.CheckConstraint("version >= 1", name=conv("ck_workflow_execution_leases_version")),
        sa.CheckConstraint(
            "claimed_at <= heartbeat_at AND heartbeat_at < expires_at",
            name=conv("ck_workflow_execution_leases_time_order"),
        ),
        sa.CheckConstraint(
            "state IN ('active', 'released', 'expired', 'superseded', 'terminal')",
            name=conv("ck_workflow_execution_leases_state"),
        ),
    )

    op.create_table(
        "workflow_execution_events",
        *_lineage_columns(),
        sa.Column("dispatch_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("lease_id", sa.Uuid(), nullable=True),
        sa.Column("fencing_token", sa.Integer(), nullable=True),
        sa.Column("previous_event_digest", sa.String(length=71), nullable=True),
        sa.Column("event_digest", sa.String(length=71), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        _created_at_column(),
        *_lineage_constraints("workflow_execution_events"),
        _dispatch_fk("workflow_execution_events"),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "dispatch_id",
            "sequence",
            name=conv("uq_workflow_execution_events_dispatch_sequence"),
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "dispatch_id",
            "event_digest",
            name=conv("uq_workflow_execution_events_dispatch_digest"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "dispatch_id", "previous_event_digest"],
            [
                "workflow_execution_events.workspace_id",
                "workflow_execution_events.project_id",
                "workflow_execution_events.dispatch_id",
                "workflow_execution_events.event_digest",
            ],
            name=conv("fk_workflow_execution_events_previous_digest"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "lease_id"],
            [
                "workflow_execution_leases.workspace_id",
                "workflow_execution_leases.project_id",
                "workflow_execution_leases.id",
            ],
            name=conv("fk_workflow_execution_events_lease_tenant"),
        ),
        sa.CheckConstraint("sequence >= 1", name=conv("ck_workflow_execution_events_sequence")),
        sa.CheckConstraint(
            "(sequence = 1 AND previous_event_digest IS NULL) OR "
            "(sequence > 1 AND previous_event_digest IS NOT NULL)",
            name=conv("ck_workflow_execution_events_chain"),
        ),
        sa.CheckConstraint(
            "(lease_id IS NULL AND fencing_token IS NULL) OR "
            "(lease_id IS NOT NULL AND fencing_token >= 1)",
            name=conv("ck_workflow_execution_events_lease_pair"),
        ),
    )

    op.create_table(
        "workflow_credential_resolution_permits",
        *_lineage_columns(),
        *_permit_columns(),
        sa.Column("purpose", sa.String(length=128), nullable=False),
        sa.Column("credential_reference_fingerprint", sa.String(length=71), nullable=False),
        _created_at_column(),
        *_permit_constraints("workflow_credential_resolution_permits"),
    )

    op.create_table(
        "workflow_provider_call_permits",
        *_lineage_columns(),
        *_permit_columns(),
        sa.Column("preflight_id", sa.String(length=71), nullable=False),
        sa.Column("policy_digest", sa.String(length=71), nullable=False),
        sa.Column("side_effect_key", sa.String(length=71), nullable=False),
        sa.Column("max_cost_usd", sa.Numeric(18, 6), nullable=False),
        sa.Column("max_quota_units", sa.Integer(), nullable=False),
        _created_at_column(),
        *_permit_constraints("workflow_provider_call_permits"),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "dispatch_id",
            "preflight_id",
            "side_effect_key",
            name=conv("uq_workflow_provider_call_permits_authority"),
        ),
        sa.CheckConstraint(
            "max_cost_usd >= 0",
            name=conv("ck_workflow_provider_call_permits_max_cost"),
        ),
        sa.CheckConstraint(
            "max_quota_units >= 0",
            name=conv("ck_workflow_provider_call_permits_max_quota"),
        ),
    )

    op.create_table(
        "workflow_provider_call_audits",
        *_lineage_columns(),
        sa.Column("dispatch_id", sa.Uuid(), nullable=False),
        sa.Column("lease_id", sa.Uuid(), nullable=False),
        sa.Column("fencing_token", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column("operation_id", sa.String(length=128), nullable=False),
        sa.Column("preflight_id", sa.String(length=71), nullable=False),
        sa.Column("policy_digest", sa.String(length=71), nullable=False),
        sa.Column("side_effect_key", sa.String(length=71), nullable=False),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column("attempt_ordinal", sa.Integer(), nullable=False),
        sa.Column("transport_state", sa.String(length=20), nullable=False),
        sa.Column("outcome_code", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        _created_at_column(),
        *_lineage_constraints("workflow_provider_call_audits"),
        _dispatch_fk("workflow_provider_call_audits"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "lease_id"],
            [
                "workflow_execution_leases.workspace_id",
                "workflow_execution_leases.project_id",
                "workflow_execution_leases.id",
            ],
            name=conv("fk_workflow_provider_call_audits_lease_tenant"),
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "dispatch_id",
            "attempt_ordinal",
            name=conv("uq_workflow_provider_call_audits_dispatch_ordinal"),
        ),
        sa.CheckConstraint(
            "fencing_token >= 1",
            name=conv("ck_workflow_provider_call_audits_fencing_token"),
        ),
        sa.CheckConstraint(
            "attempt_ordinal >= 1",
            name=conv("ck_workflow_provider_call_audits_attempt_ordinal"),
        ),
        sa.CheckConstraint(
            "environment IN ('local', 'test', 'staging', 'production')",
            name=conv("ck_workflow_provider_call_audits_environment"),
        ),
        sa.CheckConstraint(
            "(transport_state = 'not_attempted' AND started_at IS NULL "
            "AND finished_at IS NULL AND outcome_code IS NULL) OR "
            "(transport_state = 'attempting' AND started_at IS NOT NULL "
            "AND finished_at IS NULL AND outcome_code IS NULL) OR "
            "(transport_state IN ('succeeded', 'failed', 'uncertain') "
            "AND started_at IS NOT NULL AND finished_at >= started_at "
            "AND outcome_code IS NOT NULL)",
            name=conv("ck_workflow_provider_call_audits_transport_state"),
        ),
    )

    op.create_table(
        "workflow_cancellation_requests",
        *_lineage_columns(),
        sa.Column("dispatch_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("request_key", sa.String(length=71), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        _created_at_column(),
        *_lineage_constraints("workflow_cancellation_requests"),
        _dispatch_fk("workflow_cancellation_requests"),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name=conv("fk_workflow_cancellation_requests_requested_by_user"),
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "request_key",
            name=conv("uq_workflow_cancellation_requests_semantic_key"),
        ),
    )

    op.create_table(
        "workflow_cancellation_acknowledgements",
        *_lineage_columns(),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("dispatch_id", sa.Uuid(), nullable=False),
        sa.Column("lease_id", sa.Uuid(), nullable=False),
        sa.Column("fencing_token", sa.Integer(), nullable=False),
        sa.Column("safe_point", sa.String(length=128), nullable=False),
        sa.Column("outcome", sa.String(length=50), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        _created_at_column(),
        *_lineage_constraints("workflow_cancellation_acknowledgements"),
        _dispatch_fk("workflow_cancellation_acknowledgements"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "request_id"],
            [
                "workflow_cancellation_requests.workspace_id",
                "workflow_cancellation_requests.project_id",
                "workflow_cancellation_requests.id",
            ],
            name=conv("fk_workflow_cancellation_acknowledgements_request_tenant"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "lease_id"],
            [
                "workflow_execution_leases.workspace_id",
                "workflow_execution_leases.project_id",
                "workflow_execution_leases.id",
            ],
            name=conv("fk_workflow_cancellation_acknowledgements_lease_tenant"),
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "request_id",
            name=conv("uq_workflow_cancellation_acknowledgements_request"),
        ),
        sa.CheckConstraint(
            "fencing_token >= 1",
            name=conv("ck_workflow_cancellation_acknowledgements_fencing_token"),
        ),
        sa.CheckConstraint(
            "outcome IN ('cancelled_before_effect', 'cancelled_after_current_effect', "
            "'cancel_pending_external_outcome')",
            name=conv("ck_workflow_cancellation_acknowledgements_outcome"),
        ),
    )


def downgrade() -> None:
    evidence_checks = " OR ".join(f"EXISTS (SELECT 1 FROM {table} LIMIT 1)" for table in _TABLES)
    op.execute(
        "DO $$ BEGIN IF " + evidence_checks + " THEN RAISE EXCEPTION "
        "'workflow_executor_evidence_present_downgrade_refused'; "
        "END IF; END $$;"
    )
    for table in reversed(_TABLES):
        op.drop_table(table)
