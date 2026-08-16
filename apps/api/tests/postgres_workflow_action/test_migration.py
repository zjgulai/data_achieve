from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import Engine, create_engine, text

ACTION_TABLES = {
    "workflow_run_action_contexts",
    "workflow_run_action_approval_receipts",
    "workflow_run_action_requests",
    "workflow_run_action_receipts",
    "workflow_run_action_approval_consumptions",
    "workflow_run_action_audit_events",
}


def _engine(sync_database_url: str) -> Engine:
    return create_engine(sync_database_url)


def _revision(sync_database_url: str) -> str:
    engine = _engine(sync_database_url)
    try:
        with engine.connect() as connection:
            value = connection.scalar(text("SELECT version_num FROM alembic_version"))
    finally:
        engine.dispose()
    assert isinstance(value, str)
    return value


def _action_schema(sync_database_url: str) -> tuple[set[str], set[tuple[str, str]]]:
    engine = _engine(sync_database_url)
    try:
        with engine.connect() as connection:
            tables = {
                str(value)
                for value in connection.scalars(
                    text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'")
                )
            }
            columns = {
                (str(table_name), str(column_name))
                for table_name, column_name in connection.execute(
                    text(
                        "SELECT table_name, column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name IN "
                        "('step_runs', 'step_run_attempts')"
                    )
                )
            }
    finally:
        engine.dispose()
    return tables, columns


def test_revision_043_upgrade_downgrade_upgrade_lifecycle(
    alembic_runner: Callable[..., subprocess.CompletedProcess[str]],
    sync_database_url: str,
) -> None:
    alembic_runner("upgrade", "202607230042")
    assert _revision(sync_database_url) == "202607230042"
    tables_042, columns_042 = _action_schema(sync_database_url)
    assert ACTION_TABLES.isdisjoint(tables_042)
    assert ("step_runs", "retry_generation") not in columns_042
    assert ("step_run_attempts", "retry_generation") not in columns_042

    alembic_runner("upgrade", "202607270043")
    assert _revision(sync_database_url) == "202607270043"
    tables_043, columns_043 = _action_schema(sync_database_url)
    assert tables_043 >= ACTION_TABLES
    assert ("step_runs", "retry_generation") in columns_043
    assert ("step_run_attempts", "retry_generation") in columns_043

    alembic_runner("downgrade", "202607230042")
    assert _revision(sync_database_url) == "202607230042"
    tables_rollback, columns_rollback = _action_schema(sync_database_url)
    assert ACTION_TABLES.isdisjoint(tables_rollback)
    assert ("step_runs", "retry_generation") not in columns_rollback
    assert ("step_run_attempts", "retry_generation") not in columns_rollback

    alembic_runner("upgrade", "202607270043")
    assert _revision(sync_database_url) == "202607270043"


@pytest.mark.asyncio
async def test_revision_043_downgrade_refuses_nonzero_retry_evidence(
    alembic_runner: Callable[..., subprocess.CompletedProcess[str]],
    seeded_action_run: Any,
    sync_database_url: str,
) -> None:
    database = seeded_action_run.database
    step_id = seeded_action_run.step_id
    async with database.engine.begin() as connection:
        await connection.execute(
            text("UPDATE step_runs SET retry_generation = 1 WHERE id = :step_id"),
            {"step_id": step_id},
        )

    with pytest.raises(subprocess.CalledProcessError) as captured:
        alembic_runner("downgrade", "202607230042")

    assert "202607270043 downgrade refused: Workflow action evidence exists" in (
        captured.value.stderr
    )
    assert _revision(sync_database_url) == "202607270043"
