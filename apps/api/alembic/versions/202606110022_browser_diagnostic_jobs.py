"""Create browser diagnostic job assets.

Revision ID: 202606110022
Revises: 202606110021
Create Date: 2026-06-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110022"
down_revision: str | None = "202606110021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "browser_diagnostic_jobs",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("site_analysis_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_plan_id", sa.Uuid(), nullable=False),
        sa.Column("browser_diagnostic_run_id", sa.Uuid(), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("requested_url", sa.Text(), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("authorization_confirmed", sa.Boolean(), nullable=False),
        sa.Column("runner", sa.String(length=80), nullable=False),
        sa.Column("execution_mode", sa.String(length=80), nullable=False),
        sa.Column("selector_scope", sa.JSON(), nullable=False),
        sa.Column("wait_policy", sa.JSON(), nullable=False),
        sa.Column("network_observation_policy", sa.JSON(), nullable=False),
        sa.Column("artifact_policy", sa.JSON(), nullable=False),
        sa.Column("safety_flags", sa.JSON(), nullable=False),
        sa.Column("dry_run_summary", sa.JSON(), nullable=False),
        sa.Column("executable_spec_snapshot", sa.JSON(), nullable=False),
        sa.Column("blocked_reasons", sa.JSON(), nullable=False),
        sa.Column("audit_events", sa.JSON(), nullable=False),
        sa.Column("run_started", sa.Boolean(), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["browser_diagnostic_run_id"], ["browser_diagnostic_runs.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["extraction_plan_id"], ["extraction_plans.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["site_analysis_id"], ["site_analyses.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "request_fingerprint",
            name="uq_browser_diagnostic_jobs_workspace_fingerprint",
        ),
    )
    op.create_index(
        "ix_browser_diagnostic_jobs_workspace_created",
        "browser_diagnostic_jobs",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_browser_diagnostic_jobs_project_created",
        "browser_diagnostic_jobs",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_browser_diagnostic_jobs_site_analysis",
        "browser_diagnostic_jobs",
        ["site_analysis_id"],
    )
    op.create_index(
        "ix_browser_diagnostic_jobs_extraction_plan",
        "browser_diagnostic_jobs",
        ["extraction_plan_id"],
    )
    op.create_index(
        "ix_browser_diagnostic_jobs_status",
        "browser_diagnostic_jobs",
        ["workspace_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_browser_diagnostic_jobs_status", table_name="browser_diagnostic_jobs")
    op.drop_index(
        "ix_browser_diagnostic_jobs_extraction_plan",
        table_name="browser_diagnostic_jobs",
    )
    op.drop_index(
        "ix_browser_diagnostic_jobs_site_analysis",
        table_name="browser_diagnostic_jobs",
    )
    op.drop_index(
        "ix_browser_diagnostic_jobs_project_created",
        table_name="browser_diagnostic_jobs",
    )
    op.drop_index(
        "ix_browser_diagnostic_jobs_workspace_created",
        table_name="browser_diagnostic_jobs",
    )
    op.drop_table("browser_diagnostic_jobs")
