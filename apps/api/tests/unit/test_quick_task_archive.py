from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.maintenance.quick_task_archive import (
    archive_quick_test_tasks,
)
from data_intelligence_hub.models import (
    Base,
    CollectionTask,
    Project,
    Source,
    TaskRun,
    User,
    Workspace,
)
from data_intelligence_hub.repositories.workspaces import DEMO_WORKSPACE_SLUG


@pytest.mark.asyncio
async def test_quick_task_archive_dry_run_reports_without_writes() -> None:
    session_factory = await _create_session_factory()
    now = datetime.now(UTC)

    async with session_factory() as session:
        fixture = await _create_archive_fixture(session, now)
        await session.commit()

    async with session_factory() as session:
        report = await archive_quick_test_tasks(session, dry_run=True)
        await session.commit()

    assert report.dry_run is True
    assert report.workspace_slug == DEMO_WORKSPACE_SLUG
    assert report.total == 4
    assert report.breakdown == {
        "[quick] [test]": 2,
        "[quick] [probe]": 1,
        "other": 1,
    }
    assert report.updated == 0
    assert len(report.samples) == 4
    samples = {sample.name: sample for sample in report.samples}
    assert samples["[quick] [test] alpha"].latest_run_status == "success"
    assert samples["[quick] [quick] [test] legacy"].latest_run_status is None
    assert samples["[quick] [probe] gamma"].latest_run_status == "failed"
    assert samples["[quick] ad hoc"].latest_run_status is None

    payload = report.to_dict()
    assert payload["dry_run"] is True
    assert payload["workspace"]["slug"] == DEMO_WORKSPACE_SLUG
    assert payload["total"] == 4
    assert payload["updated"] == 0

    async with session_factory() as session:
        statuses = await _status_by_name(session, fixture["all_task_ids"])
    assert statuses == {
        "[quick] [test] alpha": "enabled",
        "[quick] [quick] [test] legacy": "enabled",
        "[quick] [probe] gamma": "enabled",
        "[quick] ad hoc": "enabled",
        "[quick] [test] paused": "paused",
        "nightly quick probe": "enabled",
        "[quick] [test] foreign": "enabled",
    }


@pytest.mark.asyncio
async def test_quick_task_archive_execute_pauses_selected_tasks() -> None:
    session_factory = await _create_session_factory()
    now = datetime.now(UTC)

    async with session_factory() as session:
        fixture = await _create_archive_fixture(session, now)
        await session.commit()

    async with session_factory() as session:
        report = await archive_quick_test_tasks(session, dry_run=False)
        await session.commit()

    assert report.dry_run is False
    assert report.total == 4
    assert report.updated == 4

    async with session_factory() as session:
        statuses = await _status_by_name(session, fixture["all_task_ids"])
    assert statuses == {
        "[quick] [test] alpha": "paused",
        "[quick] [quick] [test] legacy": "paused",
        "[quick] [probe] gamma": "paused",
        "[quick] ad hoc": "paused",
        "[quick] [test] paused": "paused",
        "nightly quick probe": "enabled",
        "[quick] [test] foreign": "enabled",
    }


@pytest.mark.asyncio
async def test_quick_task_archive_is_idempotent() -> None:
    session_factory = await _create_session_factory()
    now = datetime.now(UTC)

    async with session_factory() as session:
        await _create_archive_fixture(session, now)
        await session.commit()

    async with session_factory() as session:
        first = await archive_quick_test_tasks(session, dry_run=False)
        await session.commit()

    async with session_factory() as session:
        second = await archive_quick_test_tasks(session, dry_run=False)
        await session.commit()

    async with session_factory() as session:
        third = await archive_quick_test_tasks(session, dry_run=True)

    assert first.total == 4
    assert first.updated == 4
    assert second.total == 0
    assert second.updated == 0
    assert third.total == 0
    assert third.updated == 0
    assert third.breakdown == {
        "[quick] [test]": 0,
        "[quick] [probe]": 0,
        "other": 0,
    }


async def _create_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _create_archive_fixture(
    session: AsyncSession,
    now: datetime,
) -> dict[str, Any]:
    user = User(
        email="archive-owner@example.com",
        password_hash="hashed-password",
        name="Archive Owner",
        status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    await session.flush()

    demo_workspace = Workspace(
        name="Demo Workspace",
        slug=DEMO_WORKSPACE_SLUG,
        owner_id=user.id,
        created_at=now,
        updated_at=now,
    )
    other_workspace = Workspace(
        name="Other Workspace",
        slug="other-workspace",
        owner_id=user.id,
        created_at=now,
        updated_at=now,
    )
    session.add_all([demo_workspace, other_workspace])
    await session.flush()

    demo_project = Project(
        workspace_id=demo_workspace.id,
        name="Demo Project",
        description=None,
        domain="osint",
        status="active",
        owner_id=user.id,
        created_at=now,
        updated_at=now,
    )
    other_project = Project(
        workspace_id=other_workspace.id,
        name="Other Project",
        description=None,
        domain="osint",
        status="active",
        owner_id=user.id,
        created_at=now,
        updated_at=now,
    )
    session.add_all([demo_project, other_project])
    await session.flush()

    tasks = {
        "test_enabled": await _create_task(
            session,
            workspace_id=demo_workspace.id,
            project_id=demo_project.id,
            name="[quick] [test] alpha",
            status="enabled",
            created_at=now,
            run_statuses=("failed", "success"),
        ),
        "legacy_test_enabled": await _create_task(
            session,
            workspace_id=demo_workspace.id,
            project_id=demo_project.id,
            name="[quick] [quick] [test] legacy",
            status="enabled",
            created_at=now + timedelta(seconds=1),
        ),
        "probe_enabled": await _create_task(
            session,
            workspace_id=demo_workspace.id,
            project_id=demo_project.id,
            name="[quick] [probe] gamma",
            status="enabled",
            created_at=now + timedelta(seconds=2),
            run_statuses=("failed",),
        ),
        "other_enabled": await _create_task(
            session,
            workspace_id=demo_workspace.id,
            project_id=demo_project.id,
            name="[quick] ad hoc",
            status="enabled",
            created_at=now + timedelta(seconds=3),
        ),
        "paused": await _create_task(
            session,
            workspace_id=demo_workspace.id,
            project_id=demo_project.id,
            name="[quick] [test] paused",
            status="paused",
            created_at=now + timedelta(seconds=4),
        ),
        "non_quick": await _create_task(
            session,
            workspace_id=demo_workspace.id,
            project_id=demo_project.id,
            name="nightly quick probe",
            status="enabled",
            created_at=now + timedelta(seconds=5),
        ),
        "foreign": await _create_task(
            session,
            workspace_id=other_workspace.id,
            project_id=other_project.id,
            name="[quick] [test] foreign",
            status="enabled",
            created_at=now + timedelta(seconds=6),
        ),
    }
    return {
        "all_task_ids": [task.id for task in tasks.values()],
        "tasks": tasks,
    }


async def _create_task(
    session: AsyncSession,
    *,
    workspace_id: Any,
    project_id: Any,
    name: str,
    status: str,
    created_at: datetime,
    run_statuses: tuple[str, ...] = (),
) -> CollectionTask:
    source = Source(
        workspace_id=workspace_id,
        project_id=project_id,
        name=name,
        type="manual_json",
        url=None,
        config={},
        schedule_cron=None,
        enabled=True,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(source)
    await session.flush()

    task = CollectionTask(
        workspace_id=workspace_id,
        project_id=project_id,
        source_id=source.id,
        collector_type="manual_json",
        name=name,
        schedule_cron=None,
        status=status,
        config={},
        success_count=0,
        failure_count=0,
        last_run_at=None,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(task)
    await session.flush()

    for index, run_status in enumerate(run_statuses):
        run_created_at = created_at + timedelta(seconds=index + 1)
        session.add(
            TaskRun(
                task_id=task.id,
                workspace_id=workspace_id,
                status=run_status,
                started_at=run_created_at,
                finished_at=run_created_at,
                records_count=0,
                entities_count=0,
                error_message=None,
                error_traceback=None,
                logs=[],
                created_at=run_created_at,
            )
        )
    await session.flush()
    return task


async def _status_by_name(
    session: AsyncSession,
    task_ids: list[Any],
) -> dict[str, str]:
    result = await session.execute(
        select(CollectionTask).where(CollectionTask.id.in_(task_ids))
    )
    return {task.name: task.status for task in result.scalars().all()}
