"""export_policy 加唯一约束，防重复行让新策略静默失效。

Revision ID: 202610290067
Revises: 202610290066
Create Date: 2026-10-29

背景：``get_export_policy`` 的排序是
``order_by(dataset_id.is_(None), created_at).limit(1)``——dataset 级优先
（false 排在 true 前），但同一 scope 内按 ``created_at`` **升序**，取到的是
**最旧**的一行。

表上没有 ``(workspace_id, dataset_id)`` 唯一约束，``upsert_export_policy``
是「先查后改」。两个管理员并发保存（或双击）时都查不到行，各插一行；
此后读路径返回最旧那行，写路径更新任意一行——新策略静默失效，导出继续
按旧策略放行，且没有任何报错。

修法不能只改排序（改成 DESC 只是把「取最旧」变成「取最新」，重复行仍在，
写路径仍可能更新另一行）。必须让重复行不可能存在：

1. 先清理已有重复：每个 ``(workspace_id, dataset_id)`` 只留 ``created_at``
   最新的一行。生产当前只有 1 行、无重复，这一步是空操作；留在这里是为了
   在别的环境（含历史库）上同样安全。
2. 加唯一索引。``dataset_id`` 可为 NULL，而 PostgreSQL 的唯一索引把 NULL
   视为互不相等，工作区级策略（``dataset_id IS NULL``）会因此不受约束。
   所以用两个部分唯一索引分别覆盖两种 scope。
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "202610290067"
down_revision: str | None = "202610290066"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) 清理重复：保留 created_at 最新的一行，其余删除。
    op.execute(
        """
        DELETE FROM abi.export_policy p
        USING abi.export_policy keep
        WHERE p.workspace_id = keep.workspace_id
          AND p.dataset_id IS NOT DISTINCT FROM keep.dataset_id
          AND p.id <> keep.id
          AND (keep.created_at, keep.id) > (p.created_at, p.id)
        """
    )

    # 2) 数据集级唯一。
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_export_policy_dataset
        ON abi.export_policy (workspace_id, dataset_id)
        WHERE dataset_id IS NOT NULL
        """
    )

    # 3) 工作区级唯一。NULL 在普通唯一索引里互不相等，必须单独一条。
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_export_policy_workspace_default
        ON abi.export_policy (workspace_id)
        WHERE dataset_id IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS abi.uq_export_policy_workspace_default")
    op.execute("DROP INDEX IF EXISTS abi.uq_export_policy_dataset")
