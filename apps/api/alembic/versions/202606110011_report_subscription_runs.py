"""Create report subscription runs table.

Revision ID: 202606110011
Revises: 202606110010
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110011"
down_revision: str | None = "202606110010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_subscription_runs",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=True),
        sa.Column("trigger_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("delivered_channels", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("skipped_channels", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"]),
        sa.ForeignKeyConstraint(["subscription_id"], ["report_subscriptions.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_report_subscription_runs_subscription_started",
        "report_subscription_runs",
        ["subscription_id", "started_at"],
    )
    op.create_index(
        "ix_report_subscription_runs_workspace_started",
        "report_subscription_runs",
        ["workspace_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_report_subscription_runs_workspace_started",
        table_name="report_subscription_runs",
    )
    op.drop_index(
        "ix_report_subscription_runs_subscription_started",
        table_name="report_subscription_runs",
    )
    op.drop_table("report_subscription_runs")
