"""Create browser diagnostic run assets.

Revision ID: 202606110021
Revises: 202606110020
Create Date: 2026-06-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110021"
down_revision: str | None = "202606110020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "browser_diagnostic_runs",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("site_analysis_id", sa.Uuid(), nullable=True),
        sa.Column("requested_url", sa.Text(), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("authorization_confirmed", sa.Boolean(), nullable=False),
        sa.Column("schema_version", sa.String(length=80), nullable=False),
        sa.Column("recommended_path", sa.String(length=80), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("field_stability", sa.String(length=30), nullable=True),
        sa.Column("evidence_source", sa.String(length=120), nullable=False),
        sa.Column("screenshot_path", sa.Text(), nullable=True),
        sa.Column("run_policy", sa.JSON(), nullable=False),
        sa.Column("page_summary", sa.JSON(), nullable=False),
        sa.Column("network_summary", sa.JSON(), nullable=False),
        sa.Column("accessibility_summary", sa.JSON(), nullable=False),
        sa.Column("risk_flags", sa.JSON(), nullable=False),
        sa.Column("extraction_strategy", sa.JSON(), nullable=False),
        sa.Column("diagnostic_payload", sa.JSON(), nullable=False),
        sa.Column("blocked_reasons", sa.JSON(), nullable=False),
        sa.Column("run_started", sa.Boolean(), nullable=False),
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
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["site_analysis_id"], ["site_analyses.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_browser_diagnostic_runs_workspace_created",
        "browser_diagnostic_runs",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_browser_diagnostic_runs_project_created",
        "browser_diagnostic_runs",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_browser_diagnostic_runs_site_analysis",
        "browser_diagnostic_runs",
        ["site_analysis_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_browser_diagnostic_runs_site_analysis",
        table_name="browser_diagnostic_runs",
    )
    op.drop_index(
        "ix_browser_diagnostic_runs_project_created",
        table_name="browser_diagnostic_runs",
    )
    op.drop_index(
        "ix_browser_diagnostic_runs_workspace_created",
        table_name="browser_diagnostic_runs",
    )
    op.drop_table("browser_diagnostic_runs")
