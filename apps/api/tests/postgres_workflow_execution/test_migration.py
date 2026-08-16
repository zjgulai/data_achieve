from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text

API_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
VERIFY_SCRIPT = REPOSITORY_ROOT / "scripts/verify-workflow-execution-migration.sh"
SAFE_URL = "postgresql+asyncpg://user:guard-secret@127.0.0.1:55367/local_workflow_execution_test"
SAFE_TARGET = "127.0.0.1:55367/local_workflow_execution_test"
EXECUTION_TABLES = {"workflow_runs", "step_runs", "workflow_run_requests"}


@dataclass(frozen=True, slots=True)
class PreExecutionIds:
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    plan_id: uuid.UUID
    version_id: uuid.UUID


def _run_guard(
    *,
    authorized: str | None,
    database_url: str | None,
    authorized_target: str | None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    for key in (
        "DATABASE_URL",
        "WORKFLOW_EXECUTION_POSTGRES_TEST_AUTHORIZED",
        "WORKFLOW_EXECUTION_TEST_DATABASE_URL",
        "WORKFLOW_EXECUTION_AUTHORIZED_TARGET",
    ):
        environment.pop(key, None)
    if authorized is not None:
        environment["WORKFLOW_EXECUTION_POSTGRES_TEST_AUTHORIZED"] = authorized
    if database_url is not None:
        environment["WORKFLOW_EXECUTION_TEST_DATABASE_URL"] = database_url
    if authorized_target is not None:
        environment["WORKFLOW_EXECUTION_AUTHORIZED_TARGET"] = authorized_target
    return subprocess.run(
        ["bash", str(VERIFY_SCRIPT), "--check-only"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def _assert_guard_secret_safe(result: subprocess.CompletedProcess[str]) -> None:
    assert SAFE_URL not in result.stdout
    assert SAFE_URL not in result.stderr
    assert "guard-secret" not in result.stdout
    assert "guard-secret" not in result.stderr


@pytest.mark.parametrize(
    ("database_url", "authorized_target"),
    [
        (
            "postgresql+asyncpg://user:guard-secret@db.example.test:55367/"
            "local_workflow_execution_test",
            "db.example.test:55367/local_workflow_execution_test",
        ),
        (
            "postgresql+asyncpg://user:guard-secret@127.0.0.1:55367/not_safe",
            "127.0.0.1:55367/not_safe",
        ),
        (f"{SAFE_URL}?ssl=require", SAFE_TARGET),
        (
            "postgresql+asyncpg://user:guard-secret@127.0.0.1:55367/"
            "local%5fworkflow_execution_test",
            SAFE_TARGET,
        ),
        (SAFE_URL, "127.0.0.1:55368/local_workflow_execution_test"),
    ],
)
def test_guard_rejects_unsafe_or_mismatched_targets(
    database_url: str,
    authorized_target: str,
) -> None:
    result = _run_guard(
        authorized="true",
        database_url=database_url,
        authorized_target=authorized_target,
    )
    assert result.returncode == 2
    _assert_guard_secret_safe(result)


def test_guard_check_only_accepts_exact_target_without_connecting_or_leaking() -> None:
    result = _run_guard(
        authorized="true",
        database_url=SAFE_URL,
        authorized_target=SAFE_TARGET,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == (
        "migration guard passed: exact local disposable workflow execution PostgreSQL database"
    )
    assert result.stderr == ""
    _assert_guard_secret_safe(result)


def _sync_database_url(database_url: str) -> str:
    return database_url.replace(
        "postgresql+asyncpg://",
        "postgresql+psycopg://",
        1,
    )


def _engine(database_url: str, *, autocommit: bool = False) -> Engine:
    return create_engine(
        _sync_database_url(database_url),
        isolation_level="AUTOCOMMIT" if autocommit else None,
    )


def _run_alembic(
    database_url: str,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    return subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=API_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def _reset_public_schema(database_url: str) -> None:
    engine = _engine(database_url, autocommit=True)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
            connection.exec_driver_sql("CREATE SCHEMA public")
    finally:
        engine.dispose()


def _tables(database_url: str) -> set[str]:
    engine = _engine(database_url)
    try:
        with engine.connect() as connection:
            return set(
                connection.scalars(
                    text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'")
                )
            )
    finally:
        engine.dispose()


def _revision(database_url: str) -> str:
    engine = _engine(database_url)
    try:
        with engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
    finally:
        engine.dispose()
    assert isinstance(revision, str)
    return revision


def _execution_counts(database_url: str) -> dict[str, int]:
    engine = _engine(database_url)
    try:
        with engine.connect() as connection:
            return {
                table_name: int(connection.scalar(text(f"SELECT count(*) FROM {table_name}")) or 0)
                for table_name in EXECUTION_TABLES
            }
    finally:
        engine.dispose()


def _seed_pre_execution_state(database_url: str) -> PreExecutionIds:
    ids = PreExecutionIds(*(uuid.uuid4() for _ in range(5)))
    engine = _engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, name, status) "
                    "VALUES (:id, :email, 'not-real', 'Pre-029 User', 'active')"
                ),
                {"id": ids.user_id, "email": f"{ids.user_id}@example.test"},
            )
            connection.execute(
                text(
                    "INSERT INTO workspaces (id, name, slug, owner_id) "
                    "VALUES (:id, 'Pre-029 Workspace', :slug, :owner_id)"
                ),
                {
                    "id": ids.workspace_id,
                    "slug": f"pre-029-{ids.workspace_id}",
                    "owner_id": ids.user_id,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO projects "
                    "(id, workspace_id, name, description, domain, status, owner_id) "
                    "VALUES (:id, :workspace_id, 'Pre-029 Project', NULL, "
                    "'social', 'active', :owner_id)"
                ),
                {
                    "id": ids.project_id,
                    "workspace_id": ids.workspace_id,
                    "owner_id": ids.user_id,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO workflow_plans "
                    "(id, workspace_id, project_id, created_by_user_id, name, "
                    "flow_mode, status, current_version_id) VALUES "
                    "(:id, :workspace_id, :project_id, :user_id, 'Pre-029 Plan', "
                    "'periodic_monitoring', 'previewed', NULL)"
                ),
                {
                    "id": ids.plan_id,
                    "workspace_id": ids.workspace_id,
                    "project_id": ids.project_id,
                    "user_id": ids.user_id,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO workflow_versions "
                    "(id, workspace_id, project_id, workflow_plan_id, "
                    "created_by_user_id, version_number, planning_status, "
                    "planner_contract_version, catalog_snapshot_id, policy_version, "
                    "mode_template_version, query_versions, fingerprint_payload, "
                    "normalized_input, plan_payload, preview_fingerprint) VALUES "
                    "(:id, :workspace_id, :project_id, :plan_id, :user_id, 1, "
                    "'resolved', 'workflow-planner.v1', 'catalog.pre-029', "
                    "'policy.v1', 'mode.v1', CAST(:query_versions AS JSON), "
                    "CAST(:fingerprint_payload AS JSON), CAST(:normalized_input AS JSON), "
                    "CAST(:plan_payload AS JSON), :preview_fingerprint)"
                ),
                {
                    "id": ids.version_id,
                    "workspace_id": ids.workspace_id,
                    "project_id": ids.project_id,
                    "plan_id": ids.plan_id,
                    "user_id": ids.user_id,
                    "query_versions": json.dumps({"youtube": "youtube.v1"}),
                    "fingerprint_payload": json.dumps({"phase": "pre-029"}),
                    "normalized_input": json.dumps({"phase": "pre-029"}),
                    "plan_payload": json.dumps({"phase": "pre-029"}),
                    "preview_fingerprint": "sha256:" + "a" * 64,
                },
            )
            connection.execute(
                text(
                    "UPDATE workflow_plans SET current_version_id = :version_id WHERE id = :plan_id"
                ),
                {"version_id": ids.version_id, "plan_id": ids.plan_id},
            )
    finally:
        engine.dispose()
    return ids


def _preserved_snapshot(
    database_url: str,
    ids: PreExecutionIds,
) -> tuple[tuple[object, ...], ...]:
    engine = _engine(database_url)
    try:
        with engine.connect() as connection:
            return (
                tuple(
                    connection.execute(
                        text(
                            "SELECT id, workspace_id, project_id, current_version_id "
                            "FROM workflow_plans WHERE id = :id"
                        ),
                        {"id": ids.plan_id},
                    ).one()
                ),
                tuple(
                    connection.execute(
                        text(
                            "SELECT id, workflow_plan_id, version_number, "
                            "preview_fingerprint FROM workflow_versions WHERE id = :id"
                        ),
                        {"id": ids.version_id},
                    ).one()
                ),
                tuple(
                    connection.execute(
                        text(
                            "SELECT singleton_key, current_revision_id, head_version "
                            "FROM capability_catalog_head"
                        )
                    ).one()
                ),
            )
    finally:
        engine.dispose()


def test_fresh_upgrade_has_single_head_three_empty_tables_and_preserved_head(
    postgres_database_url: str,
) -> None:
    heads = [
        line
        for line in _run_alembic(postgres_database_url, "heads").stdout.splitlines()
        if line.strip()
    ]
    assert heads == ["202607170034 (head)"]
    assert _revision(postgres_database_url) == "202607170034"
    assert _tables(postgres_database_url) >= {
        *EXECUTION_TABLES,
        "workflow_versions",
        "capability_catalog_head",
    }
    assert set(_execution_counts(postgres_database_url).values()) == {0}
    engine = _engine(postgres_database_url)
    try:
        with engine.connect() as connection:
            head = tuple(
                connection.execute(
                    text(
                        "SELECT singleton_key, current_revision_id, head_version "
                        "FROM capability_catalog_head"
                    )
                ).one()
            )
    finally:
        engine.dispose()
    assert head == ("global", None, 0)


def test_028_to_029_to_028_to_029_preserves_existing_state(
    postgres_database_url: str,
) -> None:
    _reset_public_schema(postgres_database_url)
    _run_alembic(postgres_database_url, "upgrade", "202606110028")
    ids = _seed_pre_execution_state(postgres_database_url)
    before = _preserved_snapshot(postgres_database_url, ids)

    _run_alembic(postgres_database_url, "upgrade", "202606110029")
    assert _revision(postgres_database_url) == "202606110029"
    assert _preserved_snapshot(postgres_database_url, ids) == before
    assert set(_execution_counts(postgres_database_url).values()) == {0}

    _run_alembic(postgres_database_url, "downgrade", "202606110028")
    assert _revision(postgres_database_url) == "202606110028"
    assert EXECUTION_TABLES.isdisjoint(_tables(postgres_database_url))
    assert _preserved_snapshot(postgres_database_url, ids) == before

    _run_alembic(postgres_database_url, "upgrade", "202606110029")
    assert _revision(postgres_database_url) == "202606110029"
    assert _preserved_snapshot(postgres_database_url, ids) == before
    assert set(_execution_counts(postgres_database_url).values()) == {0}
