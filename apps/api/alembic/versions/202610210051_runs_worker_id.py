"""Add runs.worker_id for lease fencing.

Revision ID: 202610210051
Revises: 202610200050
Create Date: 2026-10-21

说明：

- 队列领取时写入 worker_id。续期、释放与终态写入都按 worker_id 做围栏。
- 租约被新 worker 接管后，旧 worker 的条件更新不再命中。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610210051"
down_revision: str | None = "202610200050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("worker_id", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("runs", "worker_id")
