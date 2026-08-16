"""Add durable WorkflowRun state semantics and fallback linkage.

Revision ID: 202607230038
Revises: 202607220037
Create Date: 2026-07-23

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql.elements import conv

from alembic import op

revision: str = "202607230038"
down_revision: str | None = "202607220037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _workflow_run_status_constraint() -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "status IN ('draft', 'ready', 'running', 'completed', 'degraded', "
        "'held', 'cancelled', 'empty_valid')",
        name="ck_workflow_runs_status",
    )


def _workflow_run_state_constraint() -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "(status IN ('draft', 'ready', 'running') "
        "AND status_reason_code IS NULL AND impact_code IS NULL "
        "AND json_array_length(missing_fields) = 0 "
        "AND json_array_length(recovery_action_codes) = 0 "
        "AND finished_at IS NULL) OR "
        "(status = 'completed' AND completed_steps = total_steps "
        "AND records_count >= 1 AND status_reason_code IS NULL "
        "AND impact_code IS NULL AND json_array_length(missing_fields) = 0 "
        "AND json_array_length(recovery_action_codes) = 0 "
        "AND finished_at >= started_at) OR "
        "(status = 'empty_valid' AND completed_steps = total_steps "
        "AND records_count = 0 AND status_reason_code IS NOT NULL "
        "AND impact_code IS NOT NULL AND json_array_length(missing_fields) = 0 "
        "AND json_array_length(recovery_action_codes) = 0 "
        "AND finished_at >= started_at) OR "
        "(status = 'degraded' AND completed_steps = total_steps "
        "AND status_reason_code IS NOT NULL AND impact_code IS NOT NULL "
        "AND json_array_length(missing_fields) > 0 "
        "AND json_array_length(recovery_action_codes) > 0 "
        "AND finished_at >= started_at) OR "
        "(status = 'held' AND completed_steps < total_steps "
        "AND status_reason_code IS NOT NULL AND impact_code IS NOT NULL "
        "AND json_array_length(recovery_action_codes) > 0 "
        "AND finished_at IS NULL) OR "
        "(status = 'cancelled' AND status_reason_code IS NOT NULL "
        "AND impact_code IS NOT NULL "
        "AND json_array_length(recovery_action_codes) = 0 "
        "AND finished_at >= started_at)",
        name="ck_workflow_runs_state_snapshot",
    )


def _step_run_status_constraint() -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
        name="ck_step_runs_status",
    )


def _step_run_state_constraint() -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "(status IN ('pending', 'running') "
        "AND fixture_case_id IS NULL AND fixture_content_hash IS NULL "
        "AND output_digest IS NULL AND finished_at IS NULL) OR "
        "(status = 'completed' AND fixture_case_id IS NOT NULL "
        "AND fixture_content_hash IS NOT NULL AND output_digest IS NOT NULL "
        "AND finished_at >= started_at) OR "
        "(status IN ('failed', 'cancelled') AND records_count = 0 "
        "AND fixture_case_id IS NULL AND fixture_content_hash IS NULL "
        "AND output_digest IS NULL AND finished_at >= started_at)",
        name="ck_step_runs_state_snapshot",
    )


def upgrade() -> None:
    op.drop_constraint(
        conv("ck_workflow_runs_completed_snapshot"),
        "workflow_runs",
        type_="check",
    )
    op.drop_constraint(conv("ck_workflow_runs_status"), "workflow_runs", type_="check")
    op.add_column(
        "workflow_runs",
        sa.Column("status_reason_code", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "workflow_runs",
        sa.Column("impact_code", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "workflow_runs",
        sa.Column(
            "missing_fields",
            sa.JSON(),
            server_default=sa.text("'[]'::json"),
            nullable=False,
        ),
    )
    op.add_column(
        "workflow_runs",
        sa.Column(
            "recovery_action_codes",
            sa.JSON(),
            server_default=sa.text("'[]'::json"),
            nullable=False,
        ),
    )
    op.alter_column(
        "workflow_runs",
        "finished_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )
    op.create_check_constraint(
        conv("ck_workflow_runs_status"),
        "workflow_runs",
        _workflow_run_status_constraint().sqltext,
    )
    op.create_check_constraint(
        conv("ck_workflow_runs_state_snapshot"),
        "workflow_runs",
        _workflow_run_state_constraint().sqltext,
    )

    op.drop_constraint(conv("ck_step_runs_completed_snapshot"), "step_runs", type_="check")
    op.drop_constraint(conv("ck_step_runs_records_count"), "step_runs", type_="check")
    op.drop_constraint(conv("ck_step_runs_status"), "step_runs", type_="check")
    for column_name, column_type in (
        ("fixture_case_id", sa.String(length=200)),
        ("fixture_content_hash", sa.String(length=71)),
        ("output_digest", sa.String(length=71)),
        ("finished_at", sa.DateTime(timezone=True)),
    ):
        op.alter_column(
            "step_runs",
            column_name,
            existing_type=column_type,
            nullable=True,
        )
    op.create_check_constraint(
        conv("ck_step_runs_status"),
        "step_runs",
        _step_run_status_constraint().sqltext,
    )
    op.create_check_constraint(
        conv("ck_step_runs_records_count"),
        "step_runs",
        "records_count >= 0",
    )
    op.create_check_constraint(
        conv("ck_step_runs_state_snapshot"),
        "step_runs",
        _step_run_state_constraint().sqltext,
    )

    op.drop_constraint(
        conv("ck_workflow_run_requests_outcome"),
        "workflow_run_requests",
        type_="check",
    )
    op.create_check_constraint(
        conv("ck_workflow_run_requests_outcome"),
        "workflow_run_requests",
        "outcome IN ('completed', 'held')",
    )

    op.add_column(
        "workflow_fallback_decisions",
        sa.Column("workflow_run_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "workflow_fallback_decisions",
        sa.Column("step_run_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_workflow_fallback_decisions_run_tenant",
        "workflow_fallback_decisions",
        "workflow_runs",
        ["workspace_id", "project_id", "workflow_run_id"],
        ["workspace_id", "project_id", "id"],
    )
    op.create_foreign_key(
        "fk_workflow_fallback_decisions_step_tenant",
        "workflow_fallback_decisions",
        "step_runs",
        ["workspace_id", "project_id", "workflow_run_id", "step_run_id"],
        ["workspace_id", "project_id", "workflow_run_id", "id"],
    )
    op.create_check_constraint(
        conv("ck_workflow_fallback_decisions_run_step_pair"),
        "workflow_fallback_decisions",
        "(workflow_run_id IS NULL AND step_run_id IS NULL) OR "
        "(workflow_run_id IS NOT NULL AND step_run_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM workflow_runs
                WHERE status <> 'completed'
                   OR status_reason_code IS NOT NULL
                   OR impact_code IS NOT NULL
                   OR json_array_length(missing_fields) <> 0
                   OR json_array_length(recovery_action_codes) <> 0
            ) OR EXISTS (
                SELECT 1 FROM step_runs WHERE status <> 'completed'
            ) OR EXISTS (
                SELECT 1 FROM workflow_run_requests WHERE outcome <> 'completed'
            ) OR EXISTS (
                SELECT 1 FROM workflow_fallback_decisions
                WHERE workflow_run_id IS NOT NULL OR step_run_id IS NOT NULL
            ) THEN
                RAISE EXCEPTION
                    '202607230038 downgrade refused: RUN-04 state data exists';
            END IF;
        END $$;
        """
    )

    op.drop_constraint(
        conv("ck_workflow_fallback_decisions_run_step_pair"),
        "workflow_fallback_decisions",
        type_="check",
    )
    op.drop_constraint(
        conv("fk_workflow_fallback_decisions_step_tenant"),
        "workflow_fallback_decisions",
        type_="foreignkey",
    )
    op.drop_constraint(
        conv("fk_workflow_fallback_decisions_run_tenant"),
        "workflow_fallback_decisions",
        type_="foreignkey",
    )
    op.drop_column("workflow_fallback_decisions", "step_run_id")
    op.drop_column("workflow_fallback_decisions", "workflow_run_id")

    op.drop_constraint(
        conv("ck_workflow_run_requests_outcome"),
        "workflow_run_requests",
        type_="check",
    )
    op.create_check_constraint(
        conv("ck_workflow_run_requests_outcome"),
        "workflow_run_requests",
        "outcome = 'completed'",
    )

    op.drop_constraint(conv("ck_step_runs_state_snapshot"), "step_runs", type_="check")
    op.drop_constraint(conv("ck_step_runs_records_count"), "step_runs", type_="check")
    op.drop_constraint(conv("ck_step_runs_status"), "step_runs", type_="check")
    for column_name, column_type in (
        ("fixture_case_id", sa.String(length=200)),
        ("fixture_content_hash", sa.String(length=71)),
        ("output_digest", sa.String(length=71)),
        ("finished_at", sa.DateTime(timezone=True)),
    ):
        op.alter_column(
            "step_runs",
            column_name,
            existing_type=column_type,
            nullable=False,
        )
    op.create_check_constraint(
        conv("ck_step_runs_status"),
        "step_runs",
        "status IN ('pending', 'running', 'completed')",
    )
    op.create_check_constraint(
        conv("ck_step_runs_records_count"),
        "step_runs",
        "records_count >= 1",
    )
    op.create_check_constraint(
        conv("ck_step_runs_completed_snapshot"),
        "step_runs",
        "status <> 'completed' OR finished_at >= started_at",
    )

    op.drop_constraint(conv("ck_workflow_runs_state_snapshot"), "workflow_runs", type_="check")
    op.drop_constraint(conv("ck_workflow_runs_status"), "workflow_runs", type_="check")
    op.alter_column(
        "workflow_runs",
        "finished_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.drop_column("workflow_runs", "recovery_action_codes")
    op.drop_column("workflow_runs", "missing_fields")
    op.drop_column("workflow_runs", "impact_code")
    op.drop_column("workflow_runs", "status_reason_code")
    op.create_check_constraint(
        conv("ck_workflow_runs_status"),
        "workflow_runs",
        "status IN ('draft', 'ready', 'running', 'completed', 'degraded', 'held', 'cancelled')",
    )
    op.create_check_constraint(
        conv("ck_workflow_runs_completed_snapshot"),
        "workflow_runs",
        "status <> 'completed' OR (completed_steps = total_steps "
        "AND records_count >= 1 AND finished_at >= started_at)",
    )
