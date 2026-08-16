from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from sqlalchemy import Engine, create_engine, text

API_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_DATABASE_SUFFIX = "_workflow_lineage_test"


class RedactedDatabaseUrl(str):
    def __repr__(self) -> str:
        parsed = urlsplit(str(self))
        safe = f"{parsed.scheme}://***@{parsed.hostname}:{parsed.port}{parsed.path}"
        return repr(safe)


@dataclass(frozen=True, slots=True)
class LineageSeed:
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    other_project_id: uuid.UUID
    plan_id: uuid.UUID
    version_id: uuid.UUID
    workflow_run_id: uuid.UUID
    workflow_step_run_id: uuid.UUID
    dataset_id: uuid.UUID


def _guarded_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    lineage_url = os.getenv("WORKFLOW_LINEAGE_TEST_DATABASE_URL")
    authorized = os.getenv("WORKFLOW_LINEAGE_POSTGRES_TEST_AUTHORIZED")
    authorized_target = os.getenv("WORKFLOW_LINEAGE_AUTHORIZED_TARGET")
    if not database_url or not lineage_url or authorized != "true" or not authorized_target:
        pytest.skip(
            "Workflow Lineage PostgreSQL tests require independent authorization, "
            "test URL, exact target and DATABASE_URL"
        )
    if database_url != lineage_url:
        raise pytest.UsageError(
            "DATABASE_URL must exactly match WORKFLOW_LINEAGE_TEST_DATABASE_URL"
        )
    if any(character.isspace() for character in database_url):
        raise pytest.UsageError("DATABASE_URL must not contain whitespace")
    if any(character.isspace() for character in authorized_target):
        raise pytest.UsageError("WORKFLOW_LINEAGE_AUTHORIZED_TARGET must not contain whitespace")

    try:
        parsed = urlsplit(database_url)
        port = parsed.port
    except ValueError as exc:
        raise pytest.UsageError("DATABASE_URL host or port is invalid") from exc

    database_name = parsed.path.removeprefix("/")
    raw_authority = parsed.netloc.rsplit("@", 1)[-1]
    unsafe_reason: str | None = None
    if parsed.scheme != "postgresql+asyncpg":
        unsafe_reason = "DATABASE_URL must use postgresql+asyncpg"
    elif parsed.hostname not in {"localhost", "127.0.0.1"}:
        unsafe_reason = "DATABASE_URL must target localhost or 127.0.0.1"
    elif port is None:
        unsafe_reason = "DATABASE_URL must include an explicit port"
    elif parsed.query or parsed.fragment:
        unsafe_reason = "DATABASE_URL must not contain query or fragment"
    elif "%" in raw_authority or "%" in parsed.path:
        unsafe_reason = "DATABASE_URL must not contain encoded parts"
    elif not parsed.path.startswith("/") or parsed.path.count("/") != 1:
        unsafe_reason = "DATABASE_URL must name exactly one database"
    elif re.fullmatch(r"[A-Za-z0-9_]+", database_name) is None:
        unsafe_reason = "DATABASE_URL database name is invalid"
    elif not database_name.endswith(ALLOWED_DATABASE_SUFFIX):
        unsafe_reason = f"DATABASE_URL database must end with {ALLOWED_DATABASE_SUFFIX}"
    elif authorized_target != f"{parsed.hostname}:{port}/{database_name}":
        unsafe_reason = "WORKFLOW_LINEAGE_AUTHORIZED_TARGET must exactly match DATABASE_URL"
    if unsafe_reason is not None:
        raise pytest.UsageError(unsafe_reason)
    return RedactedDatabaseUrl(database_url)


def sync_database_url(database_url: str) -> str:
    return database_url.replace(
        "postgresql+asyncpg://",
        "postgresql+psycopg://",
        1,
    )


def run_alembic(database_url: str, *arguments: str) -> subprocess.CompletedProcess[str]:
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


def reset_public_schema(database_url: str) -> None:
    engine = create_engine(sync_database_url(database_url), isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
            connection.exec_driver_sql("CREATE SCHEMA public")
    finally:
        engine.dispose()


@pytest.fixture()
def guarded_database_url() -> str:
    return _guarded_database_url()


@pytest.fixture()
def postgres_database_url(guarded_database_url: str) -> str:
    reset_public_schema(guarded_database_url)
    run_alembic(guarded_database_url, "upgrade", "head")
    return guarded_database_url


@pytest.fixture()
def postgres_engine(postgres_database_url: str) -> Iterator[Engine]:
    engine = create_engine(sync_database_url(postgres_database_url))
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def seeded_lineage_graph(postgres_engine: Engine) -> LineageSeed:
    seed = LineageSeed(*(uuid.uuid4() for _ in range(9)))
    fingerprint = "sha256:" + "a" * 64
    with postgres_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, email, password_hash, name, status) "
                "VALUES (:id, :email, 'not-real', 'Lineage User', 'active')"
            ),
            {"id": seed.user_id, "email": f"{seed.user_id}@example.test"},
        )
        connection.execute(
            text(
                "INSERT INTO workspaces (id, name, slug, owner_id) "
                "VALUES (:id, 'Lineage Workspace', :slug, :owner_id)"
            ),
            {
                "id": seed.workspace_id,
                "slug": f"lineage-{seed.workspace_id}",
                "owner_id": seed.user_id,
            },
        )
        for project_id, suffix in (
            (seed.project_id, "primary"),
            (seed.other_project_id, "other"),
        ):
            connection.execute(
                text(
                    "INSERT INTO projects "
                    "(id, workspace_id, name, description, domain, status, owner_id) "
                    "VALUES (:id, :workspace_id, :name, NULL, 'social', 'active', :owner_id)"
                ),
                {
                    "id": project_id,
                    "workspace_id": seed.workspace_id,
                    "name": f"Lineage Project {suffix}",
                    "owner_id": seed.user_id,
                },
            )
        connection.execute(
            text(
                "INSERT INTO workflow_plans "
                "(id, workspace_id, project_id, created_by_user_id, name, "
                "flow_mode, status, current_version_id) VALUES "
                "(:id, :workspace_id, :project_id, :user_id, 'Lineage Plan', "
                "'periodic_monitoring', 'previewed', NULL)"
            ),
            {
                "id": seed.plan_id,
                "workspace_id": seed.workspace_id,
                "project_id": seed.project_id,
                "user_id": seed.user_id,
            },
        )
        connection.execute(
            text(
                "INSERT INTO workflow_versions "
                "(id, workspace_id, project_id, workflow_plan_id, created_by_user_id, "
                "version_number, planning_status, planner_contract_version, "
                "catalog_snapshot_id, policy_version, mode_template_version, "
                "query_versions, fingerprint_payload, normalized_input, plan_payload, "
                "preview_fingerprint) VALUES "
                "(:id, :workspace_id, :project_id, :plan_id, :user_id, 1, 'resolved', "
                "'workflow-planner.v1', 'catalog.lineage', 'policy.v1', 'mode.v1', "
                "CAST(:query_versions AS JSON), CAST(:fingerprint_payload AS JSON), "
                "CAST(:normalized_input AS JSON), CAST(:plan_payload AS JSON), "
                ":preview_fingerprint)"
            ),
            {
                "id": seed.version_id,
                "workspace_id": seed.workspace_id,
                "project_id": seed.project_id,
                "plan_id": seed.plan_id,
                "user_id": seed.user_id,
                "query_versions": json.dumps({"reddit": "reddit.v1"}),
                "fingerprint_payload": json.dumps({"lineage": True}),
                "normalized_input": json.dumps({"lineage": True}),
                "plan_payload": json.dumps({"routes": []}),
                "preview_fingerprint": fingerprint,
            },
        )
        connection.execute(
            text("UPDATE workflow_plans SET current_version_id = :version_id WHERE id = :plan_id"),
            {"version_id": seed.version_id, "plan_id": seed.plan_id},
        )
        connection.execute(
            text(
                "INSERT INTO workflow_runs "
                "(id, workspace_id, project_id, workflow_plan_id, workflow_version_id, "
                "created_by_user_id, execution_contract_version, execution_mode, status, "
                "planner_contract_version, preview_fingerprint, catalog_snapshot_id, "
                "policy_version, mode_template_version, query_versions, fixture_profile_id, "
                "fixture_profile_hash, total_steps, completed_steps, records_count, "
                "provider_call_attempted, credential_read_attempted, actor_run, browser_run, "
                "llm_call, production_write_allowed, started_at, finished_at) VALUES "
                "(:id, :workspace_id, :project_id, :plan_id, :version_id, :user_id, "
                "'workflow_execution_fixture.v1', 'fixture', 'completed', "
                "'workflow-planner.v1', :fingerprint, 'catalog.lineage', 'policy.v1', "
                "'mode.v1', CAST(:query_versions AS JSON), 'lineage.fixture.v1', "
                ":fingerprint, 1, 1, 1, false, false, false, false, false, false, NOW(), NOW())"
            ),
            {
                "id": seed.workflow_run_id,
                "workspace_id": seed.workspace_id,
                "project_id": seed.project_id,
                "plan_id": seed.plan_id,
                "version_id": seed.version_id,
                "user_id": seed.user_id,
                "fingerprint": fingerprint,
                "query_versions": json.dumps({"reddit": "reddit.v1"}),
            },
        )
        connection.execute(
            text(
                "INSERT INTO step_runs "
                "(id, workflow_run_id, workspace_id, project_id, step_ref, requirement_ref, "
                "sequence, platform, resource_type, operation, assertion_id, implementation_id, "
                "route_plan_snapshot, evidence_refs, fixture_case_id, fixture_content_hash, "
                "input_digest, output_digest, idempotency_scope, idempotency_key_hash, status, "
                "records_count, provider_call_attempted, credential_read_attempted, actor_run, "
                "browser_run, llm_call, production_write_allowed, started_at, finished_at) "
                "VALUES (:id, :run_id, :workspace_id, :project_id, 'primary:1', 'RUN-001', 1, "
                "'reddit', 'content', 'search_discover', 'assertion.lineage', "
                "'reddit.data-api.v1', CAST(:route AS JSON), CAST(:evidence AS JSON), "
                "'lineage-case', :fingerprint, :fingerprint, :fingerprint, 'lineage.scope', "
                ":fingerprint, 'completed', 1, false, false, false, false, false, false, "
                "NOW(), NOW())"
            ),
            {
                "id": seed.workflow_step_run_id,
                "run_id": seed.workflow_run_id,
                "workspace_id": seed.workspace_id,
                "project_id": seed.project_id,
                "route": json.dumps({"route": "primary"}),
                "evidence": json.dumps(["evidence.lineage"]),
                "fingerprint": fingerprint,
            },
        )
        connection.execute(
            text(
                "INSERT INTO datasets "
                "(id, workspace_id, project_id, name, dataset_type, status, description) "
                "VALUES (:id, :workspace_id, :project_id, 'Lineage Dataset', "
                "'social_raw', 'active', NULL)"
            ),
            {
                "id": seed.dataset_id,
                "workspace_id": seed.workspace_id,
                "project_id": seed.project_id,
            },
        )
    return seed
