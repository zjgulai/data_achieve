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
from sqlalchemy import create_engine, update
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workflow_execution import StepRun, WorkflowRun
from data_intelligence_hub.models.workflow_plan import WorkflowPlan, WorkflowVersion
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.schemas.workflow_action_command import (
    RetryActionParameters,
    WorkflowActionApprovalRequest,
    WorkflowRunActionRequest,
)
from data_intelligence_hub.services.workflow_execution.action_command import (
    WorkflowActionCommandEvidence,
    issue_workflow_action_approval,
)

API_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_HOST = "127.0.0.1"
EXPECTED_PORT = 55443
EXPECTED_DATABASE = "uix09_phase_e_20260728_workflow_execution_test"
EXPECTED_USER = "phase_e_test"
EXPECTED_TARGET = f"{EXPECTED_HOST}:{EXPECTED_PORT}/{EXPECTED_DATABASE}"
NOW = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
DIGEST_D = "sha256:" + "d" * 64


@dataclass(frozen=True, slots=True)
class PostgresDatabase:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]


@dataclass(frozen=True, slots=True)
class SeededActionRun:
    database: PostgresDatabase
    owner_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    run_id: uuid.UUID
    step_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class RetryCommand:
    seed: SeededActionRun
    request: WorkflowRunActionRequest
    evidence: WorkflowActionCommandEvidence
    idempotency_key: str


def _guarded_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    workflow_url = os.getenv("WORKFLOW_ACTION_TEST_DATABASE_URL")
    authorized = os.getenv("WORKFLOW_ACTION_POSTGRES_TEST_AUTHORIZED")
    authorized_target = os.getenv("WORKFLOW_ACTION_AUTHORIZED_TARGET")
    if not database_url or not workflow_url or authorized != "true" or not authorized_target:
        pytest.skip(
            "Workflow Action PostgreSQL tests require independent authorization, "
            "the exact test URL, target and DATABASE_URL"
        )
    if database_url != workflow_url:
        raise pytest.UsageError("DATABASE_URL must exactly match WORKFLOW_ACTION_TEST_DATABASE_URL")
    if any(character.isspace() for character in database_url + authorized_target):
        raise pytest.UsageError("Workflow Action PostgreSQL inputs must not contain whitespace")

    try:
        parsed = urlsplit(database_url)
        port = parsed.port
    except ValueError as exc:
        raise pytest.UsageError("DATABASE_URL host or port is invalid") from exc

    raw_authority = parsed.netloc.rsplit("@", 1)[-1]
    unsafe_reason: str | None = None
    if parsed.scheme != "postgresql+asyncpg":
        unsafe_reason = "DATABASE_URL must use postgresql+asyncpg"
    elif parsed.hostname != EXPECTED_HOST or port != EXPECTED_PORT:
        unsafe_reason = "DATABASE_URL must match the approved loopback endpoint"
    elif parsed.username != EXPECTED_USER or parsed.password is not None:
        unsafe_reason = "DATABASE_URL must use the approved password-free test user"
    elif parsed.path != f"/{EXPECTED_DATABASE}":
        unsafe_reason = "DATABASE_URL must match the approved database"
    elif parsed.query or parsed.fragment:
        unsafe_reason = "DATABASE_URL must not contain query or fragment"
    elif "%" in raw_authority or "%" in parsed.path:
        unsafe_reason = "DATABASE_URL must not contain encoded parts"
    elif authorized_target != EXPECTED_TARGET:
        unsafe_reason = "WORKFLOW_ACTION_AUTHORIZED_TARGET must match the approved target"
    elif re.fullmatch(r"[A-Za-z0-9_]+", parsed.path.removeprefix("/")) is None:
        unsafe_reason = "DATABASE_URL database name is invalid"
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


@pytest.fixture()
def postgres_database_url() -> str:
    database_url = _guarded_database_url()
    _reset_public_schema(database_url)
    return database_url


@pytest.fixture()
def sync_database_url(postgres_database_url: str) -> str:
    return _sync_database_url(postgres_database_url)


@pytest.fixture()
def alembic_runner(
    postgres_database_url: str,
) -> Callable[..., subprocess.CompletedProcess[str]]:
    def run(*arguments: str) -> subprocess.CompletedProcess[str]:
        return _run_alembic(postgres_database_url, *arguments)

    return run


@pytest_asyncio.fixture()
async def postgres_database(postgres_database_url: str) -> AsyncIterator[PostgresDatabase]:
    _run_alembic(postgres_database_url, "upgrade", "head")
    engine = create_async_engine(postgres_database_url)
    database = PostgresDatabase(
        engine=engine,
        sessions=async_sessionmaker(engine, expire_on_commit=False),
    )
    try:
        yield database
    finally:
        await engine.dispose()


@pytest_asyncio.fixture()
async def seeded_action_run(postgres_database: PostgresDatabase) -> SeededActionRun:
    owner_id, workspace_id, project_id, plan_id, version_id, run_id, step_id = (
        uuid.uuid4() for _ in range(7)
    )
    async with postgres_database.sessions() as session:
        session.add(
            User(
                id=owner_id,
                email=f"phase-e-{owner_id}@example.test",
                password_hash="fixture-only",
                name="Phase E Owner",
                status="active",
            )
        )
        await session.flush()
        session.add(
            Workspace(
                id=workspace_id,
                name="Phase E",
                slug=f"phase-e-{workspace_id}",
                owner_id=owner_id,
            )
        )
        await session.flush()
        session.add(
            Project(
                id=project_id,
                workspace_id=workspace_id,
                owner_id=owner_id,
                name="Phase E",
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
                name="Phase E",
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
        await session.execute(
            update(WorkflowPlan)
            .where(WorkflowPlan.id == plan_id)
            .values(current_version_id=version_id)
        )
        session.add(
            WorkflowRun(
                id=run_id,
                workspace_id=workspace_id,
                project_id=project_id,
                workflow_plan_id=plan_id,
                workflow_version_id=version_id,
                created_by_user_id=owner_id,
                execution_contract_version="workflow_execution_fixture.v1",
                execution_mode="fixture",
                status="held",
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
                status_reason_code="workflow_step_retry_exhausted",
                impact_code="workflow_run_incomplete",
                missing_fields=[],
                recovery_action_codes=["retry_failed_steps"],
                started_at=NOW,
                finished_at=None,
                created_at=NOW,
            )
        )
        await session.flush()
        session.add(
            StepRun(
                id=step_id,
                workflow_run_id=run_id,
                workspace_id=workspace_id,
                project_id=project_id,
                step_ref="step.youtube.search",
                requirement_ref="requirement.youtube.search",
                sequence=1,
                retry_generation=0,
                platform="youtube",
                resource_type="video",
                operation="search",
                assertion_id="assertion.youtube.search",
                implementation_id="youtube.official.search",
                route_plan_snapshot={"ordered_candidates": ["youtube.official.search"]},
                evidence_refs=["fixture:phase-e"],
                fixture_case_id=None,
                fixture_content_hash=None,
                input_digest=DIGEST_A,
                output_digest=None,
                idempotency_scope=f"step_run.v1:{run_id}:{step_id}",
                idempotency_key_hash=DIGEST_B,
                status="failed",
                records_count=0,
                started_at=NOW,
                finished_at=NOW,
                created_at=NOW,
            )
        )
        await session.commit()
    return SeededActionRun(
        database=postgres_database,
        owner_id=owner_id,
        workspace_id=workspace_id,
        project_id=project_id,
        run_id=run_id,
        step_id=step_id,
    )


@pytest_asyncio.fixture()
async def retry_command(seeded_action_run: SeededActionRun) -> RetryCommand:
    seed = seeded_action_run
    parameters = RetryActionParameters(
        target_step_run_ids=[seed.step_id],
        expected_retry_generation=0,
        attempt_evidence_digest=DIGEST_A,
        retry_policy_digest=DIGEST_B,
    )
    evidence = WorkflowActionCommandEvidence(
        action_gate_digest=DIGEST_D,
        evidence_digests=(DIGEST_A, DIGEST_B),
        retry_policy_available=True,
        retry_generation_limit=3,
    )
    async with seed.database.sessions() as session:
        approval = await issue_workflow_action_approval(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_run_id=seed.run_id,
            actor_user_id=seed.owner_id,
            idempotency_key="phase-e-postgres-approval",
            http_request_id="req-phase-e-postgres-approval",
            request=WorkflowActionApprovalRequest(
                action="retry",
                approval_kind="owner_confirmation",
                expected_action_context_version=1,
                expected_run_status="held",
                action_gate_digest=DIGEST_D,
                reason_code="retry_after_retryable_failure",
                reason="Owner reviewed the disposable PostgreSQL retry evidence.",
                parameters=parameters,
            ),
            evidence=evidence,
            evaluated_at=NOW,
        )
    return RetryCommand(
        seed=seed,
        request=WorkflowRunActionRequest(
            action="retry",
            approval_receipt_id=approval.id,
            expected_action_context_version=1,
            expected_run_status="held",
            action_gate_digest=DIGEST_D,
            reason_code="retry_after_retryable_failure",
            reason="Owner reviewed the disposable PostgreSQL retry evidence.",
            parameters=parameters,
        ),
        evidence=evidence,
        idempotency_key="phase-e-postgres-action",
    )
