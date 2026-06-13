"""Create scheduler leases table.

Revision ID: 202606110012
Revises: 202606110011
Create Date: 2026-06-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110012"
down_revision: str | None = "202606110011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scheduler_leases",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("owner_id", sa.String(length=100), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_index(
        "ix_scheduler_leases_expires_at",
        "scheduler_leases",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_scheduler_leases_expires_at", table_name="scheduler_leases")
    op.drop_table("scheduler_leases")
