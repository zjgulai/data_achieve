"""队列执行与调度器共用任务护栏的测试。

入队后任务被暂停时，worker 不得执行。
任务正在运行时，worker 不得并发执行。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.services.exceptions import (
    TaskAlreadyRunningError,
    TaskNotRunnableError,
)
from data_intelligence_hub.services.run_collector_call import RunCollectorCall


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
    async with factory() as current:
        yield current
    await engine.dispose()


async def _seed_task(session: AsyncSession, status: str) -> tuple[uuid.UUID, uuid.UUID]:
    user = User(email="guard@example.com", password_hash="x", name="Owner")
    session.add(user)
    await session.flush()
    workspace = Workspace(name="Guard", slug="guard-ws", owner_id=user.id)
    session.add(workspace)
    await session.flush()
    session.add(
        WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
    )
    project = Project(
        workspace_id=workspace.id,
        name="Guard Project",
        domain="tiktok",
        owner_id=user.id,
    )
    session.add(project)
    await session.flush()
    source = Source(
        workspace_id=workspace.id,
        project_id=project.id,
        name="Guard source",
        type="tikhub_social",
        config={},
        enabled=True,
    )
    session.add(source)
    await session.flush()
    task = CollectionTask(
        workspace_id=workspace.id,
        project_id=project.id,
        source_id=source.id,
        collector_type="tikhub_social",
        name="Guard task",
        status=status,
        config={"endpoint_type": "tikhub_tiktok_search_web", "keyword": "x"},
    )
    session.add(task)
    await session.commit()
    return workspace.id, task.id


@pytest.mark.asyncio
async def test_paused_task_is_rejected(session: AsyncSession) -> None:
    workspace_id, task_id = await _seed_task(session, "paused")
    run = SimpleNamespace(id=uuid.uuid4(), workspace_id=workspace_id, task_id=task_id)
    with pytest.raises(TaskNotRunnableError):
        await RunCollectorCall(session)(run)


@pytest.mark.asyncio
async def test_running_task_is_rejected(session: AsyncSession) -> None:
    workspace_id, task_id = await _seed_task(session, "running")
    run = SimpleNamespace(id=uuid.uuid4(), workspace_id=workspace_id, task_id=task_id)
    with pytest.raises(TaskAlreadyRunningError):
        await RunCollectorCall(session)(run)
