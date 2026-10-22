"""运行队列 worker 装配与启动开关的单元测试。

覆盖四件事：

1. worker 跑一轮后，run 进入终态，并写了 ``run_steps`` 与等级行。
2. collector 抛异常时 run 变 failed，worker 不退出。
3. ``run_worker_enabled`` 默认关闭时 lifespan 不启动 worker。
4. ``RunCollectorCall`` 必须委托 ``execute_collector_call``。

本文件只用内存 SQLite。它不联网，也不启动真实后台循环。
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import data_intelligence_hub.main as main_module
from data_intelligence_hub.core.config import Settings
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.run import Run, RunStep
from data_intelligence_hub.models.run_evidence_grade import RunEvidenceGradeRecord
from data_intelligence_hub.models.run_ledger import RunLedgerEntry
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services import run_collector_call as collector_call_module
from data_intelligence_hub.services.collector_service import CollectionCallResult
from data_intelligence_hub.services.run_collector_call import RunCollectorCall
from data_intelligence_hub.services.run_executor_adapters import OrmRunRepository
from data_intelligence_hub.services.run_queue import enqueue_run
from data_intelligence_hub.services.run_worker_runtime import RunWorkerRuntime


class FakeCollectorCall:
    """固定返回结果的 collector 调用替身。"""

    def __init__(self, *, result: CollectionCallResult) -> None:
        self._result = result

    async def __call__(self, run: object) -> CollectionCallResult:
        return self._result


def _make_result() -> CollectionCallResult:
    return CollectionCallResult(
        status="success",
        records_count=4,
        entities_count=2,
        sample_n=4,
        source_count=1,
        window_days=7,
        collector_type="mock",
        endpoint_type="mock_endpoint",
        unit="record",
        quantity=Decimal("4"),
        unit_price=Decimal("0.250000"),
        total_cost_usd=Decimal("1.000000"),
    )


async def _make_factory() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed_context(
    session: AsyncSession,
    *,
    collector_type: str = "mock",
    task_config: dict[str, object] | None = None,
) -> tuple[Workspace, Project, CollectionTask]:
    """建工作区、项目、来源与采集任务。"""
    suffix = uuid.uuid4().hex
    config = task_config or {"endpoint_type": "mock_endpoint", "period": 7}
    owner = User(
        email=f"worker-{suffix}@example.com",
        password_hash="x",
        name="Worker Owner",
    )
    session.add(owner)
    await session.flush()
    workspace = Workspace(name="Worker", slug=f"worker-{suffix}", owner_id=owner.id)
    session.add(workspace)
    await session.flush()
    project = Project(
        workspace_id=workspace.id,
        name="Worker Project",
        domain="mother_baby",
        owner_id=owner.id,
    )
    session.add(project)
    await session.flush()
    source = Source(
        workspace_id=workspace.id,
        project_id=project.id,
        name="Worker Source",
        type=collector_type,
        url=None,
        config=dict(config),
        schedule_cron=None,
        enabled=True,
    )
    session.add(source)
    await session.flush()
    task = CollectionTask(
        workspace_id=workspace.id,
        project_id=project.id,
        source_id=source.id,
        collector_type=collector_type,
        name="Worker Task",
        schedule_cron=None,
        status="enabled",
        config=dict(config),
    )
    session.add(task)
    await session.flush()
    return workspace, project, task


async def _enqueue(
    factory: async_sessionmaker[AsyncSession],
    workspace: Workspace,
    project: Project,
    task: CollectionTask,
) -> uuid.UUID:
    async with factory() as session:
        run_id = await enqueue_run(
            session,
            values={
                "workspace_id": workspace.id,
                "project_id": project.id,
                "task_id": task.id,
                "trigger": "api",
            },
        )
        await session.commit()
    return run_id


@pytest.mark.asyncio
async def test_worker_completes_run_and_writes_step_and_grade() -> None:
    """一轮执行后 run 为 completed，并写了步骤、账本与等级行。"""
    engine, factory = await _make_factory()
    try:
        async with factory() as session:
            workspace, project, task = await _seed_context(session)
            await session.commit()
        run_id = await _enqueue(factory, workspace, project, task)

        runtime = RunWorkerRuntime(
            factory,
            worker_id="test-worker",
            lease_seconds=60.0,
            collector_call_factory=lambda _session: FakeCollectorCall(result=_make_result()),
        )

        assert await runtime.run_once() is True

        async with factory() as session:
            run = await session.get(Run, run_id)
            assert run is not None
            assert run.status == "completed"
            assert run.outcome == "success"
            assert run.evidence_grade == "L3_live_single"
            assert run.records_count == 4
            assert run.total_cost_usd == Decimal("1.000000")

            steps = list(
                (
                    await session.scalars(
                        select(RunStep).where(RunStep.run_id == run_id)
                    )
                ).all()
            )
            assert len(steps) == 1
            assert steps[0].status == "success"
            assert steps[0].outcome == "success"
            assert steps[0].records_count == 4

            grade = await session.scalar(
                select(RunEvidenceGradeRecord).where(
                    RunEvidenceGradeRecord.run_id == run_id
                )
            )
            assert grade is not None
            assert grade.grade == "L3_live_single"
            assert grade.sample_n == 4

            ledger = list(
                (
                    await session.scalars(
                        select(RunLedgerEntry).where(RunLedgerEntry.run_id == run_id)
                    )
                ).all()
            )
            assert len(ledger) == 1
            assert ledger[0].amount_usd == Decimal("1.000000")

        assert await runtime.run_once() is False
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_worker_marks_run_failed_and_keeps_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """collector 抛异常时 run 变 failed，worker 记录后继续。"""
    engine, factory = await _make_factory()
    try:
        async with factory() as session:
            workspace, project, task = await _seed_context(session)
            await session.commit()
        run_id = await _enqueue(factory, workspace, project, task)

        async def failing_execute_collector_call(**kwargs: object) -> CollectionCallResult:
            raise RuntimeError("collector exploded")

        monkeypatch.setattr(
            collector_call_module,
            "execute_collector_call",
            failing_execute_collector_call,
        )
        runtime = RunWorkerRuntime(
            factory,
            worker_id="test-worker",
            lease_seconds=60.0,
        )

        assert await runtime.run_once() is True

        async with factory() as session:
            run = await session.get(Run, run_id)
            assert run is not None
            assert run.status == "failed"
            assert run.outcome == "failed"
            assert run.error_message == "collector exploded"
            assert run.evidence_grade is None

            steps = list(
                (
                    await session.scalars(
                        select(RunStep).where(RunStep.run_id == run_id)
                    )
                ).all()
            )
            assert len(steps) == 1
            assert steps[0].status == "failed"
            assert steps[0].outcome == "failed"

            task_run = await session.scalar(
                select(TaskRun).where(TaskRun.run_id == run_id)
            )
            assert task_run is not None
            assert task_run.status == "failed"
            assert task_run.error_message == "collector exploded"

            grade = await session.scalar(
                select(RunEvidenceGradeRecord).where(
                    RunEvidenceGradeRecord.run_id == run_id
                )
            )
            assert grade is None

        # 循环没退出。下一轮没有可领取的行。
        assert await runtime.run_once() is False
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_run_collector_call_delegates_to_execute_collector_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """适配器必须调用 ``execute_collector_call``，不自己写采集逻辑。"""
    engine, factory = await _make_factory()
    try:
        async with factory() as session:
            workspace, project, task = await _seed_context(session)
            run = Run(
                workspace_id=workspace.id,
                project_id=project.id,
                task_id=task.id,
                status="queued",
                execution_mode="live",
                trigger="api",
                records_count=0,
            )
            session.add(run)
            await session.flush()
            await session.commit()

            captured: dict[str, object] = {}

            async def fake_execute_collector_call(
                *,
                session: AsyncSession,
                workspace: Workspace,
                task: CollectionTask,
                task_run: TaskRun,
                trigger: str,
                timeout_seconds: float,
                logs: list[dict[str, object]],
            ) -> CollectionCallResult:
                captured.update(
                    {
                        "workspace": workspace,
                        "task": task,
                        "task_run": task_run,
                        "trigger": trigger,
                        "timeout_seconds": timeout_seconds,
                    }
                )
                logs.append({"step": "fake_call"})
                return CollectionCallResult(
                    status="success",
                    records_count=2,
                    entities_count=1,
                    task_run_id=task_run.id,
                    collector_type=task.collector_type,
                    endpoint_type="mock_endpoint",
                    sample_n=2,
                    source_count=1,
                    window_days=7,
                    unit="record",
                    quantity=Decimal("2"),
                    unit_price=Decimal("0.500000"),
                    total_cost_usd=Decimal("1.000000"),
                )

            monkeypatch.setattr(
                collector_call_module,
                "execute_collector_call",
                fake_execute_collector_call,
            )
            record = await OrmRunRepository(session).get(run.id)
            assert record is not None

            adapter = RunCollectorCall(session)
            result = await adapter(record)

            assert captured["task"] is task
            assert captured["workspace"] is workspace
            assert result.records_count == 2
            task_run = await session.get(TaskRun, result.task_run_id)
            assert task_run is not None
            assert task_run.run_id == run.id
            assert task_run.status == "success"
            assert task_run.records_count == 2
            assert task_run.total_cost_usd == Decimal("1.000000")

            await adapter.mirror_evidence_grade(run.id, "L3_live_single")
            await session.refresh(task_run)
            assert task_run.evidence_grade == "L3_live_single"
    finally:
        await engine.dispose()


def test_run_worker_enabled_defaults_to_false() -> None:
    """配置项默认关闭。"""
    field = Settings.model_fields["run_worker_enabled"]
    assert field.default is False


@pytest.mark.asyncio
async def test_worker_runs_manual_json_collector_end_to_end() -> None:
    """真实 collector 路径：worker 完成一次离线 manual_json 采集。"""
    engine, factory = await _make_factory()
    try:
        async with factory() as session:
            workspace, project, task = await _seed_context(
                session,
                collector_type="manual_json",
                task_config={
                    "entity_type": "brand",
                    "json_data": [{"name": "Test Brand", "market": "US"}],
                },
            )
            await session.commit()
        run_id = await _enqueue(factory, workspace, project, task)

        runtime = RunWorkerRuntime(factory, worker_id="test-worker", lease_seconds=60.0)

        assert await runtime.run_once() is True

        async with factory() as session:
            run = await session.get(Run, run_id)
            assert run is not None
            assert run.status == "completed"
            assert run.outcome == "success"
            assert run.records_count == 1

            step = await session.scalar(
                select(RunStep).where(RunStep.run_id == run_id)
            )
            assert step is not None
            assert step.collector_type == "manual_json"
            assert step.task_run_id is not None

            task_run = await session.get(TaskRun, step.task_run_id)
            assert task_run is not None
            assert task_run.status == "success"
            assert task_run.records_count == 1

            raw_records = list(
                (
                    await session.scalars(
                        select(RawRecord).where(
                            RawRecord.task_run_id == task_run.id
                        )
                    )
                ).all()
            )
            assert len(raw_records) == 1

            grade = await session.scalar(
                select(RunEvidenceGradeRecord).where(
                    RunEvidenceGradeRecord.run_id == run_id
                )
            )
            assert grade is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_lifespan_does_not_start_worker_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """开关关闭时 lifespan 不创建也不启动 worker。"""
    created: list[object] = []
    started: list[object] = []

    class FakeRuntime:
        def __init__(self, **kwargs: object) -> None:
            created.append(kwargs)

        def start(self) -> None:
            started.append(True)

        async def stop(self) -> None:
            started.append(False)

    @asynccontextmanager
    async def fake_run():
        yield

    background_events: list[str] = []

    class FakeBackgroundRuntime:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def recover_interrupted(self) -> int:
            return 0

        def start(self) -> None:
            background_events.append("start")

        async def stop(self) -> None:
            background_events.append("stop")

    monkeypatch.setattr(main_module, "EnrichmentWorkerRuntime", FakeBackgroundRuntime)
    monkeypatch.setattr(main_module, "WebhookWorkerRuntime", FakeBackgroundRuntime)
    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: Settings(scheduler_enabled=False, run_worker_enabled=False),
    )
    monkeypatch.setattr(
        main_module,
        "mcp_server",
        SimpleNamespace(session_manager=SimpleNamespace(run=fake_run)),
    )
    monkeypatch.setattr(main_module, "RunWorkerRuntime", FakeRuntime)

    app = FastAPI()
    async with main_module.lifespan(app):
        pass

    assert created == []
    assert started == []
    assert background_events == ["start", "start", "stop", "stop"]
    assert not hasattr(app.state, "run_worker")


@pytest.mark.asyncio
async def test_lifespan_starts_and_stops_worker_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """开关打开时 lifespan 启动 worker，并在退出时停止。"""
    created: list[object] = []
    started: list[object] = []

    class FakeRuntime:
        def __init__(self, **kwargs: object) -> None:
            created.append(kwargs)

        def start(self) -> None:
            started.append(True)

        async def stop(self) -> None:
            started.append(False)

    @asynccontextmanager
    async def fake_run():
        yield

    background_events: list[str] = []

    class FakeBackgroundRuntime:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def recover_interrupted(self) -> int:
            return 0

        def start(self) -> None:
            background_events.append("start")

        async def stop(self) -> None:
            background_events.append("stop")

    monkeypatch.setattr(main_module, "EnrichmentWorkerRuntime", FakeBackgroundRuntime)
    monkeypatch.setattr(main_module, "WebhookWorkerRuntime", FakeBackgroundRuntime)
    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: Settings(scheduler_enabled=False, run_worker_enabled=True),
    )
    monkeypatch.setattr(
        main_module,
        "mcp_server",
        SimpleNamespace(session_manager=SimpleNamespace(run=fake_run)),
    )
    monkeypatch.setattr(main_module, "RunWorkerRuntime", FakeRuntime)

    app = FastAPI()
    async with main_module.lifespan(app):
        assert started == [True]
        assert isinstance(app.state.run_worker, FakeRuntime)

    assert len(created) == 1
    assert started == [True, False]
    assert background_events == ["start", "start", "stop", "stop"]
