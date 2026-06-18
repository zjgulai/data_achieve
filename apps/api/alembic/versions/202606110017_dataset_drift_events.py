"""Create dataset drift event table.

Revision ID: 202606110017
Revises: 202606110016
Create Date: 2026-06-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110017"
down_revision: str | None = "202606110016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dataset_drift_events",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("thresholds", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("audit_events", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"]),
        sa.ForeignKeyConstraint(["dataset_version_id"], ["dataset_versions.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dataset_drift_events_dataset",
        "dataset_drift_events",
        ["dataset_id", "created_at"],
    )
    op.create_index(
        "ix_dataset_drift_events_workspace",
        "dataset_drift_events",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_dataset_drift_events_version",
        "dataset_drift_events",
        ["dataset_version_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_dataset_drift_events_version", table_name="dataset_drift_events")
    op.drop_index("ix_dataset_drift_events_workspace", table_name="dataset_drift_events")
    op.drop_index("ix_dataset_drift_events_dataset", table_name="dataset_drift_events")
    op.drop_table("dataset_drift_events")
