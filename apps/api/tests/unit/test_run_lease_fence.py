"""租约围栏测试。

覆盖两个生产故障场景：

1. 租约被新 worker 接管后，旧 worker 不得提交终态。
2. 运行已被取消后，执行器的收尾写入不得覆盖取消状态。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.services.run_executor import (
    InvalidRunTransitionError,
    RunLeaseLostError,
)
from data_intelligence_hub.services.run_executor_adapters import OrmRunRepository


@pytest_asyncio.fixture()
async def factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _seed_run(
    factory: async_sessionmaker[AsyncSession],
    *,
    worker_id: str | None,
) -> uuid.UUID:
    async with factory() as session:
        run = Run(
            id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            status="running",
            execution_mode="live",
            trigger="api",
            records_count=0,
            worker_id=worker_id,
        )
        session.add(run)
        await session.commit()
        return run.id


@pytest.mark.asyncio
async def test_old_worker_cannot_commit_after_takeover(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _seed_run(factory, worker_id="worker-a")

    async with factory() as old_worker:
        run = await old_worker.get(Run, run_id)
        assert run is not None and run.worker_id == "worker-a"

        async with factory() as new_worker:
            await new_worker.execute(
                update(Run).where(Run.id == run_id).values(worker_id="worker-b")
            )
            await new_worker.commit()

        run.status = "completed"
        run.outcome = "success"
        with pytest.raises(RunLeaseLostError):
            await OrmRunRepository(old_worker).save(run)


@pytest.mark.asyncio
async def test_cancelled_run_is_not_overwritten(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _seed_run(factory, worker_id="worker-a")

    async with factory() as worker:
        run = await worker.get(Run, run_id)
        assert run is not None

        async with factory() as cancel_route:
            await cancel_route.execute(
                update(Run).where(Run.id == run_id).values(status="cancelled")
            )
            await cancel_route.commit()

        run.status = "completed"
        run.outcome = "success"
        with pytest.raises(InvalidRunTransitionError):
            await OrmRunRepository(worker).save(run)
        await worker.rollback()

    async with factory() as session:
        stored = await session.scalar(select(Run.status).where(Run.id == run_id))
        assert stored == "cancelled"
