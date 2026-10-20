"""TaskRun 幂等唯一约束。

守三件事：

1. 新运行把幂等键摘要写进列，不再只写 logs。
2. 同一任务下同一个摘要只能有一行，第二行会被唯一索引拒绝。
3. 历史行（列为空的旧数据）仍能通过 logs 回退被查到。

第 3 条只为兼容既有数据。回退保留一个发布周期，
之后另开迁移删除回退分支并回填历史行。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.schemas.task import TaskRunResponse

_HASH = "a" * 64
_OTHER_HASH = "b" * 64

Scenario = Callable[[AsyncSession], Awaitable[None]]


async def _seed_task(session: AsyncSession) -> tuple[Workspace, CollectionTask]:
    """建一个最小可用的 workspace + project + source + task。"""
    user = User(email="idem@example.com", password_hash="x", name="Idem")
    session.add(user)
    await session.flush()

    workspace = Workspace(name="Idem", slug="idem", owner_id=user.id)
    session.add(workspace)
    await session.flush()

    project = Project(
        workspace_id=workspace.id,
        name="Idem Project",
        domain="ecommerce",
        owner_id=user.id,
    )
    session.add(project)
    await session.flush()

    source = Source(
        workspace_id=workspace.id,
        project_id=project.id,
        name="Idem Source",
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
        name="Idem Task",
        status="active",
    )
    session.add(task)
    await session.commit()
    return workspace, task


def _run(
    *,
    task: CollectionTask,
    workspace: Workspace,
    idempotency_key_hash: str | None,
    logs: list[dict[str, object]] | None = None,
) -> TaskRun:
    now = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    return TaskRun(
        task_id=task.id,
        workspace_id=workspace.id,
        status="success",
        started_at=now,
        finished_at=now,
        records_count=1,
        entities_count=0,
        error_message=None,
        error_traceback=None,
        logs=logs or [],
        created_at=now,
        idempotency_key_hash=idempotency_key_hash,
    )


async def _with_session(callback: Scenario) -> None:
    """在内存 SQLite 上跑一段用例。"""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            await callback(session)
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_column_persists_idempotency_hash() -> None:
    """新运行写入列。"""
    captured: dict[str, str | None] = {}

    async def scenario(session: AsyncSession) -> None:
        workspace, task = await _seed_task(session)
        run = _run(task=task, workspace=workspace, idempotency_key_hash=_HASH)
        session.add(run)
        await session.commit()
        stored = await session.scalar(select(TaskRun.idempotency_key_hash))
        captured["hash"] = stored

    await _with_session(scenario)
    assert captured["hash"] == _HASH


@pytest.mark.anyio
async def test_duplicate_hash_on_same_task_is_rejected() -> None:
    """同一任务下重复摘要必须被唯一索引拒绝。"""
    rejected: dict[str, bool] = {}

    async def scenario(session: AsyncSession) -> None:
        workspace, task = await _seed_task(session)
        session.add(_run(task=task, workspace=workspace, idempotency_key_hash=_HASH))
        await session.commit()
        session.add(_run(task=task, workspace=workspace, idempotency_key_hash=_HASH))
        try:
            await session.commit()
        except (IntegrityError, OperationalError):
            rejected["value"] = True
            await session.rollback()
        else:
            rejected["value"] = False

    await _with_session(scenario)
    assert rejected["value"] is True, "重复的 (task_id, idempotency_key_hash) 未被拒绝"


@pytest.mark.anyio
async def test_null_hash_allows_multiple_runs() -> None:
    """不带幂等键的运行不受唯一索引约束。"""
    counted: dict[str, int] = {}

    async def scenario(session: AsyncSession) -> None:
        workspace, task = await _seed_task(session)
        session.add(_run(task=task, workspace=workspace, idempotency_key_hash=None))
        session.add(_run(task=task, workspace=workspace, idempotency_key_hash=None))
        await session.commit()
        total = await session.scalar(
            select(func.count()).select_from(TaskRun).where(TaskRun.idempotency_key_hash.is_(None))
        )
        counted["value"] = int(total or 0)

    await _with_session(scenario)
    assert counted["value"] == 2


@pytest.mark.anyio
async def test_different_hashes_on_same_task_are_allowed() -> None:
    """同一任务下不同摘要各自成立。"""

    async def scenario(session: AsyncSession) -> None:
        workspace, task = await _seed_task(session)
        session.add(_run(task=task, workspace=workspace, idempotency_key_hash=_HASH))
        session.add(_run(task=task, workspace=workspace, idempotency_key_hash=_OTHER_HASH))
        await session.commit()

    await _with_session(scenario)


@pytest.mark.anyio
async def test_same_hash_across_tasks_is_allowed() -> None:
    """唯一索引按任务隔离，跨任务同摘要不受约束。"""

    async def scenario(session: AsyncSession) -> None:
        workspace, first = await _seed_task(session)

        second_source = Source(
            workspace_id=workspace.id,
            project_id=first.project_id,
            name="Second Source",
            type="manual_json",
            config={},
        )
        session.add(second_source)
        await session.flush()

        second = CollectionTask(
            workspace_id=workspace.id,
            project_id=first.project_id,
            source_id=second_source.id,
            collector_type="manual_json",
            name="Second Task",
            status="active",
        )
        session.add(second)
        await session.flush()

        session.add(_run(task=first, workspace=workspace, idempotency_key_hash=_HASH))
        session.add(_run(task=second, workspace=workspace, idempotency_key_hash=_HASH))
        await session.commit()

    await _with_session(scenario)


@pytest.mark.anyio
async def test_response_schema_reads_column_first() -> None:
    """响应优先读列。列为空时回退解析 logs。"""
    observed: dict[str, str | None] = {}

    async def scenario(session: AsyncSession) -> None:
        workspace, task = await _seed_task(session)

        with_column = _run(task=task, workspace=workspace, idempotency_key_hash=_HASH)
        session.add(with_column)

        legacy_logs = [
            {
                "step": "idempotency_key_recorded",
                "scope": "task_manual_run",
                "idempotency_key_hash": _OTHER_HASH,
            }
        ]
        legacy = _run(
            task=task,
            workspace=workspace,
            idempotency_key_hash=None,
            logs=legacy_logs,
        )
        session.add(legacy)
        await session.commit()

        observed["fresh"] = TaskRunResponse.from_run(with_column).idempotency_key_hash
        observed["legacy"] = TaskRunResponse.from_run(legacy).idempotency_key_hash

    await _with_session(scenario)
    assert observed["fresh"] == _HASH
    assert observed["legacy"] == _OTHER_HASH, "历史行必须能从 logs 回退读出摘要"


def test_unique_index_is_declared_on_model() -> None:
    """索引必须声明在模型上，否则 create_all 不会建它。"""
    index_names = {index.name for index in TaskRun.__table__.indexes}
    assert "uq_task_runs_task_idempotency" in index_names

    index = next(
        item for item in TaskRun.__table__.indexes
        if item.name == "uq_task_runs_task_idempotency"
    )
    assert index.unique is True
    assert [column.name for column in index.columns] == [
        "task_id",
        "idempotency_key_hash",
    ]
