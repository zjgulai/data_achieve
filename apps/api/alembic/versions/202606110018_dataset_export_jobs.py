"""Create dataset export job table.

Revision ID: 202606110018
Revises: 202606110017
Create Date: 2026-06-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110018"
down_revision: str | None = "202606110017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dataset_export_jobs",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("export_format", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("artifact_path", sa.Text(), nullable=False),
        sa.Column("artifact_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("audit_events", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"]),
        sa.ForeignKeyConstraint(["dataset_version_id"], ["dataset_versions.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dataset_export_jobs_dataset",
        "dataset_export_jobs",
        ["dataset_id", "created_at"],
    )
    op.create_index(
        "ix_dataset_export_jobs_version",
        "dataset_export_jobs",
        ["dataset_version_id", "created_at"],
    )
    op.create_index(
        "ix_dataset_export_jobs_workspace",
        "dataset_export_jobs",
        ["workspace_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_dataset_export_jobs_workspace", table_name="dataset_export_jobs")
    op.drop_index("ix_dataset_export_jobs_version", table_name="dataset_export_jobs")
    op.drop_index("ix_dataset_export_jobs_dataset", table_name="dataset_export_jobs")
    op.drop_table("dataset_export_jobs")
