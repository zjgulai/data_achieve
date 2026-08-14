"""Create email provider live gate run table.

Revision ID: 202606110025
Revises: 202606110024
Create Date: 2026-06-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110025"
down_revision: str | None = "202606110024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_provider_live_gate_runs",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=80), nullable=False),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("max_provider_calls", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_snapshot", sa.JSON(), nullable=False),
        sa.Column("request_snapshot", sa.JSON(), nullable=False),
        sa.Column("decision_snapshot", sa.JSON(), nullable=False),
        sa.Column("provider_call_allowed", sa.Boolean(), nullable=False),
        sa.Column("email_send_allowed", sa.Boolean(), nullable=False),
        sa.Column("production_write_allowed", sa.Boolean(), nullable=False),
        sa.Column("provider_call_attempted", sa.Boolean(), nullable=False),
        sa.Column("idempotency_scope", sa.String(length=80), nullable=True),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_email_provider_live_gate_runs_workspace_created",
        "email_provider_live_gate_runs",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_email_provider_live_gate_runs_user_created",
        "email_provider_live_gate_runs",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_email_provider_live_gate_runs_idempotency",
        "email_provider_live_gate_runs",
        ["workspace_id", "user_id", "idempotency_scope", "idempotency_key_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_provider_live_gate_runs_idempotency",
        table_name="email_provider_live_gate_runs",
    )
    op.drop_index(
        "ix_email_provider_live_gate_runs_user_created",
        table_name="email_provider_live_gate_runs",
    )
    op.drop_index(
        "ix_email_provider_live_gate_runs_workspace_created",
        table_name="email_provider_live_gate_runs",
    )
    op.drop_table("email_provider_live_gate_runs")
