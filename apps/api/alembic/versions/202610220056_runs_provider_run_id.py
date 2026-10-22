"""Add runs.provider_run_id for durable external execution identity.

Revision ID: 202610220056
Revises: 202610210055
Create Date: 2026-10-22

说明：

- Exa Agent POST 成功后立即把远端 run id 写入已提交的 runs 行。
- Worker 租约接管或进程重启后读取该列，只轮询，不再重复付费提交。
- task_runs.provider_run_id 继续作为调用级镜像，不承担队列幂等权威。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610220056"
down_revision: str | None = "202610210055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("provider_run_id", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("runs", "provider_run_id")
