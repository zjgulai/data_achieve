"""队列执行与调度器共用任务护栏的测试。

入队后任务被暂停时，worker 不得执行。
任务正在运行时，worker 不得并发执行。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.services.collector_service import CollectionCallResult
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

@pytest.mark.asyncio
async def test_mark_finished_mirrors_provider_run_id_in_current_transaction(
    session: AsyncSession,
) -> None:
    workspace_id, task_id = await _seed_task(session, "enabled")
    task = await session.get(CollectionTask, task_id)
    assert task is not None
    run = Run(
        workspace_id=workspace_id,
        project_id=task.project_id,
        task_id=task.id,
        status="running",
        execution_mode="live",
        trigger="mcp",
        records_count=0,
    )
    session.add(run)
    await session.flush()
    task_run = TaskRun(
        task_id=task.id,
        workspace_id=workspace_id,
        status="running",
        records_count=0,
        entities_count=0,
        logs=[],
        created_at=datetime.now(UTC),
        run_id=run.id,
    )
    session.add(task_run)
    await session.flush()
    call = RunCollectorCall(session)
    call._previous_task_status[task.id] = "enabled"
    await call._mark_finished(
        task_run,
        task,
        CollectionCallResult(
            status="success",
            records_count=1,
            entities_count=0,
            collector_type="exa_agent",
            endpoint_type="exa_agent_research",
            unit="run",
            quantity=Decimal("1"),
            unit_price=Decimal("0.1"),
            total_cost_usd=Decimal("0.1"),
        ),
        [{"provider_run_id": "agent_run_123"}],
    )
    await session.flush()
    await session.refresh(run)
    assert task_run.provider_run_id == "agent_run_123"
    assert run.provider_run_id == "agent_run_123"
