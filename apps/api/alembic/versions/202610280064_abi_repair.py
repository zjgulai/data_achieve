"""Repair ABI schemas for databases that already ran 060-063.

Revision ID: 202610280064
Revises: 202610280063
Create Date: 2026-10-29

为什么需要这条迁移：

060-063 是尚未发布的 source-only 迁移。开发过程中它们被原地修过两处：

1. ``060`` 建的表名为 ``apify_account_daily``，而模型写 ``apify_token_daily``。
   表里存的是 token 维度的每日用量（``account_id`` + ``usage_date`` 唯一），
   叫 account 是错的。
2. ``061`` 的 ``raw.apify_dataset`` 漏了 ``endpoint_type`` 列。模型有，
   迁移没有，归因脚本写入时会缺列。

新建库直接跑修好的 060-063 就是对的。但**已经跑过旧 060-063 的库**
（本地开发库、e2e 栈、任何预发）不会自动修复——迁移是单向的记录，
改了源码不等于改了历史。

所以这条迁移只做补齐，且**必须写成条件 DDL**：
- 全新库：两处判断都为「已经是新形态」，全部跳过，064 是 no-op。
- 旧库：改名 + 加列。

不做 ``DROP SCHEMA ... CASCADE`` 重建：那会丢掉已有数据，而 ABI 的目标是
长期存历史。改名与加列都可逆，且不触碰任何业务行。

不使用 ``op.rename_table``：它生成的 ``ALTER TABLE ... RENAME TO`` 在
目标名已存在时会失败，而"目标名已存在"正是 064 要处理的两种状态之一。
这里用 inspector 先判断，再决定执行哪条。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610280064"
down_revision: str | None = "202610280063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_TOKEN_DAILY = "apify_account_daily"
NEW_TOKEN_DAILY = "apify_token_daily"
META = "meta"
RAW = "raw"

# 表名改了，约束名也要跟着改：命名约定是 ck_<table>_<name>，
# 旧名留着会让后续 autogenerate 报出一堆「约束名不一致」。
_RENAMED_CONSTRAINTS = (
    ("pk_apify_account_daily", "pk_apify_token_daily"),
    (
        "fk_apify_account_daily_account_id_apify_account",
        "fk_apify_token_daily_account_id_apify_account",
    ),
    (
        "uq_apify_account_daily_account_usage_date",
        "uq_apify_token_daily_account_id_usage_date",
    ),
)


def _inspector() -> sa.engine.reflection.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(inspector: sa.engine.reflection.Inspector, schema: str, table: str) -> bool:
    return inspector.has_table(table, schema=schema)


def _constraint_names(table: str, schema: str) -> set[str]:
    # 不用 :qualified::regclass：``::`` 紧跟在绑定参数后会干扰 SQLAlchemy
    # 的 text() 参数解析，报 "syntax error at or near ':'"。
    # 按 namespace + relname 匹配，语义相同且不受参数风格影响。
    rows = (
        op.get_bind()
        .execute(
            sa.text(
                """
                SELECT c.conname
                FROM pg_constraint AS c
                JOIN pg_class AS rel ON rel.oid = c.conrelid
                JOIN pg_namespace AS ns ON ns.oid = rel.relnamespace
                WHERE ns.nspname = :schema AND rel.relname = :table
                """
            ),
            {"schema": schema, "table": table},
        )
        .scalars()
    )
    return set(rows)


def _rename_constraint_if_present(
    table: str,
    schema: str,
    old_name: str,
    new_name: str,
) -> None:
    """只在旧约束确实存在时改名。

    必须逐条判断，不能整批 ``ALTER``：
    不同版本建出来的约束名可能不同（例如唯一约束是否含 ``_id``），
    无条件重命名会在第一条不匹配处整条迁移失败。
    """
    present = _constraint_names(table, schema)
    if old_name in present and new_name not in present:
        op.execute(
            sa.text(
                f'ALTER TABLE {schema}.{table} '
                f'RENAME CONSTRAINT "{old_name}" TO "{new_name}"'
            )
        )


def _has_column(
    inspector: sa.engine.reflection.Inspector,
    schema: str,
    table: str,
    column: str,
) -> bool:
    return any(
        item["name"] == column
        for item in inspector.get_columns(table, schema=schema)
    )


def upgrade() -> None:
    inspector = _inspector()

    # ---- 1. meta.apify_account_daily -> meta.apify_token_daily ----
    has_old = _has_table(inspector, META, OLD_TOKEN_DAILY)
    has_new = _has_table(inspector, META, NEW_TOKEN_DAILY)
    if has_old and not has_new:
        op.rename_table(OLD_TOKEN_DAILY, NEW_TOKEN_DAILY, schema=META)
        for old_name, new_name in _RENAMED_CONSTRAINTS:
            _rename_constraint_if_present(
                NEW_TOKEN_DAILY, META, old_name, new_name
            )
    # has_old 与 has_new 同时为真的情况不处理：两张表都在说明有人手工动过
    # 库，自动猜哪张是对的比留着让人查更危险。

    # ---- 2. raw.apify_dataset.endpoint_type ----
    inspector = _inspector()
    if _has_table(inspector, RAW, "apify_dataset") and not _has_column(
        inspector, RAW, "apify_dataset", "endpoint_type"
    ):
        op.add_column(
            "apify_dataset",
            sa.Column("endpoint_type", sa.Text(), nullable=True),
            schema=RAW,
        )


def downgrade() -> None:
    """回到旧形态。

    加列可以回退；改名不建议自动回退——回退改名会让已经引用新名的代码
    立刻失效，而这条迁移存在的意义就是让名字统一。因此 downgrade 只撤列。
    """
    inspector = _inspector()
    if _has_table(inspector, RAW, "apify_dataset") and _has_column(
        inspector, RAW, "apify_dataset", "endpoint_type"
    ):
        op.drop_column("apify_dataset", "endpoint_type", schema=RAW)
