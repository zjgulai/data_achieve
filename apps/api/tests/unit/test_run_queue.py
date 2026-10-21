"""持久运行队列的单元测试。

覆盖八件事：

1. 两个 worker 并发领取，不会拿到同一行。
2. 租约过期后可被重新领取。
3. 未过期时他人领不到。
4. 续期延长到期时间。
5. 租约被接管后，旧到期时间不能续期。
6. worker 执行成功后释放租约。
7. worker 的 handler 抛异常时运行置为 failed。
8. 进程重启不丢任务：queued 行留在数据库里。

测试使用文件 SQLite。文件库让两个会话各用一条连接，才能测并发。
测试显式传入回退表。回退表带 ``worker_id``，因此可以测所有权校验。
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from data_intelligence_hub.services.run_queue import (
    claim_next_run,
    enqueue_run,
    fallback_runs_table,
    release_lease,
    renew_lease,
    resolve_runs_table,
)
from data_intelligence_hub.services.run_queue_worker import RunQueueWorker

_TABLE = fallback_runs_table()


async def _create_engine_and_factory(
    path: Path,
) -> tuple[object, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    async with engine.begin() as connection:
        await connection.run_sync(_TABLE.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _enqueue(
    factory: async_sessionmaker[AsyncSession],
    *,
    now: datetime,
    task_id: uuid.UUID | None = None,
) -> uuid.UUID:
    async with factory() as session:
        run_id = await enqueue_run(
            session,
            values={
                "workspace_id": uuid.uuid4(),
                "project_id": uuid.uuid4(),
                "task_id": task_id,
            },
            now=now,
            table=_TABLE,
        )
        await session.commit()
    return run_id


async def _claim(
    factory: async_sessionmaker[AsyncSession],
    worker_id: str,
    *,
    now: datetime,
    lease_seconds: float = 60.0,
):
    async with factory() as session:
        claimed = await claim_next_run(
            session,
            worker_id,
            lease_seconds,
            now=now,
            table=_TABLE,
        )
        await session.commit()
        return claimed


def test_resolved_table_satisfies_queue_contract() -> None:
    """解析结果必须有队列所需列。B3-01 的模型落地后走真实表。"""
    table = resolve_runs_table()
    assert table.name == "runs"
    required = {"id", "status", "lease_expires_at", "created_at"}
    assert required <= set(table.c.keys())


@pytest.mark.asyncio
async def test_two_workers_concurrently_claim_distinct_runs(tmp_path: Path) -> None:
    _engine, factory = await _create_engine_and_factory(tmp_path / "queue.db")
    now = datetime.now(UTC)
    first_id = await _enqueue(factory, now=now)
    second_id = await _enqueue(factory, now=now + timedelta(seconds=1))

    first_claim, second_claim = await asyncio.gather(
        _claim(factory, "worker-a", now=now),
        _claim(factory, "worker-b", now=now),
    )

    assert first_claim is not None
    assert second_claim is not None
    assert {first_claim.run_id, second_claim.run_id} == {first_id, second_id}


@pytest.mark.asyncio
async def test_expired_lease_can_be_reclaimed(tmp_path: Path) -> None:
    _engine, factory = await _create_engine_and_factory(tmp_path / "queue.db")
    started_at = datetime.now(UTC)
    run_id = await _enqueue(factory, now=started_at)

    first = await _claim(factory, "worker-a", now=started_at, lease_seconds=30)
    assert first is not None
    assert first.run_id == run_id

    before_expiry = await _claim(
        factory,
        "worker-b",
        now=started_at + timedelta(seconds=20),
    )
    assert before_expiry is None

    after_expiry = await _claim(
        factory,
        "worker-b",
        now=started_at + timedelta(seconds=31),
        lease_seconds=30,
    )
    assert after_expiry is not None
    assert after_expiry.run_id == run_id
    assert after_expiry.previous_status == "running"
    assert after_expiry.worker_id == "worker-b"


@pytest.mark.asyncio
async def test_unexpired_lease_blocks_other_workers(tmp_path: Path) -> None:
    _engine, factory = await _create_engine_and_factory(tmp_path / "queue.db")
    now = datetime.now(UTC)
    await _enqueue(factory, now=now)

    first = await _claim(factory, "worker-a", now=now, lease_seconds=120)
    assert first is not None

    second = await _claim(
        factory,
        "worker-b",
        now=now + timedelta(seconds=60),
    )
    assert second is None


@pytest.mark.asyncio
async def test_renew_lease_extends_expiry(tmp_path: Path) -> None:
    _engine, factory = await _create_engine_and_factory(tmp_path / "queue.db")
    now = datetime.now(UTC)
    run_id = await _enqueue(factory, now=now)
    claimed = await _claim(factory, "worker-a", now=now, lease_seconds=30)
    assert claimed is not None
    original_expiry = claimed.lease_expires_at

    async with factory() as session:
        renewed_expiry = await renew_lease(
            session,
            run_id,
            "worker-a",
            lease_seconds=90,
            now=now + timedelta(seconds=10),
            table=_TABLE,
        )
        await session.commit()

    assert renewed_expiry is not None
    assert renewed_expiry == now + timedelta(seconds=100)
    assert renewed_expiry > original_expiry

    async with factory() as session:
        wrong_owner = await renew_lease(
            session,
            run_id,
            "worker-b",
            lease_seconds=90,
            now=now + timedelta(seconds=20),
            table=_TABLE,
        )
        await session.commit()

    assert wrong_owner is None


@pytest.mark.asyncio
async def test_stale_renewal_fails_after_reclaim(tmp_path: Path) -> None:
    """租约被接管后，旧到期时间不能续期。这是 worker_id 缺失时的所有权校验。"""
    _engine, factory = await _create_engine_and_factory(tmp_path / "queue.db")
    started_at = datetime.now(UTC)
    run_id = await _enqueue(factory, now=started_at)
    first = await _claim(factory, "worker-a", now=started_at, lease_seconds=30)
    assert first is not None
    stale_expiry = first.lease_expires_at

    reclaimed = await _claim(
        factory,
        "worker-b",
        now=started_at + timedelta(seconds=31),
        lease_seconds=30,
    )
    assert reclaimed is not None

    async with factory() as session:
        stale_renewal = await renew_lease(
            session,
            run_id,
            "worker-b",
            lease_seconds=90,
            now=started_at + timedelta(seconds=32),
            expected_expires_at=stale_expiry,
            table=_TABLE,
        )
        await session.commit()
    assert stale_renewal is None

    async with factory() as session:
        fresh_renewal = await renew_lease(
            session,
            run_id,
            "worker-b",
            lease_seconds=90,
            now=started_at + timedelta(seconds=33),
            expected_expires_at=reclaimed.lease_expires_at,
            table=_TABLE,
        )
        await session.commit()
    assert fresh_renewal is not None


@pytest.mark.asyncio
async def test_release_without_status_requeues_running_run(tmp_path: Path) -> None:
    _engine, factory = await _create_engine_and_factory(tmp_path / "queue.db")
    now = datetime.now(UTC)
    run_id = await _enqueue(factory, now=now)
    claimed = await _claim(factory, "worker-a", now=now, lease_seconds=60)
    assert claimed is not None

    async with factory() as session:
        released = await release_lease(
            session,
            run_id,
            worker_id="worker-a",
            now=now + timedelta(seconds=1),
            table=_TABLE,
        )
        await session.commit()
    assert released is True

    reclaimed = await _claim(
        factory,
        "worker-b",
        now=now + timedelta(seconds=2),
    )
    assert reclaimed is not None
    assert reclaimed.run_id == run_id
    assert reclaimed.previous_status == "queued"


@pytest.mark.asyncio
async def test_release_with_terminal_status_ends_run(tmp_path: Path) -> None:
    _engine, factory = await _create_engine_and_factory(tmp_path / "queue.db")
    now = datetime.now(UTC)
    run_id = await _enqueue(factory, now=now)
    await _claim(factory, "worker-a", now=now, lease_seconds=60)

    async with factory() as session:
        released = await release_lease(
            session,
            run_id,
            worker_id="worker-a",
            final_status="completed",
            now=now + timedelta(seconds=1),
            table=_TABLE,
        )
        await session.commit()
    assert released is True

    late_worker = await _claim(
        factory,
        "worker-b",
        now=now + timedelta(seconds=3600),
    )
    assert late_worker is None


@pytest.mark.asyncio
async def test_worker_runs_handler_and_releases_lease(tmp_path: Path) -> None:
    _engine, factory = await _create_engine_and_factory(tmp_path / "queue.db")
    now = datetime.now(UTC)
    run_id = await _enqueue(factory, now=now)

    async def handler(claimed) -> None:
        async with factory() as session:
            await session.execute(
                _TABLE.update()
                .where(_TABLE.c.id == claimed.run_id)
                .values(status="completed")
            )
            await session.commit()

    worker = RunQueueWorker(
        factory,
        worker_id="worker-a",
        lease_seconds=60,
        renew_interval_seconds=30,
        clock=lambda: datetime.now(UTC),
    )
    assert await worker.process_next(handler) is True
    assert await worker.process_next(handler) is False

    async with factory() as session:
        row = (
            await session.execute(
                select(_TABLE.c.status, _TABLE.c.lease_expires_at).where(
                    _TABLE.c.id == run_id
                )
            )
        ).one()
    assert row[0] == "completed"
    assert row[1] is None


@pytest.mark.asyncio
async def test_worker_marks_failed_when_handler_raises(tmp_path: Path) -> None:
    _engine, factory = await _create_engine_and_factory(tmp_path / "queue.db")
    now = datetime.now(UTC)
    run_id = await _enqueue(factory, now=now)

    async def failing_handler(_claimed) -> None:
        raise RuntimeError("boom")

    worker = RunQueueWorker(
        factory,
        worker_id="worker-a",
        lease_seconds=60,
        renew_interval_seconds=30,
        clock=lambda: datetime.now(UTC),
    )
    assert await worker.process_next(failing_handler) is True

    async with factory() as session:
        status = (
            await session.execute(
                select(_TABLE.c.status).where(_TABLE.c.id == run_id)
            )
        ).scalar_one()
    assert status == "failed"


@pytest.mark.asyncio
async def test_process_restart_keeps_queued_runs(tmp_path: Path) -> None:
    """模拟进程退出：释放引擎后重开同一文件，queued 行仍在。"""
    database = tmp_path / "queue.db"
    now = datetime.now(UTC)

    first_engine, first_factory = await _create_engine_and_factory(database)
    await _enqueue(first_factory, now=now)
    await _enqueue(first_factory, now=now + timedelta(seconds=1))
    claimed = await _claim(first_factory, "worker-a", now=now)
    assert claimed is not None
    await first_engine.dispose()

    second_engine, second_factory = await _create_engine_and_factory(database)
    try:
        remaining = await _claim(second_factory, "worker-b", now=now + timedelta(seconds=2))
        assert remaining is not None
        assert remaining.run_id != claimed.run_id

        exhausted = await _claim(
            second_factory,
            "worker-c",
            now=now + timedelta(seconds=3),
        )
        assert exhausted is None
    finally:
        await second_engine.dispose()
