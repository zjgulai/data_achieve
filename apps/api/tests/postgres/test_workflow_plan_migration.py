from __future__ import annotations

import os
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text

API_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
VERIFY_SCRIPT = REPOSITORY_ROOT / "scripts/verify-workflow-planner-phase2-migration.sh"

PHASE_TWO_TABLES = {
    "monitoring_scopes",
    "query_terms",
    "workflow_plan_save_requests",
    "workflow_plans",
    "workflow_version_scopes",
    "workflow_versions",
}
PHASE_TWO_FUNCTIONS = {
    "enforce_workflow_plan_current_version",
    "reject_workflow_plan_history_mutation",
}
PHASE_TWO_TRIGGERS = {
    "trg_monitoring_scopes_immutable",
    "trg_query_terms_immutable",
    "trg_workflow_plan_save_requests_immutable",
    "trg_workflow_plans_current_version_required",
    "trg_workflow_plans_updated_at",
    "trg_workflow_version_scopes_immutable",
    "trg_workflow_versions_immutable",
}
PHASE_TWO_CONSTRAINTS = {
    "fk_monitoring_scopes_project_tenant",
    "fk_query_terms_version_scope_tenant",
    "fk_workflow_plan_save_requests_plan_tenant",
    "fk_workflow_plan_save_requests_version_tenant",
    "fk_workflow_plans_current_version_owner",
    "fk_workflow_plans_project_tenant",
    "fk_workflow_version_scopes_scope_tenant",
    "fk_workflow_version_scopes_version_tenant",
    "fk_workflow_versions_plan_tenant",
    "uq_projects_workspace_id",
}


@dataclass(frozen=True)
class LegacyIds:
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    member_id: uuid.UUID
    project_id: uuid.UUID


def _run_guard(
    database_url: str | None,
    *,
    allow_destructive: str | None = "true",
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("TEST_DATABASE_URL", None)
    environment.pop("ALLOW_DESTRUCTIVE_MIGRATION_TEST", None)
    if database_url is not None:
        environment["TEST_DATABASE_URL"] = database_url
    if allow_destructive is not None:
        environment["ALLOW_DESTRUCTIVE_MIGRATION_TEST"] = allow_destructive
    return subprocess.run(
        ["bash", str(VERIFY_SCRIPT), "--check-only"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def _sync_database_url(database_url: str) -> str:
    return database_url.replace(
        "postgresql+asyncpg://",
        "postgresql+psycopg://",
        1,
    )


def _run_alembic(
    database_url: str,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    return subprocess.run(
        ["uv", "run", "alembic", *arguments],
        cwd=API_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def _database_engine(database_url: str, *, autocommit: bool = False) -> Engine:
    isolation_level = "AUTOCOMMIT" if autocommit else None
    return create_engine(
        _sync_database_url(database_url),
        isolation_level=isolation_level,
    )


def _reset_public_schema(database_url: str) -> None:
    engine = _database_engine(database_url, autocommit=True)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
            connection.exec_driver_sql("CREATE SCHEMA public")
    finally:
        engine.dispose()


def _seed_legacy_project(database_url: str) -> LegacyIds:
    legacy = LegacyIds(
        user_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        member_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
    )
    engine = _database_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO users (id, email, password_hash, name, status)
                    VALUES (
                        :user_id,
                        :email,
                        'not-a-real-password',
                        'Legacy Migration User',
                        'active'
                    )
                    """
                ),
                {
                    "user_id": legacy.user_id,
                    "email": f"{legacy.user_id}@example.test",
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO workspaces (id, name, slug, owner_id)
                    VALUES (
                        :workspace_id,
                        'Legacy Migration Workspace',
                        :slug,
                        :user_id
                    )
                    """
                ),
                {
                    "workspace_id": legacy.workspace_id,
                    "slug": f"legacy-migration-{legacy.workspace_id}",
                    "user_id": legacy.user_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO workspace_members (id, workspace_id, user_id, role)
                    VALUES (:member_id, :workspace_id, :user_id, 'owner')
                    """
                ),
                {
                    "member_id": legacy.member_id,
                    "workspace_id": legacy.workspace_id,
                    "user_id": legacy.user_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO projects (
                        id,
                        workspace_id,
                        name,
                        description,
                        domain,
                        status,
                        owner_id
                    )
                    VALUES (
                        :project_id,
                        :workspace_id,
                        'Legacy Migration Project',
                        'Must survive the Phase Two migration lifecycle.',
                        'osint',
                        'active',
                        :user_id
                    )
                    """
                ),
                {
                    "project_id": legacy.project_id,
                    "workspace_id": legacy.workspace_id,
                    "user_id": legacy.user_id,
                },
            )
    finally:
        engine.dispose()
    return legacy


def _legacy_snapshot(database_url: str, legacy: LegacyIds) -> tuple[tuple[object, ...], ...]:
    engine = _database_engine(database_url)
    try:
        with engine.connect() as connection:
            user = tuple(
                connection.execute(
                    text(
                        """
                        SELECT id, email, name, status
                        FROM users
                        WHERE id = :user_id
                        """
                    ),
                    {"user_id": legacy.user_id},
                ).one()
            )
            workspace = tuple(
                connection.execute(
                    text(
                        """
                        SELECT id, name, slug, owner_id
                        FROM workspaces
                        WHERE id = :workspace_id
                        """
                    ),
                    {"workspace_id": legacy.workspace_id},
                ).one()
            )
            member = tuple(
                connection.execute(
                    text(
                        """
                        SELECT id, workspace_id, user_id, role
                        FROM workspace_members
                        WHERE id = :member_id
                        """
                    ),
                    {"member_id": legacy.member_id},
                ).one()
            )
            project = tuple(
                connection.execute(
                    text(
                        """
                        SELECT id, workspace_id, name, description, domain, status, owner_id
                        FROM projects
                        WHERE id = :project_id
                        """
                    ),
                    {"project_id": legacy.project_id},
                ).one()
            )
    finally:
        engine.dispose()
    return user, workspace, member, project


def _project_column_signature(database_url: str) -> tuple[tuple[object, ...], ...]:
    engine = _database_engine(database_url)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT
                        column_name,
                        data_type,
                        is_nullable,
                        character_maximum_length
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'projects'
                    ORDER BY ordinal_position
                    """
                )
            ).all()
    finally:
        engine.dispose()
    return tuple(tuple(row) for row in rows)


def _database_revision(database_url: str) -> str:
    engine = _database_engine(database_url)
    try:
        with engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
    finally:
        engine.dispose()
    assert isinstance(revision, str)
    return revision


def _named_objects(database_url: str) -> tuple[set[str], set[str], set[str], set[str]]:
    engine = _database_engine(database_url)
    try:
        with engine.connect() as connection:
            tables = set(
                connection.scalars(
                    text(
                        """
                        SELECT tablename
                        FROM pg_catalog.pg_tables
                        WHERE schemaname = 'public'
                        """
                    )
                )
            )
            functions = set(
                connection.scalars(
                    text(
                        """
                        SELECT proname
                        FROM pg_catalog.pg_proc
                        JOIN pg_catalog.pg_namespace
                          ON pg_namespace.oid = pg_proc.pronamespace
                        WHERE pg_namespace.nspname = 'public'
                        """
                    )
                )
            )
            triggers = set(
                connection.scalars(
                    text(
                        """
                        SELECT tgname
                        FROM pg_catalog.pg_trigger
                        WHERE NOT tgisinternal
                        """
                    )
                )
            )
            constraints = set(
                connection.scalars(
                    text(
                        """
                        SELECT conname
                        FROM pg_catalog.pg_constraint
                        JOIN pg_catalog.pg_namespace
                          ON pg_namespace.oid = pg_constraint.connamespace
                        WHERE pg_namespace.nspname = 'public'
                        """
                    )
                )
            )
    finally:
        engine.dispose()
    return tables, functions, triggers, constraints


def _assert_phase_two_objects_present(database_url: str) -> None:
    tables, functions, triggers, constraints = _named_objects(database_url)
    assert tables >= PHASE_TWO_TABLES
    assert functions >= PHASE_TWO_FUNCTIONS
    assert triggers >= PHASE_TWO_TRIGGERS
    assert constraints >= PHASE_TWO_CONSTRAINTS


def _assert_phase_two_objects_absent(database_url: str) -> None:
    tables, functions, triggers, constraints = _named_objects(database_url)
    assert PHASE_TWO_TABLES.isdisjoint(tables)
    assert PHASE_TWO_FUNCTIONS.isdisjoint(functions)
    assert PHASE_TWO_TRIGGERS.isdisjoint(triggers)
    assert PHASE_TWO_CONSTRAINTS.isdisjoint(constraints)


@pytest.mark.parametrize(
    ("database_url", "expected_error"),
    [
        (
            "postgresql+asyncpg://postgres@db.example.test:5432/"
            "data_scrapy_workflow_plan_phase2_test",
            "localhost or 127.0.0.1",
        ),
        (
            "postgresql+asyncpg://postgres@127%2e0%2e0%2e1:5432/"
            "data_scrapy_workflow_plan_phase2_test",
            "encoded host or database",
        ),
        (
            "postgresql+asyncpg://postgres@127.0.0.1:5432/"
            "data_scrapy_workflow_plan_phase2_test?host=/var/run/postgresql",
            "query or fragment",
        ),
        (
            "postgresql+asyncpg://postgres@127.0.0.1:5432/data_scrapy",
            "must end with _workflow_plan_phase2_test",
        ),
        (
            "postgresql+asyncpg://postgres@127.0.0.1:5432/data_scrapy%5fworkflow_plan_phase2_test",
            "encoded host or database",
        ),
    ],
)
def test_migration_script_guard_rejects_unsafe_urls(
    database_url: str,
    expected_error: str,
) -> None:
    result = _run_guard(database_url)

    assert result.returncode != 0
    assert expected_error in result.stderr


@pytest.mark.parametrize(
    ("database_url", "allow_destructive", "expected_error"),
    [
        (None, "true", "TEST_DATABASE_URL is required"),
        (
            "postgresql+asyncpg://postgres@127.0.0.1:5432/data_scrapy_workflow_plan_phase2_test",
            None,
            "ALLOW_DESTRUCTIVE_MIGRATION_TEST=true is required",
        ),
        (
            "postgresql+asyncpg://postgres@127.0.0.1:5432/data_scrapy_workflow_plan_phase2_test",
            "TRUE",
            "ALLOW_DESTRUCTIVE_MIGRATION_TEST=true is required",
        ),
    ],
)
def test_migration_script_guard_requires_explicit_authorization(
    database_url: str | None,
    allow_destructive: str | None,
    expected_error: str,
) -> None:
    result = _run_guard(database_url, allow_destructive=allow_destructive)

    assert result.returncode != 0
    assert expected_error in result.stderr


def test_migration_script_guard_accepts_dedicated_local_database_without_leaking_url() -> None:
    password = "migration-guard-secret"
    database_url = (
        f"postgresql+asyncpg://postgres:{password}@127.0.0.1:55367/"
        "data_scrapy_workflow_plan_phase2_test"
    )

    result = _run_guard(database_url)

    assert result.returncode == 0
    assert password not in result.stdout
    assert password not in result.stderr
    assert database_url not in result.stdout
    assert database_url not in result.stderr
    assert "guard passed" in result.stdout


def test_fresh_database_upgrade_has_single_head_and_phase_two_objects(
    postgres_database_url: str,
) -> None:
    _reset_public_schema(postgres_database_url)

    _run_alembic(postgres_database_url, "upgrade", "head")

    heads = [
        line
        for line in _run_alembic(postgres_database_url, "heads").stdout.splitlines()
        if line.strip()
    ]
    assert heads == ["202607160033 (head)"]
    assert _database_revision(postgres_database_url) == "202607160033"
    _assert_phase_two_objects_present(postgres_database_url)


def test_upgrade_from_026_preserves_representative_legacy_data_and_project_schema(
    postgres_database_url: str,
) -> None:
    _reset_public_schema(postgres_database_url)
    _run_alembic(postgres_database_url, "upgrade", "202606110026")
    legacy = _seed_legacy_project(postgres_database_url)
    legacy_before = _legacy_snapshot(postgres_database_url, legacy)
    project_columns_before = _project_column_signature(postgres_database_url)

    _run_alembic(postgres_database_url, "upgrade", "202607160033")

    assert _database_revision(postgres_database_url) == "202607160033"
    assert _legacy_snapshot(postgres_database_url, legacy) == legacy_before
    assert _project_column_signature(postgres_database_url) == project_columns_before
    _assert_phase_two_objects_present(postgres_database_url)


def test_027_to_026_to_027_cleans_and_restores_all_phase_two_objects(
    postgres_database_url: str,
) -> None:
    _reset_public_schema(postgres_database_url)
    _run_alembic(postgres_database_url, "upgrade", "202606110026")
    legacy = _seed_legacy_project(postgres_database_url)
    legacy_before = _legacy_snapshot(postgres_database_url, legacy)
    project_columns_before = _project_column_signature(postgres_database_url)
    _run_alembic(postgres_database_url, "upgrade", "202607160033")
    _assert_phase_two_objects_present(postgres_database_url)

    _run_alembic(postgres_database_url, "downgrade", "202606110026")

    assert _database_revision(postgres_database_url) == "202606110026"
    assert _legacy_snapshot(postgres_database_url, legacy) == legacy_before
    assert _project_column_signature(postgres_database_url) == project_columns_before
    _assert_phase_two_objects_absent(postgres_database_url)

    _run_alembic(postgres_database_url, "upgrade", "202607160033")

    assert _database_revision(postgres_database_url) == "202607160033"
    assert _legacy_snapshot(postgres_database_url, legacy) == legacy_before
    assert _project_column_signature(postgres_database_url) == project_columns_before
    _assert_phase_two_objects_present(postgres_database_url)
