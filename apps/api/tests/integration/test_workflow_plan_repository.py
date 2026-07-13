from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workflow_plan import (
    MonitoringScope,
    WorkflowPlan,
    WorkflowPlanSaveRequest,
    WorkflowVersion,
)
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.workflow_plans import (
    add_workflow_plan,
    build_monitoring_scope_insert,
    count_monitoring_scopes,
    count_workflow_plans,
    count_workflow_versions,
    get_monitoring_scope_by_key,
    get_workflow_plan,
    get_workflow_plan_save_request,
    get_workflow_version,
    list_monitoring_scopes,
    list_workflow_plans,
    list_workflow_versions,
    project_lock_statement,
    workflow_plan_lock_statement,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)


@pytest_asyncio.fixture()
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


async def _seed_project(
    session: AsyncSession,
    *,
    suffix: str,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    session.add_all(
        [
            User(
                id=user_id,
                email=f"{suffix}@example.com",
                password_hash="not-a-real-secret",
                name=suffix,
                status="active",
            ),
            Workspace(
                id=workspace_id,
                name=suffix,
                slug=f"workspace-{suffix}",
                owner_id=user_id,
            ),
            Project(
                id=project_id,
                workspace_id=workspace_id,
                owner_id=user_id,
                name=suffix,
                description=None,
                domain="social",
                status="active",
            ),
        ]
    )
    await session.commit()
    return user_id, workspace_id, project_id


def _plan(
    *,
    plan_id: uuid.UUID,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    updated_at: datetime,
) -> WorkflowPlan:
    return WorkflowPlan(
        id=plan_id,
        workspace_id=workspace_id,
        project_id=project_id,
        created_by_user_id=user_id,
        name=name,
        flow_mode="periodic_monitoring",
        status="previewed",
        current_version_id=None,
        created_at=updated_at,
        updated_at=updated_at,
    )


def _version(
    *,
    version_id: uuid.UUID,
    plan_id: uuid.UUID,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    number: int,
) -> WorkflowVersion:
    return WorkflowVersion(
        id=version_id,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_plan_id=plan_id,
        created_by_user_id=user_id,
        version_number=number,
        planning_status="held",
        planner_contract_version="workflow_planner.v1",
        catalog_snapshot_id="sha256:" + "a" * 64,
        policy_version="policy.v1",
        mode_template_version="template.v1",
        query_versions={},
        fingerprint_payload={},
        normalized_input={},
        plan_payload={},
        preview_fingerprint="sha256:" + f"{number:x}" * 64,
        created_at=NOW + timedelta(minutes=number),
    )


@pytest.mark.asyncio
async def test_plan_queries_are_tenant_scoped_ordered_and_paginated(
    session: AsyncSession,
) -> None:
    user_id, workspace_id, project_id = await _seed_project(session, suffix="first")
    _, other_workspace_id, other_project_id = await _seed_project(
        session,
        suffix="other",
    )
    older_id = uuid.UUID("00000000-0000-0000-0000-000000000010")
    newer_low_id = uuid.UUID("00000000-0000-0000-0000-000000000011")
    newer_high_id = uuid.UUID("00000000-0000-0000-0000-000000000012")
    session.add_all(
        [
            _plan(
                plan_id=older_id,
                workspace_id=workspace_id,
                project_id=project_id,
                user_id=user_id,
                name="older",
                updated_at=NOW,
            ),
            _plan(
                plan_id=newer_low_id,
                workspace_id=workspace_id,
                project_id=project_id,
                user_id=user_id,
                name="newer-low",
                updated_at=NOW + timedelta(minutes=1),
            ),
            _plan(
                plan_id=newer_high_id,
                workspace_id=workspace_id,
                project_id=project_id,
                user_id=user_id,
                name="newer-high",
                updated_at=NOW + timedelta(minutes=1),
            ),
        ]
    )
    await session.commit()

    plans = await list_workflow_plans(
        session,
        workspace_id,
        project_id,
        limit=2,
        offset=0,
    )

    assert [plan.id for plan in plans] == [newer_high_id, newer_low_id]
    assert await count_workflow_plans(session, workspace_id, project_id) == 3
    assert await get_workflow_plan(session, workspace_id, project_id, older_id)
    assert (
        await get_workflow_plan(
            session,
            other_workspace_id,
            other_project_id,
            older_id,
        )
        is None
    )


@pytest.mark.asyncio
async def test_version_queries_are_plan_scoped_and_descending(
    session: AsyncSession,
) -> None:
    user_id, workspace_id, project_id = await _seed_project(session, suffix="versions")
    plan_id = uuid.uuid4()
    plan = _plan(
        plan_id=plan_id,
        workspace_id=workspace_id,
        project_id=project_id,
        user_id=user_id,
        name="versions",
        updated_at=NOW,
    )
    v1 = _version(
        version_id=uuid.uuid4(),
        plan_id=plan_id,
        workspace_id=workspace_id,
        project_id=project_id,
        user_id=user_id,
        number=1,
    )
    v2 = _version(
        version_id=uuid.uuid4(),
        plan_id=plan_id,
        workspace_id=workspace_id,
        project_id=project_id,
        user_id=user_id,
        number=2,
    )
    session.add_all([plan, v1, v2])
    await session.commit()

    versions = await list_workflow_versions(
        session,
        workspace_id,
        project_id,
        plan_id,
        limit=50,
        offset=0,
    )

    assert [version.version_number for version in versions] == [2, 1]
    assert (
        await count_workflow_versions(
            session,
            workspace_id,
            project_id,
            plan_id,
        )
        == 2
    )
    assert (
        await get_workflow_version(
            session,
            workspace_id,
            project_id,
            plan_id,
            v1.id,
        )
    ) is v1


@pytest.mark.asyncio
async def test_scope_and_save_request_reads_are_exactly_scoped(
    session: AsyncSession,
) -> None:
    user_id, workspace_id, project_id = await _seed_project(session, suffix="scopes")
    scope = MonitoringScope(
        workspace_id=workspace_id,
        project_id=project_id,
        created_by_user_id=user_id,
        scope_key="sha256:" + "b" * 64,
        scope_type="brand",
        canonical_term="Example",
        aliases=[],
        include_terms=[],
        exclude_terms=[],
        official_accounts=[],
        seed_urls=[],
        effective_languages=["en"],
        effective_regions=["US"],
        effective_platforms=["youtube"],
        match_mode="phrase",
        created_at=NOW,
    )
    plan = _plan(
        plan_id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        user_id=user_id,
        name="scope-plan",
        updated_at=NOW,
    )
    version = _version(
        version_id=uuid.uuid4(),
        plan_id=plan.id,
        workspace_id=workspace_id,
        project_id=project_id,
        user_id=user_id,
        number=1,
    )
    save_request = WorkflowPlanSaveRequest(
        workspace_id=workspace_id,
        project_id=project_id,
        created_by_user_id=user_id,
        idempotency_scope=f"workflow_plan.create:{project_id}",
        idempotency_key_hash="sha256:" + "c" * 64,
        request_hash="sha256:" + "d" * 64,
        workflow_plan_id=plan.id,
        workflow_version_id=version.id,
        outcome="created",
        response_status=201,
        response_payload={},
        created_at=NOW,
    )
    session.add_all([scope, plan, version, save_request])
    await session.commit()

    assert (
        await get_monitoring_scope_by_key(
            session,
            workspace_id,
            project_id,
            scope.scope_key,
        )
        is scope
    )
    assert await list_monitoring_scopes(
        session,
        workspace_id,
        project_id,
        limit=50,
        offset=0,
    ) == [scope]
    assert await count_monitoring_scopes(session, workspace_id, project_id) == 1
    assert (
        await get_workflow_plan_save_request(
            session,
            workspace_id,
            user_id,
            save_request.idempotency_scope,
            save_request.idempotency_key_hash,
        )
        is save_request
    )


def test_lock_and_scope_insert_statements_compile_for_postgresql() -> None:
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]

    project_statement = project_lock_statement(workspace_id, project_id)
    plan_statement = workflow_plan_lock_statement(workspace_id, project_id, plan_id)
    project_sql = str(project_statement.compile(dialect=dialect))
    plan_sql = str(plan_statement.compile(dialect=dialect))
    scope_sql = str(
        build_monitoring_scope_insert(
            {
                "workspace_id": workspace_id,
                "project_id": project_id,
                "created_by_user_id": uuid.uuid4(),
                "scope_key": "sha256:" + "e" * 64,
                "scope_type": "brand",
                "canonical_term": "Example",
                "aliases": [],
                "include_terms": [],
                "exclude_terms": [],
                "official_accounts": [],
                "seed_urls": [],
                "effective_languages": [],
                "effective_regions": [],
                "effective_platforms": [],
                "match_mode": "phrase",
            }
        ).compile(dialect=dialect)
    )

    assert "FOR UPDATE" in project_sql
    assert "FOR UPDATE" in plan_sql
    assert project_statement.get_execution_options()["populate_existing"] is True
    assert plan_statement.get_execution_options()["populate_existing"] is True
    assert "ON CONFLICT (project_id, scope_key) DO NOTHING" in scope_sql
    assert "RETURNING monitoring_scopes.id" in scope_sql


@pytest.mark.asyncio
async def test_add_primitives_flush_without_commit_and_rollback_cleanly(
    session: AsyncSession,
) -> None:
    user_id, workspace_id, project_id = await _seed_project(session, suffix="rollback")
    plan = _plan(
        plan_id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        user_id=user_id,
        name="rollback",
        updated_at=NOW,
    )

    await add_workflow_plan(session, plan)
    assert await count_workflow_plans(session, workspace_id, project_id) == 1

    await session.rollback()
    assert await count_workflow_plans(session, workspace_id, project_id) == 0
