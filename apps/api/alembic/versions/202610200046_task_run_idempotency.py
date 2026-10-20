"""Add TaskRun idempotency key column and unique index.

Revision ID: 202610200046
Revises: 202610190045
Create Date: 2026-10-20

缩略说明：

- `task_runs.idempotency_key_hash` 可空。空值表示该运行没有携带幂等键。
- 唯一索引 `(task_id, idempotency_key_hash)` 只约束同一任务下的同一键。
  Postgres 与 SQLite 都允许多行 NULL，因此不带键的运行不受影响。
- 历史上幂等键只记在 `task_runs.logs` 的 JSON 里。本迁移只加列与索引，
  不回填历史数据。读取路径先看列，为空再回退解析 logs。
  回退保留一个发布周期，之后另开迁移删除回退分支。

本修订为 source-only。不得在没有精确目标授权与备份/回滚计划的情况下
对真实数据库执行。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610200046"
down_revision: str | None = "202610190045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX_NAME = "uq_task_runs_task_idempotency"


def upgrade() -> None:
    op.add_column(
        "task_runs",
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        _INDEX_NAME,
        "task_runs",
        ["task_id", "idempotency_key_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="task_runs")
    op.drop_column("task_runs", "idempotency_key_hash")
