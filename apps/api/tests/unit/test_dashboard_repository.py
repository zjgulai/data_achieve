"""仪表盘仓库查询的活跃任务口径测试：已归档任务不计入。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import (
    Base,
    CollectionTask,
    Project,
    Source,
    TaskRun,
    User,
    Workspace,
)
from data_intelligence_hub.repositories.dashboard import (
    count_latest_failed_tasks,
    get_latest_task_run_at,
    list_recent_failures,
    task_run_status_counts,
)

_NOW = datetime(2026, 10, 19, 8, 0, tzinfo=UTC)


async def _create_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _seed_workspace(session: AsyncSession) -> tuple[Workspace, Project]:
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    user = User(
        id=user_id,
        email=f"{user_id}@example.com",
        password_hash="hash",
        name="Owner",
        status="active",
        created_at=_NOW,
        updated_at=_NOW,
    )
    workspace = Workspace(
        id=workspace_id,
        name="Dashboard Workspace",
        slug=f"dashboard-{workspace_id}",
        owner_id=user_id,
        created_at=_NOW,
        updated_at=_NOW,
    )
    project = Project(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        name="Dashboard Project",
        description=None,
        domain="ecommerce",
        status="active",
        owner_id=user_id,
        created_at=_NOW,
        updated_at=_NOW,
    )
    session.add_all([user, workspace, project])
    await session.flush()
    return workspace, project


async def _seed_task(
    session: AsyncSession,
    workspace: Workspace,
    project: Project,
    *,
    name: str,
    status: str,
    runs: list[tuple[str, datetime]],
) -> CollectionTask:
    source = Source(
        workspace_id=workspace.id,
        project_id=project.id,
        name=f"{name} Source",
        type="manual_json",
        url=None,
        config={},
        schedule_cron=None,
        enabled=True,
        created_at=_NOW,
        updated_at=_NOW,
    )
    session.add(source)
    await session.flush()

    task = CollectionTask(
        workspace_id=workspace.id,
        project_id=project.id,
        source_id=source.id,
        collector_type="manual_json",
        name=name,
        schedule_cron=None,
        status=status,
        config={},
        success_count=0,
        failure_count=0,
        last_run_at=None,
        created_at=_NOW,
        updated_at=_NOW,
    )
    session.add(task)
    await session.flush()

    for run_status, finished_at in runs:
        session.add(
            TaskRun(
                task_id=task.id,
                workspace_id=workspace.id,
                status=run_status,
                started_at=finished_at - timedelta(minutes=1),
                finished_at=finished_at,
                records_count=0,
                entities_count=0,
                error_message="boom" if run_status == "failed" else None,
                error_traceback=None,
                logs=[],
                created_at=finished_at,
            )
        )
    await session.flush()
    return task


@pytest.mark.asyncio
async def test_paused_task_failure_not_counted_in_failed_tasks() -> None:
    session_factory = await _create_session_factory()
    async with session_factory() as session:
        workspace, project = await _seed_workspace(session)
        await _seed_task(
            session,
            workspace,
            project,
            name="Paused Task",
            status="paused",
            runs=[("failed", _NOW)],
        )
        await session.commit()

        failed_tasks = await count_latest_failed_tasks(
            session, workspace.id, project_id=None, domain=None
        )

    assert failed_tasks == 0


@pytest.mark.asyncio
async def test_disabled_task_failure_not_counted_in_failed_tasks() -> None:
    session_factory = await _create_session_factory()
    async with session_factory() as session:
        workspace, project = await _seed_workspace(session)
        await _seed_task(
            session,
            workspace,
            project,
            name="Disabled Task",
            status="disabled",
            runs=[("failed", _NOW)],
        )
        await session.commit()

        failed_tasks = await count_latest_failed_tasks(
            session, workspace.id, project_id=None, domain=None
        )

    assert failed_tasks == 0


@pytest.mark.asyncio
async def test_enabled_task_failure_still_counted_in_failed_tasks() -> None:
    session_factory = await _create_session_factory()
    async with session_factory() as session:
        workspace, project = await _seed_workspace(session)
        await _seed_task(
            session,
            workspace,
            project,
            name="Enabled Task",
            status="enabled",
            runs=[("failed", _NOW)],
        )
        await session.commit()

        failed_tasks = await count_latest_failed_tasks(
            session, workspace.id, project_id=None, domain=None
        )

    assert failed_tasks == 1


@pytest.mark.asyncio
async def test_recent_failures_excludes_paused_task_runs() -> None:
    session_factory = await _create_session_factory()
    async with session_factory() as session:
        workspace, project = await _seed_workspace(session)
        paused_task = await _seed_task(
            session,
            workspace,
            project,
            name="Paused Task",
            status="paused",
            runs=[("failed", _NOW)],
        )
        enabled_task = await _seed_task(
            session,
            workspace,
            project,
            name="Enabled Task",
            status="enabled",
            runs=[("failed", _NOW - timedelta(hours=1))],
        )
        await session.commit()

        failures = await list_recent_failures(
            session, workspace.id, project_id=None, domain=None, limit=10
        )

    assert [row.task_id for row in failures] == [enabled_task.id]
    assert paused_task.id not in {row.task_id for row in failures}


@pytest.mark.asyncio
async def test_task_run_status_counts_excludes_paused_task_runs() -> None:
    session_factory = await _create_session_factory()
    async with session_factory() as session:
        workspace, project = await _seed_workspace(session)
        await _seed_task(
            session,
            workspace,
            project,
            name="Paused Task",
            status="paused",
            runs=[("success", _NOW - timedelta(hours=2)), ("failed", _NOW)],
        )
        await _seed_task(
            session,
            workspace,
            project,
            name="Enabled Task",
            status="enabled",
            runs=[("success", _NOW - timedelta(hours=3)), ("failed", _NOW - timedelta(hours=1))],
        )
        await session.commit()

        counts = await task_run_status_counts(
            session,
            workspace.id,
            project_id=None,
            domain=None,
            from_time=None,
            to_time=None,
        )

    assert counts == {"success": 1, "failed": 1}
    assert sum(counts.values()) == 2


async def test_latest_task_run_at_excludes_paused_task_runs() -> None:
    session_factory = await _create_session_factory()
    async with session_factory() as session:
        workspace, project = await _seed_workspace(session)
        await _seed_task(
            session,
            workspace,
            project,
            name="Paused Task",
            status="paused",
            runs=[("failed", _NOW)],
        )
        await _seed_task(
            session,
            workspace,
            project,
            name="Enabled Task",
            status="enabled",
            runs=[("success", _NOW - timedelta(hours=4))],
        )
        await session.commit()

        latest = await get_latest_task_run_at(
            session,
            workspace.id,
            project_id=None,
            domain=None,
            from_time=None,
            to_time=None,
        )

    # 最近的运行属于已归档任务，因此「最近采集」取活跃任务那条。
    # sqlite 返回无时区的时间，按 UTC 解读。
    assert latest is not None
    assert latest.replace(tzinfo=UTC) == _NOW - timedelta(hours=4)
