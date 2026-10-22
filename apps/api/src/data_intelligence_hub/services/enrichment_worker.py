"""富集任务 worker。

每次领取一条 ``status=queued`` 的富集任务，把它改为 running 并逐行执行。
进程重启后 running 任务会在启动时恢复为 queued，因此不会永久卡住。

PostgreSQL 使用 ``FOR UPDATE SKIP LOCKED``；SQLite 测试也能运行。
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import suppress
from datetime import UTC, datetime

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from data_intelligence_hub.models.enrichment import EnrichmentJob
from data_intelligence_hub.repositories.project_api_keys import consume_daily_quota
from data_intelligence_hub.services.enrichment_service import process_job

logger = structlog.get_logger(__name__)


class EnrichmentWorkerRuntime:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        poll_interval_seconds: float = 5.0,
    ) -> None:
        self._session_factory = session_factory
        self._poll_interval_seconds = poll_interval_seconds
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def recover_interrupted(self) -> int:
        """启动时把中断的 running 行放回队列。"""
        async with self._session_factory() as session:
            result = await session.execute(
                update(EnrichmentJob)
                .where(EnrichmentJob.status == "running")
                .values(status="queued", finished_at=None)
            )
            await session.commit()
            return int(result.rowcount or 0)

    def start(self) -> None:
        if self.running:
            return
        self._task = asyncio.create_task(self._run_forever())
        logger.info("enrichment_worker_started")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        logger.info("enrichment_worker_stopped")

    async def run_once(self) -> bool:
        job_id = await self._claim()
        if job_id is None:
            return False
        try:
            project_key_id = await self._job_key_id(job_id)
            await process_job(
                job_id,
                session_factory=self._session_factory,
                before_row=(
                    self._consume_quota(project_key_id)
                    if project_key_id is not None
                    else None
                ),
            )
        except Exception:
            logger.exception("enrichment_worker_job_failed", job_id=str(job_id))
            async with self._session_factory() as session:
                job = await session.get(EnrichmentJob, job_id)
                if job is not None:
                    job.status = "failed"
                    job.finished_at = datetime.now(UTC)
                    await session.commit()
        return True

    async def _job_key_id(self, job_id: uuid.UUID) -> uuid.UUID | None:
        async with self._session_factory() as session:
            job = await session.get(EnrichmentJob, job_id)
            return job.project_key_id if job is not None else None

    def _consume_quota(self, key_id: uuid.UUID):
        async def consume() -> None:
            async with self._session_factory() as session:
                allowed = await consume_daily_quota(session, key_id)
                await session.commit()
            if not allowed:
                raise ValueError("quota_exceeded")

        return consume

    async def _claim(self) -> uuid.UUID | None:
        async with self._session_factory() as session:
            statement = (
                select(EnrichmentJob)
                .where(EnrichmentJob.status == "queued")
                .order_by(EnrichmentJob.created_at, EnrichmentJob.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            job = (await session.execute(statement)).scalar_one_or_none()
            if job is None:
                return None
            job.status = "running"
            await session.commit()
            return job.id

    async def _run_forever(self) -> None:
        while True:
            try:
                processed = await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("enrichment_worker_iteration_failed")
                processed = False
            if not processed:
                await asyncio.sleep(self._poll_interval_seconds)
