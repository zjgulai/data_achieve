"""Create site analysis and extraction plan tables.

Revision ID: 202606110019
Revises: 202606110018
Create Date: 2026-06-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110019"
down_revision: str | None = "202606110018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "site_analyses",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("requested_url", sa.Text(), nullable=False),
        sa.Column("target", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("authorization_confirmed", sa.Boolean(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("platform_profile", sa.JSON(), nullable=False),
        sa.Column("page_structure", sa.JSON(), nullable=False),
        sa.Column("field_candidates", sa.JSON(), nullable=False),
        sa.Column("tool_recommendations", sa.JSON(), nullable=False),
        sa.Column("cleaning_plan", sa.JSON(), nullable=False),
        sa.Column("source_draft", sa.JSON(), nullable=False),
        sa.Column("blocked_reasons", sa.JSON(), nullable=False),
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
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "extraction_plans",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("site_analysis_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("collector_type", sa.String(length=80), nullable=False),
        sa.Column("selected_fields", sa.JSON(), nullable=False),
        sa.Column("source_draft", sa.JSON(), nullable=False),
        sa.Column("schedule_cron", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("risk_level", sa.String(length=30), nullable=False),
        sa.Column("audit_events", sa.JSON(), nullable=False),
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
        sa.UniqueConstraint(
            "site_analysis_id",
            "version_number",
            name="uq_extraction_plans_site_analysis_version",
        ),
    )
    op.create_index(
        "ix_site_analyses_workspace_created",
        "site_analyses",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_site_analyses_project_created",
        "site_analyses",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_extraction_plans_site_analysis_version",
        "extraction_plans",
        ["site_analysis_id", "version_number"],
    )
    op.create_index(
        "ix_extraction_plans_workspace_created",
        "extraction_plans",
        ["workspace_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_extraction_plans_workspace_created", table_name="extraction_plans")
    op.drop_index("ix_extraction_plans_site_analysis_version", table_name="extraction_plans")
    op.drop_index("ix_site_analyses_project_created", table_name="site_analyses")
    op.drop_index("ix_site_analyses_workspace_created", table_name="site_analyses")
    op.drop_table("extraction_plans")
    op.drop_table("site_analyses")
