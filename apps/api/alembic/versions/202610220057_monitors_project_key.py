"""Monitors record the creating project key for scheduled quota.

Revision ID: 202610220057
Revises: 202610220056
Create Date: 2026-10-25

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.

说明：

- monitors.project_key_id 记录创建该监控的项目密钥，调度器按它扣日额度。
- 列可空：全局 token 创建的监控没有密钥身份，调度时不扣额度。
- 外键指向 project_api_keys.id；密钥撤销不级联删除监控。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610220057"
down_revision: str | None = "202610220056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "monitors",
        sa.Column("project_key_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_monitors_project_key_id_project_api_keys",
        "monitors",
        "project_api_keys",
        ["project_key_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_monitors_project_key_id_project_api_keys",
        "monitors",
        type_="foreignkey",
    )
    op.drop_column("monitors", "project_key_id")
