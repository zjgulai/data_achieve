from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
import pytest_asyncio
from fastapi import HTTPException
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.api.deps import AuthContext, get_auth_context
from data_intelligence_hub.api.routes import workflow_plans as workflow_plan_routes
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.schemas.workflow_plan_persistence import (
    MonitoringScopeListResponse,
    MonitoringScopeResponse,
    WorkflowPlanCompareChange,
    WorkflowPlanCompareSection,
    WorkflowPlanCreateRequest,
    WorkflowPlanDetailResponse,
    WorkflowPlanListResponse,
    WorkflowPlanResponse,
    WorkflowPlanSaveOutcome,
    WorkflowPlanSaveResponse,
    WorkflowPlanVersionCompareResponse,
    WorkflowVersionCreateRequest,
    WorkflowVersionDetailResponse,
    WorkflowVersionListResponse,
    WorkflowVersionResponse,
    WorkflowVersionSummaryResponse,
)
from data_intelligence_hub.schemas.workflow_planner import (
    PlanningInput,
    WorkflowPlanPreview,
)
from data_intelligence_hub.services.capability_catalog import get_capability_catalog
from data_intelligence_hub.services.exceptions import (
    CapabilityCatalogLoadError,
    ProjectNotActiveError,
    ProjectNotFoundError,
    WorkflowPlanFlowModeConflictError,
    WorkflowPlanIdempotencyConflictError,
    WorkflowPlannerDependencyUnavailableError,
    WorkflowPlannerInputError,
    WorkflowPlannerTopologyError,
    WorkflowPlanNotFoundError,
    WorkflowPlanPreviewStaleError,
    WorkflowPlanVersionConflictError,
)
from data_intelligence_hub.services.workflow_planner.planner import (
    build_workflow_plan_preview,
)

FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "fixtures"
    / "workflow_planner"
    / "periodic_monitoring_request_v1.json"
)
BATCH_FIXTURE_PATH = (
    Path(__file__).parents[1] / "fixtures" / "workflow_planner" / "batch_research_request_v1.json"
)
NOW = datetime(2026, 7, 13, 10, 30, tzinfo=UTC)
RAW_PRIVATE_KEY = "route-private-idempotency-key-0001"


@dataclass(frozen=True)
class RouteContext:
    client: AsyncClient
    session: AsyncSession
    auth_override: Callable[[], Awaitable[AuthContext]]
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    plan_id: uuid.UUID
    base_version_id: uuid.UUID
    target_version_id: uuid.UUID


@dataclass
class RecordingLogger:
    info_events: list[tuple[str, dict[str, object]]]
    exception_events: list[tuple[str, dict[str, object]]]

    def info(self, event: str, **fields: object) -> None:
        self.info_events.append((event, fields))

    def exception(self, event: str, **fields: object) -> None:
        self.exception_events.append((event, fields))


ServiceCall = tuple[tuple[object, ...], dict[str, object]]


@pytest_asyncio.fixture()
async def route_context() -> AsyncIterator[RouteContext]:
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    session = cast(AsyncSession, object())
    user = User(
        id=user_id,
        email="workflow-plan-route@example.com",
        password_hash="not-used",
        name="Workflow Plan Route",
        status="active",
    )
    workspace = Workspace(
        id=workspace_id,
        name="Workflow Plan Route Workspace",
        slug=f"workflow-plan-route-{workspace_id}",
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
                base_version_id=uuid.uuid4(),
                target_version_id=uuid.uuid4(),
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


def _planning_input() -> PlanningInput:
    return PlanningInput.model_validate(
        cast(
            dict[str, object],
            json.loads(FIXTURE_PATH.read_text(encoding="utf-8")),
        )
    )


def _batch_input() -> PlanningInput:
    return PlanningInput.model_validate(
        cast(
            dict[str, object],
            json.loads(BATCH_FIXTURE_PATH.read_text(encoding="utf-8")),
        )
    )


def _preview(
    project_id: uuid.UUID,
    request_id: str,
    planning_input: PlanningInput | None = None,
) -> WorkflowPlanPreview:
    return build_workflow_plan_preview(
        project_id=project_id,
        planning_input=planning_input or _planning_input(),
        catalog=get_capability_catalog(),
        generated_at=NOW,
        request_id=request_id,
    )


def _version_response(
    context: RouteContext,
    *,
    request_id: str,
    version_number: int,
    planning_input: PlanningInput | None = None,
) -> WorkflowVersionResponse:
    effective_input = planning_input or _planning_input()
    preview = _preview(context.project_id, request_id, effective_input)
    version_id = context.base_version_id if version_number == 1 else context.target_version_id
    return WorkflowVersionResponse(
        id=version_id,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        workflow_plan_id=context.plan_id,
        created_by_user_id=context.user_id,
        version_number=version_number,
        planning_status=preview.planning_status,
        planner_contract_version=preview.planner_contract_version,
        catalog_snapshot_id=preview.catalog_snapshot_id,
        policy_version=preview.policy_version,
        mode_template_version=preview.mode_template_version,
        query_versions=preview.query_versions,
        preview_fingerprint=preview.preview_fingerprint,
        editable_input=effective_input,
        preview=preview,
        created_at=NOW,
    )


def _plan_response(
    context: RouteContext,
    *,
    current_version_number: int,
    planning_input: PlanningInput | None = None,
) -> WorkflowPlanResponse:
    effective_input = planning_input or _planning_input()
    version_id = (
        context.base_version_id if current_version_number == 1 else context.target_version_id
    )
    return WorkflowPlanResponse(
        id=context.plan_id,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        created_by_user_id=context.user_id,
        name="Competitor monitoring",
        flow_mode=effective_input.flow_mode,
        status="previewed",
        current_version_id=version_id,
        current_version_number=current_version_number,
        planning_status="held",
        scope_count=1,
        query_term_count=2,
        created_at=NOW,
        updated_at=NOW,
    )


def _save_response(
    context: RouteContext,
    *,
    request_id: str,
    outcome: WorkflowPlanSaveOutcome,
    replay: bool,
    version_number: int,
    planning_input: PlanningInput | None = None,
) -> WorkflowPlanSaveResponse:
    return WorkflowPlanSaveResponse(
        database_write=not replay,
        plan_changed=not replay and outcome == "created",
        outcome=outcome,
        idempotent_replay=replay,
        plan=_plan_response(
            context,
            current_version_number=version_number,
            planning_input=planning_input,
        ),
        version=_version_response(
            context,
            request_id=request_id,
            version_number=version_number,
            planning_input=planning_input,
        ),
    )


def _scope_response(context: RouteContext) -> MonitoringScopeResponse:
    scope = _preview(context.project_id, "scope-fixture").normalized_input.scopes[0]
    return MonitoringScopeResponse(
        id=uuid.uuid4(),
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        created_by_user_id=context.user_id,
        scope_key=scope.scope_key,
        scope_type=scope.scope_type,
        canonical_term=scope.canonical_term,
        aliases=list(scope.aliases),
        include_terms=list(scope.include_terms),
        exclude_terms=list(scope.exclude_terms),
        official_accounts=list(scope.official_accounts),
        seed_urls=list(scope.seed_urls),
        effective_languages=list(scope.effective_languages),
        effective_regions=list(scope.effective_regions),
        effective_platforms=list(scope.effective_platforms),
        match_mode=scope.match_mode,
        created_at=NOW,
    )


def _create_body(context: RouteContext) -> dict[str, object]:
    preview = _preview(context.project_id, "create-body")
    return {
        "name": "  Competitor monitoring  ",
        "preview_input": _planning_input().model_dump(mode="json"),
        "expected_preview_fingerprint": preview.preview_fingerprint,
    }


def _version_body(context: RouteContext) -> dict[str, object]:
    preview = _preview(context.project_id, "version-body")
    return {
        "preview_input": _planning_input().model_dump(mode="json"),
        "expected_preview_fingerprint": preview.preview_fingerprint,
        "expected_current_version_id": str(context.base_version_id),
    }


def _install_static_service(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    result: BaseModel,
) -> list[ServiceCall]:
    calls: list[ServiceCall] = []

    async def service(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        return result

    monkeypatch.setattr(workflow_plan_routes, name, service, raising=False)
    return calls


def _install_failing_service(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    error_factory: Callable[[], Exception],
) -> list[ServiceCall]:
    calls: list[ServiceCall] = []

    async def service(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        raise error_factory()

    monkeypatch.setattr(workflow_plan_routes, name, service, raising=False)
    return calls


def _workflow_route_contracts() -> set[tuple[str, str]]:
    contracts: set[tuple[str, str]] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or set():
            contracts.add((method, route.path))
    return contracts


def _assert_boundary_false(payload: dict[str, object]) -> None:
    for field in (
        "provider_call",
        "actor_run",
        "browser_run",
        "llm_call",
        "workflow_run_created",
        "execution_authorized",
    ):
        assert payload[field] is False


def test_registers_exact_two_write_and_six_read_persistence_contracts() -> None:
    expected = {
        ("POST", "/api/projects/{project_id}/workflow-plans"),
        ("POST", "/api/projects/{project_id}/workflow-plans/{plan_id}/versions"),
        ("GET", "/api/projects/{project_id}/workflow-plans"),
        ("GET", "/api/projects/{project_id}/workflow-plans/{plan_id}"),
        ("GET", "/api/projects/{project_id}/workflow-plans/{plan_id}/versions"),
        (
            "GET",
            "/api/projects/{project_id}/workflow-plans/{plan_id}/versions/{version_id}",
        ),
        (
            "GET",
            "/api/projects/{project_id}/workflow-plans/{plan_id}/version-compare",
        ),
        ("GET", "/api/projects/{project_id}/monitoring-scopes"),
    }
    contracts = _workflow_route_contracts()

    assert expected <= contracts
    assert not {
        (method, path)
        for method, path in contracts
        if "/workflow-plans" in path
        and (method in {"PATCH", "DELETE"} or path.endswith(("/activate", "/run", "/archive")))
    }


@pytest.mark.asyncio
async def test_write_routes_preserve_created_no_op_and_replay_status(
    route_context: RouteContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_calls: list[ServiceCall] = []
    version_calls: list[ServiceCall] = []
    create_attempt = 0
    no_op_attempt = 0

    async def create_service(*args: object, **kwargs: object) -> object:
        nonlocal create_attempt
        create_calls.append((args, kwargs))
        create_attempt += 1
        return _save_response(
            route_context,
            request_id=cast(str, kwargs["request_id"]),
            outcome="created",
            replay=create_attempt > 1,
            version_number=1,
        )

    async def version_service(*args: object, **kwargs: object) -> object:
        nonlocal no_op_attempt
        version_calls.append((args, kwargs))
        key = cast(str, kwargs["idempotency_key"])
        outcome: WorkflowPlanSaveOutcome
        if key == "new-version-key-0001":
            outcome = "created"
            replay = False
        else:
            no_op_attempt += 1
            outcome = "semantic_no_op"
            replay = no_op_attempt > 1
        return _save_response(
            route_context,
            request_id=cast(str, kwargs["request_id"]),
            outcome=outcome,
            replay=replay,
            version_number=2,
        )

    monkeypatch.setattr(
        workflow_plan_routes,
        "create_workflow_plan",
        create_service,
        raising=False,
    )
    monkeypatch.setattr(
        workflow_plan_routes,
        "create_workflow_version",
        version_service,
        raising=False,
    )

    plan_path = f"/api/projects/{route_context.project_id}/workflow-plans"
    version_path = f"{plan_path}/{route_context.plan_id}/versions"
    responses = [
        await route_context.client.post(
            plan_path,
            headers={"Idempotency-Key": "  create-plan-key-0001  "},
            json=_create_body(route_context),
        ),
        await route_context.client.post(
            plan_path,
            headers={"Idempotency-Key": "create-plan-key-0001"},
            json=_create_body(route_context),
        ),
        await route_context.client.post(
            version_path,
            headers={"Idempotency-Key": "new-version-key-0001"},
            json=_version_body(route_context),
        ),
        await route_context.client.post(
            version_path,
            headers={"Idempotency-Key": "no-op-version-key-0001"},
            json=_version_body(route_context),
        ),
        await route_context.client.post(
            version_path,
            headers={"Idempotency-Key": "no-op-version-key-0001"},
            json=_version_body(route_context),
        ),
    ]

    assert [response.status_code for response in responses] == [201, 201, 201, 200, 200]
    assert responses[0].json()["database_write"] is True
    assert responses[0].json()["plan_changed"] is True
    assert responses[1].json()["idempotent_replay"] is True
    assert responses[1].json()["database_write"] is False
    assert responses[1].json()["plan_changed"] is False
    assert responses[3].json()["outcome"] == "semantic_no_op"
    assert responses[3].json()["database_write"] is True
    assert responses[3].json()["plan_changed"] is False
    assert responses[4].json()["idempotent_replay"] is True
    assert responses[4].json()["database_write"] is False
    for response in responses:
        assert response.headers["X-Request-ID"]
        _assert_boundary_false(cast(dict[str, object], response.json()))

    assert len(create_calls) == 2
    assert len(version_calls) == 3
    assert cast(str, create_calls[0][1]["idempotency_key"]) == "create-plan-key-0001"
    assert cast(WorkflowPlanCreateRequest, create_calls[0][1]["payload"]).name == (
        "Competitor monitoring"
    )
    assert cast(uuid.UUID, version_calls[0][1]["workflow_plan_id"]) == route_context.plan_id
    assert isinstance(version_calls[0][1]["payload"], WorkflowVersionCreateRequest)
    for response, (_args, kwargs) in zip(
        responses,
        [*create_calls, *version_calls],
        strict=True,
    ):
        session_arg = kwargs.get("session", _args[0] if _args else None)
        assert session_arg is route_context.session
        assert kwargs["workspace_id"] == route_context.workspace_id
        assert kwargs["created_by_user_id"] == route_context.user_id
        assert kwargs["project_id"] == route_context.project_id
        assert kwargs["request_id"] == response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_batch_save_response_omits_schedule_intent_from_http_json(
    route_context: RouteContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch_input = _batch_input()
    response_model = _save_response(
        route_context,
        request_id="batch-response",
        outcome="created",
        replay=False,
        version_number=1,
        planning_input=batch_input,
    )
    _install_static_service(
        monkeypatch,
        "create_workflow_plan",
        response_model,
    )

    response = await route_context.client.post(
        f"/api/projects/{route_context.project_id}/workflow-plans",
        headers={"Idempotency-Key": "batch-create-key-0001"},
        json=_create_body(route_context),
    )

    assert response.status_code == 201
    editable_input = response.json()["version"]["editable_input"]
    assert editable_input["flow_mode"] == "batch_research"
    assert "schedule_intent" not in editable_input
    assert (
        "schedule_intent" not in response_model.model_dump(mode="json")["version"]["editable_input"]
    )


@pytest.mark.asyncio
async def test_write_schema_and_idempotency_header_fail_before_service(
    route_context: RouteContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_calls = _install_static_service(
        monkeypatch,
        "create_workflow_plan",
        _save_response(
            route_context,
            request_id="not-called",
            outcome="created",
            replay=False,
            version_number=1,
        ),
    )
    version_calls = _install_static_service(
        monkeypatch,
        "create_workflow_version",
        _save_response(
            route_context,
            request_id="not-called",
            outcome="created",
            replay=False,
            version_number=2,
        ),
    )
    plan_path = f"/api/projects/{route_context.project_id}/workflow-plans"
    version_path = f"{plan_path}/{route_context.plan_id}/versions"
    invalid_create_bodies = [
        {**_create_body(route_context), "plan_payload": {"trusted": True}},
        {**_create_body(route_context), "name": " "},
    ]
    invalid_version_bodies = [
        {**_version_body(route_context), "name": "forbidden"},
        {**_version_body(route_context), "version_number": 99},
    ]
    responses = [
        await route_context.client.post(plan_path, json=_create_body(route_context)),
        await route_context.client.post(
            plan_path,
            headers={"Idempotency-Key": " " * 12},
            json=_create_body(route_context),
        ),
        await route_context.client.post(
            plan_path,
            headers={"Idempotency-Key": "x" * 201},
            json=_create_body(route_context),
        ),
        *[
            await route_context.client.post(
                plan_path,
                headers={"Idempotency-Key": "invalid-body-key-0001"},
                json=body,
            )
            for body in invalid_create_bodies
        ],
        *[
            await route_context.client.post(
                version_path,
                headers={"Idempotency-Key": "invalid-body-key-0002"},
                json=body,
            )
            for body in invalid_version_bodies
        ],
    ]

    assert responses
    assert all(response.status_code == 422 for response in responses)
    assert create_calls == []
    assert version_calls == []


@pytest.mark.asyncio
async def test_six_read_routes_return_typed_false_boundaries_and_pagination(
    route_context: RouteContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan_response(route_context, current_version_number=2)
    version = _version_response(
        route_context,
        request_id="frozen-version",
        version_number=2,
    )
    summary = WorkflowVersionSummaryResponse.model_validate(
        version.model_dump(mode="python", exclude={"editable_input", "preview"})
    )
    plan_list_calls = _install_static_service(
        monkeypatch,
        "list_workflow_plans_for_project",
        WorkflowPlanListResponse(
            project_status="active",
            items=[plan],
            total=1,
            limit=7,
            offset=3,
        ),
    )
    plan_detail_calls = _install_static_service(
        monkeypatch,
        "get_workflow_plan_detail",
        WorkflowPlanDetailResponse(
            project_status="archived",
            plan=plan,
            current_version=version,
        ),
    )
    version_list_calls = _install_static_service(
        monkeypatch,
        "list_workflow_plan_versions",
        WorkflowVersionListResponse(
            project_status="active",
            items=[summary],
            total=1,
            limit=6,
            offset=2,
        ),
    )
    version_detail_calls = _install_static_service(
        monkeypatch,
        "get_workflow_version_detail",
        WorkflowVersionDetailResponse(
            project_status="active",
            plan=plan,
            version=version,
        ),
    )
    compare_calls = _install_static_service(
        monkeypatch,
        "compare_workflow_plan_versions",
        WorkflowPlanVersionCompareResponse(
            project_status="active",
            plan=plan,
            base_version=summary.model_copy(
                update={"id": route_context.base_version_id, "version_number": 1}
            ),
            target_version=summary,
            same_version=False,
            sections=[
                WorkflowPlanCompareSection(
                    key="plan",
                    changes=[
                        WorkflowPlanCompareChange(
                            field="planning_status",
                            before="partially_resolved",
                            after="held",
                        )
                    ],
                )
            ],
        ),
    )
    scope_list_calls = _install_static_service(
        monkeypatch,
        "list_monitoring_scopes_for_project",
        MonitoringScopeListResponse(
            project_status="active",
            items=[_scope_response(route_context)],
            total=1,
            limit=5,
            offset=1,
        ),
    )

    base_path = f"/api/projects/{route_context.project_id}"
    plan_path = f"{base_path}/workflow-plans/{route_context.plan_id}"
    responses = [
        await route_context.client.get(
            f"{base_path}/workflow-plans",
            params={"limit": 7, "offset": 3},
        ),
        await route_context.client.get(plan_path),
        await route_context.client.get(
            f"{plan_path}/versions",
            params={"limit": 6, "offset": 2},
        ),
        await route_context.client.get(f"{plan_path}/versions/{route_context.target_version_id}"),
        await route_context.client.get(
            f"{plan_path}/version-compare",
            params={
                "base_version_id": str(route_context.base_version_id),
                "target_version_id": str(route_context.target_version_id),
            },
        ),
        await route_context.client.get(
            f"{base_path}/monitoring-scopes",
            params={"limit": 5, "offset": 1},
        ),
    ]

    assert all(response.status_code == 200 for response in responses)
    for response in responses:
        payload = cast(dict[str, object], response.json())
        assert response.headers["X-Request-ID"]
        assert payload["database_write"] is False
        assert payload["plan_changed"] is False
        _assert_boundary_false(payload)
    assert "preview" not in responses[2].json()["items"][0]
    assert responses[1].json()["project_status"] == "archived"
    assert responses[3].json()["version"]["preview"]["request_id"] == "frozen-version"
    assert responses[3].json()["version"]["editable_input"]["flow_mode"] == ("periodic_monitoring")
    assert "fingerprint_payload" not in responses[3].json()["version"]
    assert responses[4].json()["sections"][0]["key"] == "plan"
    assert responses[5].json()["items"][0]["scope_key"]

    all_calls = [
        plan_list_calls,
        plan_detail_calls,
        version_list_calls,
        version_detail_calls,
        compare_calls,
        scope_list_calls,
    ]
    assert all(len(calls) == 1 for calls in all_calls)
    assert plan_list_calls[0][1]["limit"] == 7
    assert plan_list_calls[0][1]["offset"] == 3
    assert version_list_calls[0][1]["limit"] == 6
    assert version_list_calls[0][1]["offset"] == 2
    assert version_detail_calls[0][1]["version_id"] == route_context.target_version_id
    assert compare_calls[0][1]["base_version_id"] == route_context.base_version_id
    assert compare_calls[0][1]["target_version_id"] == route_context.target_version_id
    assert scope_list_calls[0][1]["limit"] == 5
    assert scope_list_calls[0][1]["offset"] == 1


@pytest.mark.asyncio
async def test_read_query_validation_fails_before_service(
    route_context: RouteContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty_plan_list = WorkflowPlanListResponse(
        project_status="active",
        items=[],
        total=0,
    )
    plan_list_calls = _install_static_service(
        monkeypatch,
        "list_workflow_plans_for_project",
        empty_plan_list,
    )
    compare_calls = _install_static_service(
        monkeypatch,
        "compare_workflow_plan_versions",
        WorkflowPlanVersionCompareResponse(
            project_status="active",
            plan=_plan_response(route_context, current_version_number=1),
            base_version=WorkflowVersionSummaryResponse.model_validate(
                _version_response(
                    route_context,
                    request_id="query-validation",
                    version_number=1,
                ).model_dump(mode="python", exclude={"editable_input", "preview"})
            ),
            target_version=WorkflowVersionSummaryResponse.model_validate(
                _version_response(
                    route_context,
                    request_id="query-validation",
                    version_number=1,
                ).model_dump(mode="python", exclude={"editable_input", "preview"})
            ),
            same_version=True,
            sections=[],
        ),
    )
    base_path = f"/api/projects/{route_context.project_id}/workflow-plans"
    compare_path = f"{base_path}/{route_context.plan_id}/version-compare"

    responses = [
        await route_context.client.get(base_path, params={"limit": 0}),
        await route_context.client.get(base_path, params={"limit": 101}),
        await route_context.client.get(base_path, params={"offset": -1}),
        await route_context.client.get(compare_path),
        await route_context.client.get(
            compare_path,
            params={"base_version_id": "not-a-uuid", "target_version_id": "also-bad"},
        ),
    ]

    assert all(response.status_code == 422 for response in responses)
    assert plan_list_calls == []
    assert compare_calls == []


@pytest.mark.asyncio
async def test_write_and_read_routes_require_authentication(
    route_context: RouteContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_calls = _install_static_service(
        monkeypatch,
        "create_workflow_plan",
        _save_response(
            route_context,
            request_id="not-called",
            outcome="created",
            replay=False,
            version_number=1,
        ),
    )
    list_calls = _install_static_service(
        monkeypatch,
        "list_workflow_plans_for_project",
        WorkflowPlanListResponse(project_status="active", items=[], total=0),
    )

    async def deny_authentication() -> AuthContext:
        raise HTTPException(status_code=401, detail="Authentication required")

    app.dependency_overrides[get_auth_context] = deny_authentication
    try:
        path = f"/api/projects/{route_context.project_id}/workflow-plans"
        write_response = await route_context.client.post(
            path,
            headers={"Idempotency-Key": "authentication-key-0001"},
            json=_create_body(route_context),
        )
        read_response = await route_context.client.get(path)
    finally:
        app.dependency_overrides[get_auth_context] = route_context.auth_override

    assert write_response.status_code == 401
    assert read_response.status_code == 401
    assert create_calls == []
    assert list_calls == []


def _version_not_found_error() -> Exception:
    exceptions_module = __import__(
        "data_intelligence_hub.services.exceptions",
        fromlist=["WorkflowVersionNotFoundError"],
    )
    error_type = cast(type[Exception], exceptions_module.WorkflowVersionNotFoundError)
    return error_type()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "service_name",
        "method",
        "path_kind",
        "error_factory",
        "expected_status",
        "expected_detail",
    ),
    [
        (
            "create_workflow_plan",
            "POST",
            "create",
            ProjectNotFoundError,
            404,
            "Project not found",
        ),
        (
            "create_workflow_version",
            "POST",
            "version-create",
            WorkflowPlanNotFoundError,
            404,
            "workflow_plan_not_found",
        ),
        (
            "get_workflow_version_detail",
            "GET",
            "version-detail",
            _version_not_found_error,
            404,
            "workflow_version_not_found",
        ),
        (
            "create_workflow_plan",
            "POST",
            "create",
            ProjectNotActiveError,
            409,
            "project_not_active",
        ),
        (
            "create_workflow_plan",
            "POST",
            "create",
            WorkflowPlanPreviewStaleError,
            409,
            "preview_stale",
        ),
        (
            "create_workflow_version",
            "POST",
            "version-create",
            WorkflowPlanVersionConflictError,
            409,
            "version_conflict",
        ),
        (
            "create_workflow_plan",
            "POST",
            "create",
            WorkflowPlanIdempotencyConflictError,
            409,
            "idempotency_conflict",
        ),
        (
            "create_workflow_version",
            "POST",
            "version-create",
            WorkflowPlanFlowModeConflictError,
            409,
            "workflow_plan_flow_mode_conflict",
        ),
        (
            "create_workflow_plan",
            "POST",
            "create",
            lambda: WorkflowPlannerInputError(
                [
                    {
                        "loc": ["body", "scopes", 0, "platforms"],
                        "msg": "periodic_effective_platform_required",
                        "type": "value_error",
                    }
                ]
            ),
            422,
            [
                {
                    "loc": ["body", "scopes", 0, "platforms"],
                    "msg": "periodic_effective_platform_required",
                    "type": "value_error",
                }
            ],
        ),
        (
            "create_workflow_plan",
            "POST",
            "create",
            CapabilityCatalogLoadError,
            503,
            "capability_catalog_load_failed",
        ),
        (
            "create_workflow_plan",
            "POST",
            "create",
            WorkflowPlannerDependencyUnavailableError,
            503,
            "workflow_planner_dependency_unavailable",
        ),
        (
            "create_workflow_plan",
            "POST",
            "create",
            lambda: SQLAlchemyError("private SQL statement"),
            503,
            "persistence_unavailable",
        ),
        (
            "create_workflow_plan",
            "POST",
            "create",
            WorkflowPlannerTopologyError,
            500,
            "workflow_planner_invalid_step_graph",
        ),
        (
            "create_workflow_plan",
            "POST",
            "create",
            lambda: RuntimeError("private internal path"),
            500,
            "workflow_planner_internal_error",
        ),
    ],
)
async def test_maps_service_failures_to_stable_private_errors(
    route_context: RouteContext,
    monkeypatch: pytest.MonkeyPatch,
    service_name: str,
    method: str,
    path_kind: str,
    error_factory: Callable[[], Exception],
    expected_status: int,
    expected_detail: object,
) -> None:
    calls = _install_failing_service(
        monkeypatch,
        service_name,
        error_factory,
    )
    plan_path = f"/api/projects/{route_context.project_id}/workflow-plans/{route_context.plan_id}"
    if path_kind == "create":
        path = f"/api/projects/{route_context.project_id}/workflow-plans"
        body = _create_body(route_context)
    elif path_kind == "version-create":
        path = f"{plan_path}/versions"
        body = _version_body(route_context)
    else:
        path = f"{plan_path}/versions/{route_context.target_version_id}"
        body = None

    if method == "POST":
        response = await route_context.client.post(
            path,
            headers={"Idempotency-Key": RAW_PRIVATE_KEY},
            json=body,
        )
    else:
        response = await route_context.client.get(path)

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail
    assert response.headers["X-Request-ID"]
    assert len(calls) == 1
    rendered = response.text
    assert RAW_PRIVATE_KEY not in rendered
    assert "private SQL statement" not in rendered
    assert "private internal path" not in rendered


@pytest.mark.asyncio
async def test_internal_failure_log_redacts_key_sql_path_and_input(
    route_context: RouteContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = RecordingLogger(info_events=[], exception_events=[])
    monkeypatch.setattr(workflow_plan_routes, "logger", logger, raising=False)
    private_marker = (
        f"{RAW_PRIVATE_KEY} SELECT * FROM private_table "
        "/Users/private/.env Acme https://example.com/private"
    )
    _install_failing_service(
        monkeypatch,
        "create_workflow_plan",
        lambda: RuntimeError(private_marker),
    )

    response = await route_context.client.post(
        f"/api/projects/{route_context.project_id}/workflow-plans",
        headers={"Idempotency-Key": RAW_PRIVATE_KEY},
        json=_create_body(route_context),
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "workflow_planner_internal_error"
    assert response.headers["X-Request-ID"]
    assert len(logger.exception_events) == 1
    event, fields = logger.exception_events[0]
    assert event == "workflow_plan_persistence_failed"
    assert fields["request_id"] == response.headers["X-Request-ID"]
    assert fields["project_id"] == str(route_context.project_id)
    assert fields["error_type"] == "RuntimeError"
    rendered = repr((event, fields))
    for private_value in (
        RAW_PRIVATE_KEY,
        "SELECT *",
        "/Users/private/.env",
        "Acme",
        "example.com/private",
    ):
        assert private_value not in rendered


def test_forbidden_mutation_and_execution_routes_are_not_registered() -> None:
    contracts = _workflow_route_contracts()
    forbidden_methods = {"PATCH", "DELETE"}
    forbidden_suffixes = ("/activate", "/run", "/archive")

    assert all(
        method not in forbidden_methods for method, path in contracts if "/workflow-plans" in path
    )
    assert all(
        not path.endswith(forbidden_suffixes)
        for method, path in contracts
        if method == "POST" and "/workflow-plans" in path
    )
