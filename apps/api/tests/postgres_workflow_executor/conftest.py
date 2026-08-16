from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workflow_execution import StepRun, WorkflowRun
from data_intelligence_hub.models.workflow_executor import WorkflowExecutionDispatchRecord
from data_intelligence_hub.models.workflow_plan import WorkflowPlan, WorkflowVersion
from data_intelligence_hub.models.workspace import Workspace

API_ROOT = Path(__file__).resolve().parents[2]
REVISION = "202607280044"
DATABASE_SUFFIX = "_workflow_executor_test"
CLEANUP_CONTRACT = "destroy_exact_runner_and_prove_port_closed"
NOW = datetime(2026, 7, 28, 16, 0, tzinfo=UTC)
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
DIGEST_D = "sha256:" + "d" * 64


@dataclass(frozen=True, slots=True)
class PostgresDatabase:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]


@dataclass(frozen=True, slots=True)
class SeededExecutor:
    database: PostgresDatabase
    owner_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    plan_id: uuid.UUID
    version_id: uuid.UUID
    run_id: uuid.UUID
    step_id: uuid.UUID
    dispatch_id: uuid.UUID
    dispatch_key: str


def _guarded_database_url() -> str:
    names = (
        "DATABASE_URL",
        "WORKFLOW_EXECUTOR_TEST_DATABASE_URL",
        "WORKFLOW_EXECUTOR_AUTHORIZED_TARGET",
        "WORKFLOW_EXECUTOR_RUNNER_ID",
        "WORKFLOW_EXECUTOR_POSTGRES_IMAGE",
        "WORKFLOW_EXECUTOR_CLEANUP_CONTRACT",
        "WORKFLOW_EXECUTOR_AUTHORIZATION",
    )
    values = {name: os.getenv(name) for name in names}
    authorized = os.getenv("WORKFLOW_EXECUTOR_POSTGRES_TEST_AUTHORIZED")
    runtime_authorized = os.getenv("WORKFLOW_EXECUTOR_RUNTIME_AUTHORIZED")
    if authorized is None and runtime_authorized is None and not any(values.values()):
        pytest.skip(
            "Workflow Executor PostgreSQL candidate requires a separately approved "
            "exact target and runtime tuple"
        )
    missing = [name for name, value in values.items() if not value]
    if authorized != "true":
        missing.append("WORKFLOW_EXECUTOR_POSTGRES_TEST_AUTHORIZED=true")
    if runtime_authorized != "true":
        missing.append("WORKFLOW_EXECUTOR_RUNTIME_AUTHORIZED=true")
    if missing:
        raise pytest.UsageError(
            "incomplete Workflow Executor PostgreSQL authority: " + ", ".join(missing)
        )

    database_url = values["DATABASE_URL"]
    workflow_url = values["WORKFLOW_EXECUTOR_TEST_DATABASE_URL"]
    authorized_target = values["WORKFLOW_EXECUTOR_AUTHORIZED_TARGET"]
    runner_id = values["WORKFLOW_EXECUTOR_RUNNER_ID"]
    image = values["WORKFLOW_EXECUTOR_POSTGRES_IMAGE"]
    cleanup_contract = values["WORKFLOW_EXECUTOR_CLEANUP_CONTRACT"]
    authorization = values["WORKFLOW_EXECUTOR_AUTHORIZATION"]
    assert database_url is not None
    assert workflow_url is not None
    assert authorized_target is not None
    assert runner_id is not None
    assert image is not None
    assert cleanup_contract is not None
    assert authorization is not None
    if database_url != workflow_url:
        raise pytest.UsageError(
            "DATABASE_URL must exactly match WORKFLOW_EXECUTOR_TEST_DATABASE_URL"
        )
    if any(
        character.isspace()
        for character in (
            database_url + authorized_target + runner_id + image + cleanup_contract + authorization
        )
    ):
        raise pytest.UsageError("Workflow Executor PostgreSQL inputs must not contain whitespace")

    try:
        parsed = urlsplit(database_url)
        port = parsed.port
    except ValueError as exc:
        raise pytest.UsageError("DATABASE_URL host or port is invalid") from exc
    database_name = parsed.path.removeprefix("/")
    raw_authority = parsed.netloc.rsplit("@", 1)[-1]
    image_match = re.fullmatch(r"postgres:([0-9]{2})(?:\.[0-9]+)?", image)
    unsafe_reason: str | None = None
    if parsed.scheme != "postgresql+asyncpg":
        unsafe_reason = "DATABASE_URL must use postgresql+asyncpg"
    elif parsed.hostname not in {"localhost", "127.0.0.1"}:
        unsafe_reason = "DATABASE_URL must target localhost"
    elif port is None:
        unsafe_reason = "DATABASE_URL must include an explicit port"
    elif parsed.username is None or parsed.password is not None:
        unsafe_reason = "DATABASE_URL must use a password-free test user"
    elif parsed.query or parsed.fragment:
        unsafe_reason = "DATABASE_URL must not contain query or fragment"
    elif "%" in raw_authority or "%" in parsed.path:
        unsafe_reason = "DATABASE_URL must not contain encoded parts"
    elif not parsed.path.startswith("/") or parsed.path.count("/") != 1:
        unsafe_reason = "DATABASE_URL must name exactly one database"
    elif re.fullmatch(r"[A-Za-z0-9_]+", database_name) is None:
        unsafe_reason = "DATABASE_URL database name is invalid"
    elif not database_name.endswith(DATABASE_SUFFIX):
        unsafe_reason = f"DATABASE_URL database must end with {DATABASE_SUFFIX}"
    elif authorized_target != f"{parsed.hostname}:{port}/{database_name}":
        unsafe_reason = "authorized target must exactly match DATABASE_URL"
    elif re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", runner_id) is None:
        unsafe_reason = "runner id is invalid"
    elif image_match is None or int(image_match.group(1)) < 15:
        unsafe_reason = "PostgreSQL image must pin version 15 or newer"
    elif cleanup_contract != CLEANUP_CONTRACT:
        unsafe_reason = "cleanup contract is invalid"
    expected_authorization = (
        "authorize-workflow-executor-postgres-candidate:"
        f"{authorized_target}:revision-{REVISION}:runner-{runner_id}:"
        f"image-{image}:cleanup-{cleanup_contract}"
    )
    if unsafe_reason is None and authorization != expected_authorization:
        unsafe_reason = "authorization does not match the exact candidate tuple"
    if unsafe_reason is not None:
        raise pytest.UsageError(unsafe_reason)
    return database_url


def _sync_database_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)


def _reset_public_schema(database_url: str) -> None:
    engine = create_engine(_sync_database_url(database_url), isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
            connection.exec_driver_sql("CREATE SCHEMA public")
    finally:
        engine.dispose()


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


@pytest.fixture()
def postgres_database_url() -> str:
    return _guarded_database_url()


@pytest.fixture()
def clean_database_url(postgres_database_url: str) -> str:
    _reset_public_schema(postgres_database_url)
    return postgres_database_url


@pytest.fixture()
def alembic_runner(
    clean_database_url: str,
) -> Callable[..., subprocess.CompletedProcess[str]]:
    def run(*arguments: str) -> subprocess.CompletedProcess[str]:
        return _run_alembic(clean_database_url, *arguments)

    return run


@pytest_asyncio.fixture()
async def postgres_database(clean_database_url: str) -> AsyncIterator[PostgresDatabase]:
    _run_alembic(clean_database_url, "upgrade", "head")
    engine = create_async_engine(clean_database_url)
    database = PostgresDatabase(
        engine=engine,
        sessions=async_sessionmaker(engine, expire_on_commit=False),
    )
    try:
        yield database
    finally:
        await engine.dispose()


@pytest_asyncio.fixture()
async def seeded_executor(postgres_database: PostgresDatabase) -> SeededExecutor:
    owner_id, workspace_id, project_id, plan_id, version_id, run_id, step_id = (
        uuid.uuid4() for _ in range(7)
    )
    dispatch = WorkflowExecutionDispatchRecord(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_plan_id=plan_id,
        workflow_version_id=version_id,
        workflow_run_id=run_id,
        workflow_step_run_id=step_id,
        attempt_generation=0,
        source_action_request_id=None,
        source_action_receipt_id=None,
        workflow_version_digest=DIGEST_A,
        execution_policy_digest=DIGEST_B,
        dispatch_key=DIGEST_C,
        provider_side_effect_key=DIGEST_D,
        state="claimable",
        created_at=NOW,
    )
    workflow_run = WorkflowRun(
        id=run_id,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_plan_id=plan_id,
        workflow_version_id=version_id,
        created_by_user_id=owner_id,
        execution_contract_version="workflow_execution_fixture.v1",
        execution_mode="fixture",
        status="running",
        planner_contract_version="workflow_planner.v1",
        preview_fingerprint=DIGEST_B,
        catalog_snapshot_id=DIGEST_A,
        policy_version="policy.v1",
        mode_template_version="periodic.v1",
        query_versions={"youtube": "youtube.v1"},
        fixture_profile_id="fixture-primary-v1",
        fixture_profile_hash=DIGEST_C,
        total_steps=1,
        completed_steps=0,
        records_count=0,
        status_reason_code=None,
        impact_code=None,
        missing_fields=[],
        recovery_action_codes=[],
        started_at=NOW,
        finished_at=None,
        created_at=NOW,
    )
    step_run = StepRun(
        id=step_id,
        workflow_run_id=run_id,
        workspace_id=workspace_id,
        project_id=project_id,
        step_ref="collect.youtube.v1",
        requirement_ref="youtube.search.v1",
        sequence=1,
        retry_generation=0,
        platform="youtube",
        resource_type="video",
        operation="search",
        assertion_id="youtube.search.v1",
        implementation_id="fixture.youtube.search.v1",
        route_plan_snapshot={},
        evidence_refs=[],
        fixture_case_id=None,
        fixture_content_hash=None,
        input_digest=DIGEST_A,
        output_digest=None,
        idempotency_scope=f"step.v1:{run_id}:{step_id}",
        idempotency_key_hash=DIGEST_B,
        status="pending",
        records_count=0,
        started_at=NOW,
        finished_at=None,
        created_at=NOW,
    )
    async with postgres_database.sessions.begin() as session:
        session.add(
            User(
                id=owner_id,
                email=f"f2b-{owner_id}@example.test",
                password_hash="fixture-only",
                name="F2B Candidate Owner",
                status="active",
            )
        )
        await session.flush()
        session.add(
            Workspace(
                id=workspace_id,
                name="F2B Candidate",
                slug=f"f2b-{workspace_id}",
                owner_id=owner_id,
            )
        )
        await session.flush()
        session.add(
            Project(
                id=project_id,
                workspace_id=workspace_id,
                owner_id=owner_id,
                name="F2B Candidate",
                description=None,
                domain="social",
                status="active",
            )
        )
        await session.flush()
        session.add(
            WorkflowPlan(
                id=plan_id,
                workspace_id=workspace_id,
                project_id=project_id,
                created_by_user_id=owner_id,
                name="F2B Candidate",
                flow_mode="periodic_monitoring",
                status="previewed",
                current_version_id=None,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        await session.flush()
        session.add(
            WorkflowVersion(
                id=version_id,
                workspace_id=workspace_id,
                project_id=project_id,
                workflow_plan_id=plan_id,
                created_by_user_id=owner_id,
                version_number=1,
                planning_status="resolved",
                planner_contract_version="workflow_planner.v1",
                catalog_snapshot_id=DIGEST_A,
                policy_version="policy.v1",
                mode_template_version="periodic.v1",
                query_versions={"youtube": "youtube.v1"},
                fingerprint_payload={},
                normalized_input={},
                plan_payload={},
                preview_fingerprint=DIGEST_B,
                created_at=NOW,
            )
        )
        await session.flush()
        workflow_plan = await session.get(WorkflowPlan, plan_id)
        assert workflow_plan is not None
        workflow_plan.current_version_id = version_id
        await session.flush()
        session.add(workflow_run)
        await session.flush()
        session.add(step_run)
        await session.flush()
        session.add(dispatch)
    return SeededExecutor(
        database=postgres_database,
        owner_id=owner_id,
        workspace_id=workspace_id,
        project_id=project_id,
        plan_id=plan_id,
        version_id=version_id,
        run_id=run_id,
        step_id=step_id,
        dispatch_id=dispatch.id,
        dispatch_key=dispatch.dispatch_key,
    )
