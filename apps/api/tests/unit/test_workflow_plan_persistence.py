from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncSessionTransaction,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.capability_governance import CapabilityCatalogHead
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workflow_plan import (
    MonitoringScope,
    QueryTerm,
    WorkflowPlan,
    WorkflowPlanSaveRequest,
    WorkflowVersion,
    WorkflowVersionScope,
)
from data_intelligence_hub.models.workflow_scope_template import MonitoringScopeTemplate
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityCatalog,
    CapabilityStatus,
)
from data_intelligence_hub.schemas.workflow_plan_persistence import (
    MonitoringScopeTemplateCopyRequest,
    MonitoringScopeTemplateCopyResponse,
    WorkflowPlanCloneRequest,
    WorkflowPlanCloneResponse,
    WorkflowPlanCreateRequest,
    WorkflowPlanSaveResponse,
    WorkflowPlanTransitionRequest,
    WorkflowPlanTransitionResponse,
    WorkflowVersionCreateRequest,
)
from data_intelligence_hub.schemas.workflow_planner import (
    PlanningInput,
    PlanningStatus,
)
from data_intelligence_hub.services.capability_catalog import get_capability_catalog
from data_intelligence_hub.services.exceptions import (
    MonitoringScopeNotFoundError,
    ProjectNotActiveError,
    ProjectNotFoundError,
    WorkflowPlanFlowModeConflictError,
    WorkflowPlanIdempotencyConflictError,
    WorkflowPlanInvalidTransitionError,
    WorkflowPlanNotFoundError,
    WorkflowPlanPersistenceTransactionStateError,
    WorkflowPlanPreviewStaleError,
    WorkflowPlanScopeConflictError,
    WorkflowPlanStatusConflictError,
    WorkflowPlanVersionConflictError,
    WorkflowVersionNotFoundError,
)
from data_intelligence_hub.services.workflow_planner import persistence
from data_intelligence_hub.services.workflow_planner.persistence import (
    clone_workflow_plan,
    compare_workflow_plan_versions,
    create_workflow_plan,
    create_workflow_version,
    get_workflow_plan_detail,
    get_workflow_version_detail,
    list_monitoring_scopes_for_project,
    list_workflow_plan_versions,
    list_workflow_plans_for_project,
    transition_workflow_plan_status,
)
from data_intelligence_hub.services.workflow_planner.planner import (
    WorkflowPlanBuildResult,
    build_workflow_plan_result,
)
from data_intelligence_hub.services.workflow_planner.scope_templates import (
    copy_monitoring_scope_template,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "workflow_planner"
PERIODIC_FIXTURE = FIXTURE_DIR / "periodic_monitoring_request_v1.json"
BATCH_FIXTURE = FIXTURE_DIR / "batch_research_request_v1.json"
NOW = datetime(2026, 7, 13, 9, 30, tzinfo=UTC)
RAW_KEY = "logical-save-key-0001"


class _TrackingAsyncSession(AsyncSession):
    explicit_begin_count: int = 0
    commit_count: int = 0
    rollback_count: int = 0

    def begin(self) -> AsyncSessionTransaction:
        self.explicit_begin_count += 1
        return super().begin()

    async def commit(self) -> None:
        self.commit_count += 1
        await super().commit()

    async def rollback(self) -> None:
        self.rollback_count += 1
        await super().rollback()


@dataclass(frozen=True)
class _DatabaseContext:
    session: _TrackingAsyncSession
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID


def _planning_input() -> PlanningInput:
    payload = cast(
        dict[str, object],
        json.loads(PERIODIC_FIXTURE.read_text(encoding="utf-8")),
    )
    return PlanningInput.model_validate(payload)


def _batch_input() -> PlanningInput:
    payload = cast(
        dict[str, object],
        json.loads(BATCH_FIXTURE.read_text(encoding="utf-8")),
    )
    return PlanningInput.model_validate(payload)


def _periodic_input_with_scope_overrides() -> PlanningInput:
    payload = _planning_input().model_dump(mode="json")
    first_scope = cast(dict[str, object], payload["scopes"][0])
    first_scope.update(
        {
            "seed_urls": [],
            "languages": ["fr"],
            "regions": ["CA"],
            "platforms": ["reddit"],
        }
    )
    return PlanningInput.model_validate(payload)


def _periodic_input_with_duplicate_scope() -> PlanningInput:
    payload = _planning_input().model_dump(mode="json")
    retained_scope = cast(dict[str, object], payload["scopes"][0])
    duplicate_scope = {**retained_scope, "scope_ref": "scope-duplicate"}
    payload["scopes"] = [retained_scope, duplicate_scope]
    return PlanningInput.model_validate(payload)


def _changed_input(label: str) -> PlanningInput:
    planning_input = _planning_input()
    return planning_input.model_copy(
        update={"required_fields": [*planning_input.required_fields, label]},
        deep=True,
    )


def _catalog() -> CapabilityCatalog:
    return get_capability_catalog()


def _build(project_id: uuid.UUID) -> WorkflowPlanBuildResult:
    return build_workflow_plan_result(
        project_id=project_id,
        planning_input=_planning_input(),
        catalog=_catalog(),
        generated_at=NOW,
        request_id="persistence-test-preview",
    )


def _create_request(
    project_id: uuid.UUID,
    *,
    planning_input: PlanningInput | None = None,
    fingerprint: str | None = None,
) -> WorkflowPlanCreateRequest:
    effective_input = planning_input or _planning_input()
    result = build_workflow_plan_result(
        project_id=project_id,
        planning_input=effective_input,
        catalog=_catalog(),
        generated_at=NOW,
        request_id="persistence-test-preview",
    )
    return WorkflowPlanCreateRequest(
        name="  Competitor monitoring  ",
        preview_input=effective_input,
        expected_preview_fingerprint=fingerprint or result.preview.preview_fingerprint,
    )


def _version_request(
    project_id: uuid.UUID,
    *,
    current_version_id: uuid.UUID,
    planning_input: PlanningInput,
) -> WorkflowVersionCreateRequest:
    result = build_workflow_plan_result(
        project_id=project_id,
        planning_input=planning_input,
        catalog=_catalog(),
        generated_at=NOW,
        request_id="version-request-preview",
    )
    return WorkflowVersionCreateRequest(
        preview_input=planning_input,
        expected_preview_fingerprint=result.preview.preview_fingerprint,
        expected_current_version_id=current_version_id,
    )


async def _count(session: AsyncSession, model: type[Any]) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _sqlite_scope_insert(
    session: AsyncSession,
    values: Mapping[str, Any],
) -> uuid.UUID | None:
    existing = (
        await session.execute(
            select(MonitoringScope).where(
                MonitoringScope.project_id == values["project_id"],
                MonitoringScope.scope_key == values["scope_key"],
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return None
    scope = MonitoringScope(**values)
    session.add(scope)
    await session.flush()
    return scope.id


@pytest_asyncio.fixture()
async def database(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[_DatabaseContext]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(
        engine,
        class_=_TrackingAsyncSession,
        expire_on_commit=False,
    )
    async with factory() as session:
        user_id = uuid.uuid4()
        workspace_id = uuid.uuid4()
        project_id = uuid.uuid4()
        session.add_all(
            [
                User(
                    id=user_id,
                    email=f"persistence-{user_id}@example.com",
                    password_hash="not-a-real-secret",
                    name="Persistence User",
                    status="active",
                ),
                Workspace(
                    id=workspace_id,
                    name="Persistence Workspace",
                    slug=f"persistence-{workspace_id}",
                    owner_id=user_id,
                ),
                WorkspaceMember(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    role="member",
                ),
                Project(
                    id=project_id,
                    workspace_id=workspace_id,
                    owner_id=user_id,
                    name="Persistence Project",
                    description=None,
                    domain="social",
                    status="active",
                ),
                CapabilityCatalogHead(
                    singleton_key="global",
                    current_revision_id=None,
                    head_version=0,
                ),
            ]
        )
        await session.commit()
        session.explicit_begin_count = 0
        session.commit_count = 0
        session.rollback_count = 0
        monkeypatch.setattr(
            persistence,
            "insert_monitoring_scope_on_conflict",
            _sqlite_scope_insert,
        )
        yield _DatabaseContext(
            session=session,
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
    await engine.dispose()


async def _create(
    database: _DatabaseContext,
    *,
    payload: WorkflowPlanCreateRequest | None = None,
    idempotency_key: str = RAW_KEY,
    generated_at: datetime = NOW,
) -> WorkflowPlanSaveResponse:
    return await create_workflow_plan(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        created_by_user_id=database.user_id,
        payload=payload or _create_request(database.project_id),
        idempotency_key=idempotency_key,
        request_id="save-request-id",
        generated_at=generated_at,
    )


async def _create_version(
    database: _DatabaseContext,
    *,
    plan_id: uuid.UUID,
    payload: WorkflowVersionCreateRequest,
    idempotency_key: str,
    generated_at: datetime = NOW + timedelta(minutes=1),
) -> WorkflowPlanSaveResponse:
    return await create_workflow_version(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        workflow_plan_id=plan_id,
        created_by_user_id=database.user_id,
        payload=payload,
        idempotency_key=idempotency_key,
        request_id=f"save-{idempotency_key}",
        generated_at=generated_at,
    )


async def _transition(
    database: _DatabaseContext,
    *,
    expected_status: str,
    to_status: str,
    reason: str | None = None,
    generated_at: datetime = NOW + timedelta(minutes=4),
) -> WorkflowPlanTransitionResponse:
    plan = (
        await database.session.execute(
            select(WorkflowPlan).where(WorkflowPlan.project_id == database.project_id)
        )
    ).scalar_one()
    return await transition_workflow_plan_status(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        workflow_plan_id=plan.id,
        created_by_user_id=database.user_id,
        payload=WorkflowPlanTransitionRequest(
            expected_status=expected_status,
            to_status=to_status,
            reason=reason,
        ),
        request_id="status-transition-test",
        generated_at=generated_at,
    )


async def _clone(
    database: _DatabaseContext,
    *,
    source_plan_id: uuid.UUID,
    source_version_id: uuid.UUID,
    name: str = "Cloned competitor monitoring",
    idempotency_key: str = "plan-clone-key-0001",
    generated_at: datetime = NOW + timedelta(minutes=2),
) -> WorkflowPlanCloneResponse:
    return await clone_workflow_plan(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        workflow_plan_id=source_plan_id,
        created_by_user_id=database.user_id,
        payload=WorkflowPlanCloneRequest(
            name=name,
            source_version_id=source_version_id,
        ),
        idempotency_key=idempotency_key,
        request_id=f"clone-{idempotency_key}",
        generated_at=generated_at,
    )


async def _copy_scope_template(
    database: _DatabaseContext,
    *,
    scope_id: uuid.UUID,
    source_version_id: uuid.UUID,
    idempotency_key: str = "scope-template-copy-0001",
    generated_at: datetime = NOW + timedelta(minutes=3),
) -> MonitoringScopeTemplateCopyResponse:
    return await copy_monitoring_scope_template(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        scope_id=scope_id,
        created_by_user_id=database.user_id,
        payload=MonitoringScopeTemplateCopyRequest(source_version_id=source_version_id),
        idempotency_key=idempotency_key,
        request_id=f"scope-copy-{idempotency_key}",
        generated_at=generated_at,
    )


@pytest.mark.asyncio
async def test_create_recomputes_and_saves_v1_inside_one_explicit_transaction(
    database: _DatabaseContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = database.session
    await session.execute(select(Project).where(Project.id == database.project_id))
    assert session.in_transaction()

    original_lookup = cast(
        Callable[
            [AsyncSession, uuid.UUID, uuid.UUID, str, str],
            Awaitable[WorkflowPlanSaveRequest | None],
        ],
        persistence.get_workflow_plan_save_request,  # type: ignore[attr-defined]
    )
    first_query_states: list[tuple[int, int, bool]] = []

    async def tracked_lookup(
        lookup_session: AsyncSession,
        workspace_id: uuid.UUID,
        created_by_user_id: uuid.UUID,
        idempotency_scope: str,
        idempotency_key_hash: str,
    ) -> WorkflowPlanSaveRequest | None:
        first_query_states.append(
            (
                session.explicit_begin_count,
                session.rollback_count,
                session.in_transaction(),
            )
        )
        return await original_lookup(
            lookup_session,
            workspace_id,
            created_by_user_id,
            idempotency_scope,
            idempotency_key_hash,
        )

    original_builder = cast(
        Callable[..., WorkflowPlanBuildResult],
        persistence.build_workflow_plan_result,  # type: ignore[attr-defined]
    )
    build_inputs: list[PlanningInput] = []

    def tracked_builder(**kwargs: Any) -> WorkflowPlanBuildResult:
        build_inputs.append(cast(PlanningInput, kwargs["planning_input"]))
        return original_builder(**kwargs)

    monkeypatch.setattr(
        persistence,
        "get_workflow_plan_save_request",
        tracked_lookup,
    )
    monkeypatch.setattr(persistence, "build_workflow_plan_result", tracked_builder)

    response = await _create(database)

    assert first_query_states[0] == (1, 1, True)
    assert session.explicit_begin_count == 1
    assert session.rollback_count == 1
    assert build_inputs == [_planning_input()]
    assert response.database_write is True
    assert response.plan_changed is True
    assert response.outcome == "created"
    assert response.idempotent_replay is False
    assert response.plan.name == "Competitor monitoring"
    assert response.plan.flow_mode == "periodic_monitoring"
    assert response.plan.status == "previewed"
    assert response.plan.current_version_number == 1
    assert response.version.version_number == 1
    assert response.version.editable_input.flow_mode == "periodic_monitoring"
    assert response.version.editable_input.default_languages == ["en"]
    assert response.version.editable_input.default_regions == ["us"]
    assert response.version.editable_input.default_platforms == ["youtube"]
    assert response.version.preview.database_write is False
    assert response.provider_call is False
    assert response.actor_run is False
    assert response.browser_run is False
    assert response.llm_call is False
    assert response.workflow_run_created is False

    plan = (await session.execute(select(WorkflowPlan))).scalar_one()
    version = (await session.execute(select(WorkflowVersion))).scalar_one()
    save_request = (await session.execute(select(WorkflowPlanSaveRequest))).scalar_one()
    associations = list((await session.execute(select(WorkflowVersionScope))).scalars())
    terms = list((await session.execute(select(QueryTerm))).scalars())
    associated_scope_ids = {association.monitoring_scope_id for association in associations}

    assert plan.current_version_id == version.id == response.version.id
    assert plan.updated_at == response.plan.updated_at
    assert version.preview_fingerprint == response.version.preview_fingerprint
    assert version.plan_payload == response.version.preview.model_dump(mode="json")
    assert len(associations) == len(response.version.preview.normalized_input.scopes)
    assert len(terms) == len(response.version.preview.query_terms)
    assert all(term.matched_scope_id in associated_scope_ids for term in terms)
    assert save_request.idempotency_key_hash.startswith("sha256:")
    assert save_request.idempotency_key_hash != RAW_KEY
    assert RAW_KEY not in save_request.idempotency_scope
    assert RAW_KEY not in save_request.request_hash
    assert RAW_KEY not in json.dumps(save_request.response_payload, sort_keys=True)
    serialized = response.model_dump(mode="json")
    assert "fingerprint_payload" not in serialized["version"]
    assert "fingerprint_input" not in serialized["version"]


@pytest.mark.asyncio
async def test_plan_status_transition_changes_only_lifecycle_and_supports_noop(
    database: _DatabaseContext,
) -> None:
    saved = await _create(database)
    before_version = (
        await database.session.execute(
            select(WorkflowVersion).where(WorkflowVersion.id == saved.version.id)
        )
    ).scalar_one()
    before_payload = dict(before_version.plan_payload)
    before_current_version_id = saved.plan.current_version_id

    approved = await _transition(
        database,
        expected_status="previewed",
        to_status="approved",
        reason=" owner reviewed the frozen plan ",
    )
    assert approved.database_write is True
    assert approved.plan_changed is True
    assert approved.from_status == "previewed"
    assert approved.to_status == "approved"
    assert approved.reason == "owner reviewed the frozen plan"
    assert approved.plan.status == "approved"

    replay = await _transition(
        database,
        expected_status="approved",
        to_status="approved",
    )
    assert replay.database_write is False
    assert replay.plan_changed is False
    assert replay.from_status == replay.to_status == "approved"

    with pytest.raises(WorkflowPlanStatusConflictError):
        await _transition(
            database,
            expected_status="previewed",
            to_status="active",
        )
    with pytest.raises(WorkflowPlanInvalidTransitionError):
        await _transition(
            database,
            expected_status="approved",
            to_status="paused",
        )

    after_version = (
        await database.session.execute(
            select(WorkflowVersion).where(WorkflowVersion.id == saved.version.id)
        )
    ).scalar_one()
    plan = (
        await database.session.execute(
            select(WorkflowPlan).where(WorkflowPlan.id == saved.plan.id)
        )
    ).scalar_one()
    assert after_version.plan_payload == before_payload
    assert plan.current_version_id == before_current_version_id
    assert plan.status == "approved"


@pytest.mark.asyncio
async def test_plan_status_transition_allows_pause_resume_and_archive(
    database: _DatabaseContext,
) -> None:
    saved = await _create(database)
    for expected, target in (
        ("previewed", "approved"),
        ("approved", "active"),
        ("active", "paused"),
        ("paused", "active"),
        ("active", "paused"),
        ("paused", "archived"),
    ):
        result = await _transition(
            database,
            expected_status=expected,
            to_status=target,
        )
        assert result.plan.status == target

    assert saved.version.id == (
        await database.session.execute(select(WorkflowVersion.id))
    ).scalar_one()


@pytest.mark.asyncio
async def test_plan_status_transition_locks_project_before_plan(
    database: _DatabaseContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _create(database)
    events: list[str] = []
    original_project_lock = persistence.lock_project_for_workflow_plan_save  # type: ignore[attr-defined]
    original_plan_lock = persistence.get_workflow_plan_for_update  # type: ignore[attr-defined]

    async def tracked_project_lock(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> Project | None:
        events.append("project")
        return await original_project_lock(session, workspace_id, project_id)

    async def tracked_plan_lock(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        workflow_plan_id: uuid.UUID,
    ) -> WorkflowPlan | None:
        events.append("plan")
        return await original_plan_lock(
            session,
            workspace_id,
            project_id,
            workflow_plan_id,
        )

    monkeypatch.setattr(
        persistence,
        "lock_project_for_workflow_plan_save",
        tracked_project_lock,
    )
    monkeypatch.setattr(
        persistence,
        "get_workflow_plan_for_update",
        tracked_plan_lock,
    )

    await _transition(
        database,
        expected_status="previewed",
        to_status="approved",
    )

    assert events == ["project", "plan"]


@pytest.mark.asyncio
async def test_clone_creates_independent_plan_and_preserves_frozen_source_graph(
    database: _DatabaseContext,
) -> None:
    source = await _create(database)

    cloned = await _clone(
        database,
        source_plan_id=source.plan.id,
        source_version_id=source.version.id,
    )

    assert cloned.database_write is True
    assert cloned.plan_changed is True
    assert cloned.idempotent_replay is False
    assert cloned.source_plan_id == source.plan.id
    assert cloned.source_version_id == source.version.id
    assert cloned.plan.id != source.plan.id
    assert cloned.version.id != source.version.id
    assert cloned.plan.current_version_id == cloned.version.id
    assert cloned.plan.source_plan_id == source.plan.id
    assert cloned.plan.source_version_id == source.version.id
    assert cloned.version.workflow_plan_id == cloned.plan.id
    assert cloned.version.preview_fingerprint == source.version.preview_fingerprint
    assert cloned.version.preview == source.version.preview
    assert cloned.version.editable_input == source.version.editable_input

    source_plan = (
        await database.session.execute(
            select(WorkflowPlan).where(WorkflowPlan.id == source.plan.id)
        )
    ).scalar_one()
    target_plan = (
        await database.session.execute(
            select(WorkflowPlan).where(WorkflowPlan.id == cloned.plan.id)
        )
    ).scalar_one()
    assert source_plan.current_version_id == source.version.id
    assert source_plan.source_workflow_plan_id is None
    assert target_plan.current_version_id == cloned.version.id
    assert target_plan.source_workflow_plan_id == source.plan.id
    assert target_plan.source_workflow_version_id == source.version.id
    assert await _count(database.session, WorkflowPlan) == 2
    assert await _count(database.session, WorkflowVersion) == 2
    assert await _count(database.session, WorkflowVersionScope) == (
        2 * len(source.version.preview.normalized_input.scopes)
    )
    assert await _count(database.session, QueryTerm) == 2 * len(source.version.preview.query_terms)
    assert await _count(database.session, WorkflowPlanSaveRequest) == 2


@pytest.mark.asyncio
async def test_clone_replay_is_write_free_and_same_key_conflict_fails_closed(
    database: _DatabaseContext,
) -> None:
    source = await _create(database)
    first = await _clone(
        database,
        source_plan_id=source.plan.id,
        source_version_id=source.version.id,
        idempotency_key="plan-clone-replay-0001",
    )

    replay = await _clone(
        database,
        source_plan_id=source.plan.id,
        source_version_id=source.version.id,
        idempotency_key="plan-clone-replay-0001",
    )

    assert replay.idempotent_replay is True
    assert replay.database_write is False
    assert replay.plan_changed is False
    assert replay.plan == first.plan
    assert replay.version == first.version
    assert await _count(database.session, WorkflowPlan) == 2
    assert await _count(database.session, WorkflowPlanSaveRequest) == 2

    with pytest.raises(WorkflowPlanIdempotencyConflictError):
        await _clone(
            database,
            source_plan_id=source.plan.id,
            source_version_id=source.version.id,
            name="Different clone name",
            idempotency_key="plan-clone-replay-0001",
        )
    assert await _count(database.session, WorkflowPlan) == 2


@pytest.mark.asyncio
async def test_clone_rejects_version_from_another_plan_without_writes(
    database: _DatabaseContext,
) -> None:
    source = await _create(database)
    other = await _create(
        database,
        payload=_create_request(
            database.project_id,
            planning_input=_batch_input(),
        ),
        idempotency_key="other-plan-0001",
    )

    with pytest.raises(WorkflowVersionNotFoundError):
        await _clone(
            database,
            source_plan_id=source.plan.id,
            source_version_id=other.version.id,
            idempotency_key="plan-clone-wrong-version-0001",
        )
    assert await _count(database.session, WorkflowPlan) == 2
    assert await _count(database.session, WorkflowVersion) == 2
    assert await _count(database.session, WorkflowPlanSaveRequest) == 2


@pytest.mark.asyncio
async def test_scope_template_copy_creates_new_draft_identity_and_keeps_canonical_scope(
    database: _DatabaseContext,
) -> None:
    source = await _create(database)
    scope = (await database.session.execute(select(MonitoringScope))).scalars().first()
    assert scope is not None
    scope_id = scope.id

    copied = await _copy_scope_template(
        database,
        scope_id=scope_id,
        source_version_id=source.version.id,
    )

    assert copied.database_write is True
    assert copied.idempotent_replay is False
    assert copied.template.id != scope.id
    assert copied.template.source_scope_id == scope.id
    assert copied.template.source_plan_id == source.plan.id
    assert copied.template.source_version_id == source.version.id
    assert copied.template.scope_key == scope.scope_key
    assert copied.template.canonical_term == scope.canonical_term
    assert copied.template.aliases == scope.aliases
    assert await _count(database.session, MonitoringScope) == len(
        source.version.preview.normalized_input.scopes
    )
    assert await _count(database.session, MonitoringScopeTemplate) == 1


@pytest.mark.asyncio
async def test_scope_template_copy_replay_is_write_free_and_wrong_version_fails(
    database: _DatabaseContext,
) -> None:
    source = await _create(database)
    scope = (await database.session.execute(select(MonitoringScope))).scalars().first()
    assert scope is not None
    scope_id = scope.id

    first = await _copy_scope_template(
        database,
        scope_id=scope_id,
        source_version_id=source.version.id,
        idempotency_key="scope-template-replay-0001",
    )
    replay = await _copy_scope_template(
        database,
        scope_id=scope_id,
        source_version_id=source.version.id,
        idempotency_key="scope-template-replay-0001",
    )
    assert replay.idempotent_replay is True
    assert replay.database_write is False
    assert replay.template == first.template
    assert await _count(database.session, MonitoringScopeTemplate) == 1

    other = await _create(
        database,
        payload=_create_request(database.project_id, planning_input=_batch_input()),
        idempotency_key="scope-template-other-plan-0001",
    )
    with pytest.raises(MonitoringScopeNotFoundError):
        await _copy_scope_template(
            database,
            scope_id=scope_id,
            source_version_id=other.version.id,
            idempotency_key="scope-template-wrong-version-0001",
        )
    assert await _count(database.session, MonitoringScopeTemplate) == 1


@pytest.mark.asyncio
async def test_scope_template_copy_same_key_different_source_version_conflicts(
    database: _DatabaseContext,
) -> None:
    source = await _create(database)
    scope = (await database.session.execute(select(MonitoringScope))).scalars().first()
    assert scope is not None
    second = await _create_version(
        database,
        plan_id=source.plan.id,
        payload=_version_request(
            database.project_id,
            current_version_id=source.version.id,
            planning_input=_changed_input("comments"),
        ),
        idempotency_key="scope-template-source-version-0001",
    )

    await _copy_scope_template(
        database,
        scope_id=scope.id,
        source_version_id=source.version.id,
        idempotency_key="scope-template-cross-version-0001",
    )

    with pytest.raises(WorkflowPlanIdempotencyConflictError):
        await _copy_scope_template(
            database,
            scope_id=scope.id,
            source_version_id=second.version.id,
            idempotency_key="scope-template-cross-version-0001",
        )

    assert await _count(database.session, MonitoringScopeTemplate) == 1


@pytest.mark.asyncio
async def test_create_rebuilds_defaults_and_scope_overrides_from_fingerprint(
    database: _DatabaseContext,
) -> None:
    planning_input = _periodic_input_with_scope_overrides()

    response = await _create(
        database,
        payload=_create_request(database.project_id, planning_input=planning_input),
    )

    editable_input = response.version.editable_input
    assert editable_input.default_languages == ["en"]
    assert editable_input.default_regions == ["us"]
    assert editable_input.default_platforms == ["youtube"]
    assert editable_input.schedule_intent is not None
    assert editable_input.schedule_intent.cadence == "daily"
    assert editable_input.schedule_intent.timezone == "utc"
    overridden_scope = next(
        scope for scope in editable_input.scopes if scope.canonical_term == "acme"
    )
    assert overridden_scope.languages == ["fr"]
    assert overridden_scope.regions == ["ca"]
    assert overridden_scope.platforms == ["reddit"]
    rebuilt = build_workflow_plan_result(
        project_id=database.project_id,
        planning_input=editable_input,
        catalog=_catalog(),
        generated_at=NOW,
        request_id="rebuilt-editable-input",
    )
    assert rebuilt.preview.preview_fingerprint == response.version.preview_fingerprint


@pytest.mark.asyncio
async def test_create_rebuilds_batch_without_schedule_intent(
    database: _DatabaseContext,
) -> None:
    payload = _create_request(database.project_id, planning_input=_batch_input())
    response = await _create(
        database,
        payload=payload,
    )

    editable_input = response.version.editable_input
    assert editable_input.flow_mode == "batch_research"
    assert editable_input.schedule_intent is None
    assert "schedule_intent" not in editable_input.model_fields_set
    serialized_editable_input = response.model_dump(mode="json")["version"]["editable_input"]
    assert "schedule_intent" not in serialized_editable_input
    assert serialized_editable_input["budget_ceiling"] is None
    round_trip = WorkflowPlanSaveResponse.model_validate(response.model_dump(mode="json"))
    assert "schedule_intent" not in round_trip.version.editable_input.model_fields_set

    save_request = (await database.session.execute(select(WorkflowPlanSaveRequest))).scalar_one()
    stored_response = WorkflowPlanSaveResponse.model_validate(save_request.response_payload)
    assert "schedule_intent" not in stored_response.version.editable_input.model_fields_set

    replay = await _create(database, payload=payload)
    assert replay.idempotent_replay is True
    assert replay.version.editable_input == response.version.editable_input
    assert "schedule_intent" not in replay.model_dump(mode="json")["version"]["editable_input"]


@pytest.mark.asyncio
async def test_create_rebuilds_collapsed_duplicate_as_one_canonical_scope(
    database: _DatabaseContext,
) -> None:
    response = await _create(
        database,
        payload=_create_request(
            database.project_id,
            planning_input=_periodic_input_with_duplicate_scope(),
        ),
    )

    editable_input = response.version.editable_input
    assert len(response.version.preview.normalized_input.scopes) == 1
    assert len(editable_input.scopes) == 1
    assert editable_input.scopes[0].scope_ref == "scope-1"
    rebuilt = build_workflow_plan_result(
        project_id=database.project_id,
        planning_input=editable_input,
        catalog=_catalog(),
        generated_at=NOW,
        request_id="rebuilt-collapsed-scope",
    )
    assert rebuilt.preview.preview_fingerprint == response.version.preview_fingerprint


@pytest.mark.asyncio
async def test_create_stale_fingerprint_rolls_back_with_zero_business_rows(
    database: _DatabaseContext,
) -> None:
    payload = _create_request(
        database.project_id,
        fingerprint="sha256:" + "0" * 64,
    )

    with pytest.raises(WorkflowPlanPreviewStaleError):
        await _create(database, payload=payload)

    assert database.session.explicit_begin_count == 1
    for model in (
        WorkflowPlan,
        WorkflowVersion,
        MonitoringScope,
        WorkflowVersionScope,
        QueryTerm,
        WorkflowPlanSaveRequest,
    ):
        assert await _count(database.session, model) == 0


@pytest.mark.asyncio
async def test_create_requires_active_project_before_catalog_recompute(
    database: _DatabaseContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = (
        await database.session.execute(select(Project).where(Project.id == database.project_id))
    ).scalar_one()
    project.status = "archived"
    await database.session.commit()

    async def fail_catalog_load(_session: AsyncSession) -> CapabilityCatalog:
        raise AssertionError("catalog must not load for inactive project")

    monkeypatch.setattr(
        persistence,
        "resolve_current_capability_catalog",
        fail_catalog_load,
    )

    with pytest.raises(ProjectNotActiveError):
        await _create(database)

    assert await _count(database.session, WorkflowPlan) == 0
    assert await _count(database.session, WorkflowPlanSaveRequest) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "planning_status",
    [
        PlanningStatus.RESOLVED,
        PlanningStatus.PARTIALLY_RESOLVED,
        PlanningStatus.HELD,
    ],
)
async def test_create_accepts_every_planning_status_including_held(
    database: _DatabaseContext,
    monkeypatch: pytest.MonkeyPatch,
    planning_status: PlanningStatus,
) -> None:
    original_builder = cast(
        Callable[..., WorkflowPlanBuildResult],
        persistence.build_workflow_plan_result,  # type: ignore[attr-defined]
    )

    def build_with_status(**kwargs: Any) -> WorkflowPlanBuildResult:
        result = original_builder(**kwargs)
        return WorkflowPlanBuildResult(
            preview=result.preview.model_copy(
                update={"planning_status": planning_status},
                deep=True,
            ),
            fingerprint_payload=result.fingerprint_payload,
        )

    monkeypatch.setattr(
        persistence,
        "build_workflow_plan_result",
        build_with_status,
    )

    response = await _create(database)

    assert response.plan.planning_status is planning_status
    assert response.version.planning_status is planning_status
    assert response.version.preview.planning_status is planning_status
    assert response.execution_authorized is False


@pytest.mark.asyncio
async def test_completed_replay_short_circuits_project_and_catalog(
    database: _DatabaseContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = await _create(database)
    project = (
        await database.session.execute(select(Project).where(Project.id == database.project_id))
    ).scalar_one()
    project.status = "archived"
    await database.session.commit()

    async def fail_project_read(*args: object, **kwargs: object) -> Project:
        raise AssertionError("project must not be read during completed replay")

    async def fail_catalog_load(_session: AsyncSession) -> CapabilityCatalog:
        raise AssertionError("catalog must not load during completed replay")

    monkeypatch.setattr(persistence, "get_project", fail_project_read)
    monkeypatch.setattr(
        persistence,
        "resolve_current_capability_catalog",
        fail_catalog_load,
    )

    replay = await _create(database)

    assert replay.database_write is False
    assert replay.plan_changed is False
    assert replay.idempotent_replay is True
    assert replay.outcome == first.outcome
    assert replay.plan == first.plan
    assert replay.version == first.version
    assert replay.version.editable_input == first.version.editable_input
    assert await _count(database.session, WorkflowPlan) == 1
    assert await _count(database.session, WorkflowVersion) == 1
    assert await _count(database.session, WorkflowPlanSaveRequest) == 1


@pytest.mark.asyncio
async def test_existing_pending_session_state_fails_closed_without_rollback(
    database: _DatabaseContext,
) -> None:
    database.session.add(
        User(
            email=f"pending-{uuid.uuid4()}@example.com",
            password_hash="not-a-real-secret",
            name="Pending User",
            status="active",
        )
    )

    with pytest.raises(WorkflowPlanPersistenceTransactionStateError):
        await _create(database)

    assert database.session.explicit_begin_count == 0
    assert database.session.rollback_count == 0
    assert database.session.new


def test_version_request_requires_expected_current_version() -> None:
    planning_input = _planning_input()
    result = _build(uuid.uuid4())

    with pytest.raises(ValidationError):
        WorkflowVersionCreateRequest.model_validate(
            {
                "preview_input": planning_input.model_dump(mode="json"),
                "expected_preview_fingerprint": result.preview.preview_fingerprint,
            }
        )


@pytest.mark.asyncio
async def test_version_locks_project_then_plan_rechecks_key_and_allocates_v2(
    database: _DatabaseContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    v1 = await _create(database)
    payload = _version_request(
        database.project_id,
        current_version_id=v1.version.id,
        planning_input=_changed_input("comments"),
    )
    events: list[str] = []
    original_lookup = cast(
        Callable[
            [AsyncSession, uuid.UUID, uuid.UUID, str, str],
            Awaitable[WorkflowPlanSaveRequest | None],
        ],
        persistence.get_workflow_plan_save_request,  # type: ignore[attr-defined]
    )
    original_project_lock = cast(
        Callable[
            [AsyncSession, uuid.UUID, uuid.UUID],
            Awaitable[Project | None],
        ],
        persistence.lock_project_for_workflow_plan_save,  # type: ignore[attr-defined]
    )
    original_plan_lock = cast(
        Callable[
            [AsyncSession, uuid.UUID, uuid.UUID, uuid.UUID],
            Awaitable[WorkflowPlan | None],
        ],
        persistence.get_workflow_plan_for_update,  # type: ignore[attr-defined]
    )

    async def tracked_lookup(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        created_by_user_id: uuid.UUID,
        idempotency_scope: str,
        idempotency_key_hash: str,
    ) -> WorkflowPlanSaveRequest | None:
        events.append("idempotency")
        return await original_lookup(
            session,
            workspace_id,
            created_by_user_id,
            idempotency_scope,
            idempotency_key_hash,
        )

    async def tracked_project_lock(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> Project | None:
        events.append("project")
        return await original_project_lock(session, workspace_id, project_id)

    async def tracked_plan_lock(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        workflow_plan_id: uuid.UUID,
    ) -> WorkflowPlan | None:
        events.append("plan")
        return await original_plan_lock(
            session,
            workspace_id,
            project_id,
            workflow_plan_id,
        )

    monkeypatch.setattr(
        persistence,
        "get_workflow_plan_save_request",
        tracked_lookup,
    )
    monkeypatch.setattr(
        persistence,
        "lock_project_for_workflow_plan_save",
        tracked_project_lock,
    )
    monkeypatch.setattr(
        persistence,
        "get_workflow_plan_for_update",
        tracked_plan_lock,
    )

    response = await _create_version(
        database,
        plan_id=v1.plan.id,
        payload=payload,
        idempotency_key="version-change-0001",
    )

    assert events == ["idempotency", "project", "idempotency", "plan"]
    assert response.outcome == "created"
    assert response.plan_changed is True
    assert response.version.version_number == 2
    assert response.plan.current_version_id == response.version.id
    saved_plan = (await database.session.execute(select(WorkflowPlan))).scalar_one()
    assert saved_plan.updated_at == response.plan.updated_at
    versions = list(
        (
            await database.session.execute(
                select(WorkflowVersion).order_by(WorkflowVersion.version_number)
            )
        ).scalars()
    )
    assert [version.version_number for version in versions] == [1, 2]


@pytest.mark.asyncio
async def test_version_conflict_has_zero_business_writes(
    database: _DatabaseContext,
) -> None:
    v1 = await _create(database)
    payload = _version_request(
        database.project_id,
        current_version_id=uuid.uuid4(),
        planning_input=_changed_input("comments"),
    )

    with pytest.raises(WorkflowPlanVersionConflictError):
        await _create_version(
            database,
            plan_id=v1.plan.id,
            payload=payload,
            idempotency_key="version-conflict-0001",
        )

    assert await _count(database.session, WorkflowVersion) == 1
    assert await _count(database.session, WorkflowPlanSaveRequest) == 1
    plan = (await database.session.execute(select(WorkflowPlan))).scalar_one()
    assert plan.current_version_id == v1.version.id


@pytest.mark.asyncio
async def test_version_rejects_flow_mode_change_without_writes(
    database: _DatabaseContext,
) -> None:
    v1 = await _create(database)
    payload = _version_request(
        database.project_id,
        current_version_id=v1.version.id,
        planning_input=_batch_input(),
    )

    with pytest.raises(WorkflowPlanFlowModeConflictError):
        await _create_version(
            database,
            plan_id=v1.plan.id,
            payload=payload,
            idempotency_key="mode-conflict-0001",
        )

    assert await _count(database.session, WorkflowVersion) == 1
    assert await _count(database.session, WorkflowPlanSaveRequest) == 1


@pytest.mark.asyncio
async def test_same_current_fingerprint_writes_only_semantic_no_op_request(
    database: _DatabaseContext,
) -> None:
    v1 = await _create(database)
    plan_before = (await database.session.execute(select(WorkflowPlan))).scalar_one()
    updated_at_before = plan_before.updated_at
    scope_count_before = await _count(database.session, MonitoringScope)
    term_count_before = await _count(database.session, QueryTerm)
    payload = _version_request(
        database.project_id,
        current_version_id=v1.version.id,
        planning_input=_planning_input(),
    )

    response = await _create_version(
        database,
        plan_id=v1.plan.id,
        payload=payload,
        idempotency_key="semantic-no-op-0001",
    )

    assert response.database_write is True
    assert response.plan_changed is False
    assert response.outcome == "semantic_no_op"
    assert response.idempotent_replay is False
    assert response.version.id == v1.version.id
    assert response.plan.current_version_id == v1.version.id
    assert await _count(database.session, WorkflowVersion) == 1
    assert await _count(database.session, MonitoringScope) == scope_count_before
    assert await _count(database.session, QueryTerm) == term_count_before
    assert await _count(database.session, WorkflowPlanSaveRequest) == 2
    plan_after = (await database.session.execute(select(WorkflowPlan))).scalar_one()
    assert plan_after.updated_at == updated_at_before


@pytest.mark.asyncio
async def test_a_to_b_to_a_creates_v3_instead_of_reusing_history(
    database: _DatabaseContext,
) -> None:
    v1 = await _create(database)
    b_payload = _version_request(
        database.project_id,
        current_version_id=v1.version.id,
        planning_input=_changed_input("comments"),
    )
    v2 = await _create_version(
        database,
        plan_id=v1.plan.id,
        payload=b_payload,
        idempotency_key="a-to-b-version-0001",
        generated_at=NOW + timedelta(minutes=1),
    )
    a_payload = _version_request(
        database.project_id,
        current_version_id=v2.version.id,
        planning_input=_planning_input(),
    )

    v3 = await _create_version(
        database,
        plan_id=v1.plan.id,
        payload=a_payload,
        idempotency_key="b-to-a-version-0001",
        generated_at=NOW + timedelta(minutes=2),
    )

    assert v3.version.version_number == 3
    assert v3.version.preview_fingerprint == v1.version.preview_fingerprint
    assert v3.version.id != v1.version.id
    assert v2.version.preview_fingerprint != v1.version.preview_fingerprint


@pytest.mark.asyncio
async def test_new_version_uses_current_catalog_and_historical_version_stays_frozen(
    database: _DatabaseContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    v1 = await _create(database)
    base = _catalog()
    changed_assertion = base.assertions[0].model_copy(
        update={"support_status": CapabilityStatus.DEPRECATED},
        deep=True,
    )
    overlay = CapabilityCatalog.model_validate(
        base.model_copy(
            update={"assertions": [changed_assertion, *base.assertions[1:]]},
            deep=True,
        ).model_dump(mode="json")
    )
    planning_input = _changed_input("catalog-overlay")
    expected = build_workflow_plan_result(
        project_id=database.project_id,
        planning_input=planning_input,
        catalog=overlay,
        generated_at=NOW + timedelta(minutes=1),
        request_id="save-catalog-overlay-version-0001",
    )
    resolver_calls = 0

    async def resolve_overlay(_session: AsyncSession) -> CapabilityCatalog:
        nonlocal resolver_calls
        resolver_calls += 1
        return overlay

    monkeypatch.setattr(
        persistence,
        "resolve_current_capability_catalog",
        resolve_overlay,
    )
    v2 = await _create_version(
        database,
        plan_id=v1.plan.id,
        payload=WorkflowVersionCreateRequest(
            preview_input=planning_input,
            expected_preview_fingerprint=expected.preview.preview_fingerprint,
            expected_current_version_id=v1.version.id,
        ),
        idempotency_key="catalog-overlay-version-0001",
    )

    assert resolver_calls == 1
    assert v2.version.catalog_snapshot_id == expected.preview.catalog_snapshot_id
    assert v2.version.catalog_snapshot_id != v1.version.catalog_snapshot_id

    async def fail_current_catalog_resolution(
        _session: AsyncSession,
    ) -> CapabilityCatalog:
        raise AssertionError("historical read must not resolve the current Catalog")

    monkeypatch.setattr(
        persistence,
        "resolve_current_capability_catalog",
        fail_current_catalog_resolution,
    )
    historical = await get_workflow_version_detail(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        plan_id=v1.plan.id,
        version_id=v1.version.id,
    )

    assert historical.version.id == v1.version.id
    assert historical.version.catalog_snapshot_id == v1.version.catalog_snapshot_id
    assert historical.version.preview.catalog_snapshot_id == v1.version.catalog_snapshot_id


@pytest.mark.asyncio
async def test_version_replay_returns_original_snapshot_after_current_advances(
    database: _DatabaseContext,
) -> None:
    v1 = await _create(database)
    b_payload = _version_request(
        database.project_id,
        current_version_id=v1.version.id,
        planning_input=_changed_input("comments"),
    )
    replay_key = "version-replay-0001"
    v2 = await _create_version(
        database,
        plan_id=v1.plan.id,
        payload=b_payload,
        idempotency_key=replay_key,
    )
    c_payload = _version_request(
        database.project_id,
        current_version_id=v2.version.id,
        planning_input=_changed_input("comments-v2"),
    )
    v3 = await _create_version(
        database,
        plan_id=v1.plan.id,
        payload=c_payload,
        idempotency_key="version-advance-0001",
        generated_at=NOW + timedelta(minutes=2),
    )

    replay = await _create_version(
        database,
        plan_id=v1.plan.id,
        payload=b_payload,
        idempotency_key=replay_key,
    )

    assert replay.database_write is False
    assert replay.plan_changed is False
    assert replay.idempotent_replay is True
    assert replay.outcome == v2.outcome
    assert replay.version == v2.version
    assert replay.version.editable_input == v2.version.editable_input
    assert replay.plan == v2.plan
    plan = (await database.session.execute(select(WorkflowPlan))).scalar_one()
    assert plan.current_version_id == v3.version.id

    with pytest.raises(WorkflowPlanIdempotencyConflictError):
        await _create_version(
            database,
            plan_id=v1.plan.id,
            payload=c_payload,
            idempotency_key=replay_key,
        )
    assert await _count(database.session, WorkflowVersion) == 3
    assert await _count(database.session, WorkflowPlanSaveRequest) == 3


@pytest.mark.asyncio
async def test_scope_key_collision_with_different_payload_fails_closed(
    database: _DatabaseContext,
) -> None:
    v1 = await _create(database)
    scope = (
        (
            await database.session.execute(
                select(MonitoringScope).order_by(MonitoringScope.created_at)
            )
        )
        .scalars()
        .first()
    )
    assert scope is not None
    scope.aliases = [*scope.aliases, "corrupted collision payload"]
    await database.session.commit()
    payload = _version_request(
        database.project_id,
        current_version_id=v1.version.id,
        planning_input=_changed_input("comments"),
    )

    with pytest.raises(WorkflowPlanScopeConflictError):
        await _create_version(
            database,
            plan_id=v1.plan.id,
            payload=payload,
            idempotency_key="scope-collision-0001",
        )

    assert await _count(database.session, WorkflowVersion) == 1
    assert await _count(database.session, WorkflowPlanSaveRequest) == 1


class _AsyncpgUniqueViolationError(Exception):
    def __init__(self, constraint_name: str) -> None:
        super().__init__(constraint_name)
        self.constraint_name = constraint_name


class _AsyncpgIntegrityError(Exception):
    def __init__(self, *, sqlstate: str, constraint_name: str) -> None:
        super().__init__(sqlstate)
        self.sqlstate = sqlstate
        self.__cause__ = _AsyncpgUniqueViolationError(constraint_name)


@pytest.mark.asyncio
@pytest.mark.parametrize("conflicting_winner", [False, True])
async def test_final_unique_race_rolls_back_then_replays_or_conflicts(
    database: _DatabaseContext,
    monkeypatch: pytest.MonkeyPatch,
    conflicting_winner: bool,
) -> None:
    v1 = await _create(database)
    payload = _version_request(
        database.project_id,
        current_version_id=v1.version.id,
        planning_input=_changed_input("comments"),
    )
    session = database.session
    session.explicit_begin_count = 0
    captured: list[WorkflowPlanSaveRequest] = []
    recovery_begin_counts: list[int] = []
    race_raised = False
    original_lookup = cast(
        Callable[
            [AsyncSession, uuid.UUID, uuid.UUID, str, str],
            Awaitable[WorkflowPlanSaveRequest | None],
        ],
        persistence.get_workflow_plan_save_request,  # type: ignore[attr-defined]
    )

    async def race_lookup(
        lookup_session: AsyncSession,
        workspace_id: uuid.UUID,
        created_by_user_id: uuid.UUID,
        idempotency_scope: str,
        idempotency_key_hash: str,
    ) -> WorkflowPlanSaveRequest | None:
        if race_raised:
            recovery_begin_counts.append(session.explicit_begin_count)
            winner = captured[0]
            if conflicting_winner:
                winner.request_hash = "sha256:" + "f" * 64
            return winner
        return await original_lookup(
            lookup_session,
            workspace_id,
            created_by_user_id,
            idempotency_scope,
            idempotency_key_hash,
        )

    async def raise_unique_race(
        _session: AsyncSession,
        save_request: WorkflowPlanSaveRequest,
    ) -> WorkflowPlanSaveRequest:
        nonlocal race_raised
        captured.append(save_request)
        race_raised = True
        raise IntegrityError(
            "INSERT workflow_plan_save_requests",
            {},
            _AsyncpgIntegrityError(
                sqlstate="23505",
                constraint_name="uq_workflow_plan_save_requests_idempotency",
            ),
        )

    monkeypatch.setattr(
        persistence,
        "get_workflow_plan_save_request",
        race_lookup,
    )
    monkeypatch.setattr(
        persistence,
        "add_workflow_plan_save_request",
        raise_unique_race,
    )

    call = _create_version(
        database,
        plan_id=v1.plan.id,
        payload=payload,
        idempotency_key="final-unique-race-0001",
    )
    if conflicting_winner:
        with pytest.raises(WorkflowPlanIdempotencyConflictError):
            await call
    else:
        response = await call
        assert response.database_write is False
        assert response.plan_changed is False
        assert response.idempotent_replay is True

    assert session.explicit_begin_count == 2
    assert recovery_begin_counts == [2]
    assert await _count(session, WorkflowVersion) == 1
    assert await _count(session, WorkflowPlanSaveRequest) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("sqlstate", "constraint_name"),
    [
        ("23514", "uq_workflow_plan_save_requests_idempotency"),
        ("23505", "uq_some_other_constraint"),
    ],
)
async def test_non_idempotency_integrity_errors_do_not_enter_recovery(
    database: _DatabaseContext,
    monkeypatch: pytest.MonkeyPatch,
    sqlstate: str,
    constraint_name: str,
) -> None:
    v1 = await _create(database)
    payload = _version_request(
        database.project_id,
        current_version_id=v1.version.id,
        planning_input=_changed_input("comments"),
    )
    session = database.session
    session.explicit_begin_count = 0

    async def raise_unrelated_integrity_error(
        _session: AsyncSession,
        _save_request: WorkflowPlanSaveRequest,
    ) -> WorkflowPlanSaveRequest:
        raise IntegrityError(
            "INSERT workflow_plan_save_requests",
            {},
            _AsyncpgIntegrityError(
                sqlstate=sqlstate,
                constraint_name=constraint_name,
            ),
        )

    monkeypatch.setattr(
        persistence,
        "add_workflow_plan_save_request",
        raise_unrelated_integrity_error,
    )

    with pytest.raises(IntegrityError):
        await _create_version(
            database,
            plan_id=v1.plan.id,
            payload=payload,
            idempotency_key=f"integrity-{sqlstate}-{constraint_name}",
        )

    assert session.explicit_begin_count == 1
    assert await _count(session, WorkflowVersion) == 1
    assert await _count(session, WorkflowPlanSaveRequest) == 1


@pytest.mark.asyncio
async def test_read_plan_and_scope_lists_are_tenant_safe_paginated_and_read_only(
    database: _DatabaseContext,
) -> None:
    older = await _create(database)
    newer = await _create(
        database,
        idempotency_key="second-plan-save-0001",
        generated_at=NOW + timedelta(minutes=1),
    )
    scope_total = await _count(database.session, MonitoringScope)
    transaction_counts = (
        database.session.explicit_begin_count,
        database.session.commit_count,
        database.session.rollback_count,
    )

    first_page = await list_workflow_plans_for_project(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        limit=1,
        offset=0,
    )
    second_page = await list_workflow_plans_for_project(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        limit=1,
        offset=1,
    )
    scopes = await list_monitoring_scopes_for_project(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        limit=1,
        offset=1,
    )

    assert first_page.project_status == "active"
    assert first_page.total == second_page.total == 2
    assert (first_page.limit, first_page.offset) == (1, 0)
    assert (second_page.limit, second_page.offset) == (1, 1)
    listed_ids = {item.id for item in [*first_page.items, *second_page.items]}
    assert listed_ids == {older.plan.id, newer.plan.id}
    assert first_page.items[0].id != second_page.items[0].id
    assert scopes.project_status == "active"
    assert scopes.total == scope_total == 2
    assert (scopes.limit, scopes.offset) == (1, 1)
    assert len(scopes.items) == 1
    for response in (first_page, second_page, scopes):
        assert response.database_write is False
        assert response.plan_changed is False
        assert response.provider_call is False
        assert response.actor_run is False
        assert response.browser_run is False
        assert response.llm_call is False
        assert response.workflow_run_created is False
    assert (
        database.session.explicit_begin_count,
        database.session.commit_count,
        database.session.rollback_count,
    ) == transaction_counts
    assert not database.session.new
    assert not database.session.dirty
    assert not database.session.deleted


@pytest.mark.asyncio
async def test_read_fails_closed_on_pending_state_without_autoflush_or_rollback(
    database: _DatabaseContext,
) -> None:
    pending_user = User(
        email=f"pending-read-{uuid.uuid4()}@example.com",
        password_hash="not-a-real-secret",
        name="Pending Read User",
        status="active",
    )
    database.session.add(pending_user)
    transaction_counts = (
        database.session.explicit_begin_count,
        database.session.commit_count,
        database.session.rollback_count,
    )

    with pytest.raises(WorkflowPlanPersistenceTransactionStateError):
        await list_workflow_plans_for_project(
            database.session,
            workspace_id=database.workspace_id,
            project_id=database.project_id,
        )

    assert pending_user in database.session.new
    assert (
        database.session.explicit_begin_count,
        database.session.commit_count,
        database.session.rollback_count,
    ) == transaction_counts
    await database.session.rollback()


@pytest.mark.asyncio
async def test_archived_project_read_detail_and_version_history_remain_available(
    database: _DatabaseContext,
) -> None:
    v1 = await _create(database)
    v2 = await _create_version(
        database,
        plan_id=v1.plan.id,
        payload=_version_request(
            database.project_id,
            current_version_id=v1.version.id,
            planning_input=_changed_input("comments"),
        ),
        idempotency_key="archived-history-v2-0001",
    )
    project = (
        await database.session.execute(select(Project).where(Project.id == database.project_id))
    ).scalar_one()
    project.status = "archived"
    await database.session.commit()
    transaction_counts = (
        database.session.explicit_begin_count,
        database.session.commit_count,
        database.session.rollback_count,
    )

    detail = await get_workflow_plan_detail(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        plan_id=v1.plan.id,
    )
    history = await list_workflow_plan_versions(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        plan_id=v1.plan.id,
        limit=1,
        offset=0,
    )
    historical = await get_workflow_version_detail(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        plan_id=v1.plan.id,
        version_id=v1.version.id,
    )
    comparison = await compare_workflow_plan_versions(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        plan_id=v1.plan.id,
        base_version_id=v1.version.id,
        target_version_id=v2.version.id,
    )

    assert detail.project_status == "archived"
    assert detail.plan.current_version_id == v2.version.id
    assert detail.current_version.id == v2.version.id
    assert detail.current_version.editable_input.required_fields == (
        v2.version.editable_input.required_fields
    )
    assert detail.current_version.preview.preview_fingerprint == (
        v2.version.preview.preview_fingerprint
    )
    assert history.project_status == "archived"
    assert history.total == 2
    assert (history.limit, history.offset) == (1, 0)
    assert [item.id for item in history.items] == [v2.version.id]
    assert "preview" not in history.items[0].model_dump(mode="json")
    assert historical.project_status == "archived"
    assert historical.version.id == v1.version.id
    assert historical.version.editable_input.required_fields == (
        v1.version.editable_input.required_fields
    )
    assert historical.version.preview.preview_fingerprint == (
        v1.version.preview.preview_fingerprint
    )
    assert comparison.project_status == "archived"
    assert comparison.sections
    assert (
        database.session.explicit_begin_count,
        database.session.commit_count,
        database.session.rollback_count,
    ) == transaction_counts


@pytest.mark.asyncio
@pytest.mark.parametrize("tamper_target", ["fingerprint_payload", "preview_hash"])
async def test_read_detail_fails_closed_on_tampered_version_fingerprint(
    database: _DatabaseContext,
    tamper_target: str,
) -> None:
    saved = await _create(database)
    version = (await database.session.execute(select(WorkflowVersion))).scalar_one()
    if tamper_target == "fingerprint_payload":
        fingerprint_payload = deepcopy(version.fingerprint_payload)
        fingerprint_input = cast(
            dict[str, Any],
            fingerprint_payload["fingerprint_input"],
        )
        required_fields = cast(list[str], fingerprint_input["required_fields"])
        fingerprint_input["required_fields"] = [*required_fields, "tampered-field"]
        version.fingerprint_payload = fingerprint_payload
    else:
        plan_payload = deepcopy(version.plan_payload)
        plan_payload["preview_fingerprint"] = "sha256:" + "0" * 64
        version.plan_payload = plan_payload
    await database.session.commit()

    before_counts = {
        model: await _count(database.session, model)
        for model in (WorkflowPlan, WorkflowVersion, WorkflowPlanSaveRequest)
    }

    with pytest.raises(ValueError, match="workflow_plan_version_fingerprint_mismatch"):
        await get_workflow_plan_detail(
            database.session,
            workspace_id=database.workspace_id,
            project_id=database.project_id,
            plan_id=saved.plan.id,
        )

    assert {
        model: await _count(database.session, model)
        for model in (WorkflowPlan, WorkflowVersion, WorkflowPlanSaveRequest)
    } == before_counts
    assert not database.session.new
    assert not database.session.dirty
    assert not database.session.deleted


@pytest.mark.asyncio
async def test_read_detail_fails_closed_when_preview_normalized_snapshot_diverges(
    database: _DatabaseContext,
) -> None:
    saved = await _create(database)
    version = (await database.session.execute(select(WorkflowVersion))).scalar_one()
    original_fingerprint_payload = deepcopy(version.fingerprint_payload)
    original_preview_fingerprint = version.preview_fingerprint
    plan_payload = deepcopy(version.plan_payload)
    normalized_input = cast(dict[str, Any], plan_payload["normalized_input"])
    required_fields = cast(list[str], normalized_input["required_fields"])
    normalized_input["required_fields"] = [
        *required_fields,
        "tampered-normalized-only",
    ]
    version.plan_payload = plan_payload
    await database.session.commit()

    assert version.fingerprint_payload == original_fingerprint_payload
    assert version.preview_fingerprint == original_preview_fingerprint
    assert plan_payload["preview_fingerprint"] == original_preview_fingerprint
    assert version.normalized_input != plan_payload["normalized_input"]
    before_counts = {
        model: await _count(database.session, model)
        for model in (WorkflowPlan, WorkflowVersion, WorkflowPlanSaveRequest)
    }

    with pytest.raises(ValueError, match="workflow_plan_version_fingerprint_mismatch"):
        await get_workflow_plan_detail(
            database.session,
            workspace_id=database.workspace_id,
            project_id=database.project_id,
            plan_id=saved.plan.id,
        )

    assert {
        model: await _count(database.session, model)
        for model in (WorkflowPlan, WorkflowVersion, WorkflowPlanSaveRequest)
    } == before_counts
    assert not database.session.new
    assert not database.session.dirty
    assert not database.session.deleted


@pytest.mark.asyncio
async def test_read_detail_fails_closed_when_preview_semantic_body_diverges(
    database: _DatabaseContext,
) -> None:
    saved = await _create(database)
    version = (await database.session.execute(select(WorkflowVersion))).scalar_one()
    original_fingerprint_payload = deepcopy(version.fingerprint_payload)
    original_preview_fingerprint = version.preview_fingerprint
    plan_payload = deepcopy(version.plan_payload)
    query_terms = cast(list[dict[str, Any]], plan_payload["query_terms"])
    original_status = cast(str, query_terms[0]["status"])
    query_terms[0]["status"] = "rejected" if original_status != "rejected" else "active"
    version.plan_payload = plan_payload
    await database.session.commit()

    assert version.fingerprint_payload == original_fingerprint_payload
    assert version.preview_fingerprint == original_preview_fingerprint
    assert plan_payload["preview_fingerprint"] == original_preview_fingerprint
    assert version.normalized_input == plan_payload["normalized_input"]
    before_counts = {
        model: await _count(database.session, model)
        for model in (WorkflowPlan, WorkflowVersion, WorkflowPlanSaveRequest)
    }

    with pytest.raises(ValueError, match="workflow_plan_version_fingerprint_mismatch"):
        await get_workflow_plan_detail(
            database.session,
            workspace_id=database.workspace_id,
            project_id=database.project_id,
            plan_id=saved.plan.id,
        )

    assert {
        model: await _count(database.session, model)
        for model in (WorkflowPlan, WorkflowVersion, WorkflowPlanSaveRequest)
    } == before_counts
    assert not database.session.new
    assert not database.session.dirty
    assert not database.session.deleted


@pytest.mark.asyncio
async def test_read_plan_resources_fail_closed_across_tenant_and_project(
    database: _DatabaseContext,
) -> None:
    saved = await _create(database)

    with pytest.raises(ProjectNotFoundError):
        await list_workflow_plans_for_project(
            database.session,
            workspace_id=uuid.uuid4(),
            project_id=database.project_id,
            limit=50,
            offset=0,
        )
    with pytest.raises(WorkflowPlanNotFoundError):
        await get_workflow_plan_detail(
            database.session,
            workspace_id=database.workspace_id,
            project_id=database.project_id,
            plan_id=uuid.uuid4(),
        )

    assert await _count(database.session, WorkflowPlan) == 1
    assert saved.plan.project_id == database.project_id


@pytest.mark.asyncio
async def test_read_version_must_belong_to_requested_plan(
    database: _DatabaseContext,
) -> None:
    first = await _create(database)
    second = await _create(
        database,
        idempotency_key="version-owner-second-plan-0001",
        generated_at=NOW + timedelta(minutes=1),
    )

    with pytest.raises(WorkflowVersionNotFoundError):
        await get_workflow_version_detail(
            database.session,
            workspace_id=database.workspace_id,
            project_id=database.project_id,
            plan_id=second.plan.id,
            version_id=first.version.id,
        )

    assert await _count(database.session, WorkflowVersion) == 2


@pytest.mark.asyncio
async def test_compare_versions_handles_same_changed_missing_and_cross_plan(
    database: _DatabaseContext,
) -> None:
    v1 = await _create(database)
    v2 = await _create_version(
        database,
        plan_id=v1.plan.id,
        payload=_version_request(
            database.project_id,
            current_version_id=v1.version.id,
            planning_input=_changed_input("comments"),
        ),
        idempotency_key="compare-v2-save-0001",
    )
    other_plan = await _create(
        database,
        idempotency_key="compare-other-plan-0001",
        generated_at=NOW + timedelta(minutes=2),
    )
    before_counts = {
        model: await _count(database.session, model)
        for model in (
            WorkflowPlan,
            WorkflowVersion,
            MonitoringScope,
            WorkflowVersionScope,
            QueryTerm,
            WorkflowPlanSaveRequest,
        )
    }
    transaction_counts = (
        database.session.explicit_begin_count,
        database.session.commit_count,
        database.session.rollback_count,
    )

    same = await compare_workflow_plan_versions(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        plan_id=v1.plan.id,
        base_version_id=v1.version.id,
        target_version_id=v1.version.id,
    )
    changed = await compare_workflow_plan_versions(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        plan_id=v1.plan.id,
        base_version_id=v1.version.id,
        target_version_id=v2.version.id,
    )

    assert same.same_version is True
    assert same.sections == []
    assert same.base_version.id == same.target_version.id == v1.version.id
    assert "preview" not in same.base_version.model_dump(mode="json")
    assert changed.same_version is False
    assert changed.base_version.id == v1.version.id
    assert changed.target_version.id == v2.version.id
    assert changed.sections
    assert changed.database_write is False
    assert changed.plan_changed is False

    with pytest.raises(WorkflowVersionNotFoundError):
        await compare_workflow_plan_versions(
            database.session,
            workspace_id=database.workspace_id,
            project_id=database.project_id,
            plan_id=v1.plan.id,
            base_version_id=v1.version.id,
            target_version_id=uuid.uuid4(),
        )
    with pytest.raises(WorkflowVersionNotFoundError):
        await compare_workflow_plan_versions(
            database.session,
            workspace_id=database.workspace_id,
            project_id=database.project_id,
            plan_id=v1.plan.id,
            base_version_id=v1.version.id,
            target_version_id=other_plan.version.id,
        )

    after_counts = {model: await _count(database.session, model) for model in before_counts}
    assert after_counts == before_counts
    assert (
        database.session.explicit_begin_count,
        database.session.commit_count,
        database.session.rollback_count,
    ) == transaction_counts
    assert not database.session.new
    assert not database.session.dirty
    assert not database.session.deleted
