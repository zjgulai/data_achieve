"""Add Provider health snapshots and versioned route feedback.

Revision ID: 202607230042
Revises: 202607230041
Create Date: 2026-07-23

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607230042"
down_revision: str | None = "202607230041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _fixture_boundary_columns() -> tuple[sa.Column[bool], ...]:
    return tuple(
        sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.false())
        for name in (
            "health_probe_attempted",
            "provider_call_attempted",
            "credential_read_attempted",
            "actor_run",
            "browser_run",
            "llm_call",
            "raw_record_write",
            "dataset_write",
            "production_write_allowed",
        )
    )


def upgrade() -> None:
    op.create_table(
        "provider_health_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("contract_version", sa.String(length=100), nullable=False),
        sa.Column("scope_key", sa.String(length=71), nullable=False),
        sa.Column("aggregation_key", sa.String(length=71), nullable=False),
        sa.Column("snapshot_version", sa.Integer(), nullable=False),
        sa.Column("platform_id", sa.String(length=200), nullable=False),
        sa.Column("implementation_id", sa.String(length=200), nullable=False),
        sa.Column("resource_type", sa.String(length=200), nullable=False),
        sa.Column("operation", sa.String(length=200), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("timeout_count", sa.Integer(), nullable=False),
        sa.Column("rate_limited_count", sa.Integer(), nullable=False),
        sa.Column("transient_error_count", sa.Integer(), nullable=False),
        sa.Column("terminal_error_count", sa.Integer(), nullable=False),
        sa.Column("success_rate_bps", sa.Integer(), nullable=False),
        sa.Column("p95_latency_ms", sa.Integer(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("policy_snapshot", sa.JSON(), nullable=False),
        sa.Column("observation_manifest", sa.JSON(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("previous_snapshot_digest", sa.String(length=71), nullable=True),
        sa.Column("snapshot_digest", sa.String(length=71), nullable=False),
        sa.Column("routing_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_retain_until", sa.DateTime(timezone=True), nullable=False),
        *_fixture_boundary_columns(),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_provider_health_snapshots"),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "scope_key",
            "snapshot_version",
            name="uq_provider_health_snapshots_scope_version",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "aggregation_key",
            name="uq_provider_health_snapshots_aggregation",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "snapshot_digest",
            name="uq_provider_health_snapshots_digest",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_provider_health_snapshots_project_tenant",
        ),
        sa.CheckConstraint(
            "contract_version = 'provider_health_snapshot.v1'",
            name="ck_provider_health_snapshots_contract_version",
        ),
        sa.CheckConstraint(
            "snapshot_version >= 1",
            name="ck_provider_health_snapshots_version",
        ),
        sa.CheckConstraint(
            "status IN ('unknown', 'healthy', 'degraded', 'unhealthy')",
            name="ck_provider_health_snapshots_status",
        ),
        sa.CheckConstraint(
            "sample_count >= 1 AND success_count >= 0 AND timeout_count >= 0 "
            "AND rate_limited_count >= 0 AND transient_error_count >= 0 "
            "AND terminal_error_count >= 0 AND success_count + timeout_count "
            "+ rate_limited_count + transient_error_count + terminal_error_count "
            "= sample_count",
            name="ck_provider_health_snapshots_counts",
        ),
        sa.CheckConstraint(
            "success_rate_bps >= 0 AND success_rate_bps <= 10000 AND p95_latency_ms >= 0",
            name="ck_provider_health_snapshots_metrics",
        ),
        sa.CheckConstraint(
            "window_ended_at > window_started_at AND evaluated_at >= window_ended_at "
            "AND routing_valid_until > evaluated_at "
            "AND evidence_retain_until > routing_valid_until",
            name="ck_provider_health_snapshots_time_order",
        ),
        sa.CheckConstraint(
            "NOT health_probe_attempted AND NOT provider_call_attempted "
            "AND NOT credential_read_attempted AND NOT actor_run "
            "AND NOT browser_run AND NOT llm_call AND NOT raw_record_write "
            "AND NOT dataset_write AND NOT production_write_allowed",
            name="ck_provider_health_snapshots_fixture_boundaries",
        ),
    )
    op.create_table(
        "provider_health_route_feedbacks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("contract_version", sa.String(length=100), nullable=False),
        sa.Column("route_key", sa.String(length=500), nullable=False),
        sa.Column("feedback_key", sa.String(length=71), nullable=False),
        sa.Column("feedback_version", sa.Integer(), nullable=False),
        sa.Column("platform_id", sa.String(length=200), nullable=False),
        sa.Column("resource_type", sa.String(length=200), nullable=False),
        sa.Column("operation", sa.String(length=200), nullable=False),
        sa.Column("original_candidate_order", sa.JSON(), nullable=False),
        sa.Column("adjusted_candidate_order", sa.JSON(), nullable=False),
        sa.Column("candidate_score_manifest", sa.JSON(), nullable=False),
        sa.Column("source_snapshot_manifest", sa.JSON(), nullable=False),
        sa.Column("ranking_changed", sa.Boolean(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("previous_feedback_digest", sa.String(length=71), nullable=True),
        sa.Column("feedback_digest", sa.String(length=71), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_retain_until", sa.DateTime(timezone=True), nullable=False),
        *_fixture_boundary_columns(),
        sa.Column(
            "catalog_mutation_applied",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "automatic_route_switch_executed",
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
        sa.PrimaryKeyConstraint("id", name="pk_provider_health_route_feedbacks"),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "route_key",
            "feedback_version",
            name="uq_provider_health_feedbacks_route_version",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "feedback_key",
            name="uq_provider_health_feedbacks_key",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "feedback_digest",
            name="uq_provider_health_feedbacks_digest",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_provider_health_feedbacks_project_tenant",
        ),
        sa.CheckConstraint(
            "contract_version = 'provider_health_route_feedback.v1'",
            name="ck_provider_health_route_feedbacks_contract_version",
        ),
        sa.CheckConstraint(
            "feedback_version >= 1",
            name="ck_provider_health_route_feedbacks_version",
        ),
        sa.CheckConstraint(
            "evidence_retain_until > evaluated_at",
            name="ck_provider_health_route_feedbacks_retention",
        ),
        sa.CheckConstraint(
            "NOT health_probe_attempted AND NOT catalog_mutation_applied "
            "AND NOT automatic_route_switch_executed "
            "AND NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT actor_run AND NOT browser_run AND NOT llm_call "
            "AND NOT raw_record_write AND NOT dataset_write "
            "AND NOT production_write_allowed",
            name="ck_provider_health_route_feedbacks_fixture_boundaries",
        ),
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM provider_health_route_feedbacks)
               OR EXISTS (SELECT 1 FROM provider_health_snapshots) THEN
                RAISE EXCEPTION
                    '202607230042 downgrade refused: Provider health evidence exists';
            END IF;
        END $$;
        """
    )
    op.drop_table("provider_health_route_feedbacks")
    op.drop_table("provider_health_snapshots")
