"""Add durable per-step pagination checkpoints.

Revision ID: 202607230040
Revises: 202607230039
Create Date: 2026-07-23

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607230040"
down_revision: str | None = "202607230039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_step_checkpoints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execution_session_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_plan_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("step_ref", sa.String(length=500), nullable=False),
        sa.Column("requirement_ref", sa.String(length=500), nullable=False),
        sa.Column("implementation_id", sa.String(length=500), nullable=False),
        sa.Column("contract_version", sa.String(length=100), nullable=False),
        sa.Column("fixture_profile_id", sa.String(length=100), nullable=False),
        sa.Column("fixture_profile_hash", sa.String(length=71), nullable=False),
        sa.Column("step_input_digest", sa.String(length=71), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("cursor_before", sa.String(length=1000), nullable=True),
        sa.Column("cursor_before_digest", sa.String(length=71), nullable=False),
        sa.Column("cursor_after", sa.String(length=1000), nullable=True),
        sa.Column("cursor_after_digest", sa.String(length=71), nullable=True),
        sa.Column("side_effect_key_hash", sa.String(length=71), nullable=False),
        sa.Column("page_output_digest", sa.String(length=71), nullable=False),
        sa.Column("checkpoint_digest", sa.String(length=71), nullable=False),
        sa.Column("records_count", sa.Integer(), nullable=False),
        sa.Column("terminal", sa.Boolean(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
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
        sa.Column("browser_run", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("llm_call", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "raw_record_write",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "dataset_write",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "production_write_allowed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_step_checkpoints"),
        sa.UniqueConstraint(
            "execution_session_id",
            "step_ref",
            "page_number",
            name="uq_workflow_step_checkpoints_session_step_page",
        ),
        sa.UniqueConstraint(
            "execution_session_id",
            "step_ref",
            "cursor_before_digest",
            name="uq_workflow_step_checkpoints_session_step_cursor",
        ),
        sa.UniqueConstraint(
            "execution_session_id",
            "side_effect_key_hash",
            name="uq_workflow_step_checkpoints_session_side_effect_key",
        ),
        sa.ForeignKeyConstraint(
            [
                "workspace_id",
                "project_id",
                "workflow_plan_id",
                "workflow_version_id",
            ],
            [
                "workflow_versions.workspace_id",
                "workflow_versions.project_id",
                "workflow_versions.workflow_plan_id",
                "workflow_versions.id",
            ],
            name="fk_workflow_step_checkpoints_version_tenant",
        ),
        sa.CheckConstraint(
            "contract_version = 'workflow_step_checkpoint.v1'",
            name="ck_workflow_step_checkpoints_contract_version",
        ),
        sa.CheckConstraint(
            "page_number >= 1",
            name="ck_workflow_step_checkpoints_page_number",
        ),
        sa.CheckConstraint(
            "records_count >= 0",
            name="ck_workflow_step_checkpoints_records_count",
        ),
        sa.CheckConstraint(
            "(page_number = 1 AND cursor_before IS NULL) OR "
            "(page_number > 1 AND cursor_before IS NOT NULL)",
            name="ck_workflow_step_checkpoints_cursor_before",
        ),
        sa.CheckConstraint(
            "(terminal AND cursor_after IS NULL AND cursor_after_digest IS NULL) OR "
            "(NOT terminal AND cursor_after IS NOT NULL "
            "AND cursor_after_digest IS NOT NULL)",
            name="ck_workflow_step_checkpoints_cursor_after",
        ),
        sa.CheckConstraint(
            "NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT actor_run AND NOT browser_run AND NOT llm_call "
            "AND NOT raw_record_write AND NOT dataset_write "
            "AND NOT production_write_allowed",
            name="ck_workflow_step_checkpoints_fixture_boundaries",
        ),
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM workflow_step_checkpoints) THEN
                RAISE EXCEPTION
                    '202607230040 downgrade refused: checkpoint evidence exists';
            END IF;
        END $$;
        """
    )
    op.drop_table("workflow_step_checkpoints")
