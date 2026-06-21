"""Create browser diagnostic local run assets.

Revision ID: 202606110023
Revises: 202606110022
Create Date: 2026-06-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110023"
down_revision: str | None = "202606110022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "browser_diagnostic_job_runs",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("browser_diagnostic_job_id", sa.Uuid(), nullable=False),
        sa.Column("site_analysis_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_plan_id", sa.Uuid(), nullable=False),
        sa.Column("browser_diagnostic_run_id", sa.Uuid(), nullable=False),
        sa.Column("requested_url", sa.Text(), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("runner", sa.String(length=80), nullable=False),
        sa.Column("run_mode", sa.String(length=80), nullable=False),
        sa.Column("contract_snapshot", sa.JSON(), nullable=False),
        sa.Column("artifact_manifest", sa.JSON(), nullable=False),
        sa.Column("selector_results", sa.JSON(), nullable=False),
        sa.Column("preview_rows", sa.JSON(), nullable=False),
        sa.Column("network_observation_summary", sa.JSON(), nullable=False),
        sa.Column("error_summary", sa.JSON(), nullable=False),
        sa.Column("blocked_reasons", sa.JSON(), nullable=False),
        sa.Column("audit_events", sa.JSON(), nullable=False),
        sa.Column("execution_started", sa.Boolean(), nullable=False),
        sa.Column("browser_started", sa.Boolean(), nullable=False),
        sa.Column("files_written", sa.Boolean(), nullable=False),
        sa.Column("collection_resources_written", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["browser_diagnostic_job_id"],
            ["browser_diagnostic_jobs.id"],
        ),
        sa.ForeignKeyConstraint(["browser_diagnostic_run_id"], ["browser_diagnostic_runs.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["extraction_plan_id"], ["extraction_plans.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["site_analysis_id"], ["site_analyses.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_browser_diagnostic_job_runs_workspace_created",
        "browser_diagnostic_job_runs",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_browser_diagnostic_job_runs_project_created",
        "browser_diagnostic_job_runs",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_browser_diagnostic_job_runs_job_created",
        "browser_diagnostic_job_runs",
        ["browser_diagnostic_job_id", "created_at"],
    )
    op.create_index(
        "ix_browser_diagnostic_job_runs_status",
        "browser_diagnostic_job_runs",
        ["workspace_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_browser_diagnostic_job_runs_status",
        table_name="browser_diagnostic_job_runs",
    )
    op.drop_index(
        "ix_browser_diagnostic_job_runs_job_created",
        table_name="browser_diagnostic_job_runs",
    )
    op.drop_index(
        "ix_browser_diagnostic_job_runs_project_created",
        table_name="browser_diagnostic_job_runs",
    )
    op.drop_index(
        "ix_browser_diagnostic_job_runs_workspace_created",
        table_name="browser_diagnostic_job_runs",
    )
    op.drop_table("browser_diagnostic_job_runs")
