from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
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
from data_intelligence_hub.models.workflow_plan import WorkflowPlan, WorkflowVersion
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.schemas.capability_catalog import CapabilityCatalog
from data_intelligence_hub.schemas.workflow_plan_persistence import (
    serialize_preview_snapshot,
)
from data_intelligence_hub.schemas.workflow_planner import PlanningInput
from data_intelligence_hub.services.workflow_planner.planner import (
    build_workflow_plan_result,
)

API_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = API_ROOT / "tests" / "fixtures" / "workflow_planner"
PERIODIC_FIXTURE = FIXTURE_DIR / "periodic_monitoring_request_v1.json"
SYNTHETIC_CATALOG_FIXTURE = FIXTURE_DIR / "synthetic_capability_catalog_v1.json"
ALLOWED_DATABASE_SUFFIX = "_workflow_execution_test"
NOW = datetime(2026, 7, 15, 17, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class PostgresDatabase:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]


@dataclass(frozen=True, slots=True)
class SeededWorkflowVersion:
    database: PostgresDatabase
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    plan_id: uuid.UUID
    version_id: uuid.UUID
    preview_fingerprint: str


def _guarded_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    workflow_url = os.getenv("WORKFLOW_EXECUTION_TEST_DATABASE_URL")
    authorized = os.getenv("WORKFLOW_EXECUTION_POSTGRES_TEST_AUTHORIZED")
    authorized_target = os.getenv("WORKFLOW_EXECUTION_AUTHORIZED_TARGET")
    if not database_url or not workflow_url or authorized != "true" or not authorized_target:
        pytest.skip(
            "Workflow Execution PostgreSQL tests require the independent authorization, "
            "test URL, exact target and DATABASE_URL"
        )
    if database_url != workflow_url:
        raise pytest.UsageError(
            "DATABASE_URL must exactly match WORKFLOW_EXECUTION_TEST_DATABASE_URL"
        )
    if any(character.isspace() for character in database_url):
        raise pytest.UsageError("DATABASE_URL must not contain whitespace")
    if any(character.isspace() for character in authorized_target):
        raise pytest.UsageError("WORKFLOW_EXECUTION_AUTHORIZED_TARGET must not contain whitespace")

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
        unsafe_reason = "WORKFLOW_EXECUTION_AUTHORIZED_TARGET must exactly match DATABASE_URL"
    if unsafe_reason is not None:
        raise pytest.UsageError(unsafe_reason)
    return database_url


def _sync_database_url(database_url: str) -> str:
    return database_url.replace(
        "postgresql+asyncpg://",
        "postgresql+psycopg://",
        1,
    )


def _reset_public_schema(database_url: str) -> None:
    engine = create_engine(
        _sync_database_url(database_url),
        isolation_level="AUTOCOMMIT",
    )
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
            connection.exec_driver_sql("CREATE SCHEMA public")
    finally:
        engine.dispose()


def _run_alembic(database_url: str, *arguments: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    subprocess.run(
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
    _run_alembic(database_url, "upgrade", "head")
    return database_url


@pytest_asyncio.fixture()
async def postgres_database(
    postgres_database_url: str,
) -> AsyncIterator[PostgresDatabase]:
    engine = create_async_engine(postgres_database_url)
    database = PostgresDatabase(
        engine=engine,
        sessions=async_sessionmaker(engine, expire_on_commit=False),
    )
    try:
        yield database
    finally:
        await engine.dispose()


def _planning_input() -> PlanningInput:
    payload = cast(
        dict[str, object],
        json.loads(PERIODIC_FIXTURE.read_text(encoding="utf-8")),
    )
    payload["required_fields"] = ["id", "url", "text"]
    return PlanningInput.model_validate(payload)


def _catalog() -> CapabilityCatalog:
    return CapabilityCatalog.model_validate_json(
        SYNTHETIC_CATALOG_FIXTURE.read_text(encoding="utf-8")
    )


@pytest_asyncio.fixture()
async def seeded_workflow_version(
    postgres_database: PostgresDatabase,
) -> SeededWorkflowVersion:
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    version_id = uuid.uuid4()
    result = build_workflow_plan_result(
        project_id=project_id,
        planning_input=_planning_input(),
        catalog=_catalog(),
        generated_at=NOW,
        request_id="workflow-execution-postgres",
    )
    preview = result.preview
    async with postgres_database.sessions.begin() as session:
        session.add_all(
            [
                User(
                    id=user_id,
                    email=f"workflow-execution-postgres-{user_id}@example.test",
                    password_hash="not-a-real-password",
                    name="Workflow Execution PostgreSQL",
                    status="active",
                ),
                Workspace(
                    id=workspace_id,
                    name="Workflow Execution PostgreSQL",
                    slug=f"workflow-execution-postgres-{workspace_id}",
                    owner_id=user_id,
                ),
                Project(
                    id=project_id,
                    workspace_id=workspace_id,
                    owner_id=user_id,
                    name="Workflow Execution PostgreSQL",
                    description=None,
                    domain="social",
                    status="active",
                ),
            ]
        )
        await session.flush()
        plan = WorkflowPlan(
            id=plan_id,
            workspace_id=workspace_id,
            project_id=project_id,
            created_by_user_id=user_id,
            name="Workflow Execution PostgreSQL",
            flow_mode=preview.flow_mode.value,
            status="active",
            current_version_id=None,
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(plan)
        await session.flush()
        session.add(
            WorkflowVersion(
                id=version_id,
                workspace_id=workspace_id,
                project_id=project_id,
                workflow_plan_id=plan_id,
                created_by_user_id=user_id,
                version_number=1,
                planning_status=preview.planning_status.value,
                planner_contract_version=preview.planner_contract_version,
                catalog_snapshot_id=preview.catalog_snapshot_id,
                policy_version=preview.policy_version,
                mode_template_version=preview.mode_template_version,
                query_versions={key.value: value for key, value in preview.query_versions.items()},
                fingerprint_payload=result.fingerprint_payload.model_dump(mode="json"),
                normalized_input=preview.normalized_input.model_dump(mode="json"),
                plan_payload=serialize_preview_snapshot(preview),
                preview_fingerprint=preview.preview_fingerprint,
                created_at=NOW,
            )
        )
        await session.flush()
        plan.current_version_id = version_id
        await session.flush()
    return SeededWorkflowVersion(
        database=postgres_database,
        user_id=user_id,
        workspace_id=workspace_id,
        project_id=project_id,
        plan_id=plan_id,
        version_id=version_id,
        preview_fingerprint=preview.preview_fingerprint,
    )
