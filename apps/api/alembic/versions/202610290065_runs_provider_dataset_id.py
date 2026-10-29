"""Add provider_dataset_id to runs and task_runs.

Revision ID: 202610290065
Revises: 202610280064
Create Date: 2026-10-29

说明：

- ``runs.provider_run_id`` 已在 202610220056 落地，用于租约接管后恢复轮询。
  但一次外部采集还需要 dataset 标识才能重取结果：Apify 的
  ``defaultDatasetId`` 是取回 item 的唯一句柄——run 结束后 item 仍在
  dataset 里，而 run 一旦被清理就再也拿不到。
- 列名带 ``provider_`` 前缀，不叫 ``dataset_id``：仓库已有 ``datasets`` 表，
  ABI 也有 ``catalog_dataset``。裸 ``dataset_id`` 会被读成内部数据集外键。
- ``task_runs`` 上的同名列为调用级镜像，与 ``provider_run_id`` 的处理一致
  （队列幂等权威仍在 ``runs``）。
- 两列都可空：历史行没有这个值，且 Exa 这类 provider 没有 dataset 概念。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610290065"
down_revision: str | None = "202610280064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("provider_dataset_id", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "task_runs",
        sa.Column("provider_dataset_id", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("task_runs", "provider_dataset_id")
    op.drop_column("runs", "provider_dataset_id")
