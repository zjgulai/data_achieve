"""Create signals table.

Revision ID: 202606110006
Revises: 202606110005
Create Date: 2026-06-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110006"
down_revision: str | None = "202606110005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "signals",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("signal_type", sa.String(length=30), nullable=False),
        sa.Column("previous_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("current_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("current_value", sa.Float(), nullable=True),
        sa.Column("previous_value", sa.Float(), nullable=True),
        sa.Column("delta", sa.Float(), nullable=True),
        sa.Column("delta_ratio", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["current_snapshot_id"], ["entity_snapshots.id"]),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["previous_snapshot_id"], ["entity_snapshots.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signals_entity_detected", "signals", ["entity_id", "detected_at"])
    op.create_index(
        "ix_signals_project_type_detected",
        "signals",
        ["project_id", "signal_type", "detected_at"],
    )
    op.create_index(
        "ix_signals_snapshot_pair",
        "signals",
        ["signal_type", "previous_snapshot_id", "current_snapshot_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_signals_snapshot_pair", table_name="signals")
    op.drop_index("ix_signals_project_type_detected", table_name="signals")
    op.drop_index("ix_signals_entity_detected", table_name="signals")
    op.drop_table("signals")
