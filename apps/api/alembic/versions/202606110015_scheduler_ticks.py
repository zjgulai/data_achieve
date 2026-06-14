"""Create scheduler tick observability table.

Revision ID: 202606110015
Revises: 202606110014
Create Date: 2026-06-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110015"
down_revision: str | None = "202606110014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scheduler_ticks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lease_name", sa.String(length=100), nullable=False),
        sa.Column("owner_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("lock_acquired", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scanned", sa.Integer(), nullable=False),
        sa.Column("due", sa.Integer(), nullable=False),
        sa.Column("started", sa.Integer(), nullable=False),
        sa.Column("skipped_running", sa.Integer(), nullable=False),
        sa.Column("skipped_invalid_schedule", sa.Integer(), nullable=False),
        sa.Column("task_errors", sa.Integer(), nullable=False),
        sa.Column("report_subscriptions_scanned", sa.Integer(), nullable=False),
        sa.Column("report_subscriptions_due", sa.Integer(), nullable=False),
        sa.Column("report_subscriptions_started", sa.Integer(), nullable=False),
        sa.Column("report_subscriptions_skipped_running", sa.Integer(), nullable=False),
        sa.Column("report_subscription_errors", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scheduler_ticks_finished_at",
        "scheduler_ticks",
        ["finished_at"],
    )
    op.create_index(
        "ix_scheduler_ticks_status",
        "scheduler_ticks",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_scheduler_ticks_status", table_name="scheduler_ticks")
    op.drop_index("ix_scheduler_ticks_finished_at", table_name="scheduler_ticks")
    op.drop_table("scheduler_ticks")
