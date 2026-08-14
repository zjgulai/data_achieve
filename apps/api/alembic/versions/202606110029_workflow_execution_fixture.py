"""Add Primary-only fixture WorkflowRun persistence.

Revision ID: 202606110029
Revises: 202606110028
Create Date: 2026-07-15
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.sql.elements import conv

from alembic import op

revision: str = "202606110029"
down_revision: str | None = "202606110028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WORKFLOW_EXECUTION_TABLES: tuple[str, ...] = (
    "workflow_runs",
    "step_runs",
    "workflow_run_requests",
)


def _uuid_primary_key() -> sa.Column[UUID]:
    return sa.Column("id", sa.Uuid(), nullable=False)


def _created_at() -> sa.Column[datetime]:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def _false_flag(name: str) -> sa.Column[bool]:
    return sa.Column(
        name,
        sa.Boolean(),
        server_default=sa.false(),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "workflow_runs",
        _uuid_primary_key(),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_plan_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "execution_contract_version",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column("execution_mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "planner_contract_version",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column("preview_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("catalog_snapshot_id", sa.String(length=100), nullable=False),
        sa.Column("policy_version", sa.String(length=100), nullable=False),
        sa.Column("mode_template_version", sa.String(length=100), nullable=False),
        sa.Column("query_versions", sa.JSON(), nullable=False),
        sa.Column("fixture_profile_id", sa.String(length=100), nullable=False),
        sa.Column("fixture_profile_hash", sa.String(length=71), nullable=False),
        sa.Column("total_steps", sa.Integer(), nullable=False),
        sa.Column("completed_steps", sa.Integer(), nullable=False),
        sa.Column("records_count", sa.Integer(), nullable=False),
        _false_flag("provider_call_attempted"),
        _false_flag("credential_read_attempted"),
        _false_flag("actor_run"),
        _false_flag("browser_run"),
        _false_flag("llm_call"),
        _false_flag("production_write_allowed"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "execution_contract_version = 'workflow_execution_fixture.v1'",
            name=conv("ck_workflow_runs_execution_contract"),
        ),
        sa.CheckConstraint(
            "execution_mode = 'fixture'",
            name=conv("ck_workflow_runs_execution_mode"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'ready', 'running', 'completed', 'degraded', "
            "'held', 'cancelled')",
            name=conv("ck_workflow_runs_status"),
        ),
        sa.CheckConstraint(
            "total_steps >= 1 AND completed_steps >= 0 "
            "AND completed_steps <= total_steps AND records_count >= 0",
            name=conv("ck_workflow_runs_counts"),
        ),
        sa.CheckConstraint(
            "status <> 'completed' OR (completed_steps = total_steps "
            "AND records_count >= 1 AND finished_at >= started_at)",
            name=conv("ck_workflow_runs_completed_snapshot"),
        ),
        sa.CheckConstraint(
            "NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT actor_run AND NOT browser_run AND NOT llm_call "
            "AND NOT production_write_allowed",
            name=conv("ck_workflow_runs_fixture_boundaries"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_workflow_runs_created_by_user",
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
            name="fk_workflow_runs_version_tenant",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_runs"),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_runs_tenant_id",
        ),
    )

    op.create_table(
        "step_runs",
        _uuid_primary_key(),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("step_ref", sa.String(length=500), nullable=False),
        sa.Column("requirement_ref", sa.String(length=500), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=30), nullable=False),
        sa.Column("resource_type", sa.String(length=40), nullable=False),
        sa.Column("operation", sa.String(length=40), nullable=False),
        sa.Column("assertion_id", sa.String(length=500), nullable=False),
        sa.Column("implementation_id", sa.String(length=500), nullable=False),
        sa.Column("route_plan_snapshot", sa.JSON(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("fixture_case_id", sa.String(length=200), nullable=False),
        sa.Column("fixture_content_hash", sa.String(length=71), nullable=False),
        sa.Column("input_digest", sa.String(length=71), nullable=False),
        sa.Column("output_digest", sa.String(length=71), nullable=False),
        sa.Column("idempotency_scope", sa.String(length=500), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=71), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("records_count", sa.Integer(), nullable=False),
        _false_flag("provider_call_attempted"),
        _false_flag("credential_read_attempted"),
        _false_flag("actor_run"),
        _false_flag("browser_run"),
        _false_flag("llm_call"),
        _false_flag("production_write_allowed"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        _created_at(),
        sa.CheckConstraint("sequence >= 1", name=conv("ck_step_runs_sequence")),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed')",
            name=conv("ck_step_runs_status"),
        ),
        sa.CheckConstraint(
            "records_count >= 1",
            name=conv("ck_step_runs_records_count"),
        ),
        sa.CheckConstraint(
            "status <> 'completed' OR finished_at >= started_at",
            name=conv("ck_step_runs_completed_snapshot"),
        ),
        sa.CheckConstraint(
            "NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT actor_run AND NOT browser_run AND NOT llm_call "
            "AND NOT production_write_allowed",
            name=conv("ck_step_runs_fixture_boundaries"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id"],
            [
                "workflow_runs.workspace_id",
                "workflow_runs.project_id",
                "workflow_runs.id",
            ],
            name="fk_step_runs_run_tenant",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_step_runs"),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_step_runs_tenant_id",
        ),
        sa.UniqueConstraint(
            "workflow_run_id",
            "step_ref",
            name="uq_step_runs_run_step_ref",
        ),
        sa.UniqueConstraint(
            "workflow_run_id",
            "requirement_ref",
            "implementation_id",
            name="uq_step_runs_run_requirement_implementation",
        ),
    )

    op.create_table(
        "workflow_run_requests",
        _uuid_primary_key(),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_scope", sa.String(length=500), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=71), nullable=False),
        sa.Column("request_hash", sa.String(length=71), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "outcome = 'completed'",
            name=conv("ck_workflow_run_requests_outcome"),
        ),
        sa.CheckConstraint(
            "response_status BETWEEN 200 AND 599",
            name=conv("ck_workflow_run_requests_response_status"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_workflow_run_requests_created_by_user",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id"],
            [
                "workflow_runs.workspace_id",
                "workflow_runs.project_id",
                "workflow_runs.id",
            ],
            name="fk_workflow_run_requests_run_tenant",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_run_requests"),
        sa.UniqueConstraint(
            "workspace_id",
            "created_by_user_id",
            "idempotency_scope",
            "idempotency_key_hash",
            name="uq_workflow_run_requests_idempotency",
        ),
    )


def downgrade() -> None:
    for table_name in reversed(WORKFLOW_EXECUTION_TABLES):
        op.drop_table(table_name)
