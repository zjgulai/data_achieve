from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from sqlalchemy import create_engine

API_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_DATABASE_SUFFIX = "_capability_governance_test"


def _guarded_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    authorized = os.getenv("CAPABILITY_GOVERNANCE_POSTGRES_TEST_AUTHORIZED")
    if not database_url or authorized != "true":
        pytest.skip(
            "Capability Governance PostgreSQL tests require DATABASE_URL and "
            "CAPABILITY_GOVERNANCE_POSTGRES_TEST_AUTHORIZED=true"
        )

    if any(character.isspace() for character in database_url):
        raise pytest.UsageError("DATABASE_URL must not contain whitespace")

    try:
        parsed = urlsplit(database_url)
        _ = parsed.port
    except ValueError as exc:
        raise pytest.UsageError("DATABASE_URL host or port is invalid") from exc

    database_name = parsed.path.removeprefix("/")
    raw_authority = parsed.netloc.rsplit("@", 1)[-1]
    unsafe_reason: str | None = None
    if parsed.scheme != "postgresql+asyncpg":
        unsafe_reason = "DATABASE_URL must use postgresql+asyncpg"
    elif parsed.hostname not in {"localhost", "127.0.0.1"}:
        unsafe_reason = "DATABASE_URL must target localhost or 127.0.0.1"
    elif parsed.query or parsed.fragment:
        unsafe_reason = "DATABASE_URL must not contain query or fragment"
    elif "%" in raw_authority or "%" in parsed.path:
        unsafe_reason = "DATABASE_URL must not contain encoded parts"
    elif not parsed.path.startswith("/") or parsed.path.count("/") != 1:
        unsafe_reason = "DATABASE_URL must name exactly one database"
    elif not database_name.endswith(ALLOWED_DATABASE_SUFFIX):
        unsafe_reason = f"DATABASE_URL database must end with {ALLOWED_DATABASE_SUFFIX}"

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
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_ROOT,
        env=environment,
        check=True,
    )
    return database_url
