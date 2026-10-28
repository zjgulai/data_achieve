"""ABI 契约测试的数据库夹具。

与 ``tests/postgres/conftest.py`` 的关键差别：清理范围。

ABI 迁移 060-063 建的是 ``meta`` / ``raw`` / ``abi`` 三个独立 schema，
不在 ``public`` 里。只 ``DROP SCHEMA public`` 会让这三个 schema 留存，
第二次 ``alembic upgrade head`` 在建表处报 ``DuplicateTable``。
本夹具把四个 schema 一起清掉。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from sqlalchemy import create_engine

API_ROOT = Path(__file__).resolve().parents[2]
# 不加前导下划线：库名就取 ``abi_contract_test``。这个后缀已经足够特定
# ——误连生产的前提是有人把生产库改名成它，而那种情况下 DROP SCHEMA 的
# 破坏早已发生，守卫拦不住的是人不是名字。
ALLOWED_DATABASE_SUFFIX = "abi_contract_test"
ABI_SCHEMAS = ("meta", "raw", "abi")


def _guarded_database_url() -> str:
    """只允许连本机、且库名以特定后缀结尾的库。

    这套夹具会 DROP SCHEMA，误连生产就是数据丢失。守卫必须在建引擎之前。
    """
    database_url = os.getenv("TEST_DATABASE_URL")
    allow_destructive = os.getenv("ALLOW_DESTRUCTIVE_MIGRATION_TEST")
    if not database_url or allow_destructive != "true":
        pytest.skip(
            "ABI 契约测试需要 TEST_DATABASE_URL 与 ALLOW_DESTRUCTIVE_MIGRATION_TEST=true"
        )

    parsed = urlsplit(database_url)
    database_name = parsed.path.removeprefix("/")
    unsafe_reason: str | None = None
    if parsed.scheme != "postgresql+asyncpg":
        unsafe_reason = "TEST_DATABASE_URL 必须使用 postgresql+asyncpg"
    elif parsed.hostname not in {"localhost", "127.0.0.1"}:
        unsafe_reason = "TEST_DATABASE_URL 必须指向 localhost 或 127.0.0.1"
    elif parsed.query or parsed.fragment:
        unsafe_reason = "TEST_DATABASE_URL 不得带 query 或 fragment"
    elif not database_name.endswith(ALLOWED_DATABASE_SUFFIX):
        unsafe_reason = f"TEST_DATABASE_URL 的库名必须以 {ALLOWED_DATABASE_SUFFIX} 结尾"

    if unsafe_reason is not None:
        raise pytest.UsageError(unsafe_reason)
    return database_url


def _sync_database_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)


@pytest.fixture()
def abi_database_url() -> str:
    """清空四个 schema 后把迁移推到 head，返回 asyncpg 形式的 DSN。"""
    database_url = _guarded_database_url()
    engine = create_engine(
        _sync_database_url(database_url), isolation_level="AUTOCOMMIT"
    )
    try:
        with engine.connect() as connection:
            # 顺序有意义：先 public 再 ABI 三 schema，因为 ABI 有指向
            # public.users / public.workspaces 的外键占位。
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
            for schema in ABI_SCHEMAS:
                connection.exec_driver_sql(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            connection.exec_driver_sql("CREATE SCHEMA public")
    finally:
        engine.dispose()

    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    # 用当前解释器跑 -m alembic，而不是 `uv run alembic`：
    # 后者要求 PATH 里有 uv，本地 .venv 环境下会报 "Failed to spawn: alembic"。
    # 当前解释器一定是跑 pytest 的那个，两处环境天然一致。
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_ROOT,
        env=environment,
        check=True,
    )
    return database_url


@pytest.fixture()
def abi_sync_engine(abi_database_url: str):
    engine = create_engine(_sync_database_url(abi_database_url))
    try:
        yield engine
    finally:
        engine.dispose()
