"""Add per-day quota counters to project_api_keys.

Revision ID: 202610210052
Revises: 202610210051
Create Date: 2026-10-21

说明：

- ``quota_date`` 记录计数所属的自然日（UTC）。跨日时计数归零。
- ``quota_used`` 记录当日已用次数。默认 0，非空。
- 两列只服务项目密钥的日额度硬拦。全局 token 路径不使用它们。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610210052"
down_revision: str | None = "202610210051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project_api_keys",
        sa.Column("quota_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "project_api_keys",
        sa.Column(
            "quota_used",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("project_api_keys", "quota_used")
    op.drop_column("project_api_keys", "quota_date")