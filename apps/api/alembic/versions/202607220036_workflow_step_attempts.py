"""Add append-only workflow step attempt ledger.

Revision ID: 202607220036
Revises: 202607220035
Create Date: 2026-07-22

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607220036"
down_revision: str | None = "202607220035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "step_run_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("step_run_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("attempt_key_hash", sa.String(length=71), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("backoff_ms", sa.Integer(), nullable=False),
        sa.Column(
            "provider_call_attempted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "credential_read_attempted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("actor_run", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "browser_run",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("llm_call", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "production_write_allowed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_step_run_attempts"),
        sa.UniqueConstraint(
            "step_run_id",
            "attempt_number",
            name="uq_step_run_attempts_step_number",
        ),
        sa.UniqueConstraint(
            "step_run_id",
            "attempt_key_hash",
            name="uq_step_run_attempts_step_key",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id", "step_run_id"],
            [
                "step_runs.workspace_id",
                "step_runs.project_id",
                "step_runs.workflow_run_id",
                "step_runs.id",
            ],
            name="fk_step_run_attempts_step_tenant",
        ),
        sa.CheckConstraint(
            "attempt_number >= 1",
            name="ck_step_run_attempts_attempt_number",
        ),
        sa.CheckConstraint(
            "status IN ('succeeded', 'retryable_error', 'timeout', 'terminal_error')",
            name="ck_step_run_attempts_status",
        ),
        sa.CheckConstraint(
            "(status = 'succeeded' AND error_code IS NULL AND backoff_ms = 0) "
            "OR (status <> 'succeeded' AND error_code IS NOT NULL)",
            name="ck_step_run_attempts_outcome",
        ),
        sa.CheckConstraint(
            "finished_at >= started_at",
            name="ck_step_run_attempts_time_order",
        ),
        sa.CheckConstraint(
            "NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT actor_run AND NOT browser_run AND NOT llm_call "
            "AND NOT production_write_allowed",
            name="ck_step_run_attempts_fixture_boundaries",
        ),
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM step_run_attempts) THEN
                RAISE EXCEPTION
                    '202607220036 downgrade refused: step attempt data exists';
            END IF;
        END $$;
        """
    )
    op.drop_table("step_run_attempts")
