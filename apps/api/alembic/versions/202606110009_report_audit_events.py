"""Create report audit events table.

Revision ID: 202606110009
Revises: 202606110008
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110009"
down_revision: str | None = "202606110008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_column(name: str) -> sa.Column[sa.DateTime]:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "report_audit_events",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        timestamp_column("created_at"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_report_audit_events_report_created",
        "report_audit_events",
        ["report_id", "created_at"],
    )
    op.create_index(
        "ix_report_audit_events_workspace_created",
        "report_audit_events",
        ["workspace_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_report_audit_events_workspace_created", table_name="report_audit_events")
    op.drop_index("ix_report_audit_events_report_created", table_name="report_audit_events")
    op.drop_table("report_audit_events")
