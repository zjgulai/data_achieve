"""Create the monitors table.

Revision ID: 202610210053
Revises: 202610210052
Create Date: 2026-10-21

说明：

- 一个监控绑定一条执行任务；暂停监控时同步暂停任务。
- params 存端点参数，执行任务 config 里另带 monitor_id 作为回链。
- last_checked_at 与 last_new_count 供列表页展示最近一次检查结果。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610210053"
down_revision: str | None = "202610210052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "monitors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("endpoint_type", sa.String(length=80), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("interval_hours", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_new_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["collection_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_monitors_workspace_project", "monitors", ["workspace_id", "project_id"])


def downgrade() -> None:
    op.drop_index("ix_monitors_workspace_project", table_name="monitors")
    op.drop_table("monitors")