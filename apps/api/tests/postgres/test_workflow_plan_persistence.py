from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

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
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.repositories.workflow_plans import (
    add_query_term,
    add_workflow_plan,
    add_workflow_plan_save_request,
    add_workflow_version,
    add_workflow_version_scope,
    insert_monitoring_scope_on_conflict,
)
from data_intelligence_hub.schemas.workflow_plan_persistence import (
    WorkflowPlanCreateRequest,
    WorkflowPlanSaveResponse,
    WorkflowVersionCreateRequest,
)
from data_intelligence_hub.schemas.workflow_planner import (
    NormalizedMonitoringScope,
    PlanningInput,
)
from data_intelligence_hub.services.capability_catalog import get_capability_catalog
from data_intelligence_hub.services.exceptions import WorkflowPlanVersionConflictError
from data_intelligence_hub.services.workflow_planner import persistence
from data_intelligence_hub.services.workflow_planner.persistence import (
    create_workflow_plan,
    create_workflow_version,
)
from data_intelligence_hub.services.workflow_planner.planner import (
    build_workflow_plan_result,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "workflow_planner"
PERIODIC_FIXTURE = FIXTURE_DIR / "periodic_monitoring_request_v1.json"
NOW = datetime(2026, 7, 13, 11, 30, tzinfo=UTC)


@dataclass(frozen=True)
class _Tenant:
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True)
class _PostgresDatabase:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]


class _InjectedWriteFailure(RuntimeError):
    pass


def _planning_input() -> PlanningInput:
    payload = cast(
        dict[str, object],
        json.loads(PERIODIC_FIXTURE.read_text(encoding="utf-8")),
    )
    return PlanningInput.model_validate(payload)


def _changed_input(label: str) -> PlanningInput:
    planning_input = _planning_input()
    return planning_input.model_copy(
        update={"required_fields": [*planning_input.required_fields, label]},
        deep=True,
    )


def _create_request(
    project_id: uuid.UUID,
    *,
    name: str = "PostgreSQL workflow plan",
) -> WorkflowPlanCreateRequest:
    planning_input = _planning_input()
    result = build_workflow_plan_result(
        project_id=project_id,
        planning_input=planning_input,
        catalog=get_capability_catalog(),
        generated_at=NOW,
        request_id="postgres-preview-v1",
    )
    return WorkflowPlanCreateRequest(
        name=name,
        preview_input=planning_input,
        expected_preview_fingerprint=result.preview.preview_fingerprint,
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
        catalog=get_capability_catalog(),
        generated_at=NOW + timedelta(minutes=1),
        request_id="postgres-preview-version",
    )
    return WorkflowVersionCreateRequest(
        preview_input=planning_input,
        expected_preview_fingerprint=result.preview.preview_fingerprint,
        expected_current_version_id=current_version_id,
    )


@pytest_asyncio.fixture()
async def postgres_database(
    postgres_database_url: str,
) -> AsyncIterator[_PostgresDatabase]:
    engine = create_async_engine(postgres_database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield _PostgresDatabase(engine=engine, sessions=sessions)
    finally:
        await engine.dispose()


async def _seed_tenant(database: _PostgresDatabase) -> _Tenant:
    tenant = _Tenant(
        user_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
    )
    async with database.sessions.begin() as session:
        session.add_all(
            [
                User(
                    id=tenant.user_id,
                    email=f"workflow-pg-{tenant.user_id}@example.test",
                    password_hash="not-a-real-password",
                    name="Workflow PostgreSQL Test User",
                    status="active",
                ),
                Workspace(
                    id=tenant.workspace_id,
                    name="Workflow PostgreSQL Test Workspace",
                    slug=f"workflow-pg-{tenant.workspace_id}",
                    owner_id=tenant.user_id,
                ),
                WorkspaceMember(
                    workspace_id=tenant.workspace_id,
                    user_id=tenant.user_id,
                    role="owner",
                ),
                Project(
                    id=tenant.project_id,
                    workspace_id=tenant.workspace_id,
                    owner_id=tenant.user_id,
                    name="Workflow PostgreSQL Test Project",
                    description=None,
                    domain="social",
                    status="active",
                ),
            ]
        )
    return tenant


async def _create(
    database: _PostgresDatabase,
    tenant: _Tenant,
    *,
    payload: WorkflowPlanCreateRequest | None = None,
    idempotency_key: str,
    generated_at: datetime = NOW,
) -> WorkflowPlanSaveResponse:
    async with database.sessions() as session:
        return await create_workflow_plan(
            session,
            workspace_id=tenant.workspace_id,
            project_id=tenant.project_id,
            created_by_user_id=tenant.user_id,
            payload=payload or _create_request(tenant.project_id),
            idempotency_key=idempotency_key,
            request_id="postgres-create-request",
            generated_at=generated_at,
        )


async def _create_version(
    database: _PostgresDatabase,
    tenant: _Tenant,
    *,
    plan_id: uuid.UUID,
    payload: WorkflowVersionCreateRequest,
    idempotency_key: str,
    generated_at: datetime,
) -> WorkflowPlanSaveResponse:
    async with database.sessions() as session:
        return await create_workflow_version(
            session,
            workspace_id=tenant.workspace_id,
            project_id=tenant.project_id,
            workflow_plan_id=plan_id,
            created_by_user_id=tenant.user_id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_id="postgres-version-request",
            generated_at=generated_at,
        )


async def _count_for_project(
    database: _PostgresDatabase,
    tenant: _Tenant,
    model: type[Any],
) -> int:
    async with database.sessions() as session:
        return int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(model)
                    .where(model.project_id == tenant.project_id)
                )
            ).scalar_one()
        )


async def _business_counts(
    database: _PostgresDatabase,
    tenant: _Tenant,
) -> dict[str, int]:
    models = (
        WorkflowPlan,
        WorkflowVersion,
        MonitoringScope,
        WorkflowVersionScope,
        QueryTerm,
        WorkflowPlanSaveRequest,
    )
    return {
        model.__tablename__: await _count_for_project(database, tenant, model) for model in models
    }


def _scope_insert_values(
    tenant: _Tenant,
    scope: NormalizedMonitoringScope,
    *,
    scope_id: uuid.UUID,
) -> dict[str, Any]:
    return {
        "id": scope_id,
        "workspace_id": tenant.workspace_id,
        "project_id": tenant.project_id,
        "created_by_user_id": tenant.user_id,
        "scope_key": scope.scope_key,
        "scope_type": scope.scope_type.value,
        "canonical_term": scope.canonical_term,
        "aliases": list(scope.aliases),
        "include_terms": list(scope.include_terms),
        "exclude_terms": list(scope.exclude_terms),
        "official_accounts": list(scope.official_accounts),
        "seed_urls": list(scope.seed_urls),
        "effective_languages": list(scope.effective_languages),
        "effective_regions": list(scope.effective_regions),
        "effective_platforms": [platform.value for platform in scope.effective_platforms],
        "match_mode": scope.match_mode.value,
        "created_at": NOW,
    }


def _inject_failure(monkeypatch: pytest.MonkeyPatch, phase: str) -> None:
    async def fail_scope(
        session: AsyncSession,
        values: Mapping[str, Any],
    ) -> uuid.UUID | None:
        await insert_monitoring_scope_on_conflict(session, values)
        raise _InjectedWriteFailure(phase)

    async def fail_version(
        session: AsyncSession,
        version: WorkflowVersion,
    ) -> WorkflowVersion:
        await add_workflow_version(session, version)
        raise _InjectedWriteFailure(phase)

    async def fail_version_scope(
        session: AsyncSession,
        association: WorkflowVersionScope,
    ) -> WorkflowVersionScope:
        await add_workflow_version_scope(session, association)
        raise _InjectedWriteFailure(phase)

    async def fail_query_term(
        session: AsyncSession,
        query_term: QueryTerm,
    ) -> QueryTerm:
        await add_query_term(session, query_term)
        raise _InjectedWriteFailure(phase)

    async def fail_save_request(
        session: AsyncSession,
        save_request: WorkflowPlanSaveRequest,
    ) -> WorkflowPlanSaveRequest:
        await add_workflow_plan_save_request(session, save_request)
        raise _InjectedWriteFailure(phase)

    if phase == "scope":
        monkeypatch.setattr(persistence, "insert_monitoring_scope_on_conflict", fail_scope)
    elif phase == "version":
        monkeypatch.setattr(persistence, "add_workflow_version", fail_version)
    elif phase == "version_scope":
        monkeypatch.setattr(
            persistence,
            "add_workflow_version_scope",
            fail_version_scope,
        )
    elif phase == "query_term":
        monkeypatch.setattr(persistence, "add_query_term", fail_query_term)
    elif phase == "current_pointer":
        add_plan_calls = 0

        async def fail_current_pointer(
            session: AsyncSession,
            plan: WorkflowPlan,
        ) -> WorkflowPlan:
            nonlocal add_plan_calls
            add_plan_calls += 1
            persisted = await add_workflow_plan(session, plan)
            if add_plan_calls == 2:
                raise _InjectedWriteFailure(phase)
            return persisted

        monkeypatch.setattr(persistence, "add_workflow_plan", fail_current_pointer)
    elif phase == "save_request":
        monkeypatch.setattr(
            persistence,
            "add_workflow_plan_save_request",
            fail_save_request,
        )
    else:
        raise AssertionError(f"unknown failure phase: {phase}")


@pytest.mark.asyncio
async def test_real_postgres_v1_version_semantic_no_op_and_replay(
    postgres_database: _PostgresDatabase,
) -> None:
    tenant = await _seed_tenant(postgres_database)
    create_key = "postgres-create-key-0001"
    v1 = await _create(
        postgres_database,
        tenant,
        idempotency_key=create_key,
    )
    async with postgres_database.sessions() as session:
        v1_database_updated_at = await session.scalar(
            select(WorkflowPlan.updated_at).where(WorkflowPlan.id == v1.plan.id)
        )
    changed_input = _changed_input("comments")
    version_payload = _version_request(
        tenant.project_id,
        current_version_id=v1.version.id,
        planning_input=changed_input,
    )
    version_key = "postgres-version-key-0001"
    v2 = await _create_version(
        postgres_database,
        tenant,
        plan_id=v1.plan.id,
        payload=version_payload,
        idempotency_key=version_key,
        generated_at=NOW + timedelta(minutes=1),
    )
    async with postgres_database.sessions() as session:
        v2_database_updated_at = await session.scalar(
            select(WorkflowPlan.updated_at).where(WorkflowPlan.id == v1.plan.id)
        )
        created_snapshots = [
            WorkflowPlanSaveResponse.model_validate(payload)
            for payload in (
                await session.scalars(
                    select(WorkflowPlanSaveRequest.response_payload)
                    .where(WorkflowPlanSaveRequest.project_id == tenant.project_id)
                    .order_by(WorkflowPlanSaveRequest.created_at)
                )
            ).all()
        ]
    no_op_payload = _version_request(
        tenant.project_id,
        current_version_id=v2.version.id,
        planning_input=changed_input,
    )
    no_op_key = "postgres-no-op-key-0001"
    no_op = await _create_version(
        postgres_database,
        tenant,
        plan_id=v1.plan.id,
        payload=no_op_payload,
        idempotency_key=no_op_key,
        generated_at=NOW + timedelta(minutes=2),
    )
    replay = await _create_version(
        postgres_database,
        tenant,
        plan_id=v1.plan.id,
        payload=no_op_payload,
        idempotency_key=no_op_key,
        generated_at=NOW + timedelta(minutes=3),
    )

    assert v1.outcome == "created"
    assert v1.version.version_number == 1
    assert v2.outcome == "created"
    assert v2.version.version_number == 2
    assert v1_database_updated_at == v1.plan.updated_at
    assert v2_database_updated_at == v2.plan.updated_at
    assert created_snapshots[0].plan.updated_at == v1_database_updated_at
    assert created_snapshots[1].plan.updated_at == v2_database_updated_at
    assert no_op.outcome == "semantic_no_op"
    assert no_op.database_write is True
    assert no_op.plan_changed is False
    assert no_op.version.id == v2.version.id
    assert replay.outcome == "semantic_no_op"
    assert replay.database_write is False
    assert replay.plan_changed is False
    assert replay.idempotent_replay is True
    assert replay.plan == no_op.plan
    assert replay.version == no_op.version

    counts = await _business_counts(postgres_database, tenant)
    assert counts["workflow_plans"] == 1
    assert counts["workflow_versions"] == 2
    assert counts["workflow_plan_save_requests"] == 3

    async with postgres_database.sessions() as session:
        plan = (
            await session.execute(
                select(WorkflowPlan).where(WorkflowPlan.project_id == tenant.project_id)
            )
        ).scalar_one()
        save_requests = list(
            (
                await session.execute(
                    select(WorkflowPlanSaveRequest).where(
                        WorkflowPlanSaveRequest.project_id == tenant.project_id
                    )
                )
            ).scalars()
        )

    assert plan.current_version_id == v2.version.id
    raw_keys = (create_key, version_key, no_op_key)
    for save_request in save_requests:
        serialized_response = json.dumps(
            save_request.response_payload,
            sort_keys=True,
        )
        assert save_request.idempotency_key_hash.startswith("sha256:")
        assert all(raw_key != save_request.idempotency_key_hash for raw_key in raw_keys)
        assert all(raw_key not in save_request.idempotency_scope for raw_key in raw_keys)
        assert all(raw_key not in save_request.request_hash for raw_key in raw_keys)
        assert all(raw_key not in serialized_response for raw_key in raw_keys)


@pytest.mark.asyncio
async def test_injected_failure_at_each_write_phase_rolls_back_all_business_rows(
    postgres_database: _PostgresDatabase,
) -> None:
    phases = (
        "scope",
        "version",
        "version_scope",
        "query_term",
        "current_pointer",
        "save_request",
    )
    for phase in phases:
        tenant = await _seed_tenant(postgres_database)
        with pytest.MonkeyPatch.context() as phase_patch:
            _inject_failure(phase_patch, phase)
            with pytest.raises(_InjectedWriteFailure, match=phase):
                await _create(
                    postgres_database,
                    tenant,
                    idempotency_key=f"failure-{phase}-key-0001",
                )

        assert await _business_counts(postgres_database, tenant) == {
            "workflow_plans": 0,
            "workflow_versions": 0,
            "monitoring_scopes": 0,
            "workflow_version_scopes": 0,
            "query_terms": 0,
            "workflow_plan_save_requests": 0,
        }


@pytest.mark.asyncio
async def test_two_sessions_advancing_same_plan_have_one_winner_and_one_conflict(
    postgres_database: _PostgresDatabase,
) -> None:
    tenant = await _seed_tenant(postgres_database)
    v1 = await _create(
        postgres_database,
        tenant,
        idempotency_key="concurrent-version-create-v1",
    )
    payload = _version_request(
        tenant.project_id,
        current_version_id=v1.version.id,
        planning_input=_changed_input("comments"),
    )
    start = asyncio.Event()

    async def advance(key: str) -> WorkflowPlanSaveResponse:
        await start.wait()
        return await _create_version(
            postgres_database,
            tenant,
            plan_id=v1.plan.id,
            payload=payload,
            idempotency_key=key,
            generated_at=NOW + timedelta(minutes=1),
        )

    tasks = [
        asyncio.create_task(advance("concurrent-version-a")),
        asyncio.create_task(advance("concurrent-version-b")),
    ]
    start.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    responses = [result for result in results if isinstance(result, WorkflowPlanSaveResponse)]
    conflicts = [
        result for result in results if isinstance(result, WorkflowPlanVersionConflictError)
    ]

    result_diagnostics = [
        (
            type(result).__name__,
            getattr(getattr(result, "orig", None), "sqlstate", None),
            getattr(
                getattr(getattr(result, "orig", None), "__cause__", None),
                "constraint_name",
                None,
            ),
        )
        for result in results
    ]
    assert len(responses) == 1, result_diagnostics
    assert len(conflicts) == 1, result_diagnostics
    winner = responses[0]
    assert winner.version.version_number == 2
    assert winner.plan.current_version_id == winner.version.id
    counts = await _business_counts(postgres_database, tenant)
    assert counts["workflow_plans"] == 1
    assert counts["workflow_versions"] == 2
    assert counts["workflow_plan_save_requests"] == 2

    async with postgres_database.sessions() as session:
        current_version_id = await session.scalar(
            select(WorkflowPlan.current_version_id).where(WorkflowPlan.id == v1.plan.id)
        )
    assert current_version_id == winner.version.id


@pytest.mark.asyncio
async def test_concurrent_plan_creates_reuse_project_scopes(
    postgres_database: _PostgresDatabase,
) -> None:
    tenant = await _seed_tenant(postgres_database)
    payloads = (
        _create_request(tenant.project_id, name="Concurrent scope plan A"),
        _create_request(tenant.project_id, name="Concurrent scope plan B"),
    )
    start = asyncio.Event()

    async def create_plan(
        payload: WorkflowPlanCreateRequest,
        key: str,
    ) -> WorkflowPlanSaveResponse:
        await start.wait()
        return await _create(
            postgres_database,
            tenant,
            payload=payload,
            idempotency_key=key,
        )

    tasks = [
        asyncio.create_task(create_plan(payloads[0], "concurrent-scope-a")),
        asyncio.create_task(create_plan(payloads[1], "concurrent-scope-b")),
    ]
    start.set()
    first, second = await asyncio.gather(*tasks)

    scope_count = len(first.version.preview.normalized_input.scopes)
    assert first.plan.id != second.plan.id
    assert len(second.version.preview.normalized_input.scopes) == scope_count
    counts = await _business_counts(postgres_database, tenant)
    assert counts["workflow_plans"] == 2
    assert counts["workflow_versions"] == 2
    assert counts["monitoring_scopes"] == scope_count
    assert counts["workflow_version_scopes"] == scope_count * 2


@pytest.mark.asyncio
async def test_concurrent_scope_inserts_have_one_winner_and_one_durable_row(
    postgres_database: _PostgresDatabase,
) -> None:
    tenant = await _seed_tenant(postgres_database)
    result = build_workflow_plan_result(
        project_id=tenant.project_id,
        planning_input=_planning_input(),
        catalog=get_capability_catalog(),
        generated_at=NOW,
        request_id="postgres-concurrent-scope-preview",
    )
    scope = result.preview.normalized_input.scopes[0]
    proposed_ids = (uuid.uuid4(), uuid.uuid4())
    start = asyncio.Event()

    async def insert_scope(scope_id: uuid.UUID) -> uuid.UUID | None:
        await start.wait()
        async with postgres_database.sessions.begin() as session:
            return await insert_monitoring_scope_on_conflict(
                session,
                _scope_insert_values(tenant, scope, scope_id=scope_id),
            )

    tasks = [
        asyncio.create_task(insert_scope(proposed_ids[0])),
        asyncio.create_task(insert_scope(proposed_ids[1])),
    ]
    start.set()
    insert_results = await asyncio.gather(*tasks)

    winners = [scope_id for scope_id in insert_results if scope_id is not None]
    assert len(winners) == 1
    assert sum(scope_id is None for scope_id in insert_results) == 1
    async with postgres_database.sessions() as session:
        durable_scope_ids = list(
            await session.scalars(
                select(MonitoringScope.id).where(
                    MonitoringScope.project_id == tenant.project_id,
                    MonitoringScope.scope_key == scope.scope_key,
                )
            )
        )
    assert durable_scope_ids == winners


@pytest.mark.asyncio
async def test_concurrent_same_idempotency_key_has_one_durable_result(
    postgres_database: _PostgresDatabase,
) -> None:
    tenant = await _seed_tenant(postgres_database)
    payload = _create_request(tenant.project_id)
    raw_key = "concurrent-idempotency-key-0001"
    start = asyncio.Event()

    async def create_once() -> WorkflowPlanSaveResponse:
        await start.wait()
        return await _create(
            postgres_database,
            tenant,
            payload=payload,
            idempotency_key=raw_key,
        )

    tasks = [asyncio.create_task(create_once()), asyncio.create_task(create_once())]
    start.set()
    first, second = await asyncio.gather(*tasks)

    assert sorted((first.idempotent_replay, second.idempotent_replay)) == [False, True]
    assert first.plan == second.plan
    assert first.version == second.version
    assert {first.database_write, second.database_write} == {False, True}
    counts = await _business_counts(postgres_database, tenant)
    assert counts["workflow_plans"] == 1
    assert counts["workflow_versions"] == 1
    assert counts["workflow_plan_save_requests"] == 1

    async with postgres_database.sessions() as session:
        save_request = (
            await session.execute(
                select(WorkflowPlanSaveRequest).where(
                    WorkflowPlanSaveRequest.project_id == tenant.project_id
                )
            )
        ).scalar_one()
    assert raw_key != save_request.idempotency_key_hash
    assert raw_key not in save_request.idempotency_scope
    assert raw_key not in save_request.request_hash
    assert raw_key not in json.dumps(save_request.response_payload, sort_keys=True)
