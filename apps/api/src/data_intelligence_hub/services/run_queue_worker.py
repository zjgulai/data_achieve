"""运行队列的 worker 执行循环。

队列原语在 ``services/run_queue.py``。它们只 flush，不 commit。
本模块持有 worker 自己的事务边界：

- 领取后提交，让其他 worker 看得到 ``running`` 状态。
- 执行成功后提交释放。
- 执行失败后提交 ``failed``。

handler 的契约：

- 正常返回：保留 handler 写入的状态。若仍是 ``running``，放回队列。
- 抛异常：运行置为 ``failed``。

worker 在执行期间自动续期。续期用 ``expected_expires_at`` 做比较并交换。
租约被接管后旧 worker 无法续期，也不会覆盖新 worker 的状态。
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from data_intelligence_hub.services.run_queue import (
    ClaimedRun,
    claim_next_run,
    release_lease,
    renew_lease,
)

logger = structlog.get_logger(__name__)

RunHandler = Callable[[ClaimedRun], Awaitable[None]]


class RunQueueWorker:
    """领取并执行运行的 worker。"""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        worker_id: str | None = None,
        lease_seconds: float = 300.0,
        renew_interval_seconds: float | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._worker_id = worker_id or f"run-worker-{uuid.uuid4()}"
        self._lease_seconds = lease_seconds
        self._renew_interval_seconds = renew_interval_seconds or max(lease_seconds / 2, 1.0)
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def worker_id(self) -> str:
        return self._worker_id

    async def process_next(self, handler: RunHandler) -> bool:
        """领取一行并执行。没有可领取的行时返回 ``False``。"""
        async with self._session_factory() as session:
            claimed = await claim_next_run(
                session,
                self._worker_id,
                self._lease_seconds,
                now=self._clock(),
            )
            await session.commit()
        if claimed is None:
            return False

        heartbeat = _LeaseHeartbeat(
            session_factory=self._session_factory,
            run_id=claimed.run_id,
            worker_id=self._worker_id,
            lease_seconds=self._lease_seconds,
            initial_expires_at=claimed.lease_expires_at,
            interval_seconds=self._renew_interval_seconds,
            clock=self._clock,
        )
        await heartbeat.start()
        try:
            await handler(claimed)
        except asyncio.CancelledError:
            await heartbeat.stop()
            await self._release(claimed.run_id, final_status=None)
            raise
        except Exception:
            logger.exception("run_queue_handler_failed", run_id=str(claimed.run_id))
            await heartbeat.stop()
            await self._release(claimed.run_id, final_status="failed")
            return True
        await heartbeat.stop()
        if heartbeat.lost:
            # 另一个 worker 可能已接管。不要覆盖它的状态。
            logger.warning("run_queue_lease_lost", run_id=str(claimed.run_id))
            return True
        await self._release(claimed.run_id, final_status=None)
        return True

    async def run_forever(
        self,
        handler: RunHandler,
        *,
        poll_interval_seconds: float = 5.0,
    ) -> None:
        """持续领取。没有任务时休眠 ``poll_interval_seconds`` 秒。"""
        while True:
            processed = await self.process_next(handler)
            if not processed:
                await asyncio.sleep(poll_interval_seconds)

    async def _release(self, run_id: uuid.UUID, *, final_status: str | None) -> None:
        async with self._session_factory() as session:
            released = await release_lease(
                session,
                run_id,
                worker_id=self._worker_id,
                final_status=final_status,
                now=self._clock(),
            )
            await session.commit()
        if not released:
            logger.warning("run_queue_release_missed", run_id=str(run_id))


class _LeaseHeartbeat:
    """运行租约的后台续期器。"""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        run_id: uuid.UUID,
        worker_id: str,
        lease_seconds: float,
        initial_expires_at: datetime,
        interval_seconds: float,
        clock: Callable[[], datetime],
    ) -> None:
        self._session_factory = session_factory
        self._run_id = run_id
        self._worker_id = worker_id
        self._lease_seconds = lease_seconds
        self._last_expires_at = initial_expires_at
        self._interval_seconds = interval_seconds
        self._clock = clock
        self._task: asyncio.Task[None] | None = None
        self.lost = False
        self.renewal_count = 0

    async def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self._interval_seconds)
            try:
                async with self._session_factory() as session:
                    renewed = await renew_lease(
                        session,
                        self._run_id,
                        self._worker_id,
                        self._lease_seconds,
                        now=self._clock(),
                        expected_expires_at=self._last_expires_at,
                    )
                    await session.commit()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("run_queue_lease_renewal_failed", run_id=str(self._run_id))
                renewed = None
            if renewed is None:
                self.lost = True
                logger.warning("run_queue_lease_renewal_lost", run_id=str(self._run_id))
                return
            self._last_expires_at = renewed
            self.renewal_count += 1
