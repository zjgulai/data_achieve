"""ABI ORM 与迁移的列级契约。

写这个测试的原因：``models/abi.py`` 挂在独立的 ``AbiBase.metadata`` 上，
而 ``alembic/env.py`` 的 ``target_metadata`` 是 ``Base.metadata``。两者不通，
``alembic revision --autogenerate`` 看不见 ABI 的表，**漂移不会自动暴露**。

实际已经漂移过两次：
- 060 建 ``apify_account_daily``，模型写 ``apify_token_daily``；
- 三张 ``si_*`` 宽表模型只有 ``id`` 桩，迁移里是 6/23/43 列。

两次都是"没人调所以不报错"，接上查询就 500。这里把它变成会红的测试。

刻意不用 ``compare_metadata``：跨 schema 时它的过滤器行为不稳定——
实测在 44 张表上会报出 96 条 ``add_table`` 假阳性（表明明存在）。
直接读 ``information_schema`` 更可信，也更容易读懂失败信息。
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect

from data_intelligence_hub.models.abi import AbiBase

# AbiBase 注册的 public 占位表：只为了让 ABI 表的跨 schema 外键能在
# 同一个 MetaData 里解析，真实列由主 Base 管，不在这里比对。
PUBLIC_PLACEHOLDERS = {"users", "workspaces"}


def _comparable_tables():
    for table in AbiBase.metadata.tables.values():
        if table.schema is None and table.name in PUBLIC_PLACEHOLDERS:
            continue
        yield table


def test_every_abi_model_table_exists_in_migration_output(abi_sync_engine) -> None:
    inspector = inspect(abi_sync_engine)
    missing = [
        f"{table.schema}.{table.name}"
        for table in _comparable_tables()
        if not inspector.has_table(table.name, schema=table.schema)
    ]

    assert missing == [], f"迁移没有建这些模型表：{missing}"


def test_no_column_drift_between_models_and_migrations(abi_sync_engine) -> None:
    inspector = inspect(abi_sync_engine)
    problems: list[str] = []

    for table in _comparable_tables():
        qualified = f"{table.schema}.{table.name}"
        if not inspector.has_table(table.name, schema=table.schema):
            problems.append(f"{qualified}: 表不存在")
            continue
        database_columns = {
            column["name"]
            for column in inspector.get_columns(table.name, schema=table.schema)
        }
        model_columns = {column.name for column in table.columns}
        extra_in_model = sorted(model_columns - database_columns)
        missing_in_model = sorted(database_columns - model_columns)
        if extra_in_model:
            problems.append(f"{qualified}: 模型多出 {extra_in_model}")
        if missing_in_model:
            problems.append(f"{qualified}: 模型缺少 {missing_in_model}")

    assert problems == [], "ABI 模型与迁移漂移：\n" + "\n".join(problems)


@pytest.mark.parametrize(
    ("schema", "table", "expected"),
    [
        ("meta", "apify_token_daily", True),
        # 这张表在 060 里曾叫 apify_account_daily，模型却写 token_daily。
        # 保留一条反向断言，避免有人"修好"成旧名后两边一起错。
        ("meta", "apify_account_daily", False),
    ],
)
def test_token_daily_table_name(
    abi_sync_engine, schema: str, table: str, expected: bool
) -> None:
    inspector = inspect(abi_sync_engine)

    assert inspector.has_table(table, schema=schema) is expected


def test_retention_index_predicate_excludes_only_terminal_states(
    abi_sync_engine,
) -> None:
    """retention 索引的谓词必须与模型逐字一致。

    用 ``status = 'active'`` 会把已入仓但面临删除的数据集排除在风险查询之外
    （实测 8,465 行全是 complete，索引命中 0 行）。
    """
    with abi_sync_engine.connect() as connection:
        predicate = connection.exec_driver_sql(
            """
            SELECT pg_get_expr(indpred, indrelid)
            FROM pg_index
            WHERE indexrelid = 'raw.ix_apify_dataset_retention'::regclass
            """
        ).scalar_one()

    assert "expired" in predicate
    assert "missing" in predicate
    assert "active" not in predicate


@pytest.mark.parametrize(
    ("schema", "table", "constraint_fragment"),
    [
        ("meta", "actor_registry", "confidence"),
        ("meta", "ingest_run", "status"),
    ],
)
def test_check_constraints_present(
    abi_sync_engine, schema: str, table: str, constraint_fragment: str
) -> None:
    with abi_sync_engine.connect() as connection:
        rows = connection.exec_driver_sql(
            """
            SELECT conname FROM pg_constraint
            WHERE conrelid = %s::regclass AND contype = 'c'
            """,
            (f"{schema}.{table}",),
        ).scalars().all()

    assert any(constraint_fragment in name for name in rows), (
        f"{schema}.{table} 缺少含 {constraint_fragment} 的 CHECK 约束，实际有：{rows}"
    )


def test_endpoint_type_column_exists_on_apify_dataset(abi_sync_engine) -> None:
    """endpoint_type 与 endpoint_source 是两件事，迁移里曾漏了前者。"""
    inspector = inspect(abi_sync_engine)
    columns = {
        column["name"]
        for column in inspector.get_columns("apify_dataset", schema="raw")
    }

    assert {"endpoint_type", "endpoint_source"} <= columns


def test_upload_batch_tables_exist(abi_sync_engine) -> None:
    """上传链路当前已有的表。

    刻意不断言 ``upload_table_registry``：那张表要等 U3（上传物理表 DDL 契约）
    才加入 063。现在断言它等于把未完成的切片写成已完成，测试会红在一个
    「还没到那一步」的地方，掩盖真实回归。
    """
    inspector = inspect(abi_sync_engine)
    present = set(inspector.get_table_names(schema="abi"))

    assert {"upload_batch", "upload_error"} <= present


def test_contract_survives_two_consecutive_upgrades(abi_database_url) -> None:
    """连跑两次迁移：第二次必须不报 DuplicateTable。

    这正是现有 postgres 夹具会踩的坑——它们只 DROP public，
    三个 ABI schema 留存，第二次 upgrade 在建表处失败。
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    api_root = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["DATABASE_URL"] = abi_database_url

    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=api_root,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, (
        "第二次 upgrade 失败，说明 schema 清理不完整：\n"
        f"{completed.stdout}\n{completed.stderr}"
    )
