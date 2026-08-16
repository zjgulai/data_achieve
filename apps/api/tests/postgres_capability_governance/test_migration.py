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
VERIFY_SCRIPT = REPOSITORY_ROOT / "scripts/verify-capability-governance-migration.sh"

GOVERNANCE_TABLES = {
    "capability_governance_memberships",
    "capability_discovery_batches",
    "capability_source_snapshots",
    "capability_discovery_batch_sources",
    "capability_evidence",
    "capability_candidate_versions",
    "capability_candidate_evidence",
    "capability_verification_tasks",
    "capability_verification_decisions",
    "capability_catalog_snapshots",
    "capability_publication_revisions",
    "capability_catalog_head",
    "capability_governance_requests",
}
IMMUTABLE_TABLES = {
    "capability_discovery_batches",
    "capability_source_snapshots",
    "capability_discovery_batch_sources",
    "capability_evidence",
    "capability_candidate_versions",
    "capability_candidate_evidence",
    "capability_verification_decisions",
    "capability_catalog_snapshots",
    "capability_publication_revisions",
    "capability_governance_requests",
}
GOVERNANCE_FUNCTIONS = {
    "reject_capability_governance_mutation",
    "enforce_capability_verification_task_transition",
    "enforce_capability_catalog_head_transition",
}
GOVERNANCE_TRIGGERS = {
    *(f"trg_{table_name}_immutable" for table_name in IMMUTABLE_TABLES),
    "trg_capability_verification_task_transition",
    "trg_capability_catalog_head_transition",
    "trg_cap_gov_membership_updated_at",
    "trg_cap_catalog_head_updated_at",
}
GOVERNANCE_INDEXES = {
    "uq_cap_verification_task_open",
    "ix_cap_candidate_key_created",
    "ix_cap_verification_status_opened",
    "ix_cap_publication_published",
    "ix_cap_gov_request_actor_created",
}
CRITICAL_GOVERNANCE_CONSTRAINTS = {
    "uq_cap_gov_membership_user",
    "uq_cap_discovery_batch_preview",
    "uq_cap_evidence_external_id",
    "fk_cap_candidate_predecessor_key",
    "uq_cap_candidate_key_version",
    "uq_cap_candidate_key_fingerprint",
    "uq_cap_verification_decision_task",
    "uq_cap_publication_revision_number",
    "uq_cap_gov_request_idempotency",
}
GOVERNANCE_CHECK_COUNTS = {
    "capability_governance_memberships": 1,
    "capability_source_snapshots": 1,
    "capability_discovery_batch_sources": 1,
    "capability_candidate_versions": 2,
    "capability_verification_tasks": 4,
    "capability_verification_decisions": 3,
    "capability_publication_revisions": 2,
    "capability_catalog_head": 2,
    "capability_governance_requests": 1,
}
PHASE_TWO_TABLES = {
    "monitoring_scopes",
    "query_terms",
    "workflow_plan_save_requests",
    "workflow_plans",
    "workflow_version_scopes",
    "workflow_versions",
}


@dataclass(frozen=True)
class PreGovernanceIds:
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    member_id: uuid.UUID
    project_id: uuid.UUID
    plan_id: uuid.UUID
    version_id: uuid.UUID


def _run_guard(
    database_url: str | None,
    *,
    authorized: str | None = "true",
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("CAPABILITY_GOVERNANCE_TEST_DATABASE_URL", None)
    environment.pop("CAPABILITY_GOVERNANCE_POSTGRES_TEST_AUTHORIZED", None)
    if database_url is not None:
        environment["CAPABILITY_GOVERNANCE_TEST_DATABASE_URL"] = database_url
    if authorized is not None:
        environment["CAPABILITY_GOVERNANCE_POSTGRES_TEST_AUTHORIZED"] = authorized
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


def _run_alembic(database_url: str, *arguments: str) -> subprocess.CompletedProcess[str]:
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


def _database_engine(database_url: str, *, autocommit: bool = False) -> Engine:
    return create_engine(
        _sync_database_url(database_url),
        isolation_level="AUTOCOMMIT" if autocommit else None,
    )


def _reset_public_schema(database_url: str) -> None:
    engine = _database_engine(database_url, autocommit=True)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
            connection.exec_driver_sql("CREATE SCHEMA public")
    finally:
        engine.dispose()


def _seed_pre_governance_state(database_url: str) -> PreGovernanceIds:
    ids = PreGovernanceIds(
        user_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        member_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        plan_id=uuid.uuid4(),
        version_id=uuid.uuid4(),
    )
    engine = _database_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO users (id, email, password_hash, name, status)
                    VALUES (:id, :email, 'not-a-real-password', 'Pre-028 User', 'active')
                    """
                ),
                {"id": ids.user_id, "email": f"{ids.user_id}@example.test"},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO workspaces (id, name, slug, owner_id)
                    VALUES (:id, 'Pre-028 Workspace', :slug, :owner_id)
                    """
                ),
                {
                    "id": ids.workspace_id,
                    "slug": f"pre-028-{ids.workspace_id}",
                    "owner_id": ids.user_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO workspace_members (id, workspace_id, user_id, role)
                    VALUES (:id, :workspace_id, :user_id, 'owner')
                    """
                ),
                {
                    "id": ids.member_id,
                    "workspace_id": ids.workspace_id,
                    "user_id": ids.user_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO projects (
                        id, workspace_id, name, description, domain, status, owner_id
                    ) VALUES (
                        :id, :workspace_id, 'Pre-028 Project',
                        'Must survive the Governance migration lifecycle.',
                        'osint', 'active', :owner_id
                    )
                    """
                ),
                {
                    "id": ids.project_id,
                    "workspace_id": ids.workspace_id,
                    "owner_id": ids.user_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO workflow_plans (
                        id, workspace_id, project_id, created_by_user_id,
                        name, flow_mode, status, current_version_id
                    ) VALUES (
                        :id, :workspace_id, :project_id, :user_id,
                        'Pre-028 Plan', 'periodic_monitoring', 'previewed', NULL
                    )
                    """
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
                    """
                    INSERT INTO workflow_versions (
                        id, workspace_id, project_id, workflow_plan_id,
                        created_by_user_id, version_number, planning_status,
                        planner_contract_version, catalog_snapshot_id, policy_version,
                        mode_template_version, query_versions, fingerprint_payload,
                        normalized_input, plan_payload, preview_fingerprint
                    ) VALUES (
                        :id, :workspace_id, :project_id, :plan_id,
                        :user_id, 1, 'resolved',
                        'workflow-planner.v1', 'catalog.pre-028', 'policy.v1',
                        'mode-template.v1', CAST(:query_versions AS JSON),
                        CAST(:fingerprint_payload AS JSON), CAST(:normalized_input AS JSON),
                        CAST(:plan_payload AS JSON), :preview_fingerprint
                    )
                    """
                ),
                {
                    "id": ids.version_id,
                    "workspace_id": ids.workspace_id,
                    "project_id": ids.project_id,
                    "plan_id": ids.plan_id,
                    "user_id": ids.user_id,
                    "query_versions": json.dumps({"compiler": "v1"}),
                    "fingerprint_payload": json.dumps({"phase": "pre-028"}),
                    "normalized_input": json.dumps({"brand": "example"}),
                    "plan_payload": json.dumps({"routes": []}),
                    "preview_fingerprint": f"sha256:{'a' * 64}",
                },
            )
            connection.execute(
                text(
                    """
                    UPDATE workflow_plans
                    SET current_version_id = :version_id
                    WHERE id = :plan_id
                    """
                ),
                {"version_id": ids.version_id, "plan_id": ids.plan_id},
            )
    finally:
        engine.dispose()
    return ids


def _pre_governance_snapshot(
    database_url: str,
    ids: PreGovernanceIds,
) -> tuple[tuple[object, ...], ...]:
    engine = _database_engine(database_url)
    try:
        with engine.connect() as connection:
            statements = (
                (
                    "SELECT id, email, name, status FROM users WHERE id = :id",
                    ids.user_id,
                ),
                (
                    "SELECT id, workspace_id, name, domain, status, owner_id "
                    "FROM projects WHERE id = :id",
                    ids.project_id,
                ),
                (
                    "SELECT id, workspace_id, project_id, name, flow_mode, status, "
                    "current_version_id FROM workflow_plans WHERE id = :id",
                    ids.plan_id,
                ),
                (
                    "SELECT id, workflow_plan_id, version_number, planning_status, "
                    "catalog_snapshot_id, preview_fingerprint "
                    "FROM workflow_versions WHERE id = :id",
                    ids.version_id,
                ),
            )
            return tuple(
                tuple(connection.execute(text(statement), {"id": row_id}).one())
                for statement, row_id in statements
            )
    finally:
        engine.dispose()


def _database_revision(database_url: str) -> str:
    engine = _database_engine(database_url)
    try:
        with engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
    finally:
        engine.dispose()
    assert isinstance(revision, str)
    return revision


def _named_objects(
    database_url: str,
) -> tuple[set[str], set[str], set[str], set[str], set[str]]:
    engine = _database_engine(database_url)
    try:
        with engine.connect() as connection:
            tables = set(
                connection.scalars(
                    text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'")
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
                        SELECT pg_trigger.tgname
                        FROM pg_catalog.pg_trigger
                        JOIN pg_catalog.pg_class ON pg_class.oid = pg_trigger.tgrelid
                        JOIN pg_catalog.pg_namespace
                          ON pg_namespace.oid = pg_class.relnamespace
                        WHERE NOT pg_trigger.tgisinternal
                          AND pg_namespace.nspname = 'public'
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
            indexes = set(
                connection.scalars(
                    text("SELECT indexname FROM pg_catalog.pg_indexes WHERE schemaname = 'public'")
                )
            )
    finally:
        engine.dispose()
    return tables, functions, triggers, constraints, indexes


def _governance_check_counts(database_url: str) -> dict[str, int]:
    engine = _database_engine(database_url)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT pg_class.relname, count(*)
                    FROM pg_catalog.pg_constraint
                    JOIN pg_catalog.pg_class
                      ON pg_class.oid = pg_constraint.conrelid
                    JOIN pg_catalog.pg_namespace
                      ON pg_namespace.oid = pg_class.relnamespace
                    WHERE pg_namespace.nspname = 'public'
                      AND pg_constraint.contype = 'c'
                      AND pg_class.relname LIKE 'capability_%'
                    GROUP BY pg_class.relname
                    """
                )
            ).all()
    finally:
        engine.dispose()
    return {str(table_name): int(count) for table_name, count in rows}


def _assert_governance_objects_present(database_url: str) -> None:
    tables, functions, triggers, constraints, indexes = _named_objects(database_url)
    assert tables >= GOVERNANCE_TABLES
    assert functions >= GOVERNANCE_FUNCTIONS
    assert triggers >= GOVERNANCE_TRIGGERS
    assert constraints >= CRITICAL_GOVERNANCE_CONSTRAINTS
    assert indexes >= GOVERNANCE_INDEXES
    assert _governance_check_counts(database_url) == GOVERNANCE_CHECK_COUNTS


def _assert_governance_objects_absent(database_url: str) -> None:
    tables, functions, triggers, constraints, indexes = _named_objects(database_url)
    assert GOVERNANCE_TABLES.isdisjoint(tables)
    assert GOVERNANCE_FUNCTIONS.isdisjoint(functions)
    assert GOVERNANCE_TRIGGERS.isdisjoint(triggers)
    assert CRITICAL_GOVERNANCE_CONSTRAINTS.isdisjoint(constraints)
    assert GOVERNANCE_INDEXES.isdisjoint(indexes)
    assert not (GOVERNANCE_CHECK_COUNTS.keys() & _governance_check_counts(database_url).keys())


@pytest.mark.parametrize(
    ("database_url", "expected_error"),
    [
        (
            "postgresql+asyncpg://postgres@db.example.test:5432/"
            "data_scrapy_capability_governance_test",
            "must target localhost",
        ),
        (
            "postgresql+asyncpg://postgres@127%2e0%2e0%2e1:5432/"
            "data_scrapy_capability_governance_test",
            "must not contain encoded parts",
        ),
        (
            "postgresql+asyncpg://postgres@127.0.0.1:5432/"
            "data_scrapy_capability_governance_test?host=/var/run/postgresql",
            "must not contain query or fragment",
        ),
        (
            "postgresql+asyncpg://postgres@127.0.0.1:5432/data_scrapy",
            "must end with _capability_governance_test",
        ),
    ],
)
def test_migration_guard_rejects_unsafe_urls(
    database_url: str,
    expected_error: str,
) -> None:
    result = _run_guard(database_url)

    assert result.returncode != 0
    assert expected_error in result.stderr


@pytest.mark.parametrize(
    ("database_url", "authorized"),
    [
        (None, "true"),
        (
            "postgresql+asyncpg://postgres@127.0.0.1:55367/data_scrapy_capability_governance_test",
            None,
        ),
        (
            "postgresql+asyncpg://postgres@127.0.0.1:55367/data_scrapy_capability_governance_test",
            "TRUE",
        ),
    ],
)
def test_migration_guard_requires_explicit_authorization(
    database_url: str | None,
    authorized: str | None,
) -> None:
    result = _run_guard(database_url, authorized=authorized)

    assert result.returncode != 0


def test_migration_guard_accepts_local_dedicated_database_without_leaking_url() -> None:
    password = "migration-guard-secret"
    database_url = (
        f"postgresql+asyncpg://postgres:{password}@127.0.0.1:55367/"
        "data_scrapy_capability_governance_test"
    )

    result = _run_guard(database_url)

    assert result.returncode == 0
    assert password not in result.stdout
    assert password not in result.stderr
    assert database_url not in result.stdout
    assert database_url not in result.stderr
    assert "guard passed" in result.stdout


def test_fresh_upgrade_has_single_head_objects_and_only_system_head_seed(
    postgres_database_url: str,
) -> None:
    _reset_public_schema(postgres_database_url)
    _run_alembic(postgres_database_url, "upgrade", "head")

    heads = [
        line
        for line in _run_alembic(postgres_database_url, "heads").stdout.splitlines()
        if line.strip()
    ]
    assert heads == ["202607170034 (head)"]
    assert _database_revision(postgres_database_url) == "202607170034"
    _assert_governance_objects_present(postgres_database_url)

    engine = _database_engine(postgres_database_url)
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
            counts = {
                table_name: connection.scalar(text(f"SELECT count(*) FROM {table_name}"))
                for table_name in GOVERNANCE_TABLES - {"capability_catalog_head"}
            }
    finally:
        engine.dispose()

    assert head == ("global", None, 0)
    assert set(counts.values()) == {0}


def test_027_to_028_preserves_legacy_and_phase_two_state(
    postgres_database_url: str,
) -> None:
    _reset_public_schema(postgres_database_url)
    _run_alembic(postgres_database_url, "upgrade", "202606110027")
    ids = _seed_pre_governance_state(postgres_database_url)
    before = _pre_governance_snapshot(postgres_database_url, ids)

    _run_alembic(postgres_database_url, "upgrade", "202606110028")

    assert _database_revision(postgres_database_url) == "202606110028"
    assert _pre_governance_snapshot(postgres_database_url, ids) == before
    tables, _, _, _, _ = _named_objects(postgres_database_url)
    assert tables >= PHASE_TWO_TABLES
    _assert_governance_objects_present(postgres_database_url)


def test_028_to_027_to_028_cleans_and_restores_governance_objects(
    postgres_database_url: str,
) -> None:
    _reset_public_schema(postgres_database_url)
    _run_alembic(postgres_database_url, "upgrade", "202606110027")
    ids = _seed_pre_governance_state(postgres_database_url)
    before = _pre_governance_snapshot(postgres_database_url, ids)
    _run_alembic(postgres_database_url, "upgrade", "202606110028")
    _assert_governance_objects_present(postgres_database_url)

    _run_alembic(postgres_database_url, "downgrade", "202606110027")

    assert _database_revision(postgres_database_url) == "202606110027"
    assert _pre_governance_snapshot(postgres_database_url, ids) == before
    tables, _, _, _, _ = _named_objects(postgres_database_url)
    assert tables >= PHASE_TWO_TABLES
    _assert_governance_objects_absent(postgres_database_url)

    _run_alembic(postgres_database_url, "upgrade", "202606110028")

    assert _database_revision(postgres_database_url) == "202606110028"
    assert _pre_governance_snapshot(postgres_database_url, ids) == before
    _assert_governance_objects_present(postgres_database_url)
