from __future__ import annotations

import importlib
import json
import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import cast

import pytest
import pytest_asyncio
from fastapi import HTTPException
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient
from pydantic import JsonValue
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.api.deps import AuthContext, get_auth_context
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.dataset import DatasetVersion
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workflow_action import (
    WorkflowRunActionRequestRecord,
)
from data_intelligence_hub.models.workflow_execution import (
    StepRun,
    WorkflowLineageMaterializationRequest,
    WorkflowRun,
    WorkflowRunRequest,
)
from data_intelligence_hub.models.workflow_plan import WorkflowPlan, WorkflowVersion
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.schemas.capability_catalog import CapabilityCatalog
from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowFixtureRunCreateResponse,
    WorkflowRunResponse,
    WorkflowStepRunResponse,
)
from data_intelligence_hub.schemas.workflow_plan_persistence import (
    serialize_preview_snapshot,
)
from data_intelligence_hub.schemas.workflow_planner import (
    PlanningInput,
    WorkflowPlanPreview,
)
from data_intelligence_hub.services.workflow_execution.eligibility import (
    WorkflowVersionNotFixtureRunnableError,
)
from data_intelligence_hub.services.workflow_execution.execution import (
    WorkflowExecutionIdempotencyConflictError,
    WorkflowExecutionLineageInvalidError,
    WorkflowExecutionPlanNotFoundError,
    WorkflowExecutionProjectNotActiveError,
    WorkflowExecutionProjectNotFoundError,
    WorkflowExecutionStepFailedError,
    WorkflowExecutionTransactionStateError,
    WorkflowExecutionVersionNotFoundError,
)
from data_intelligence_hub.services.workflow_execution.fixtures import (
    WorkflowFixtureAdapterUnavailableError,
    WorkflowFixtureContractInvalidError,
    WorkflowFixturePayloadUnboundError,
    WorkflowFixtureProfileUnknownError,
)
from data_intelligence_hub.services.workflow_execution.integrity import (
    WorkflowVersionExpectedFingerprintConflictError,
    WorkflowVersionSnapshotInvalidError,
)
from data_intelligence_hub.services.workflow_execution.materialization import (
    WorkflowMaterializationDatasetConflictError,
    WorkflowMaterializationIdempotencyConflictError,
    WorkflowMaterializationLedgerInvalidError,
    WorkflowMaterializationLineageDigestConflictError,
    WorkflowMaterializationPayloadInvalidError,
    WorkflowMaterializationProjectNotActiveError,
    WorkflowMaterializationProjectNotFoundError,
    WorkflowMaterializationRunNotCompletedError,
    WorkflowMaterializationRunNotFoundError,
    WorkflowMaterializationTransactionStateError,
    WorkflowRunAlreadyMaterializedError,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id
from data_intelligence_hub.services.workflow_planner.planner import (
    build_workflow_plan_preview,
    build_workflow_plan_result,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "workflow_planner"
PERIODIC_FIXTURE = FIXTURE_DIR / "periodic_monitoring_request_v1.json"
SYNTHETIC_CATALOG_FIXTURE = FIXTURE_DIR / "synthetic_capability_catalog_v1.json"
NOW = datetime(2026, 7, 15, 15, 0, tzinfo=UTC)
RAW_PRIVATE_KEY = "workflow-route-private-key-0001"


@dataclass(frozen=True, slots=True)
class RouteContext:
    client: AsyncClient
    session: AsyncSession
    auth_override: Callable[[], Awaitable[AuthContext]]
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    plan_id: uuid.UUID
    version_id: uuid.UUID
    run_id: uuid.UUID


@dataclass(slots=True)
class RecordingLogger:
    exception_events: list[tuple[str, dict[str, object]]]

    def exception(self, event: str, **fields: object) -> None:
        self.exception_events.append((event, fields))


@dataclass(frozen=True, slots=True)
class VerticalRouteContext:
    client: AsyncClient
    sessions: async_sessionmaker[AsyncSession]
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    plan_id: uuid.UUID
    version_id: uuid.UUID
    preview_fingerprint: str


@pytest_asyncio.fixture()
async def route_context() -> AsyncIterator[RouteContext]:
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    session = cast(AsyncSession, object())
    user = User(
        id=user_id,
        email="workflow-execution-route@example.com",
        password_hash="not-used",
        name="Workflow Execution Route",
        status="active",
    )
    workspace = Workspace(
        id=workspace_id,
        name="Workflow Execution Route",
        slug=f"workflow-execution-route-{workspace_id.hex[:8]}",
        owner_id=user_id,
    )

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    async def override_auth_context() -> AuthContext:
        return AuthContext(user=user, workspace=workspace)

    previous_session_override = app.dependency_overrides.get(get_session)
    previous_auth_override = app.dependency_overrides.get(get_auth_context)
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth_context
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield RouteContext(
                client=client,
                session=session,
                auth_override=override_auth_context,
                user_id=user_id,
                workspace_id=workspace_id,
                project_id=uuid.uuid4(),
                plan_id=uuid.uuid4(),
                version_id=uuid.uuid4(),
                run_id=uuid.uuid4(),
            )
    finally:
        if previous_session_override is None:
            app.dependency_overrides.pop(get_session, None)
        else:
            app.dependency_overrides[get_session] = previous_session_override
        if previous_auth_override is None:
            app.dependency_overrides.pop(get_auth_context, None)
        else:
            app.dependency_overrides[get_auth_context] = previous_auth_override


@pytest_asyncio.fixture()
async def vertical_route_context() -> AsyncIterator[VerticalRouteContext]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
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
        request_id="workflow-execution-route-vertical",
    )
    preview = result.preview
    user = User(
        id=user_id,
        email="workflow-execution-vertical@example.com",
        password_hash="not-used",
        name="Workflow Execution Vertical",
        status="active",
    )
    workspace = Workspace(
        id=workspace_id,
        name="Workflow Execution Vertical",
        slug=f"workflow-execution-vertical-{workspace_id.hex[:8]}",
        owner_id=user_id,
    )
    plan = WorkflowPlan(
        id=plan_id,
        workspace_id=workspace_id,
        project_id=project_id,
        created_by_user_id=user_id,
        name="Workflow Execution Vertical",
        flow_mode=preview.flow_mode.value,
        status="active",
        current_version_id=None,
        created_at=NOW,
        updated_at=NOW,
    )
    version = WorkflowVersion(
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
    async with sessions() as session:
        session.add_all(
            [
                user,
                workspace,
                Project(
                    id=project_id,
                    workspace_id=workspace_id,
                    owner_id=user_id,
                    name="Workflow Execution Vertical",
                    description=None,
                    domain="social",
                    status="active",
                ),
                plan,
                version,
            ]
        )
        await session.flush()
        plan.current_version_id = version_id
        await session.commit()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with sessions() as session:
            yield session

    async def override_auth_context() -> AuthContext:
        return AuthContext(user=user, workspace=workspace)

    previous_session_override = app.dependency_overrides.get(get_session)
    previous_auth_override = app.dependency_overrides.get(get_auth_context)
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth_context
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield VerticalRouteContext(
                client=client,
                sessions=sessions,
                workspace_id=workspace_id,
                project_id=project_id,
                plan_id=plan_id,
                version_id=version_id,
                preview_fingerprint=preview.preview_fingerprint,
            )
    finally:
        if previous_session_override is None:
            app.dependency_overrides.pop(get_session, None)
        else:
            app.dependency_overrides[get_session] = previous_session_override
        if previous_auth_override is None:
            app.dependency_overrides.pop(get_auth_context, None)
        else:
            app.dependency_overrides[get_auth_context] = previous_auth_override
        await engine.dispose()


def _routes_module() -> ModuleType:
    return importlib.import_module("data_intelligence_hub.api.routes.workflow_runs")


def _route_contracts() -> set[tuple[str, str]]:
    return {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }


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


def _preview(project_id: uuid.UUID) -> WorkflowPlanPreview:
    return build_workflow_plan_preview(
        project_id=project_id,
        planning_input=_planning_input(),
        catalog=_catalog(),
        generated_at=NOW,
        request_id="workflow-execution-route-fixture",
    )


def _run(context: RouteContext) -> WorkflowRunResponse:
    preview = _preview(context.project_id)
    return WorkflowRunResponse(
        id=context.run_id,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        workflow_plan_id=context.plan_id,
        workflow_version_id=context.version_id,
        created_by_user_id=context.user_id,
        execution_contract_version="workflow_execution_fixture.v1",
        execution_mode="fixture",
        status="completed",
        planner_contract_version=preview.planner_contract_version,
        preview_fingerprint=preview.preview_fingerprint,
        catalog_snapshot_id=preview.catalog_snapshot_id,
        policy_version=preview.policy_version,
        mode_template_version=preview.mode_template_version,
        query_versions=preview.query_versions,
        fixture_profile_id="fixture-primary-v1",
        fixture_profile_hash="sha256:" + "b" * 64,
        total_steps=1,
        completed_steps=1,
        records_count=2,
        started_at=NOW,
        finished_at=NOW,
        created_at=NOW,
    )


def _step(context: RouteContext) -> WorkflowStepRunResponse:
    preview = _preview(context.project_id)
    step = next(item for item in preview.steps if item.execution_kind == "future_capability")
    route = next(
        item for item in preview.route_plans if item.requirement_ref == step.requirement_ref
    )
    candidate = route.primary_implementation
    assert candidate is not None
    assert step.platform is not None
    assert step.resource_type is not None
    assert step.operation is not None
    assert step.requirement_ref is not None
    return WorkflowStepRunResponse(
        id=uuid.uuid4(),
        workflow_run_id=context.run_id,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        step_ref=step.step_ref,
        requirement_ref=step.requirement_ref,
        sequence=step.sequence,
        platform=step.platform,
        resource_type=step.resource_type,
        operation=step.operation,
        assertion_id=candidate.assertion_id,
        implementation_id=candidate.implementation_id,
        route_plan_snapshot=route,
        evidence_refs=candidate.evidence_refs,
        fixture_case_id="fixture-route-case-v1",
        fixture_content_hash="sha256:" + "c" * 64,
        input_digest="sha256:" + "d" * 64,
        output_digest="sha256:" + "e" * 64,
        idempotency_scope=f"workflow_fixture_step:{context.run_id}",
        idempotency_key_hash="sha256:" + "f" * 64,
        status="completed",
        records_count=2,
        started_at=NOW,
        finished_at=NOW,
        created_at=NOW,
    )


def _create_response(
    context: RouteContext,
    *,
    replay: bool,
) -> WorkflowFixtureRunCreateResponse:
    return WorkflowFixtureRunCreateResponse(
        database_write=not replay,
        idempotent_replay=replay,
        run=_run(context),
        steps=[_step(context)],
    )


def _create_path(context: RouteContext) -> str:
    return (
        f"/api/projects/{context.project_id}/workflow-plans/{context.plan_id}/"
        f"versions/{context.version_id}/fixture-runs"
    )


def _create_body(context: RouteContext) -> dict[str, str]:
    return {
        "expected_preview_fingerprint": _run(context).preview_fingerprint,
        "fixture_profile_id": "fixture-primary-v1",
    }


@pytest.mark.asyncio
async def test_real_api_service_sqlite_create_replay_and_archived_reads(
    vertical_route_context: VerticalRouteContext,
) -> None:
    context = vertical_route_context
    create_path = (
        f"/api/projects/{context.project_id}/workflow-plans/{context.plan_id}/"
        f"versions/{context.version_id}/fixture-runs"
    )
    create_body = {
        "expected_preview_fingerprint": context.preview_fingerprint,
        "fixture_profile_id": "fixture-primary-v1",
    }
    gate_path = (
        f"/api/projects/{context.project_id}/workflow-plans/{context.plan_id}/"
        f"versions/{context.version_id}/fixture-run-gate"
    )
    runnable_gate = await context.client.get(gate_path)
    first = await context.client.post(
        create_path,
        headers={"Idempotency-Key": "vertical-fixture-key-0001"},
        json=create_body,
    )
    replay = await context.client.post(
        create_path,
        headers={"Idempotency-Key": "vertical-fixture-key-0001"},
        json=create_body,
    )
    run_id = uuid.UUID(first.json()["run"]["id"])

    async with context.sessions() as session:
        project = await session.get(Project, context.project_id)
        assert project is not None
        project.status = "archived"
        await session.commit()

    listed = await context.client.get(
        f"/api/projects/{context.project_id}/workflow-runs",
        params={
            "workflow_plan_id": str(context.plan_id),
            "workflow_version_id": str(context.version_id),
        },
    )
    detailed = await context.client.get(
        f"/api/projects/{context.project_id}/workflow-runs/{run_id}"
    )
    archived_gate = await context.client.get(gate_path)

    assert runnable_gate.status_code == 200
    assert runnable_gate.json()["runnable"] is True
    assert runnable_gate.json()["blocker_codes"] == []
    assert runnable_gate.json()["next_action_codes"] == ["create_fixture_run"]
    assert runnable_gate.json()["database_write"] is False
    assert [first.status_code, replay.status_code] == [201, 200]
    assert first.json()["database_write"] is True
    assert replay.json()["database_write"] is False
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["run"]["id"] == first.json()["run"]["id"]
    assert listed.status_code == 200
    assert listed.json()["project_status"] == "archived"
    assert listed.json()["total"] == 1
    assert len(listed.json()["items"]) == 1
    assert "route_plan_snapshot" not in listed.text
    assert detailed.status_code == 200
    assert detailed.json()["project_status"] == "archived"
    assert archived_gate.status_code == 200
    assert archived_gate.json()["runnable"] is False
    assert archived_gate.json()["blocker_codes"] == ["project_not_active"]
    assert archived_gate.json()["next_action_codes"] == ["activate_project"]
    sequences = [step["sequence"] for step in detailed.json()["steps"]]
    assert sequences == sorted(sequences)
    assert len(sequences) == 3
    assert all(step["route_plan_snapshot"] for step in detailed.json()["steps"])
    assert all(
        response.headers["X-Request-ID"]
        for response in (
            runnable_gate,
            first,
            replay,
            listed,
            detailed,
            archived_gate,
        )
    )

    async with context.sessions() as session:
        counts = [
            int((await session.execute(select(func.count()).select_from(model))).scalar_one())
            for model in (WorkflowRun, StepRun, WorkflowRunRequest)
        ]
    assert counts == [1, 3, 1]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        (
            "POST",
            "/api/projects/{project_id}/workflow-plans/{plan_id}/versions/"
            "{version_id}/fixture-runs",
        ),
        ("GET", "/api/projects/{project_id}/workflow-runs"),
        ("GET", "/api/projects/{project_id}/workflow-runs/{run_id}"),
        (
            "GET",
            "/api/projects/{project_id}/workflow-runs/{run_id}/attempt-fallback-evidence",
        ),
        (
            "GET",
            "/api/projects/{project_id}/workflow-runs/{run_id}/checkpoint-budget-evidence",
        ),
        (
            "GET",
            "/api/projects/{project_id}/workflow-runs/{run_id}/provider-health-evidence",
        ),
        (
            "GET",
            "/api/projects/{project_id}/workflow-runs/{run_id}/executor-evidence",
        ),
        (
            "GET",
            "/api/projects/{project_id}/workflow-runs/{run_id}/action-gates",
        ),
        (
            "POST",
            "/api/projects/{project_id}/workflow-runs/{run_id}/action-approval-receipts",
        ),
        (
            "POST",
            "/api/projects/{project_id}/workflow-runs/{run_id}/actions",
        ),
        (
            "GET",
            "/api/projects/{project_id}/workflow-runs/{run_id}/shadow-comparisons",
        ),
        (
            "GET",
            "/api/projects/{project_id}/workflow-runs/{run_id}/lineage-preview",
        ),
    ],
)
def test_approved_workflow_execution_route_is_registered(
    method: str,
    path: str,
) -> None:
    assert (method, path) in _route_contracts()


@pytest.mark.asyncio
async def test_create_returns_201_then_replay_200_and_normalizes_private_key(
    route_context: RouteContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    async def create_service(**kwargs: object) -> WorkflowFixtureRunCreateResponse:
        calls.append(kwargs)
        return _create_response(route_context, replay=len(calls) > 1)

    monkeypatch.setattr(
        _routes_module(),
        "create_workflow_fixture_run",
        create_service,
    )
    responses = [
        await route_context.client.post(
            _create_path(route_context),
            headers={"Idempotency-Key": f"  {RAW_PRIVATE_KEY}  "},
            json=_create_body(route_context),
        ),
        await route_context.client.post(
            _create_path(route_context),
            headers={"Idempotency-Key": RAW_PRIVATE_KEY},
            json=_create_body(route_context),
        ),
    ]

    assert [response.status_code for response in responses] == [201, 200]
    assert [response.json()["database_write"] for response in responses] == [True, False]
    assert [response.json()["idempotent_replay"] for response in responses] == [
        False,
        True,
    ]
    assert len(calls) == 2
    assert all(call["session"] is route_context.session for call in calls)
    assert all(call["workspace_id"] == route_context.workspace_id for call in calls)
    assert all(call["created_by_user_id"] == route_context.user_id for call in calls)
    assert all(call["idempotency_key"] == RAW_PRIVATE_KEY for call in calls)
    for response, call in zip(responses, calls, strict=True):
        assert response.headers["X-Request-ID"] == call["request_id"]
        assert RAW_PRIVATE_KEY not in response.text
        assert response.json()["provider_call"] is False
        assert response.json()["live_execution_authorized"] is False


@pytest.mark.asyncio
async def test_strict_body_and_idempotency_validation_fail_before_service(
    route_context: RouteContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    async def create_service(**kwargs: object) -> WorkflowFixtureRunCreateResponse:
        calls.append(kwargs)
        return _create_response(route_context, replay=False)

    monkeypatch.setattr(
        _routes_module(),
        "create_workflow_fixture_run",
        create_service,
    )
    valid = _create_body(route_context)
    responses = [
        await route_context.client.post(_create_path(route_context), json=valid),
        await route_context.client.post(
            _create_path(route_context),
            headers={"Idempotency-Key": "short"},
            json=valid,
        ),
        await route_context.client.post(
            _create_path(route_context),
            headers={"Idempotency-Key": "x" * 201},
            json=valid,
        ),
        await route_context.client.post(
            _create_path(route_context),
            headers={"Idempotency-Key": RAW_PRIVATE_KEY},
            json={**valid, "fixture_body": {"private": True}},
        ),
        await route_context.client.post(
            _create_path(route_context),
            headers={"Idempotency-Key": RAW_PRIVATE_KEY},
            json={**valid, "fixture_profile_id": "../private"},
        ),
    ]

    assert all(response.status_code == 422 for response in responses)
    assert all(response.headers["X-Request-ID"] for response in responses)
    assert calls == []


@pytest.mark.asyncio
async def test_list_and_detail_pass_filters_and_keep_archived_read_shapes(
    route_context: RouteContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = _routes_module()
    list_calls: list[dict[str, object]] = []
    count_calls: list[dict[str, object]] = []

    async def get_project(*args: object) -> SimpleNamespace:
        assert args == (
            route_context.session,
            route_context.workspace_id,
            route_context.project_id,
        )
        return SimpleNamespace(status="archived")

    async def list_runs(*args: object, **kwargs: object) -> list[WorkflowRunResponse]:
        assert args == (
            route_context.session,
            route_context.workspace_id,
            route_context.project_id,
        )
        list_calls.append(kwargs)
        return [_run(route_context)]

    async def count_runs(*args: object, **kwargs: object) -> int:
        assert args == (
            route_context.session,
            route_context.workspace_id,
            route_context.project_id,
        )
        count_calls.append(kwargs)
        return 1

    async def get_run(*args: object) -> WorkflowRunResponse:
        assert args[-1] == route_context.run_id
        return _run(route_context)

    async def list_steps(*args: object) -> list[WorkflowStepRunResponse]:
        assert args[-1] == route_context.run_id
        return [_step(route_context)]

    async def get_materialized_version(*args: object, **kwargs: object) -> None:
        del args, kwargs
        return None

    async def get_materialization_ledger(*args: object, **kwargs: object) -> None:
        del args, kwargs
        return None

    monkeypatch.setattr(routes, "get_project", get_project)
    monkeypatch.setattr(routes, "list_workflow_runs", list_runs)
    monkeypatch.setattr(routes, "count_workflow_runs", count_runs)
    monkeypatch.setattr(routes, "get_workflow_run", get_run)
    monkeypatch.setattr(routes, "list_step_runs", list_steps)
    monkeypatch.setattr(
        routes,
        "get_dataset_version_by_workflow_run",
        get_materialized_version,
    )
    monkeypatch.setattr(
        routes,
        "get_materialization_request_by_run",
        get_materialization_ledger,
    )

    list_response = await route_context.client.get(
        f"/api/projects/{route_context.project_id}/workflow-runs",
        params={
            "workflow_plan_id": str(route_context.plan_id),
            "workflow_version_id": str(route_context.version_id),
            "limit": 1,
            "offset": 2,
        },
    )
    detail_response = await route_context.client.get(
        f"/api/projects/{route_context.project_id}/workflow-runs/{route_context.run_id}"
    )
    lineage_preview_response = await route_context.client.get(
        f"/api/projects/{route_context.project_id}/workflow-runs/"
        f"{route_context.run_id}/lineage-preview"
    )

    assert list_response.status_code == 200
    assert list_response.json()["project_status"] == "archived"
    assert list_response.json()["database_write"] is False
    assert list_response.json()["limit"] == 1
    assert list_response.json()["offset"] == 2
    assert "steps" not in list_response.json()["items"][0]
    assert "route_plan_snapshot" not in list_response.text
    expected_filters = {
        "workflow_plan_id": route_context.plan_id,
        "workflow_version_id": route_context.version_id,
    }
    assert list_calls == [{**expected_filters, "limit": 1, "offset": 2}]
    assert count_calls == [expected_filters]

    assert detail_response.status_code == 200
    assert detail_response.json()["project_status"] == "archived"
    assert detail_response.json()["database_write"] is False
    assert detail_response.json()["steps"][0]["route_plan_snapshot"]
    assert lineage_preview_response.status_code == 200
    assert lineage_preview_response.json()["schema_version"] == "workflow_lineage_preview.v2"
    assert lineage_preview_response.json()["database_write"] is False
    assert lineage_preview_response.json()["raw_record_write"] is False
    assert lineage_preview_response.json()["dataset_write"] is False
    assert lineage_preview_response.json()["provider_evidence"][0]["evidence_refs"]
    assert lineage_preview_response.json()["raw_record"]["materialized"] is False
    assert lineage_preview_response.json()["dataset"]["materialized"] is False
    assert "raw_payload" not in lineage_preview_response.text
    assert "fixture_body" not in lineage_preview_response.text
    assert list_response.headers["X-Request-ID"]
    assert detail_response.headers["X-Request-ID"]
    assert lineage_preview_response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_executor_evidence_route_is_tenant_scoped_read_only_and_non_live(
    route_context: RouteContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = _routes_module()
    calls: list[dict[str, object]] = []

    async def get_project(*args: object) -> SimpleNamespace:
        assert args == (
            route_context.session,
            route_context.workspace_id,
            route_context.project_id,
        )
        return SimpleNamespace(status="active")

    async def get_run(*args: object) -> WorkflowRunResponse:
        assert args == (
            route_context.session,
            route_context.workspace_id,
            route_context.project_id,
            route_context.run_id,
        )
        return _run(route_context)

    async def load_evidence(*args: object, **kwargs: object) -> object:
        assert args == (route_context.session,)
        calls.append(kwargs)
        return routes.WorkflowExecutorEvidenceResponse(
            workspace_id=route_context.workspace_id,
            project_id=route_context.project_id,
            workflow_run_id=route_context.run_id,
            evaluated_at=NOW,
            dispatches=[],
            dispatch_total=0,
            business_cause_code="executor_dispatch_not_created",
            business_impact_code="workflow_execution_not_started",
            next_action_code="review_action_receipt_and_dispatch_gate",
        )

    monkeypatch.setattr(routes, "get_project", get_project)
    monkeypatch.setattr(routes, "get_workflow_run", get_run)
    monkeypatch.setattr(routes, "load_workflow_executor_evidence", load_evidence)
    monkeypatch.setattr(routes, "_provider_health_read_time", lambda _value=None: NOW)

    response = await route_context.client.get(
        f"/api/projects/{route_context.project_id}/workflow-runs/"
        f"{route_context.run_id}/executor-evidence"
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    body = response.json()
    assert body["schema_version"] == "workflow_executor_evidence.v1"
    assert body["evidence_grade"] == "L2_fixture_local"
    assert body["dispatch_total"] == 0
    assert body["live_execution_authorized"] is False
    assert body["credential_read_attempted"] is False
    assert body["client_construction"] is False
    assert body["provider_call"] is False
    assert body["network_call"] is False
    assert body["database_write"] is False
    assert body["live_provider_proof"] is False
    assert calls == [
        {
            "workspace_id": route_context.workspace_id,
            "project_id": route_context.project_id,
            "workflow_run_id": route_context.run_id,
            "evaluated_at": NOW,
        }
    ]


@pytest.mark.asyncio
async def test_attempt_fallback_route_maps_persisted_evidence_without_actions(
    route_context: RouteContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = _routes_module()
    step_id = uuid.uuid4()

    async def get_project(*args: object) -> SimpleNamespace:
        del args
        return SimpleNamespace(status="active")

    async def get_run(*args: object) -> WorkflowRunResponse:
        del args
        return _run(route_context)

    async def list_attempts(*args: object) -> list[SimpleNamespace]:
        del args
        return [
            SimpleNamespace(
                id=uuid.uuid4(),
                workspace_id=route_context.workspace_id,
                project_id=route_context.project_id,
                workflow_run_id=route_context.run_id,
                step_run_id=step_id,
                attempt_number=1,
                attempt_key_hash="sha256:" + "a" * 64,
                status="retryable_error",
                error_code="step_rate_limited",
                backoff_ms=500,
                provider_call_attempted=False,
                credential_read_attempted=False,
                actor_run=False,
                browser_run=False,
                llm_call=False,
                production_write_allowed=False,
                started_at=NOW,
                finished_at=NOW,
                created_at=NOW,
            )
        ]

    async def list_decisions(*args: object) -> list[SimpleNamespace]:
        del args
        return [
            SimpleNamespace(
                id=uuid.uuid4(),
                workspace_id=route_context.workspace_id,
                project_id=route_context.project_id,
                workflow_plan_id=route_context.plan_id,
                workflow_version_id=route_context.version_id,
                workflow_run_id=route_context.run_id,
                step_run_id=step_id,
                created_by_user_id=route_context.user_id,
                step_ref="step.reddit.search",
                requirement_ref="requirement.reddit.posts",
                contract_version="workflow_fallback_gate_replay.v1",
                decision_digest="sha256:" + "b" * 64,
                primary_failure_code="step_rate_limited",
                primary_assertion_id="assertion.reddit.search.primary",
                primary_implementation_id="fixture.reddit.search.v1",
                fallback_assertion_id="assertion.reddit.search.fallback",
                fallback_implementation_id="fixture.reddit.search.fallback.v1",
                outcome="blocked",
                gate_snapshot=[
                    {
                        "gate": gate,
                        "status": "blocked" if gate == "approval" else "passed",
                        "code": f"fallback_{gate}_recorded",
                        "evidence_refs": [],
                    }
                    for gate in (
                        "trigger",
                        "policy",
                        "credential",
                        "budget",
                        "fields",
                        "evidence",
                        "approval",
                    )
                ],
                field_difference={
                    "evidence_status": "verified",
                    "required_fields": ["post.id"],
                    "missing_required_fields": [],
                    "primary_missing_optional_fields": [],
                    "fallback_missing_optional_fields": [],
                },
                cost_snapshot={
                    "evidence_status": "verified",
                    "currency": "USD",
                    "unit_cost_usd": "0.01",
                    "ceiling_usd": "0.02",
                    "within_ceiling": True,
                },
                evidence_refs=["fixture://reddit/fallback/001"],
                approval_required=True,
                approval_status="pending",
                switch_executed=False,
                provider_call_attempted=False,
                credential_read_attempted=False,
                actor_run=False,
                browser_run=False,
                llm_call=False,
                production_write_allowed=False,
                created_at=NOW,
            )
        ]

    monkeypatch.setattr(routes, "get_project", get_project)
    monkeypatch.setattr(routes, "get_workflow_run", get_run)
    monkeypatch.setattr(routes, "list_step_run_attempts_for_run", list_attempts)
    monkeypatch.setattr(
        routes,
        "list_workflow_fallback_decisions_for_run",
        list_decisions,
    )

    response = await route_context.client.get(
        f"/api/projects/{route_context.project_id}/workflow-runs/"
        f"{route_context.run_id}/attempt-fallback-evidence"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["attempt_total"] == 1
    assert payload["fallback_decision_total"] == 1
    assert payload["fallback_decisions"][0]["outcome"] == "blocked"
    assert payload["fallback_decisions"][0]["switch_executed"] is False
    assert payload["fallback_decisions"][0]["gates"][-1]["gate"] == "approval"
    assert payload["database_write"] is False
    assert payload["provider_call"] is False


@pytest.mark.asyncio
async def test_checkpoint_budget_route_maps_persisted_evidence_without_actions(
    route_context: RouteContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = _routes_module()
    step = _step(route_context)
    account_id = uuid.uuid4()
    reserved_digest = "sha256:" + "1" * 64
    held_digest = "sha256:" + "2" * 64
    side_effect_key_hash = "sha256:" + "3" * 64

    async def get_project(*args: object) -> SimpleNamespace:
        del args
        return SimpleNamespace(status="active")

    async def get_run(*args: object) -> WorkflowRunResponse:
        del args
        return _run(route_context)

    async def list_steps(*args: object) -> list[WorkflowStepRunResponse]:
        del args
        return [step]

    async def list_checkpoints(*args: object, **kwargs: object) -> list[SimpleNamespace]:
        del args, kwargs
        return [
            SimpleNamespace(
                id=uuid.uuid4(),
                execution_session_id=route_context.run_id,
                workspace_id=route_context.workspace_id,
                project_id=route_context.project_id,
                workflow_plan_id=route_context.plan_id,
                workflow_version_id=route_context.version_id,
                step_ref=step.step_ref,
                requirement_ref=step.requirement_ref,
                implementation_id=step.implementation_id,
                contract_version="workflow_step_checkpoint.v1",
                fixture_profile_id="fixture-primary-v1",
                fixture_profile_hash="sha256:" + "4" * 64,
                step_input_digest="sha256:" + "5" * 64,
                page_number=1,
                cursor_before=None,
                cursor_before_digest="sha256:" + "6" * 64,
                cursor_after="cursor-page-2",
                cursor_after_digest="sha256:" + "7" * 64,
                side_effect_key_hash=side_effect_key_hash,
                page_output_digest="sha256:" + "8" * 64,
                checkpoint_digest="sha256:" + "9" * 64,
                records_count=2,
                terminal=False,
                evidence_refs=["fixture://checkpoint/page-1"],
                provider_call_attempted=False,
                credential_read_attempted=False,
                actor_run=False,
                browser_run=False,
                llm_call=False,
                raw_record_write=False,
                dataset_write=False,
                production_write_allowed=False,
                confirmed_at=NOW,
                created_at=NOW,
            )
        ]

    async def get_account(*args: object, **kwargs: object) -> SimpleNamespace:
        del args, kwargs
        return SimpleNamespace(
            id=account_id,
            execution_session_id=route_context.run_id,
            workspace_id=route_context.workspace_id,
            project_id=route_context.project_id,
            workflow_plan_id=route_context.plan_id,
            workflow_version_id=route_context.version_id,
            contract_version="workflow_budget_account.v1",
            policy_digest="sha256:" + "a" * 64,
            max_requests=1,
            max_items=10,
            quota_ceilings={"fixture.read": 5},
            max_cost_usd="1.00000000",
            max_time_ms=1000,
            evidence_refs=["fixture://budget/policy"],
            provider_call_attempted=False,
            credential_read_attempted=False,
            actor_run=False,
            browser_run=False,
            llm_call=False,
            raw_record_write=False,
            dataset_write=False,
            production_write_allowed=False,
        )

    async def list_entries(*args: object) -> list[SimpleNamespace]:
        assert args == (route_context.session, account_id)
        common = {
            "budget_account_id": account_id,
            "execution_session_id": route_context.run_id,
            "workspace_id": route_context.workspace_id,
            "project_id": route_context.project_id,
            "contract_version": "workflow_budget_ledger.v1",
            "policy_digest": "sha256:" + "a" * 64,
            "provider_call_attempted": False,
            "credential_read_attempted": False,
            "actor_run": False,
            "browser_run": False,
            "llm_call": False,
            "raw_record_write": False,
            "dataset_write": False,
            "production_write_allowed": False,
        }
        return [
            SimpleNamespace(
                id=uuid.uuid4(),
                entry_number=1,
                step_ref=step.step_ref,
                page_number=1,
                side_effect_key_hash=side_effect_key_hash,
                status="reserved",
                blocker_code=None,
                request_count=1,
                item_count=2,
                quota_units={"fixture.read": 2},
                estimated_cost_usd="0.10000000",
                reserved_time_ms=100,
                cumulative_request_count=1,
                cumulative_item_count=2,
                cumulative_quota_units={"fixture.read": 2},
                cumulative_cost_usd="0.10000000",
                cumulative_time_ms=100,
                previous_ledger_digest=None,
                ledger_digest=reserved_digest,
                **common,
            ),
            SimpleNamespace(
                id=uuid.uuid4(),
                entry_number=2,
                step_ref=step.step_ref,
                page_number=2,
                side_effect_key_hash="sha256:" + "b" * 64,
                status="blocked",
                blocker_code="workflow_request_budget_exceeded",
                request_count=1,
                item_count=2,
                quota_units={"fixture.read": 2},
                estimated_cost_usd="0.10000000",
                reserved_time_ms=100,
                cumulative_request_count=1,
                cumulative_item_count=2,
                cumulative_quota_units={"fixture.read": 2},
                cumulative_cost_usd="0.10000000",
                cumulative_time_ms=100,
                previous_ledger_digest=reserved_digest,
                ledger_digest=held_digest,
                **common,
            ),
        ]

    monkeypatch.setattr(routes, "get_project", get_project)
    monkeypatch.setattr(routes, "get_workflow_run", get_run)
    monkeypatch.setattr(routes, "list_step_runs", list_steps)
    monkeypatch.setattr(routes, "list_workflow_step_checkpoints_for_run", list_checkpoints)
    monkeypatch.setattr(routes, "get_workflow_budget_account_for_run", get_account)
    monkeypatch.setattr(routes, "list_workflow_budget_ledger_entries", list_entries)

    response = await route_context.client.get(
        f"/api/projects/{route_context.project_id}/workflow-runs/"
        f"{route_context.run_id}/checkpoint-budget-evidence"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "workflow_checkpoint_budget_evidence.v1"
    assert payload["execution_session_id"] == str(route_context.run_id)
    assert payload["checkpoint_step_total"] == 1
    assert payload["checkpoint_page_total"] == 1
    assert payload["checkpoint_steps"][0]["confirmed_records"] == 2
    assert payload["budget_status"] == "held"
    assert payload["held_reason_code"] == "workflow_request_budget_exceeded"
    assert payload["usage"]["request_count"] == 1
    assert payload["resume_action_available"] is False
    assert payload["budget_override_available"] is False
    assert payload["database_write"] is False
    assert payload["provider_call"] is False


@pytest.mark.asyncio
async def test_provider_health_route_maps_project_evidence_without_probe_or_switch(
    route_context: RouteContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = _routes_module()
    step = _step(route_context)
    route = step.route_plan_snapshot
    primary = route.primary_implementation
    assert primary is not None
    candidate_ids = [
        primary.implementation_id,
        *(item.implementation_id for item in route.fallback_implementations),
    ]
    assert len(candidate_ids) >= 2
    snapshot_digest = "sha256:" + "1" * 64

    async def get_project(*args: object) -> SimpleNamespace:
        del args
        return SimpleNamespace(status="active")

    async def get_run(*args: object) -> WorkflowRunResponse:
        del args
        return _run(route_context)

    async def list_steps(*args: object) -> list[WorkflowStepRunResponse]:
        del args
        return [step]

    async def list_snapshots(*args: object, **kwargs: object) -> list[SimpleNamespace]:
        del args
        assert kwargs["implementation_ids"] == candidate_ids
        return [
            SimpleNamespace(
                id=uuid.uuid4(),
                workspace_id=route_context.workspace_id,
                project_id=route_context.project_id,
                contract_version="provider_health_snapshot.v1",
                scope_key="sha256:" + "2" * 64,
                aggregation_key="sha256:" + "3" * 64,
                snapshot_version=1,
                platform_id=step.platform,
                implementation_id=step.implementation_id,
                resource_type=step.resource_type,
                operation=step.operation,
                window_started_at=NOW - timedelta(hours=2),
                window_ended_at=NOW - timedelta(hours=1),
                evaluated_at=NOW,
                status="unhealthy",
                sample_count=3,
                success_count=1,
                timeout_count=1,
                rate_limited_count=1,
                transient_error_count=0,
                terminal_error_count=0,
                success_rate_bps=3333,
                p95_latency_ms=6000,
                reason_codes=["provider_health_success_rate_unhealthy"],
                policy_snapshot={"min_sample_size": 3},
                observation_manifest=[{"observation_digest": "sha256:" + "4" * 64}],
                evidence_refs=["fixture://health/primary/window"],
                previous_snapshot_digest=None,
                snapshot_digest=snapshot_digest,
                routing_valid_until=datetime(2099, 1, 2, tzinfo=UTC),
                evidence_retain_until=datetime(2100, 1, 2, tzinfo=UTC),
                health_probe_attempted=False,
                provider_call_attempted=False,
                credential_read_attempted=False,
                actor_run=False,
                browser_run=False,
                llm_call=False,
                raw_record_write=False,
                dataset_write=False,
                production_write_allowed=False,
            )
        ]

    async def list_feedbacks(*args: object, **kwargs: object) -> list[SimpleNamespace]:
        del args, kwargs
        source_manifest = [
            {
                "implementation_id": candidate_id,
                "snapshot_digest": snapshot_digest,
                "routing_applied": candidate_id == step.implementation_id,
            }
            for candidate_id in candidate_ids
        ]
        return [
            SimpleNamespace(
                id=uuid.uuid4(),
                workspace_id=route_context.workspace_id,
                project_id=route_context.project_id,
                contract_version="provider_health_route_feedback.v1",
                route_key="route://fixture/run-health",
                feedback_key="sha256:" + "5" * 64,
                feedback_version=1,
                platform_id=step.platform,
                resource_type=step.resource_type,
                operation=step.operation,
                original_candidate_order=candidate_ids,
                adjusted_candidate_order=list(reversed(candidate_ids)),
                candidate_score_manifest=[
                    {"implementation_id": candidate_id, "score_bps": 5000}
                    for candidate_id in candidate_ids
                ],
                source_snapshot_manifest=source_manifest,
                ranking_changed=True,
                reason_codes=["provider_health_ranking_reordered"],
                evidence_refs=["fixture://health/route-feedback"],
                previous_feedback_digest=None,
                feedback_digest="sha256:" + "6" * 64,
                evaluated_at=NOW + timedelta(minutes=30),
                evidence_retain_until=datetime(2100, 1, 2, tzinfo=UTC),
                health_probe_attempted=False,
                catalog_mutation_applied=False,
                automatic_route_switch_executed=False,
                provider_call_attempted=False,
                credential_read_attempted=False,
                actor_run=False,
                browser_run=False,
                llm_call=False,
                raw_record_write=False,
                dataset_write=False,
                production_write_allowed=False,
            )
        ]

    monkeypatch.setattr(routes, "get_project", get_project)
    monkeypatch.setattr(routes, "get_workflow_run", get_run)
    monkeypatch.setattr(routes, "list_step_runs", list_steps)
    monkeypatch.setattr(routes, "list_provider_health_snapshots_for_candidates", list_snapshots)
    monkeypatch.setattr(routes, "list_latest_provider_health_feedbacks", list_feedbacks)

    response = await route_context.client.get(
        f"/api/projects/{route_context.project_id}/workflow-runs/"
        f"{route_context.run_id}/provider-health-evidence"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "workflow_provider_health_evidence.v1"
    assert payload["step_total"] == 1
    assert payload["observed_candidate_total"] == 1
    assert payload["routing_active_candidate_total"] == 1
    assert payload["attention_candidate_total"] == 1
    assert payload["route_feedback_total"] == 1
    assert payload["steps"][0]["route_feedback_match"] == "ordered_candidate_match"
    assert payload["steps"][0]["route_decision_applied_to_run"] is False
    assert payload["health_probe_attempted"] is False
    assert payload["catalog_mutation_applied"] is False
    assert payload["automatic_route_switch_executed"] is False
    assert payload["route_switch_action_available"] is False
    assert payload["database_write"] is False
    assert payload["provider_call"] is False


@pytest.mark.asyncio
async def test_run_read_response_derives_template_revision_lineage_from_version(
    route_context: RouteContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = _routes_module()
    template_id = uuid.uuid4()
    revision_id = uuid.uuid4()
    run = SimpleNamespace(**_run(route_context).model_dump())

    async def get_version(*args: object) -> SimpleNamespace:
        assert args == (
            route_context.session,
            route_context.workspace_id,
            route_context.project_id,
            route_context.plan_id,
            route_context.version_id,
        )
        return SimpleNamespace(
            workflow_template_id=template_id,
            workflow_template_revision_id=revision_id,
        )

    monkeypatch.setattr(routes, "get_workflow_version", get_version)
    mapped = await routes._run_response_with_template_lineage(
        session=route_context.session,
        workspace_id=route_context.workspace_id,
        project_id=route_context.project_id,
        run=run,
    )

    assert mapped.workflow_template_id == template_id
    assert mapped.workflow_template_revision_id == revision_id


@pytest.mark.asyncio
async def test_read_paths_hide_missing_project_and_run(
    route_context: RouteContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = _routes_module()

    async def missing_project(*args: object) -> None:
        return None

    monkeypatch.setattr(routes, "get_project", missing_project)
    project_response = await route_context.client.get(
        f"/api/projects/{route_context.project_id}/workflow-runs"
    )
    assert project_response.status_code == 404
    assert project_response.json()["detail"] == "project_not_found"

    async def archived_project(*args: object) -> SimpleNamespace:
        return SimpleNamespace(status="archived")

    async def missing_run(*args: object) -> None:
        return None

    monkeypatch.setattr(routes, "get_project", archived_project)
    monkeypatch.setattr(routes, "get_workflow_run", missing_run)
    run_response = await route_context.client.get(
        f"/api/projects/{route_context.project_id}/workflow-runs/{route_context.run_id}"
    )
    assert run_response.status_code == 404
    assert run_response.json()["detail"] == "workflow_run_not_found"
    assert project_response.headers["X-Request-ID"]
    assert run_response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_create_and_read_require_existing_auth_context(
    route_context: RouteContext,
) -> None:
    async def deny_authentication() -> AuthContext:
        raise HTTPException(status_code=401, detail="Authentication required")

    app.dependency_overrides[get_auth_context] = deny_authentication
    try:
        responses = [
            await route_context.client.post(
                _create_path(route_context),
                headers={"Idempotency-Key": RAW_PRIVATE_KEY},
                json=_create_body(route_context),
            ),
            await route_context.client.get(
                f"/api/projects/{route_context.project_id}/workflow-runs"
            ),
            await route_context.client.post(
                f"/api/projects/{route_context.project_id}/workflow-runs/"
                f"{route_context.run_id}/materializations",
                headers={"Idempotency-Key": RAW_PRIVATE_KEY},
                json={
                    "dataset_name": "authentication-required-dataset",
                    "expected_lineage_digest": "sha256:" + "a" * 64,
                },
            ),
        ]
    finally:
        app.dependency_overrides[get_auth_context] = route_context.auth_override

    assert [response.status_code for response in responses] == [401, 401, 401]
    assert all(response.headers["X-Request-ID"] for response in responses)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_factory", "expected_status", "expected_detail"),
    [
        (WorkflowExecutionProjectNotFoundError, 404, "project_not_found"),
        (WorkflowExecutionPlanNotFoundError, 404, "workflow_plan_not_found"),
        (WorkflowExecutionVersionNotFoundError, 404, "workflow_version_not_found"),
        (WorkflowExecutionProjectNotActiveError, 409, "project_not_active"),
        (
            WorkflowVersionExpectedFingerprintConflictError,
            409,
            "workflow_version_fingerprint_conflict",
        ),
        (
            WorkflowVersionNotFixtureRunnableError,
            409,
            "workflow_version_not_fixture_runnable",
        ),
        (WorkflowExecutionIdempotencyConflictError, 409, "idempotency_conflict"),
        (
            WorkflowExecutionTransactionStateError,
            409,
            "workflow_execution_transaction_state_invalid",
        ),
        (
            WorkflowExecutionStepFailedError,
            503,
            "workflow_step_execution_failed",
        ),
        (WorkflowFixtureProfileUnknownError, 422, "workflow_fixture_profile_unknown"),
        (WorkflowFixtureContractInvalidError, 422, "workflow_fixture_contract_invalid"),
        (
            WorkflowFixtureAdapterUnavailableError,
            409,
            "workflow_fixture_adapter_unavailable",
        ),
        (WorkflowVersionSnapshotInvalidError, 500, "workflow_version_snapshot_invalid"),
        (WorkflowExecutionLineageInvalidError, 500, "workflow_run_lineage_invalid"),
        (
            lambda: WorkflowMaterializationDatasetConflictError("dataset_type_conflict"),
            409,
            "dataset_type_conflict",
        ),
        (
            lambda: WorkflowMaterializationDatasetConflictError("private dataset failure detail"),
            409,
            "dataset_lineage_conflict",
        ),
        (
            lambda: SQLAlchemyError("SELECT private FROM workflow_runs"),
            503,
            "workflow_execution_persistence_unavailable",
        ),
        (
            lambda: RuntimeError("private /Users/example/.env fixture body"),
            500,
            "workflow_execution_internal_error",
        ),
    ],
)
async def test_create_maps_only_allowlisted_sanitized_errors(
    route_context: RouteContext,
    monkeypatch: pytest.MonkeyPatch,
    error_factory: Callable[[], Exception],
    expected_status: int,
    expected_detail: str,
) -> None:
    async def failing_service(**kwargs: object) -> WorkflowFixtureRunCreateResponse:
        del kwargs
        error = error_factory()
        if not error.args:
            error.args = ("private-error-detail",)
        raise error

    monkeypatch.setattr(
        _routes_module(),
        "create_workflow_fixture_run",
        failing_service,
    )
    response = await route_context.client.post(
        _create_path(route_context),
        headers={"Idempotency-Key": RAW_PRIVATE_KEY},
        json=_create_body(route_context),
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail
    assert response.headers["X-Request-ID"]
    for private_value in (
        RAW_PRIVATE_KEY,
        "private-error-detail",
        "SELECT private",
        "/Users/example/.env",
        "fixture body",
    ):
        assert private_value not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_factory", "expected_status", "expected_detail"),
    [
        (WorkflowMaterializationProjectNotFoundError, 404, "project_not_found"),
        (WorkflowMaterializationRunNotFoundError, 404, "workflow_run_not_found"),
        (WorkflowMaterializationProjectNotActiveError, 409, "project_not_active"),
        (
            WorkflowMaterializationRunNotCompletedError,
            409,
            "workflow_run_not_completed",
        ),
        (WorkflowFixturePayloadUnboundError, 409, "workflow_payload_unbound"),
        (
            WorkflowMaterializationLineageDigestConflictError,
            409,
            "workflow_lineage_digest_conflict",
        ),
        (
            WorkflowMaterializationIdempotencyConflictError,
            409,
            "idempotency_conflict",
        ),
        (
            WorkflowRunAlreadyMaterializedError,
            409,
            "workflow_run_already_materialized",
        ),
        (
            lambda: WorkflowMaterializationDatasetConflictError("dataset_project_lineage_conflict"),
            409,
            "dataset_project_lineage_conflict",
        ),
        (
            WorkflowMaterializationTransactionStateError,
            409,
            "workflow_materialization_transaction_state_invalid",
        ),
        (
            WorkflowMaterializationPayloadInvalidError,
            500,
            "workflow_materialization_payload_invalid",
        ),
        (
            WorkflowMaterializationLedgerInvalidError,
            500,
            "workflow_materialization_ledger_invalid",
        ),
        (
            lambda: SQLAlchemyError("SELECT private FROM materialization"),
            503,
            "workflow_execution_persistence_unavailable",
        ),
        (
            lambda: RuntimeError("private materialization detail"),
            500,
            "workflow_execution_internal_error",
        ),
    ],
)
async def test_materialization_post_maps_only_allowlisted_sanitized_errors(
    route_context: RouteContext,
    monkeypatch: pytest.MonkeyPatch,
    error_factory: Callable[[], Exception],
    expected_status: int,
    expected_detail: str,
) -> None:
    async def failing_service(**kwargs: object) -> object:
        del kwargs
        error = error_factory()
        if not error.args:
            error.args = ("private-error-detail",)
        raise error

    monkeypatch.setattr(
        _routes_module(),
        "materialize_workflow_lineage",
        failing_service,
    )
    response = await route_context.client.post(
        f"/api/projects/{route_context.project_id}/workflow-runs/"
        f"{route_context.run_id}/materializations",
        headers={"Idempotency-Key": RAW_PRIVATE_KEY},
        json={
            "dataset_name": "route-error-dataset",
            "expected_lineage_digest": "sha256:" + "a" * 64,
        },
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail
    assert response.headers["X-Request-ID"]
    for private_value in (
        RAW_PRIVATE_KEY,
        "private-error-detail",
        "SELECT private",
        "private materialization detail",
    ):
        assert private_value not in response.text


@pytest.mark.asyncio
async def test_internal_failure_log_is_sanitized(
    route_context: RouteContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = _routes_module()
    logger = RecordingLogger(exception_events=[])
    marker = f"{RAW_PRIVATE_KEY} SELECT secret /Users/private/.env fixture body"

    async def failing_service(**kwargs: object) -> WorkflowFixtureRunCreateResponse:
        del kwargs
        raise RuntimeError(marker)

    monkeypatch.setattr(routes, "logger", logger)
    monkeypatch.setattr(routes, "create_workflow_fixture_run", failing_service)
    response = await route_context.client.post(
        _create_path(route_context),
        headers={"Idempotency-Key": RAW_PRIVATE_KEY},
        json=_create_body(route_context),
    )

    assert response.status_code == 500
    assert len(logger.exception_events) == 1
    event, fields = logger.exception_events[0]
    assert event == "workflow_execution_failed"
    assert fields["request_id"] == response.headers["X-Request-ID"]
    assert fields["project_id"] == str(route_context.project_id)
    assert fields["error_type"] == "RuntimeError"
    rendered = repr((event, fields))
    for private_value in (
        RAW_PRIVATE_KEY,
        "SELECT secret",
        "/Users/private/.env",
        "fixture body",
    ):
        assert private_value not in rendered


@pytest.mark.asyncio
async def test_real_api_materializes_payload_bound_run_and_preview_reads_assets(
    vertical_route_context: VerticalRouteContext,
) -> None:
    context = vertical_route_context
    run_response = await context.client.post(
        (
            f"/api/projects/{context.project_id}/workflow-plans/{context.plan_id}/"
            f"versions/{context.version_id}/fixture-runs"
        ),
        headers={"Idempotency-Key": "vertical-payload-run-key-0001"},
        json={
            "expected_preview_fingerprint": context.preview_fingerprint,
            "fixture_profile_id": "fixture-primary-payload-v1",
        },
    )
    assert run_response.status_code == 201
    run_id = run_response.json()["run"]["id"]
    preview_path = f"/api/projects/{context.project_id}/workflow-runs/{run_id}/lineage-preview"
    before = await context.client.get(preview_path)
    assert before.status_code == 200
    assert before.json()["schema_version"] == "workflow_lineage_preview.v2"
    assert before.json()["materialization_eligible"] is True

    path = f"/api/projects/{context.project_id}/workflow-runs/{run_id}/materializations"
    body = {
        "dataset_name": "vertical-workflow-materialization",
        "expected_lineage_digest": before.json()["lineage_digest"],
    }
    first = await context.client.post(
        path,
        headers={"Idempotency-Key": "vertical-materialization-key-0001"},
        json=body,
    )
    replay = await context.client.post(
        path,
        headers={"Idempotency-Key": "vertical-materialization-key-0001"},
        json=body,
    )
    after = await context.client.get(preview_path)

    assert [first.status_code, replay.status_code, after.status_code] == [201, 200, 200]
    assert first.json()["database_write"] is True
    assert replay.json()["database_write"] is False
    assert after.json()["raw_record"]["materialized"] is True
    assert after.json()["dataset"]["materialized"] is True
    assert after.json()["materialization_eligible"] is False
    assert after.json()["blocked_reasons"] == ["workflow_run_already_materialized"]
    assert after.json()["dataset"]["dataset_version_id"] == first.json()["dataset_version_id"]
    async with context.sessions() as session:
        counts = [
            int((await session.execute(select(func.count()).select_from(model))).scalar_one())
            for model in (
                RawRecord,
                DatasetVersion,
                WorkflowLineageMaterializationRequest,
            )
        ]
    assert counts == [run_response.json()["run"]["records_count"], 1, 1]


@pytest.mark.asyncio
async def test_real_api_exposes_readonly_shadow_equivalence_evidence(
    vertical_route_context: VerticalRouteContext,
) -> None:
    context = vertical_route_context
    created = await context.client.post(
        (
            f"/api/projects/{context.project_id}/workflow-plans/{context.plan_id}/"
            f"versions/{context.version_id}/fixture-runs"
        ),
        headers={"Idempotency-Key": "vertical-shadow-run-key-0001"},
        json={
            "expected_preview_fingerprint": context.preview_fingerprint,
            "fixture_profile_id": "fixture-shadow-v1",
        },
    )
    assert created.status_code == 201
    run_id = created.json()["run"]["id"]

    response = await context.client.get(
        f"/api/projects/{context.project_id}/workflow-runs/{run_id}/shadow-comparisons"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert all(item["sampled_items"] == 1 for item in payload["items"])
    assert all(item["equivalence_status"] == "equivalent" for item in payload["items"])
    assert all(
        item["routing_recommendation"] == "eligible_for_governance_review"
        for item in payload["items"]
    )
    assert all(item["catalog_mutation_applied"] is False for item in payload["items"])
    assert all(item["route_ranking_mutation_applied"] is False for item in payload["items"])
    assert all(item["provider_call_attempted"] is False for item in payload["items"])
    assert all(item["database_write"] is False for item in payload["items"])


@pytest.mark.asyncio
async def test_real_api_exposes_readonly_step_attempt_evidence(
    vertical_route_context: VerticalRouteContext,
) -> None:
    context = vertical_route_context
    created = await context.client.post(
        (
            f"/api/projects/{context.project_id}/workflow-plans/{context.plan_id}/"
            f"versions/{context.version_id}/fixture-runs"
        ),
        headers={"Idempotency-Key": "vertical-attempt-evidence-key-0001"},
        json={
            "expected_preview_fingerprint": context.preview_fingerprint,
            "fixture_profile_id": "fixture-primary-v1",
        },
    )
    assert created.status_code == 201
    run_id = created.json()["run"]["id"]

    response = await context.client.get(
        f"/api/projects/{context.project_id}/workflow-runs/{run_id}/attempt-fallback-evidence"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "workflow_attempt_fallback_evidence.v1"
    assert payload["workflow_run_id"] == run_id
    assert payload["attempt_total"] == len(payload["attempts"]) == 3
    assert payload["fallback_decision_total"] == 0
    assert payload["fallback_decisions"] == []
    assert all(item["attempt_number"] == 1 for item in payload["attempts"])
    assert all(item["status"] == "succeeded" for item in payload["attempts"])
    assert all(item["provider_call_attempted"] is False for item in payload["attempts"])
    assert payload["database_write"] is False
    assert payload["provider_call"] is False


@pytest.mark.asyncio
async def test_real_api_exposes_explicit_empty_checkpoint_budget_evidence(
    vertical_route_context: VerticalRouteContext,
) -> None:
    context = vertical_route_context
    created = await context.client.post(
        (
            f"/api/projects/{context.project_id}/workflow-plans/{context.plan_id}/"
            f"versions/{context.version_id}/fixture-runs"
        ),
        headers={"Idempotency-Key": "vertical-checkpoint-budget-key-0001"},
        json={
            "expected_preview_fingerprint": context.preview_fingerprint,
            "fixture_profile_id": "fixture-primary-v1",
        },
    )
    assert created.status_code == 201
    run_id = created.json()["run"]["id"]

    response = await context.client.get(
        f"/api/projects/{context.project_id}/workflow-runs/{run_id}/checkpoint-budget-evidence"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "workflow_checkpoint_budget_evidence.v1"
    assert payload["workflow_run_id"] == run_id
    assert payload["execution_session_id"] == run_id
    assert payload["checkpoint_steps"] == []
    assert payload["checkpoint_step_total"] == 0
    assert payload["checkpoint_page_total"] == 0
    assert payload["budget_status"] == "not_configured"
    assert payload["budget_account"] is None
    assert payload["budget_entries"] == []
    assert payload["usage"] is None
    assert payload["resume_action_available"] is False
    assert payload["budget_override_available"] is False
    assert payload["database_write"] is False
    assert payload["provider_call"] is False


@pytest.mark.asyncio
async def test_real_api_exposes_terminal_run_action_gates_without_available_action(
    vertical_route_context: VerticalRouteContext,
) -> None:
    context = vertical_route_context
    created = await context.client.post(
        (
            f"/api/projects/{context.project_id}/workflow-plans/{context.plan_id}/"
            f"versions/{context.version_id}/fixture-runs"
        ),
        headers={"Idempotency-Key": "vertical-action-gates-key-0001"},
        json={
            "expected_preview_fingerprint": context.preview_fingerprint,
            "fixture_profile_id": "fixture-primary-v1",
        },
    )
    assert created.status_code == 201
    run_id = created.json()["run"]["id"]

    response = await context.client.get(
        f"/api/projects/{context.project_id}/workflow-runs/{run_id}/action-gates"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "workflow_run_action_gates.v2"
    assert payload["workflow_run_id"] == run_id
    assert payload["run_status"] == "completed"
    assert payload["action_context_version"] == 1
    assert payload["action_gate_digest"].startswith("sha256:")
    assert [item["action"] for item in payload["gates"]] == [
        "retry",
        "resume",
        "cancel",
        "budget_override",
        "route_switch",
    ]
    assert payload["ready_for_review_total"] == 0
    assert payload["blocked_total"] == 0
    assert payload["not_applicable_total"] == 5
    assert payload["available_action_total"] == 0
    assert payload["mutation_endpoints_available"] is True
    assert payload["durable_action_audit_available"] is True
    assert payload["action_mutation_executed"] is False
    assert all(item["submission_available"] is False for item in payload["gates"])
    assert payload["database_write"] is False
    assert payload["provider_call"] is False


@pytest.mark.asyncio
async def test_real_api_held_cancel_issues_receipts_replays_and_refreshes(
    vertical_route_context: VerticalRouteContext,
) -> None:
    context = vertical_route_context
    created = await context.client.post(
        (
            f"/api/projects/{context.project_id}/workflow-plans/{context.plan_id}/"
            f"versions/{context.version_id}/fixture-runs"
        ),
        headers={"Idempotency-Key": "vertical-action-cancel-run-0001"},
        json={
            "expected_preview_fingerprint": context.preview_fingerprint,
            "fixture_profile_id": "fixture-primary-v1",
        },
    )
    assert created.status_code == 201
    run_id = created.json()["run"]["id"]
    async with context.sessions() as session:
        run = await session.get(WorkflowRun, uuid.UUID(run_id))
        assert run is not None
        run.status = "held"
        run.status_reason_code = "workflow_operator_review_required"
        run.impact_code = "workflow_run_paused"
        run.recovery_action_codes = ["cancel_run"]
        run.completed_steps = 0
        run.finished_at = None
        await session.commit()

    gates_response = await context.client.get(
        f"/api/projects/{context.project_id}/workflow-runs/{run_id}/action-gates"
    )
    assert gates_response.status_code == 200
    gates = gates_response.json()
    cancel_gate = next(item for item in gates["gates"] if item["action"] == "cancel")
    assert cancel_gate["submission_available"] is True
    assert gates["available_action_total"] == 1

    proposal = {
        "schema_version": "workflow_action_approval_request.v1",
        "action": "cancel",
        "approval_kind": "owner_confirmation",
        "expected_action_context_version": gates["action_context_version"],
        "expected_run_status": "held",
        "action_gate_digest": gates["action_gate_digest"],
        "reason_code": "cancel_operator_request",
        "reason": "Cancel this held fixture Run after Owner review.",
        "parameters": {
            "action": "cancel",
            "cancel_scope": "held_run",
        },
    }
    approval_response = await context.client.post(
        f"/api/projects/{context.project_id}/workflow-runs/{run_id}/action-approval-receipts",
        headers={"Idempotency-Key": "vertical-action-cancel-approval-0001"},
        json=proposal,
    )
    assert approval_response.status_code == 201
    approval = approval_response.json()
    assert approval["database_write"] is True
    assert approval["idempotent_replay"] is False
    assert approval["provider_call"] is False

    action_request = {
        **proposal,
        "schema_version": "workflow_run_action_request.v1",
        "approval_receipt_id": approval["id"],
    }
    action_request.pop("approval_kind")
    action_response = await context.client.post(
        f"/api/projects/{context.project_id}/workflow-runs/{run_id}/actions",
        headers={"Idempotency-Key": "vertical-action-cancel-command-0001"},
        json=action_request,
    )
    assert action_response.status_code == 201
    receipt = action_response.json()
    assert receipt["outcome"] == "accepted"
    assert receipt["after_run_status"] == "cancelled"
    assert receipt["database_write"] is True
    assert receipt["idempotent_replay"] is False
    assert receipt["provider_call"] is False
    assert receipt["execution_started"] is False
    async with context.sessions() as session:
        workspace = await session.get(Workspace, context.workspace_id)
        assert workspace is not None
        stored_requests = (
            (
                await session.execute(
                    select(WorkflowRunActionRequestRecord).where(
                        WorkflowRunActionRequestRecord.workflow_run_id == uuid.UUID(run_id)
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(stored_requests) == 1
    assert stored_requests[0].actor_user_id == workspace.owner_id
    assert stored_requests[0].idempotency_scope == (
        f"workflow_run_action.v1:{context.project_id}:{run_id}"
    )

    replay = await context.client.post(
        f"/api/projects/{context.project_id}/workflow-runs/{run_id}/actions",
        headers={"Idempotency-Key": "vertical-action-cancel-command-0001"},
        json=action_request,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == receipt["id"]
    assert replay.json()["database_write"] is False
    assert replay.json()["idempotent_replay"] is True

    refreshed = await context.client.get(
        f"/api/projects/{context.project_id}/workflow-runs/{run_id}/action-gates"
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["run_status"] == "cancelled"
    assert refreshed.json()["action_context_version"] == 2
    assert refreshed.json()["available_action_total"] == 0


@pytest.mark.asyncio
async def test_lineage_preview_fails_closed_on_tampered_materialized_step_lineage(
    vertical_route_context: VerticalRouteContext,
) -> None:
    context = vertical_route_context
    created = await context.client.post(
        (
            f"/api/projects/{context.project_id}/workflow-plans/{context.plan_id}/"
            f"versions/{context.version_id}/fixture-runs"
        ),
        headers={"Idempotency-Key": "tampered-payload-run-key-0001"},
        json={
            "expected_preview_fingerprint": context.preview_fingerprint,
            "fixture_profile_id": "fixture-primary-payload-v1",
        },
    )
    assert created.status_code == 201
    run_id = created.json()["run"]["id"]
    preview_path = f"/api/projects/{context.project_id}/workflow-runs/{run_id}/lineage-preview"
    preview = await context.client.get(preview_path)
    materialized = await context.client.post(
        f"/api/projects/{context.project_id}/workflow-runs/{run_id}/materializations",
        headers={"Idempotency-Key": "tampered-materialization-key-0001"},
        json={
            "dataset_name": "tampered-lineage-dataset",
            "expected_lineage_digest": preview.json()["lineage_digest"],
        },
    )
    assert materialized.status_code == 201

    async with context.sessions() as session:
        version = (
            await session.execute(
                select(DatasetVersion).where(
                    DatasetVersion.source_workflow_run_id == uuid.UUID(run_id)
                )
            )
        ).scalar_one()
        version.source_workflow_step_run_ids = [str(uuid.uuid4())]
        await session.commit()

    response = await context.client.get(preview_path)
    assert response.status_code == 500
    assert response.json()["detail"] == "workflow_run_lineage_invalid"
    assert "materialized_state_mismatch" not in response.text


@pytest.mark.parametrize(
    "tamper",
    ["content_and_version", "record_type", "source_url", "collected_at"],
)
@pytest.mark.asyncio
async def test_lineage_preview_rebinds_materialized_records_to_registered_envelope(
    tamper: str,
    vertical_route_context: VerticalRouteContext,
) -> None:
    context = vertical_route_context
    created = await context.client.post(
        (
            f"/api/projects/{context.project_id}/workflow-plans/{context.plan_id}/"
            f"versions/{context.version_id}/fixture-runs"
        ),
        headers={"Idempotency-Key": f"envelope-rebind-run-{tamper}-0001"},
        json={
            "expected_preview_fingerprint": context.preview_fingerprint,
            "fixture_profile_id": "fixture-primary-payload-v1",
        },
    )
    assert created.status_code == 201
    run_id = created.json()["run"]["id"]
    preview_path = f"/api/projects/{context.project_id}/workflow-runs/{run_id}/lineage-preview"
    preview = await context.client.get(preview_path)
    materialized = await context.client.post(
        f"/api/projects/{context.project_id}/workflow-runs/{run_id}/materializations",
        headers={"Idempotency-Key": f"envelope-rebind-write-{tamper}-0001"},
        json={
            "dataset_name": f"envelope-rebind-{tamper}",
            "expected_lineage_digest": preview.json()["lineage_digest"],
        },
    )
    assert materialized.status_code == 201

    async with context.sessions() as session:
        version = (
            await session.execute(
                select(DatasetVersion).where(
                    DatasetVersion.source_workflow_run_id == uuid.UUID(run_id)
                )
            )
        ).scalar_one()
        assert version.source_raw_record_ids is not None
        first_raw_id = uuid.UUID(version.source_raw_record_ids[0])
        record = await session.get(RawRecord, first_raw_id)
        assert record is not None
        if tamper == "content_and_version":
            content = {"tampered": True}
            record.content = content
            record.content_hash = sha256_id(cast(JsonValue, content)).removeprefix("sha256:")
            rows = list(version.rows)
            rows[0] = content
            version.rows = rows
        elif tamper == "record_type":
            record.record_type = "tampered"
        elif tamper == "source_url":
            record.source_url = "https://example.invalid/tampered"
        else:
            record.collected_at += timedelta(minutes=1)
        await session.commit()

    response = await context.client.get(preview_path)
    assert response.status_code == 500
    assert response.json()["detail"] == "workflow_run_lineage_invalid"
    assert "raw_record_mismatch" not in response.text


def test_only_approved_fixture_execution_routes_exist() -> None:
    execution_contracts = {
        (method, path)
        for method, path in _route_contracts()
        if "/workflow-runs" in path
        or path.endswith("/fixture-runs")
        or path.endswith("/fixture-run-gate")
    }
    assert execution_contracts == {
        (
            "GET",
            "/api/projects/{project_id}/workflow-plans/{plan_id}/versions/"
            "{version_id}/fixture-run-gate",
        ),
        (
            "POST",
            "/api/projects/{project_id}/workflow-plans/{plan_id}/versions/"
            "{version_id}/fixture-runs",
        ),
        ("GET", "/api/projects/{project_id}/workflow-runs"),
        ("GET", "/api/projects/{project_id}/workflow-runs/{run_id}"),
        (
            "GET",
            "/api/projects/{project_id}/workflow-runs/{run_id}/attempt-fallback-evidence",
        ),
        (
            "GET",
            "/api/projects/{project_id}/workflow-runs/{run_id}/checkpoint-budget-evidence",
        ),
        (
            "GET",
            "/api/projects/{project_id}/workflow-runs/{run_id}/provider-health-evidence",
        ),
        (
            "GET",
            "/api/projects/{project_id}/workflow-runs/{run_id}/executor-evidence",
        ),
        (
            "GET",
            "/api/projects/{project_id}/workflow-runs/{run_id}/action-gates",
        ),
        (
            "POST",
            "/api/projects/{project_id}/workflow-runs/{run_id}/action-approval-receipts",
        ),
        (
            "POST",
            "/api/projects/{project_id}/workflow-runs/{run_id}/actions",
        ),
        (
            "GET",
            "/api/projects/{project_id}/workflow-runs/{run_id}/shadow-comparisons",
        ),
        (
            "GET",
            "/api/projects/{project_id}/workflow-runs/{run_id}/lineage-preview",
        ),
        (
            "POST",
            "/api/projects/{project_id}/workflow-runs/{run_id}/materializations",
        ),
    }


def test_legacy_task_routes_do_not_import_workflow_execution_context() -> None:
    source = (
        Path(__file__).parents[2] / "src/data_intelligence_hub/api/routes/tasks.py"
    ).read_text(encoding="utf-8")
    assert "workflow_execution" not in source
    assert "WorkflowRun" not in source
    assert "StepRun" not in source
