from __future__ import annotations

import subprocess
from collections.abc import Callable

from sqlalchemy import Engine, create_engine, text

EXECUTOR_TABLES = {
    "workflow_execution_dispatches",
    "workflow_execution_leases",
    "workflow_execution_events",
    "workflow_credential_resolution_permits",
    "workflow_provider_call_permits",
    "workflow_provider_call_audits",
    "workflow_cancellation_requests",
    "workflow_cancellation_acknowledgements",
}


def _sync_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)


def _engine(database_url: str) -> Engine:
    return create_engine(_sync_url(database_url))


def _revision(database_url: str) -> str:
    engine = _engine(database_url)
    try:
        with engine.connect() as connection:
            value = connection.scalar(text("SELECT version_num FROM alembic_version"))
    finally:
        engine.dispose()
    assert isinstance(value, str)
    return value


def _tables(database_url: str) -> set[str]:
    engine = _engine(database_url)
    try:
        with engine.connect() as connection:
            return {
                str(value)
                for value in connection.scalars(
                    text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'")
                )
            }
    finally:
        engine.dispose()


def test_revision_044_upgrade_downgrade_upgrade_lifecycle(
    alembic_runner: Callable[..., subprocess.CompletedProcess[str]],
    clean_database_url: str,
) -> None:
    alembic_runner("upgrade", "202607270043")
    assert _revision(clean_database_url) == "202607270043"
    assert EXECUTOR_TABLES.isdisjoint(_tables(clean_database_url))

    alembic_runner("upgrade", "202607280044")
    assert _revision(clean_database_url) == "202607280044"
    assert _tables(clean_database_url) >= EXECUTOR_TABLES

    alembic_runner("downgrade", "202607270043")
    assert _revision(clean_database_url) == "202607270043"
    assert EXECUTOR_TABLES.isdisjoint(_tables(clean_database_url))

    alembic_runner("upgrade", "202607280044")
    assert _revision(clean_database_url) == "202607280044"
    assert _tables(clean_database_url) >= EXECUTOR_TABLES
