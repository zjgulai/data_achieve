"""搜索监控：创建、状态切换与新结果判定。"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.entity import Entity, EntitySnapshot
from data_intelligence_hub.models.notification import Notification
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.signal import Signal
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services.monitor_service import (
    create_monitor,
    list_monitors,
    process_monitor_run,
    set_monitor_status,
)


@pytest_asyncio.fixture()
async def session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await _seed(factory)
    yield factory
    await engine.dispose()


async def _seed(factory: async_sessionmaker[AsyncSession]) -> None:
    ids = {
        "user": uuid.uuid4(),
        "workspace": uuid.uuid4(),
        "project": uuid.uuid4(),
    }
    async with factory() as session:
        session.add_all(
            [
                User(
                    id=ids["user"],
                    email="monitor@example.com",
                    password_hash="x",
                    name="Monitor",
                    status="active",
                ),
                Workspace(
                    id=ids["workspace"],
                    name="Monitor WS",
                    slug="monitor-ws",
                    owner_id=ids["user"],
                ),
                Project(
                    id=ids["project"],
                    workspace_id=ids["workspace"],
                    name="Monitor Project",
                    domain="mixed",
                    status="active",
                    owner_id=ids["user"],
                ),
            ]
        )
        await session.commit()
    _seed.ids = ids  # type: ignore[attr-defined]


def _ids() -> dict[str, uuid.UUID]:
    return _seed.ids  # type: ignore[attr-defined]


async def _workspace(session: AsyncSession) -> Workspace:
    workspace = await session.get(Workspace, _ids()["workspace"])
    assert workspace is not None
    return workspace


@pytest.mark.asyncio
async def test_create_monitor_builds_task_and_cron(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        workspace = await _workspace(session)
        monitor = await create_monitor(
            session,
            workspace=workspace,
            project_id=_ids()["project"],
            name="Exa 定价",
            endpoint_type="exa_search_lite",
            params={"query": "exa pricing"},
            interval_hours=6,
        )
        task = await session.get(CollectionTask, monitor.task_id)
        assert task is not None
        assert task.schedule_cron == "0 */6 * * *"
        assert task.status == "enabled"
        assert task.config["monitor_id"] == str(monitor.id)
        assert task.config["search_type"] == "lite"

        await set_monitor_status(session, monitor, "paused")
        await session.refresh(task)
        assert task.status == "paused"
        listed = await list_monitors(session, workspace_id=workspace.id)
        assert [item.id for item in listed] == [monitor.id]


@pytest.mark.asyncio
async def test_monitor_stores_creating_key_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        workspace = await _workspace(session)
        key_id = uuid.uuid4()
        monitor = await create_monitor(
            session,
            workspace=workspace,
            project_id=_ids()["project"],
            name="keyed",
            endpoint_type="exa_search_lite",
            params={"query": "q"},
            interval_hours=1,
            project_key_id=key_id,
        )
    assert monitor.project_key_id == key_id


@pytest.mark.asyncio
async def test_monitor_defaults_to_null_key_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        workspace = await _workspace(session)
        monitor = await create_monitor(
            session,
            workspace=workspace,
            project_id=_ids()["project"],
            name="unkeyed",
            endpoint_type="exa_search_lite",
            params={"query": "q"},
            interval_hours=1,
        )
    assert monitor.project_key_id is None


@pytest.mark.asyncio
async def test_process_monitor_run_emits_signal_for_new_urls(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        workspace = await _workspace(session)
        monitor = await create_monitor(
            session,
            workspace=workspace,
            project_id=_ids()["project"],
            name="新闻",
            endpoint_type="exa_search_lite",
            params={"query": "ai news"},
            interval_hours=1,
        )
        task = await session.get(CollectionTask, monitor.task_id)
        assert task is not None

        run1 = await _run_with_urls(session, task, ["https://a.example", "https://b.example"])
        first = await process_monitor_run(session, task, run1)
        assert first == 2
        await session.refresh(monitor)
        assert monitor.last_new_count == 2

        run2 = await _run_with_urls(
            session, task, ["https://a.example", "https://b.example", "https://c.example"]
        )
        second = await process_monitor_run(session, task, run2)
        assert second == 1
        await session.refresh(monitor)
        assert monitor.last_new_count == 1

        signals = (
            await session.execute(select(Signal).where(Signal.signal_type == "new_search_result"))
        ).scalars().all()
        assert len(signals) == 2
        assert signals[-1].current_value == 1.0

        snapshots = (
            await session.execute(select(EntitySnapshot))
        ).scalars().all()
        assert len(snapshots) == 2

        entity = (
            await session.execute(
                select(Entity).where(Entity.entity_type == "monitor")
            )
        ).scalar_one()
        assert entity.external_id == str(monitor.id)
        assert entity.latest_snapshot_id is not None

        notifications = (
            await session.execute(select(Notification))
        ).scalars().all()
        assert len(notifications) == 2
        assert "2 条新结果" in notifications[0].title


@pytest.mark.asyncio
async def test_process_monitor_run_ignores_regular_tasks(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        workspace = await _workspace(session)
        source = Source(
            workspace_id=workspace.id,
            project_id=_ids()["project"],
            name="plain source",
            type="exa_search",
            url=None,
            config={},
            schedule_cron=None,
            enabled=True,
        )
        session.add(source)
        await session.flush()
        task = CollectionTask(
            workspace_id=workspace.id,
            project_id=_ids()["project"],
            source_id=source.id,
            collector_type="exa_search",
            name="plain",
            schedule_cron=None,
            status="enabled",
            config={"endpoint_type": "exa_search_lite"},
        )
        session.add(task)
        await session.flush()
        run = await _run_with_urls(session, task, ["https://x.example"])
        result = await process_monitor_run(session, task, run)
    assert result is None


async def _run_with_urls(
    session: AsyncSession,
    task: CollectionTask,
    urls: list[str],
) -> TaskRun:
    now = datetime.now(UTC)
    run = TaskRun(
        task_id=task.id,
        workspace_id=task.workspace_id,
        status="success",
        started_at=now,
        finished_at=now,
        records_count=len(urls),
        entities_count=0,
        logs=[],
        created_at=now,
    )
    session.add(run)
    await session.flush()
    for url in urls:
        session.add(
            RawRecord(
                workspace_id=task.workspace_id,
                project_id=task.project_id,
                source_id=task.source_id,
                task_run_id=run.id,
                record_type="search_result",
                source_url=url,
                content={"url": url},
                content_hash=hashlib.sha256(f"{run.id}:{url}".encode()).hexdigest(),
                collected_at=now,
                created_at=now,
            )
        )
    await session.flush()
    return run