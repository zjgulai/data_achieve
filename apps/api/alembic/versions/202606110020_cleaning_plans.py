"""Create cleaning plan assets.

Revision ID: 202606110020
Revises: 202606110019
Create Date: 2026-06-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110020"
down_revision: str | None = "202606110019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cleaning_plans",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("target", sa.String(length=50), nullable=False),
        sa.Column("selected_fields", sa.JSON(), nullable=False),
        sa.Column("source_task_run_ids", sa.JSON(), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("cleaning_script", sa.JSON(), nullable=False),
        sa.Column("dry_run_preview", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
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
        sa.UniqueConstraint(
            "workspace_id",
            "name",
            "version_number",
            name="uq_cleaning_plans_workspace_name_version",
        ),
    )
    op.create_index(
        "ix_cleaning_plans_workspace_created",
        "cleaning_plans",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_cleaning_plans_project_created",
        "cleaning_plans",
        ["project_id", "created_at"],
    )
    op.add_column(
        "dataset_versions",
        sa.Column("cleaning_plan_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_dataset_versions_cleaning_plan_id_cleaning_plans",
        "dataset_versions",
        "cleaning_plans",
        ["cleaning_plan_id"],
        ["id"],
    )
    op.create_index(
        "ix_dataset_versions_cleaning_plan_id",
        "dataset_versions",
        ["cleaning_plan_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_dataset_versions_cleaning_plan_id", table_name="dataset_versions")
    op.drop_constraint(
        "fk_dataset_versions_cleaning_plan_id_cleaning_plans",
        "dataset_versions",
        type_="foreignkey",
    )
    op.drop_column("dataset_versions", "cleaning_plan_id")
    op.drop_index("ix_cleaning_plans_project_created", table_name="cleaning_plans")
    op.drop_index("ix_cleaning_plans_workspace_created", table_name="cleaning_plans")
    op.drop_table("cleaning_plans")
