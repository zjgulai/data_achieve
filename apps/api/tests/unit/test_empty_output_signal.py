"""连续空产出信号的行为测试。

一次空产出可能是正常的。连续三次说明来源或参数已经失效，
而运行本身仍然不带错误。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.entity import Entity, EntitySnapshot
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.signal import Signal
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services.signal_service import (
    _consecutive_empty,
    detect_empty_output_anomaly,
)


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
    async with factory() as db_session:
        yield db_session
    await engine.dispose()


async def _seed_task_with_runs(
    session: AsyncSession,
    *,
    statuses: list[str],
    with_snapshot: bool = True,
) -> tuple[Workspace, CollectionTask, TaskRun]:
    """建一个任务，按给定状态倒序写入运行记录。

    ``statuses`` 的第一个元素是最新的运行。
    """
    now = datetime.now(UTC)
    user = User(email="empty@example.com", password_hash="test-hash", name="Empty")
    session.add(user)
    await session.flush()

    workspace = Workspace(name="Empty WS", slug="empty-ws", owner_id=user.id)
    session.add(workspace)
    await session.flush()

    project = Project(
        workspace_id=workspace.id, name="Empty Project", domain="ecommerce", owner_id=user.id
    )
    session.add(project)
    await session.flush()

    source = Source(
        workspace_id=workspace.id,
        project_id=project.id,
        name="Empty Source",
        type="manual_json",
        config={},
    )
    session.add(source)
    await session.flush()

    task = CollectionTask(
        workspace_id=workspace.id,
        project_id=project.id,
        source_id=source.id,
        collector_type="manual_json",
        name="Empty Task",
        status="active",
    )
    session.add(task)
    await session.flush()

    latest: TaskRun | None = None
    for index, status in enumerate(statuses):
        run = TaskRun(
            task_id=task.id,
            workspace_id=workspace.id,
            status=status,
            started_at=now - timedelta(hours=index),
            finished_at=now - timedelta(hours=index),
            records_count=1 if status == "success" else 0,
            entities_count=0,
            error_message=None,
            error_traceback=None,
            logs=[],
            created_at=now - timedelta(hours=index),
        )
        session.add(run)
        await session.flush()
        if index == 0:
            latest = run

    if with_snapshot:
        entity = Entity(
            workspace_id=workspace.id,
            project_id=project.id,
            entity_type="manual_record",
            external_id="empty-1",
            name="Empty Entity",
            domain="ecommerce",
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(entity)
        await session.flush()

        record = RawRecord(
            workspace_id=workspace.id,
            project_id=project.id,
            source_id=source.id,
            task_run_id=latest.id if latest else None,
            record_type="manual_record",
            source_url="https://example.com",
            content={"name": "seed"},
            content_hash="seed-hash",
            collected_at=now,
            created_at=now,
        )
        session.add(record)
        await session.flush()

        snapshot = EntitySnapshot(
            entity_id=entity.id,
            raw_record_id=record.id,
            snapshot_data={"name": "seed"},
            metrics={},
            captured_at=now,
            created_at=now,
        )
        session.add(snapshot)
        await session.flush()

    await session.commit()
    assert latest is not None
    return workspace, task, latest


def test_consecutive_empty_counts_only_leading_empties() -> None:
    now = datetime.now(UTC)

    def run(status: str) -> TaskRun:
        return TaskRun(
            task_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            status=status,
            started_at=now,
            finished_at=now,
            records_count=0,
            entities_count=0,
            error_message=None,
            error_traceback=None,
            logs=[],
            created_at=now,
        )

    assert _consecutive_empty([run("empty"), run("empty"), run("success"), run("empty")]) == 2
    assert _consecutive_empty([run("success"), run("empty")]) == 0
    assert _consecutive_empty([]) == 0


@pytest.mark.asyncio
async def test_three_consecutive_empty_runs_raise_an_anomaly(
    session: AsyncSession,
) -> None:
    workspace, task, latest = await _seed_task_with_runs(
        session, statuses=["empty", "empty", "empty"]
    )

    signal = await detect_empty_output_anomaly(session, workspace, task, latest)

    assert signal is not None
    assert signal.signal_type == "empty_output_anomaly"
    assert signal.severity == "medium"
    assert signal.metadata_json["consecutive_empty_runs"] == 3
    assert signal.metadata_json["task_run_id"] == str(latest.id)


@pytest.mark.asyncio
async def test_five_consecutive_empty_runs_raise_high_severity(
    session: AsyncSession,
) -> None:
    workspace, task, latest = await _seed_task_with_runs(
        session, statuses=["empty"] * 5
    )

    signal = await detect_empty_output_anomaly(session, workspace, task, latest)

    assert signal is not None
    assert signal.signal_type == "empty_output_anomaly"
    assert signal.severity == "high"
    assert signal.metadata_json["consecutive_empty_runs"] == 5


@pytest.mark.asyncio
async def test_two_consecutive_empty_runs_do_not_raise(
    session: AsyncSession,
) -> None:
    workspace, task, latest = await _seed_task_with_runs(
        session, statuses=["empty", "empty", "success"]
    )

    signal = await detect_empty_output_anomaly(session, workspace, task, latest)

    assert signal is None


@pytest.mark.asyncio
async def test_non_empty_run_is_ignored(session: AsyncSession) -> None:
    workspace, task, latest = await _seed_task_with_runs(
        session, statuses=["success", "empty", "empty", "empty"]
    )

    signal = await detect_empty_output_anomaly(session, workspace, task, latest)

    assert signal is None


@pytest.mark.asyncio
async def test_source_without_snapshot_cannot_attach_a_signal(
    session: AsyncSession,
) -> None:
    """没有任何快照的来源挂不上信号，此时不报错也不创建。"""
    workspace, task, latest = await _seed_task_with_runs(
        session, statuses=["empty", "empty", "empty"], with_snapshot=False
    )

    signal = await detect_empty_output_anomaly(session, workspace, task, latest)

    assert signal is None
    remaining = (await session.execute(select(Signal))).scalars().all()
    assert list(remaining) == []