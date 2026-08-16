from __future__ import annotations

import inspect
import json
import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Iterator
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, cast

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from httpx import Response as HttpxResponse
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.api.routes import workflow_plans as workflow_plan_routes
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.core.security import create_access_token
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.capability_governance import CapabilityCatalogHead
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityCatalog,
    CapabilityStatus,
)
from data_intelligence_hub.services.capability_catalog import (
    clear_capability_catalog_cache,
    get_capability_catalog,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityCatalogLoadError,
    ProjectNotActiveError,
    ProjectNotFoundError,
    WorkflowPlannerDependencyUnavailableError,
    WorkflowPlannerTopologyError,
)
from data_intelligence_hub.services.project_service import get_active_project_or_raise
from data_intelligence_hub.services.workflow_planner.fingerprint import (
    compute_catalog_snapshot_id,
)
from data_intelligence_hub.services.workflow_planner.planner import (
    build_workflow_plan_preview,
)

PERIODIC_FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "workflow_planner"
    / "periodic_monitoring_request_v1.json"
)


@pytest.fixture(autouse=True)
def isolate_capability_catalog_cache() -> Iterator[None]:
    clear_capability_catalog_cache()
    yield
    clear_capability_catalog_cache()


@dataclass(frozen=True)
class PlannerTestContext:
    client: AsyncClient
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    workspace: Workspace
    active_project: Project
    archived_project: Project
    foreign_project: Project


@dataclass
class RecordingLogger:
    info_events: list[tuple[str, dict[str, object]]]
    exception_events: list[tuple[str, dict[str, object]]]

    def info(self, event: str, **fields: object) -> None:
        self.info_events.append((event, fields))

    def exception(self, event: str, **fields: object) -> None:
        self.exception_events.append((event, fields))


@pytest_asyncio.fixture()
async def planner_context() -> AsyncIterator[PlannerTestContext]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    owner_id = uuid.uuid4()
    foreign_owner_id = uuid.uuid4()
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Planner Workspace",
        slug="planner-workspace",
        owner_id=owner_id,
    )
    active_project = Project(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        owner_id=owner_id,
        name="Active Planner Project",
        description=None,
        domain="social",
        status="active",
    )
    foreign_workspace = Workspace(
        id=uuid.uuid4(),
        name="Foreign Workspace",
        slug="foreign-workspace",
        owner_id=foreign_owner_id,
    )
    archived_project = Project(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        owner_id=owner_id,
        name="Archived Planner Project",
        description=None,
        domain="social",
        status="archived",
    )
    foreign_project = Project(
        id=uuid.uuid4(),
        workspace_id=foreign_workspace.id,
        owner_id=foreign_owner_id,
        name="Foreign Planner Project",
        description=None,
        domain="social",
        status="active",
    )
    async with session_factory() as session:
        session.add_all(
            [
                User(
                    id=owner_id,
                    email="planner-owner@example.com",
                    password_hash="not-used",
                    name="Planner Owner",
                    status="active",
                ),
                User(
                    id=foreign_owner_id,
                    email="foreign-owner@example.com",
                    password_hash="not-used",
                    name="Foreign Owner",
                    status="active",
                ),
            ]
        )
        session.add_all(
            [
                workspace,
                foreign_workspace,
                WorkspaceMember(
                    workspace_id=workspace.id,
                    user_id=owner_id,
                    role="owner",
                ),
                WorkspaceMember(
                    workspace_id=foreign_workspace.id,
                    user_id=foreign_owner_id,
                    role="owner",
                ),
                active_project,
                archived_project,
                foreign_project,
                CapabilityCatalogHead(
                    singleton_key="global",
                    current_revision_id=None,
                    head_version=0,
                ),
            ]
        )
        await session.commit()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            client.cookies.set("access_token", create_access_token(owner_id))
            yield PlannerTestContext(
                client=client,
                engine=engine,
                session_factory=session_factory,
                workspace=workspace,
                active_project=active_project,
                archived_project=archived_project,
                foreign_project=foreign_project,
            )
    finally:
        app.dependency_overrides.pop(get_session, None)
        clear_capability_catalog_cache()
        await engine.dispose()


def load_periodic_request() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(PERIODIC_FIXTURE.read_text(encoding="utf-8")),
    )


def preview_path(context: PlannerTestContext) -> str:
    return f"/api/projects/{context.active_project.id}/workflow-plans/preview"


async def count_all_tables(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    async with session_factory() as session:
        for table in Base.metadata.sorted_tables:
            result = await session.execute(select(func.count()).select_from(table))
            counts[table.name] = result.scalar_one()
    return counts


def normalized_statement(statement: str) -> str:
    return " ".join(statement.split()).upper()


async def request_with_sql_capture(
    context: PlannerTestContext,
    payload: dict[str, object],
) -> tuple[HttpxResponse, list[str]]:
    statements: list[str] = []
    forbidden_commands = {"INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"}

    def capture_statement(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _execution_context: object,
        _executemany: bool,
    ) -> None:
        normalized = normalized_statement(statement)
        statements.append(normalized)
        command = normalized.split(maxsplit=1)[0] if normalized else ""
        if command in forbidden_commands:
            raise AssertionError(f"preview_sql_write_forbidden:{command}")

    event.listen(
        context.engine.sync_engine,
        "before_cursor_execute",
        capture_statement,
    )
    try:
        response = await context.client.post(
            preview_path(context),
            json=payload,
        )
    finally:
        event.remove(
            context.engine.sync_engine,
            "before_cursor_execute",
            capture_statement,
        )
    return response, statements


def equivalent_scope_payload(scope_count: int) -> dict[str, object]:
    payload = load_periodic_request()
    scopes = cast(list[dict[str, object]], payload["scopes"])
    source_scope = scopes[0]
    payload["scopes"] = [
        {**deepcopy(source_scope), "scope_ref": f"scope-{index + 1}"}
        for index in range(scope_count)
    ]
    return payload


@pytest.mark.asyncio
async def test_active_project_lookup_hides_cross_workspace_project(
    planner_context: PlannerTestContext,
) -> None:
    async with planner_context.session_factory() as session:
        with pytest.raises(ProjectNotFoundError):
            await get_active_project_or_raise(
                session,
                planner_context.workspace,
                planner_context.foreign_project.id,
            )


@pytest.mark.asyncio
async def test_active_project_lookup_rejects_archived_project(
    planner_context: PlannerTestContext,
) -> None:
    async with planner_context.session_factory() as session:
        with pytest.raises(ProjectNotActiveError):
            await get_active_project_or_raise(
                session,
                planner_context.workspace,
                planner_context.archived_project.id,
            )


@pytest.mark.asyncio
async def test_preview_endpoint_requires_authentication(
    planner_context: PlannerTestContext,
) -> None:
    planner_context.client.cookies.clear()
    response = await planner_context.client.post(
        f"/api/projects/{planner_context.active_project.id}/workflow-plans/preview",
        json=load_periodic_request(),
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_preview_endpoint_returns_404_for_missing_project(
    planner_context: PlannerTestContext,
) -> None:
    response = await planner_context.client.post(
        f"/api/projects/{uuid.uuid4()}/workflow-plans/preview",
        json=load_periodic_request(),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"
    assert response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_preview_endpoint_hides_cross_workspace_project(
    planner_context: PlannerTestContext,
) -> None:
    response = await planner_context.client.post(
        f"/api/projects/{planner_context.foreign_project.id}/workflow-plans/preview",
        json=load_periodic_request(),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"
    assert response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_preview_endpoint_rejects_archived_project(
    planner_context: PlannerTestContext,
) -> None:
    response = await planner_context.client.post(
        f"/api/projects/{planner_context.archived_project.id}/workflow-plans/preview",
        json=load_periodic_request(),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "project_not_active"
    assert response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_canonical_preview_returns_held_with_bounded_logging(
    planner_context: PlannerTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = RecordingLogger(info_events=[], exception_events=[])
    monkeypatch.setattr(workflow_plan_routes, "logger", logger, raising=False)
    request_payload = load_periodic_request()

    response = await planner_context.client.post(
        preview_path(planner_context),
        json=request_payload,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["planning_status"] == "held"
    assert payload["project_id"] == str(planner_context.active_project.id)
    assert payload["request_id"] == response.headers["X-Request-ID"]
    assert payload["catalog_snapshot_id"] == compute_catalog_snapshot_id(get_capability_catalog())
    for boundary_field in (
        "provider_call",
        "actor_run",
        "browser_run",
        "llm_call",
        "workflow_run_created",
        "database_write",
        "execution_authorized",
    ):
        assert payload[boundary_field] is False

    assert len(logger.info_events) == 1
    event, fields = logger.info_events[0]
    assert event == "workflow_plan_preview_generated"
    assert set(fields) == {
        "request_id",
        "project_id",
        "flow_mode",
        "planner_contract_version",
        "catalog_snapshot_id",
        "policy_version",
        "preview_fingerprint",
        "planning_status",
        "route_requirement_count",
        "resolved_count",
        "held_count",
        "duration_ms",
    }
    assert fields["request_id"] == payload["request_id"]
    assert fields["project_id"] == payload["project_id"]
    assert fields["flow_mode"] == payload["flow_mode"]
    assert fields["route_requirement_count"] == len(payload["route_plans"])
    assert isinstance(fields["duration_ms"], (int, float))
    assert cast(float, fields["duration_ms"]) >= 0
    rendered_log = repr((event, fields))
    assert "Acme" not in rendered_log
    assert "youtube.com/watch" not in rendered_log
    assert not any(
        forbidden in key.lower()
        for key in fields
        for forbidden in ("term", "url", "body", "credential", "password", "secret")
    )


@pytest.mark.asyncio
async def test_preview_resolves_one_current_catalog_for_planner_fingerprint(
    planner_context: PlannerTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = get_capability_catalog()
    changed_assertion = base.assertions[0].model_copy(
        update={"support_status": CapabilityStatus.DEPRECATED},
        deep=True,
    )
    overlay = base.model_copy(
        update={"assertions": [changed_assertion, *base.assertions[1:]]},
        deep=True,
    )
    calls = 0

    async def resolve_once(_session: AsyncSession) -> CapabilityCatalog:
        nonlocal calls
        calls += 1
        return overlay

    monkeypatch.setattr(
        workflow_plan_routes,
        "resolve_current_capability_catalog",
        resolve_once,
    )
    response = await planner_context.client.post(
        preview_path(planner_context),
        json=load_periodic_request(),
    )

    assert response.status_code == 200
    assert response.json()["catalog_snapshot_id"] == compute_catalog_snapshot_id(overlay)
    assert calls == 1


@pytest.mark.parametrize(
    ("field_name", "expected_loc"),
    [
        ("project_id", ["body", "project_id"]),
        ("scope_key", ["body", "scopes", 0, "scope_key"]),
    ],
)
@pytest.mark.asyncio
async def test_preview_rejects_server_owned_body_fields(
    planner_context: PlannerTestContext,
    field_name: str,
    expected_loc: list[str | int],
) -> None:
    payload = load_periodic_request()
    if field_name == "project_id":
        payload[field_name] = str(planner_context.active_project.id)
    else:
        scopes = cast(list[dict[str, object]], payload["scopes"])
        scopes[0][field_name] = "sha256:" + ("a" * 64)

    response = await planner_context.client.post(
        preview_path(planner_context),
        json=payload,
    )

    assert response.status_code == 422
    assert any(issue["loc"] == expected_loc for issue in response.json()["detail"])


@pytest.mark.asyncio
async def test_periodic_platformless_youtu_be_seed_derives_youtube(
    planner_context: PlannerTestContext,
) -> None:
    payload = load_periodic_request()
    scopes = cast(list[dict[str, object]], payload["scopes"])
    payload["default_platforms"] = []
    payload["scopes"] = [scopes[0]]
    scopes[0]["platforms"] = []
    scopes[0]["seed_urls"] = ["https://youtu.be/demo"]

    response = await planner_context.client.post(
        preview_path(planner_context),
        json=payload,
    )

    assert response.status_code == 200
    assert response.json()["planning_status"] == "held"
    assert response.json()["normalized_input"]["scopes"][0]["effective_platforms"] == ["youtube"]


@pytest.mark.asyncio
async def test_periodic_unclassified_seed_returns_exact_input_issues(
    planner_context: PlannerTestContext,
) -> None:
    payload = load_periodic_request()
    scopes = cast(list[dict[str, object]], payload["scopes"])
    payload["default_platforms"] = []
    payload["scopes"] = [scopes[0]]
    scopes[0]["platforms"] = []
    scopes[0]["seed_urls"] = ["https://example.com/demo"]

    response = await planner_context.client.post(
        preview_path(planner_context),
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == [
        {
            "loc": ["body", "scopes", 0, "platforms"],
            "msg": "periodic_effective_platform_required",
            "type": "value_error",
        }
    ]
    assert response.headers["X-Request-ID"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_type", "expected_detail"),
    [
        (CapabilityCatalogLoadError, "capability_catalog_load_failed"),
        (
            WorkflowPlannerDependencyUnavailableError,
            "workflow_planner_dependency_unavailable",
        ),
    ],
)
async def test_preview_maps_dependency_failures_to_503(
    planner_context: PlannerTestContext,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
    expected_detail: str,
) -> None:
    if error_type is CapabilityCatalogLoadError:

        async def fail_catalog(_session: AsyncSession) -> CapabilityCatalog:
            raise CapabilityCatalogLoadError

        monkeypatch.setattr(
            workflow_plan_routes,
            "resolve_current_capability_catalog",
            fail_catalog,
        )
    else:

        def fail_planner(**_kwargs: object) -> object:
            raise WorkflowPlannerDependencyUnavailableError

        monkeypatch.setattr(
            workflow_plan_routes,
            "build_workflow_plan_preview",
            fail_planner,
        )

    response = await planner_context.client.post(
        preview_path(planner_context),
        json=load_periodic_request(),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == expected_detail
    assert response.headers["X-Request-ID"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_detail"),
    [
        (
            WorkflowPlannerTopologyError(),
            "workflow_planner_invalid_step_graph",
        ),
        (RuntimeError("raw Acme https://example.com secret"), "workflow_planner_internal_error"),
    ],
)
async def test_preview_maps_internal_failures_to_stable_500(
    planner_context: PlannerTestContext,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected_detail: str,
) -> None:
    logger = RecordingLogger(info_events=[], exception_events=[])
    monkeypatch.setattr(workflow_plan_routes, "logger", logger, raising=False)

    def fail_planner(**_kwargs: object) -> object:
        raise error

    monkeypatch.setattr(
        workflow_plan_routes,
        "build_workflow_plan_preview",
        fail_planner,
    )

    response = await planner_context.client.post(
        preview_path(planner_context),
        json=load_periodic_request(),
    )

    assert response.status_code == 500
    assert response.json()["detail"] == expected_detail
    assert response.headers["X-Request-ID"]
    assert len(logger.exception_events) == 1
    event, fields = logger.exception_events[0]
    assert event == "workflow_plan_preview_failed"
    assert set(fields) == {
        "request_id",
        "project_id",
        "flow_mode",
        "error_type",
        "exc_info",
    }
    assert fields["request_id"] == response.headers["X-Request-ID"]
    assert fields["project_id"] == str(planner_context.active_project.id)
    assert fields["flow_mode"] == "periodic_monitoring"
    assert fields["error_type"] == type(error).__name__
    sanitized_exc_info = cast(
        tuple[type[BaseException], BaseException, object],
        fields["exc_info"],
    )
    assert sanitized_exc_info[0] is RuntimeError
    assert isinstance(sanitized_exc_info[1], RuntimeError)
    assert sanitized_exc_info[1] is not error
    assert str(sanitized_exc_info[1]) == type(error).__name__
    assert sanitized_exc_info[2] is error.__traceback__
    assert "Acme" not in repr((event, fields))
    assert "example.com" not in repr((event, fields))


@pytest.mark.asyncio
async def test_internal_failure_real_renderer_redacts_exception_value(
    planner_context: PlannerTestContext,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    private_marker = "raw Acme https://example.com secret=topsecret"

    def fail_planner(**_kwargs: object) -> object:
        raise RuntimeError(private_marker)

    monkeypatch.setattr(
        workflow_plan_routes,
        "build_workflow_plan_preview",
        fail_planner,
    )
    capsys.readouterr()

    response = await planner_context.client.post(
        preview_path(planner_context),
        json=load_periodic_request(),
    )
    captured = capsys.readouterr()
    rendered = f"{captured.out}\n{captured.err}"

    assert response.status_code == 500
    assert response.json()["detail"] == "workflow_planner_internal_error"
    assert response.headers["X-Request-ID"]
    assert "workflow_plan_preview_failed" in rendered
    assert "RuntimeError" in rendered
    assert private_marker not in rendered
    assert "example.com" not in rendered
    assert "topsecret" not in rendered


@pytest.mark.asyncio
async def test_preview_is_write_free_across_every_mapped_table(
    planner_context: PlannerTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before_counts = await count_all_tables(planner_context.session_factory)

    def fail_sync_session_write(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("preview_session_write_forbidden")

    async def fail_async_session_write(
        *_args: object,
        **_kwargs: object,
    ) -> NoReturn:
        raise AssertionError("preview_session_write_forbidden")

    monkeypatch.setattr(AsyncSession, "add", fail_sync_session_write)
    monkeypatch.setattr(AsyncSession, "add_all", fail_sync_session_write)
    monkeypatch.setattr(AsyncSession, "flush", fail_async_session_write)
    monkeypatch.setattr(AsyncSession, "commit", fail_async_session_write)
    monkeypatch.setattr(AsyncSession, "delete", fail_async_session_write)

    response, statements = await request_with_sql_capture(
        planner_context,
        equivalent_scope_payload(1),
    )
    after_counts = await count_all_tables(planner_context.session_factory)

    assert response.status_code == 200
    assert before_counts == after_counts
    assert all(
        statement.split(maxsplit=1)[0]
        not in {"INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"}
        for statement in statements
        if statement
    )
    select_count = sum(statement.startswith("SELECT") for statement in statements)
    print(
        "preview_zero_write_table_count="
        f"{len(before_counts)} captured_statement_count={len(statements)} "
        f"select_count={select_count} write_count=0"
    )


@pytest.mark.asyncio
async def test_scope_expansion_adds_no_database_selects(
    planner_context: PlannerTestContext,
) -> None:
    one_response, one_statements = await request_with_sql_capture(
        planner_context,
        equivalent_scope_payload(1),
    )
    twenty_response, twenty_statements = await request_with_sql_capture(
        planner_context,
        equivalent_scope_payload(20),
    )

    assert one_response.status_code == 200
    assert twenty_response.status_code == 200
    one_select_count = sum(statement.startswith("SELECT") for statement in one_statements)
    twenty_select_count = sum(statement.startswith("SELECT") for statement in twenty_statements)
    assert one_select_count == twenty_select_count
    assert (
        one_response.json()["preview_fingerprint"] == twenty_response.json()["preview_fingerprint"]
    )
    print(
        f"preview_select_count_one_scope={one_select_count} "
        f"preview_select_count_twenty_scopes={twenty_select_count}"
    )


def test_pure_planner_signature_has_no_session_parameter() -> None:
    parameters = inspect.signature(build_workflow_plan_preview).parameters

    assert "session" not in parameters
    assert all("session" not in name.casefold() for name in parameters)
