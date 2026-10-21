"""调度器租约续期测试。

背景：tick 开始时获取租约，整个 tick 期间不续期。
慢端点可以让 tick 跑 1700 秒，而 TTL 只有 300 秒。
第二个实例会在第一个 tick 未结束时拿到租约。

修复后 tick 在运行期间按固定间隔续期。
续期失败时 tick 停止认领新任务。``scanned`` 的可观测行为不变。
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from data_intelligence_hub.models import (
    Base,
    CollectionTask,
    Project,
    Source,
    User,
    Workspace,
    WorkspaceMember,
)
from data_intelligence_hub.scheduler import service as scheduler_service
from data_intelligence_hub.scheduler.service import CollectionScheduler


async def _create_file_session_factory(
    path: Path,
) -> tuple[object, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _create_due_task(
    session: AsyncSession,
    schedule_cron: str | None = "* * * * *",
) -> CollectionTask:
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    source_id = uuid.uuid4()

    user = User(
        id=user_id,
        email=f"{user_id}@example.com",
        password_hash="hash",
        name="Owner",
        status="active",
        created_at=now,
        updated_at=now,
    )
    workspace = Workspace(
        id=workspace_id,
        name="Lease Workspace",
        slug=f"lease-{workspace_id}",
        owner_id=user_id,
        created_at=now,
        updated_at=now,
    )
    project = Project(
        id=project_id,
        workspace_id=workspace_id,
        name="Lease Project",
        description=None,
        domain="ecommerce",
        status="active",
        owner_id=user_id,
        created_at=now,
        updated_at=now,
    )
    source = Source(
        id=source_id,
        workspace_id=workspace_id,
        project_id=project_id,
        name="Manual JSON",
        type="manual_json",
        url=None,
        config={"entity_type": "product", "json_data": {"name": "Demo", "price": 12}},
        schedule_cron=schedule_cron,
        enabled=True,
        created_at=now,
        updated_at=now,
    )
    task = CollectionTask(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        source_id=source_id,
        collector_type="manual_json",
        name="Manual JSON Task",
        schedule_cron=schedule_cron,
        status="enabled",
        config={"entity_type": "product", "json_data": {"name": "Demo", "price": 12}},
        success_count=0,
        failure_count=0,
        last_run_at=None,
        created_at=now,
        updated_at=now,
    )
    session.add_all(
        [
            user,
            workspace,
            WorkspaceMember(
                workspace_id=workspace_id,
                user_id=user_id,
                role="owner",
                created_at=now,
                updated_at=now,
            ),
            project,
            source,
            task,
        ]
    )
    await session.flush()
    return task


@pytest.mark.asyncio
async def test_tick_renews_lease_while_task_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, session_factory = await _create_file_session_factory(tmp_path / "scheduler.db")
    try:
        async with session_factory() as session:
            await _create_due_task(session)
            await session.commit()

        renewal_calls: list[datetime] = []
        original_renew = scheduler_service._renew_scheduler_lease

        async def spy_renew(*args: object, **kwargs: object) -> bool:
            renewal_calls.append(datetime.now(UTC))
            return await original_renew(*args, **kwargs)

        async def slow_execute(
            session: AsyncSession,
            workspace: Workspace,
            task: CollectionTask,
            trigger: str,
        ) -> None:
            # 真实执行器会在采集期间提交。先提交，让心跳拿到写锁。
            await session.commit()
            await asyncio.sleep(0.35)

        monkeypatch.setattr(
            scheduler_service,
            "_renew_scheduler_lease",
            spy_renew,
        )
        monkeypatch.setattr(
            scheduler_service,
            "execute_collection_task",
            slow_execute,
        )

        scheduler = CollectionScheduler(
            session_factory=session_factory,
            poll_interval_seconds=60,
            clock=lambda: datetime.now(UTC),
            lease_renew_interval_seconds=0.1,
        )
        result = await scheduler.tick()

        assert result.lock_acquired is True
        assert result.scanned == 1
        assert result.started == 1
        assert result.task_errors == 0
        assert len(renewal_calls) >= 2
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_tick_stops_claiming_after_renewal_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, session_factory = await _create_file_session_factory(tmp_path / "scheduler.db")
    try:
        async with session_factory() as session:
            for _ in range(3):
                await _create_due_task(session)
            await session.commit()

        async def failed_renew(*_args: object, **_kwargs: object) -> bool:
            return False

        async def slow_execute(
            session: AsyncSession,
            workspace: Workspace,
            task: CollectionTask,
            trigger: str,
        ) -> None:
            await session.commit()
            await asyncio.sleep(0.08)

        monkeypatch.setattr(
            scheduler_service,
            "_renew_scheduler_lease",
            failed_renew,
        )
        monkeypatch.setattr(
            scheduler_service,
            "execute_collection_task",
            slow_execute,
        )

        scheduler = CollectionScheduler(
            session_factory=session_factory,
            poll_interval_seconds=60,
            clock=lambda: datetime.now(UTC),
            lease_renew_interval_seconds=0.01,
        )
        result = await scheduler.tick()

        assert result.scanned == 3
        assert result.started < 3
        assert result.status == "completed"
    finally:
        await engine.dispose()
