from __future__ import annotations

import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from sqlalchemy import create_engine

API_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_DATABASE_SUFFIX = "_workflow_plan_phase2_test"


def _guarded_database_url() -> str:
    database_url = os.getenv("TEST_DATABASE_URL")
    allow_destructive = os.getenv("ALLOW_DESTRUCTIVE_MIGRATION_TEST")
    if not database_url or allow_destructive != "true":
        pytest.skip(
            "PostgreSQL migration tests require TEST_DATABASE_URL and "
            "ALLOW_DESTRUCTIVE_MIGRATION_TEST=true"
        )

    parsed = urlsplit(database_url)
    database_name = parsed.path.removeprefix("/")
    unsafe_reason: str | None = None
    if parsed.scheme != "postgresql+asyncpg":
        unsafe_reason = "TEST_DATABASE_URL must use postgresql+asyncpg"
    elif parsed.hostname not in {"localhost", "127.0.0.1"}:
        unsafe_reason = "TEST_DATABASE_URL must target localhost or 127.0.0.1"
    elif parsed.query or parsed.fragment:
        unsafe_reason = "TEST_DATABASE_URL must not contain query or fragment overrides"
    elif "%" in parsed.netloc or "%" in parsed.path:
        unsafe_reason = "TEST_DATABASE_URL must not contain encoded host or database parts"
    elif not database_name.endswith(ALLOWED_DATABASE_SUFFIX):
        unsafe_reason = f"TEST_DATABASE_URL database must end with {ALLOWED_DATABASE_SUFFIX}"

    if unsafe_reason is not None:
        raise pytest.UsageError(unsafe_reason)
    return database_url


def _sync_database_url(database_url: str) -> str:
    return database_url.replace(
        "postgresql+asyncpg://",
        "postgresql+psycopg://",
        1,
    )


@pytest.fixture()
def postgres_database_url() -> str:
    database_url = _guarded_database_url()
    engine = create_engine(_sync_database_url(database_url), isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
            connection.exec_driver_sql("CREATE SCHEMA public")
    finally:
        engine.dispose()

    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=API_ROOT,
        env=environment,
        check=True,
    )
    return database_url
