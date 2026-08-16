"""Add append-only fixture Shadow comparison evidence.

Revision ID: 202607230039
Revises: 202607230038
Create Date: 2026-07-23

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607230039"
down_revision: str | None = "202607230038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_shadow_comparisons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("step_run_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_ref", sa.String(length=500), nullable=False),
        sa.Column("contract_version", sa.String(length=100), nullable=False),
        sa.Column("comparison_digest", sa.String(length=71), nullable=False),
        sa.Column("primary_implementation_id", sa.String(length=500), nullable=False),
        sa.Column("shadow_implementation_id", sa.String(length=500), nullable=False),
        sa.Column("fixture_profile_id", sa.String(length=100), nullable=False),
        sa.Column("fixture_profile_hash", sa.String(length=71), nullable=False),
        sa.Column("primary_fixture_case_id", sa.String(length=200), nullable=False),
        sa.Column("primary_fixture_content_hash", sa.String(length=71), nullable=False),
        sa.Column("shadow_fixture_case_id", sa.String(length=200), nullable=False),
        sa.Column("shadow_fixture_content_hash", sa.String(length=71), nullable=False),
        sa.Column("sample_rate", sa.Float(), nullable=False),
        sa.Column("max_items", sa.Integer(), nullable=False),
        sa.Column("sampled_items", sa.Integer(), nullable=False),
        sa.Column("matched_items", sa.Integer(), nullable=False),
        sa.Column("mismatched_items", sa.Integer(), nullable=False),
        sa.Column("primary_only_items", sa.Integer(), nullable=False),
        sa.Column("shadow_only_items", sa.Integer(), nullable=False),
        sa.Column("equivalence_status", sa.String(length=20), nullable=False),
        sa.Column("difference_evidence", sa.JSON(), nullable=False),
        sa.Column("routing_recommendation", sa.String(length=50), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column(
            "catalog_mutation_applied",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "route_ranking_mutation_applied",
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
        sa.PrimaryKeyConstraint("id", name="pk_workflow_shadow_comparisons"),
        sa.UniqueConstraint(
            "workflow_run_id",
            "step_run_id",
            name="uq_workflow_shadow_comparisons_run_step",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id"],
            ["workflow_runs.workspace_id", "workflow_runs.project_id", "workflow_runs.id"],
            name="fk_workflow_shadow_comparisons_run_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id", "step_run_id"],
            [
                "step_runs.workspace_id",
                "step_runs.project_id",
                "step_runs.workflow_run_id",
                "step_runs.id",
            ],
            name="fk_workflow_shadow_comparisons_step_tenant",
        ),
        sa.CheckConstraint(
            "contract_version = 'workflow_shadow_comparison.v1'",
            name="ck_workflow_shadow_comparisons_contract_version",
        ),
        sa.CheckConstraint(
            "sample_rate > 0 AND sample_rate <= 1 "
            "AND max_items >= 1 AND max_items <= 100 "
            "AND sampled_items >= 1 AND sampled_items <= max_items",
            name="ck_workflow_shadow_comparisons_sample_budget",
        ),
        sa.CheckConstraint(
            "matched_items >= 0 AND mismatched_items >= 0 "
            "AND primary_only_items >= 0 AND shadow_only_items >= 0 "
            "AND matched_items + mismatched_items + primary_only_items "
            "+ shadow_only_items = sampled_items",
            name="ck_workflow_shadow_comparisons_comparison_counts",
        ),
        sa.CheckConstraint(
            "equivalence_status IN ('equivalent', 'different')",
            name="ck_workflow_shadow_comparisons_equivalence_status",
        ),
        sa.CheckConstraint(
            "(equivalence_status = 'equivalent' AND matched_items = sampled_items "
            "AND routing_recommendation = 'eligible_for_governance_review') OR "
            "(equivalence_status = 'different' AND matched_items < sampled_items "
            "AND routing_recommendation = 'keep_primary_investigate_shadow')",
            name="ck_workflow_shadow_comparisons_recommendation",
        ),
        sa.CheckConstraint(
            "NOT catalog_mutation_applied AND NOT route_ranking_mutation_applied",
            name="ck_workflow_shadow_comparisons_no_automatic_governance_mutation",
        ),
        sa.CheckConstraint(
            "NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT actor_run AND NOT browser_run AND NOT llm_call "
            "AND NOT production_write_allowed",
            name="ck_workflow_shadow_comparisons_fixture_boundaries",
        ),
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM workflow_shadow_comparisons) THEN
                RAISE EXCEPTION
                    '202607230039 downgrade refused: Shadow comparison data exists';
            END IF;
        END $$;
        """
    )
    op.drop_table("workflow_shadow_comparisons")
