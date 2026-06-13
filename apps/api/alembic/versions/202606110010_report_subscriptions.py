"""Create report subscriptions table.

Revision ID: 202606110010
Revises: 202606110009
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110010"
down_revision: str | None = "202606110009"
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
        "report_subscriptions",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("report_type", sa.String(length=20), nullable=False, server_default="daily"),
        sa.Column("schedule_time", sa.String(length=5), nullable=False, server_default="09:00"),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Asia/Shanghai"),
        sa.Column("channels", sa.JSON(), nullable=False, server_default=sa.text("'[\"in_app\"]'")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_report_subscriptions_workspace_enabled",
        "report_subscriptions",
        ["workspace_id", "enabled"],
    )
    op.create_index(
        "uq_report_subscriptions_global",
        "report_subscriptions",
        ["workspace_id", "user_id", "report_type"],
        unique=True,
        postgresql_where=sa.text("project_id IS NULL"),
    )
    op.create_index(
        "uq_report_subscriptions_project",
        "report_subscriptions",
        ["workspace_id", "user_id", "project_id", "report_type"],
        unique=True,
        postgresql_where=sa.text("project_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_report_subscriptions_project", table_name="report_subscriptions")
    op.drop_index("uq_report_subscriptions_global", table_name="report_subscriptions")
    op.drop_index("ix_report_subscriptions_workspace_enabled", table_name="report_subscriptions")
    op.drop_table("report_subscriptions")
