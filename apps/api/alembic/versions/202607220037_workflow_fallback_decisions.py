"""Add append-only workflow fallback decision ledger.

Revision ID: 202607220037
Revises: 202607220036
Create Date: 2026-07-22

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607220037"
down_revision: str | None = "202607220036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_fallback_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_plan_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_scope", sa.String(length=500), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=71), nullable=False),
        sa.Column("request_hash", sa.String(length=71), nullable=False),
        sa.Column("step_ref", sa.String(length=500), nullable=False),
        sa.Column("requirement_ref", sa.String(length=500), nullable=False),
        sa.Column("contract_version", sa.String(length=100), nullable=False),
        sa.Column("decision_digest", sa.String(length=71), nullable=False),
        sa.Column("primary_failure_code", sa.String(length=100), nullable=False),
        sa.Column("primary_assertion_id", sa.String(length=500), nullable=False),
        sa.Column("primary_implementation_id", sa.String(length=500), nullable=False),
        sa.Column("fallback_assertion_id", sa.String(length=500), nullable=True),
        sa.Column("fallback_implementation_id", sa.String(length=500), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("gate_snapshot", sa.JSON(), nullable=False),
        sa.Column("field_difference", sa.JSON(), nullable=False),
        sa.Column("cost_snapshot", sa.JSON(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("approval_required", sa.Boolean(), nullable=False),
        sa.Column("approval_status", sa.String(length=30), nullable=False),
        sa.Column(
            "switch_executed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
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
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_fallback_decisions"),
        sa.UniqueConstraint(
            "workspace_id",
            "created_by_user_id",
            "idempotency_scope",
            "idempotency_key_hash",
            "step_ref",
            name="uq_workflow_fallback_decisions_request_step",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_plan_id", "workflow_version_id"],
            [
                "workflow_versions.workspace_id",
                "workflow_versions.project_id",
                "workflow_versions.workflow_plan_id",
                "workflow_versions.id",
            ],
            name="fk_workflow_fallback_decisions_version_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_workflow_fallback_decisions_created_by_user",
        ),
        sa.CheckConstraint(
            "contract_version = 'workflow_fallback_gate_replay.v1'",
            name="ck_workflow_fallback_decisions_contract_version",
        ),
        sa.CheckConstraint(
            "outcome IN ('eligible', 'blocked')",
            name="ck_workflow_fallback_decisions_outcome",
        ),
        sa.CheckConstraint(
            "((fallback_assertion_id IS NULL AND fallback_implementation_id IS NULL) "
            "OR (fallback_assertion_id IS NOT NULL "
            "AND fallback_implementation_id IS NOT NULL)) "
            "AND (outcome <> 'eligible' OR fallback_implementation_id IS NOT NULL)",
            name="ck_workflow_fallback_decisions_candidate_identity",
        ),
        sa.CheckConstraint(
            "NOT switch_executed",
            name="ck_workflow_fallback_decisions_no_silent_switch",
        ),
        sa.CheckConstraint(
            "NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT actor_run AND NOT browser_run AND NOT llm_call "
            "AND NOT production_write_allowed",
            name="ck_workflow_fallback_decisions_fixture_boundaries",
        ),
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM workflow_fallback_decisions) THEN
                RAISE EXCEPTION
                    '202607220037 downgrade refused: fallback decision data exists';
            END IF;
        END $$;
        """
    )
    op.drop_table("workflow_fallback_decisions")
