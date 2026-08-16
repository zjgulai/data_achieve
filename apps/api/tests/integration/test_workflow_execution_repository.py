from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workflow_execution import (
    StepRun,
    WorkflowRun,
    WorkflowRunRequest,
)
from data_intelligence_hub.models.workflow_plan import WorkflowPlan, WorkflowVersion
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.workflow_execution import (
    add_step_runs,
    add_workflow_run,
    add_workflow_run_request,
    count_workflow_runs,
    get_completed_workflow_run_request,
    get_project,
    get_workflow_plan,
    get_workflow_run,
    get_workflow_version,
    list_step_runs,
    list_workflow_runs,
    project_lock_statement,
    workflow_plan_lock_statement,
    workflow_version_lock_statement,
)

NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class SeedIdentity:
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    plan_id: uuid.UUID
    version_id: uuid.UUID


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


async def _seed_identity(session: AsyncSession, *, suffix: str) -> SeedIdentity:
    identity = SeedIdentity(
        user_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        plan_id=uuid.uuid4(),
        version_id=uuid.uuid4(),
    )
    session.add_all(
        [
            User(
                id=identity.user_id,
                email=f"{suffix}@example.com",
                password_hash="not-a-real-secret",
                name=suffix,
                status="active",
            ),
            Workspace(
                id=identity.workspace_id,
                name=suffix,
                slug=f"workflow-execution-{suffix}",
                owner_id=identity.user_id,
            ),
            Project(
                id=identity.project_id,
                workspace_id=identity.workspace_id,
                owner_id=identity.user_id,
                name=suffix,
                description=None,
                domain="social",
                status="active",
            ),
            WorkflowPlan(
                id=identity.plan_id,
                workspace_id=identity.workspace_id,
                project_id=identity.project_id,
                created_by_user_id=identity.user_id,
                name=suffix,
                flow_mode="periodic_monitoring",
                status="previewed",
                current_version_id=None,
                created_at=NOW,
                updated_at=NOW,
            ),
            WorkflowVersion(
                id=identity.version_id,
                workspace_id=identity.workspace_id,
                project_id=identity.project_id,
                workflow_plan_id=identity.plan_id,
                created_by_user_id=identity.user_id,
                version_number=1,
                planning_status="resolved",
                planner_contract_version="workflow_planner.v1",
                catalog_snapshot_id="sha256:" + "a" * 64,
                policy_version="policy.v1",
                mode_template_version="periodic.v1",
                query_versions={"youtube": "youtube.v1"},
                fingerprint_payload={},
                normalized_input={},
                plan_payload={},
                preview_fingerprint="sha256:" + "b" * 64,
                created_at=NOW,
            ),
        ]
    )
    await session.commit()
    return identity


def _run(
    identity: SeedIdentity,
    *,
    run_id: uuid.UUID,
    created_at: datetime,
    records_count: int = 2,
) -> WorkflowRun:
    return WorkflowRun(
        id=run_id,
        workspace_id=identity.workspace_id,
        project_id=identity.project_id,
        workflow_plan_id=identity.plan_id,
        workflow_version_id=identity.version_id,
        created_by_user_id=identity.user_id,
        execution_contract_version="workflow_execution_fixture.v1",
        execution_mode="fixture",
        status="completed",
        planner_contract_version="workflow_planner.v1",
        preview_fingerprint="sha256:" + "b" * 64,
        catalog_snapshot_id="sha256:" + "a" * 64,
        policy_version="policy.v1",
        mode_template_version="periodic.v1",
        query_versions={"youtube": "youtube.v1"},
        fixture_profile_id="fixture-primary-v1",
        fixture_profile_hash="sha256:" + "c" * 64,
        total_steps=2,
        completed_steps=2,
        records_count=records_count,
        started_at=created_at,
        finished_at=created_at + timedelta(seconds=1),
        created_at=created_at,
    )


def _step(
    identity: SeedIdentity,
    *,
    run_id: uuid.UUID,
    step_id: uuid.UUID,
    sequence: int,
) -> StepRun:
    return StepRun(
        id=step_id,
        workflow_run_id=run_id,
        workspace_id=identity.workspace_id,
        project_id=identity.project_id,
        step_ref=f"step-{sequence}",
        requirement_ref=f"requirement-{sequence}",
        sequence=sequence,
        platform="youtube",
        resource_type="content",
        operation="search_discover",
        assertion_id=f"assertion-{sequence}",
        implementation_id="youtube.v3",
        route_plan_snapshot={"requirement_ref": f"requirement-{sequence}"},
        evidence_refs=[f"evidence-{sequence}"],
        fixture_case_id=f"fixture-case-{sequence}",
        fixture_content_hash="sha256:" + f"{sequence:x}" * 64,
        input_digest="sha256:" + f"{sequence + 2:x}" * 64,
        output_digest="sha256:" + f"{sequence + 4:x}" * 64,
        idempotency_scope=f"workflow-step:{run_id}:step-{sequence}",
        idempotency_key_hash="sha256:" + f"{sequence + 6:x}" * 64,
        status="completed",
        records_count=1,
        started_at=NOW + timedelta(seconds=sequence),
        finished_at=NOW + timedelta(seconds=sequence + 1),
        created_at=NOW + timedelta(seconds=sequence),
    )


def _request(
    identity: SeedIdentity,
    *,
    run_id: uuid.UUID,
    scope: str,
    key_hash: str,
) -> WorkflowRunRequest:
    return WorkflowRunRequest(
        workspace_id=identity.workspace_id,
        project_id=identity.project_id,
        created_by_user_id=identity.user_id,
        idempotency_scope=scope,
        idempotency_key_hash=key_hash,
        request_hash="sha256:" + "d" * 64,
        workflow_run_id=run_id,
        outcome="completed",
        response_status=201,
        response_payload={"run_id": str(run_id)},
        created_at=NOW,
    )


def test_project_plan_and_version_lock_statements_compile_for_postgresql() -> None:
    identity = SeedIdentity(*(uuid.uuid4() for _ in range(5)))
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]
    statements = (
        project_lock_statement(identity.workspace_id, identity.project_id),
        workflow_plan_lock_statement(
            identity.workspace_id,
            identity.project_id,
            identity.plan_id,
        ),
        workflow_version_lock_statement(
            identity.workspace_id,
            identity.project_id,
            identity.plan_id,
            identity.version_id,
        ),
    )

    for statement in statements:
        assert "FOR UPDATE" in str(statement.compile(dialect=dialect))
        assert statement.get_execution_options()["populate_existing"] is True


@pytest.mark.asyncio
async def test_project_plan_version_reads_are_exactly_tenant_scoped(
    session: AsyncSession,
) -> None:
    first = await _seed_identity(session, suffix="repository-first")
    other = await _seed_identity(session, suffix="repository-other")

    assert await get_project(session, first.workspace_id, first.project_id)
    assert await get_workflow_plan(
        session,
        first.workspace_id,
        first.project_id,
        first.plan_id,
    )
    assert await get_workflow_version(
        session,
        first.workspace_id,
        first.project_id,
        first.plan_id,
        first.version_id,
    )
    assert (
        await get_workflow_plan(
            session,
            other.workspace_id,
            other.project_id,
            first.plan_id,
        )
        is None
    )
    assert (
        await get_workflow_version(
            session,
            first.workspace_id,
            first.project_id,
            other.plan_id,
            first.version_id,
        )
        is None
    )


@pytest.mark.asyncio
async def test_run_list_detail_steps_and_request_replay_are_exactly_scoped(
    session: AsyncSession,
) -> None:
    identity = await _seed_identity(session, suffix="repository-runs")
    other = await _seed_identity(session, suffix="repository-hidden")
    older_id = uuid.UUID("00000000-0000-0000-0000-000000000510")
    newer_low_id = uuid.UUID("00000000-0000-0000-0000-000000000511")
    newer_high_id = uuid.UUID("00000000-0000-0000-0000-000000000512")
    runs = (
        _run(identity, run_id=older_id, created_at=NOW),
        _run(identity, run_id=newer_low_id, created_at=NOW + timedelta(minutes=1)),
        _run(identity, run_id=newer_high_id, created_at=NOW + timedelta(minutes=1)),
    )
    steps = (
        _step(
            identity,
            run_id=newer_high_id,
            step_id=uuid.uuid4(),
            sequence=2,
        ),
        _step(
            identity,
            run_id=newer_high_id,
            step_id=uuid.uuid4(),
            sequence=1,
        ),
    )
    scope = f"POST:/projects/{identity.project_id}/fixture-runs"
    key_hash = "sha256:" + "e" * 64
    request = _request(
        identity,
        run_id=newer_high_id,
        scope=scope,
        key_hash=key_hash,
    )
    session.add_all([*runs, *steps, request])
    await session.commit()

    page = await list_workflow_runs(
        session,
        identity.workspace_id,
        identity.project_id,
        limit=2,
        offset=0,
    )
    assert [item.id for item in page] == [newer_high_id, newer_low_id]
    assert (
        await count_workflow_runs(
            session,
            identity.workspace_id,
            identity.project_id,
        )
        == 3
    )
    assert (
        await get_workflow_run(
            session,
            identity.workspace_id,
            identity.project_id,
            newer_high_id,
        )
    ) is runs[2]
    ordered_steps = await list_step_runs(
        session,
        identity.workspace_id,
        identity.project_id,
        newer_high_id,
    )
    assert [item.sequence for item in ordered_steps] == [1, 2]

    replay = await get_completed_workflow_run_request(
        session,
        identity.workspace_id,
        identity.project_id,
        identity.user_id,
        scope,
        key_hash,
    )
    assert replay is not None and replay.workflow_run_id == newer_high_id
    assert (
        await get_completed_workflow_run_request(
            session,
            other.workspace_id,
            other.project_id,
            identity.user_id,
            scope,
            key_hash,
        )
        is None
    )
    assert (
        await get_workflow_run(
            session,
            other.workspace_id,
            other.project_id,
            newer_high_id,
        )
        is None
    )
    assert (
        await list_step_runs(
            session,
            other.workspace_id,
            other.project_id,
            newer_high_id,
        )
        == []
    )


@pytest.mark.asyncio
async def test_insert_primitives_flush_without_commit_and_rollback_together(
    session: AsyncSession,
) -> None:
    identity = await _seed_identity(session, suffix="repository-rollback")
    run_id = uuid.uuid4()
    run = _run(identity, run_id=run_id, created_at=NOW)
    steps = (
        _step(identity, run_id=run_id, step_id=uuid.uuid4(), sequence=1),
        _step(identity, run_id=run_id, step_id=uuid.uuid4(), sequence=2),
    )
    request = _request(
        identity,
        run_id=run_id,
        scope=f"POST:/projects/{identity.project_id}/fixture-runs",
        key_hash="sha256:" + "f" * 64,
    )

    assert await add_workflow_run(session, run) is run
    assert await add_step_runs(session, steps) == steps
    assert await add_workflow_run_request(session, request) is request
    assert (
        await count_workflow_runs(
            session,
            identity.workspace_id,
            identity.project_id,
        )
        == 1
    )

    await session.rollback()
    assert (
        await count_workflow_runs(
            session,
            identity.workspace_id,
            identity.project_id,
        )
        == 0
    )


@pytest.mark.asyncio
async def test_run_pagination_fails_closed(session: AsyncSession) -> None:
    identity = await _seed_identity(session, suffix="repository-pagination")
    with pytest.raises(ValueError, match="workflow_run_pagination_invalid"):
        await list_workflow_runs(
            session,
            identity.workspace_id,
            identity.project_id,
            limit=0,
            offset=0,
        )


@pytest.mark.asyncio
async def test_run_list_and_count_share_optional_plan_version_filters(
    session: AsyncSession,
) -> None:
    identity = await _seed_identity(session, suffix="repository-filters")
    run = _run(identity, run_id=uuid.uuid4(), created_at=NOW)
    session.add(run)
    await session.commit()

    matching = await list_workflow_runs(
        session,
        identity.workspace_id,
        identity.project_id,
        workflow_plan_id=identity.plan_id,
        workflow_version_id=identity.version_id,
        limit=50,
        offset=0,
    )
    matching_total = await count_workflow_runs(
        session,
        identity.workspace_id,
        identity.project_id,
        workflow_plan_id=identity.plan_id,
        workflow_version_id=identity.version_id,
    )
    hidden = await list_workflow_runs(
        session,
        identity.workspace_id,
        identity.project_id,
        workflow_plan_id=uuid.uuid4(),
        workflow_version_id=identity.version_id,
        limit=50,
        offset=0,
    )
    hidden_total = await count_workflow_runs(
        session,
        identity.workspace_id,
        identity.project_id,
        workflow_plan_id=identity.plan_id,
        workflow_version_id=uuid.uuid4(),
    )

    assert [item.id for item in matching] == [run.id]
    assert matching_total == 1
    assert hidden == []
    assert hidden_total == 0
