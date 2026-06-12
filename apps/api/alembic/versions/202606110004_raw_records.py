"""Create raw record table.

Revision ID: 202606110004
Revises: 202606110003
Create Date: 2026-06-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110004"
down_revision: str | None = "202606110003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "raw_records",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("task_run_id", sa.Uuid(), nullable=False),
        sa.Column("record_type", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("screenshot_url", sa.Text(), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.ForeignKeyConstraint(["task_run_id"], ["task_runs.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "content_hash", name="uq_raw_records_source_content_hash"),
    )
    op.create_index(
        "ix_raw_records_workspace_created",
        "raw_records",
        ["workspace_id", "created_at"],
    )
    op.create_index("ix_raw_records_source_collected", "raw_records", ["source_id", "collected_at"])
    op.create_index("ix_raw_records_task_run", "raw_records", ["task_run_id"])
    op.create_index(op.f("ix_raw_records_content_hash"), "raw_records", ["content_hash"])


def downgrade() -> None:
    op.drop_index(op.f("ix_raw_records_content_hash"), table_name="raw_records")
    op.drop_index("ix_raw_records_task_run", table_name="raw_records")
    op.drop_index("ix_raw_records_source_collected", table_name="raw_records")
    op.drop_index("ix_raw_records_workspace_created", table_name="raw_records")
    op.drop_table("raw_records")
