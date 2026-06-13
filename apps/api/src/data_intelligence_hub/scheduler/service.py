from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from data_intelligence_hub.models.task import CollectionTask
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.scheduler.cron import UnsupportedCronExpression, is_schedule_due
from data_intelligence_hub.services.collector_service import execute_collection_task

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SchedulerTickResult:
    scanned: int
    due: int
    started: int
    skipped_running: int
    skipped_invalid_schedule: int


class CollectionScheduler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        poll_interval_seconds: float,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._poll_interval_seconds = poll_interval_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        self._loop_task: asyncio.Task[None] | None = None
        self._running_task_ids: set[uuid.UUID] = set()

    @property
    def running(self) -> bool:
        return self._loop_task is not None and not self._loop_task.done()

    def start(self) -> None:
        if self.running:
            return
        self._loop_task = asyncio.create_task(self._run_forever())
        logger.info(
            "collection_scheduler_started",
            poll_interval_seconds=self._poll_interval_seconds,
        )

    async def stop(self) -> None:
        if self._loop_task is None:
            return
        self._loop_task.cancel()
        try:
            await self._loop_task
        except asyncio.CancelledError:
            logger.info("collection_scheduler_stopped")
        finally:
            self._loop_task = None

    async def tick(self, now: datetime | None = None) -> SchedulerTickResult:
        current_time = now or self._clock()
        scanned = 0
        due = 0
        started = 0
        skipped_running = 0
        skipped_invalid_schedule = 0

        async with self._session_factory() as session:
            candidates = await _list_scheduled_tasks(session)
            scanned = len(candidates)
            for task, workspace in candidates:
                if task.id in self._running_task_ids:
                    skipped_running += 1
                    continue

                try:
                    task_is_due = is_schedule_due(
                        task.schedule_cron,
                        task.last_run_at,
                        current_time,
                    )
                except UnsupportedCronExpression as exc:
                    skipped_invalid_schedule += 1
                    logger.warning(
                        "collection_scheduler_invalid_schedule",
                        task_id=str(task.id),
                        schedule_cron=task.schedule_cron,
                        error=str(exc),
                    )
                    continue

                if not task_is_due:
                    continue

                due += 1
                self._running_task_ids.add(task.id)
                try:
                    await execute_collection_task(session, workspace, task)
                    started += 1
                except Exception:
                    logger.exception("collection_scheduler_task_failed", task_id=str(task.id))
                finally:
                    self._running_task_ids.discard(task.id)

        return SchedulerTickResult(
            scanned=scanned,
            due=due,
            started=started,
            skipped_running=skipped_running,
            skipped_invalid_schedule=skipped_invalid_schedule,
        )

    async def _run_forever(self) -> None:
        while True:
            try:
                result = await self.tick()
                logger.info(
                    "collection_scheduler_tick_completed",
                    scanned=result.scanned,
                    due=result.due,
                    started=result.started,
                    skipped_running=result.skipped_running,
                    skipped_invalid_schedule=result.skipped_invalid_schedule,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("collection_scheduler_tick_failed")
            await asyncio.sleep(self._poll_interval_seconds)


async def _list_scheduled_tasks(
    session: AsyncSession,
) -> list[tuple[CollectionTask, Workspace]]:
    statement = (
        select(CollectionTask, Workspace)
        .join(Workspace, CollectionTask.workspace_id == Workspace.id)
        .where(
            CollectionTask.status == "enabled",
            CollectionTask.schedule_cron.is_not(None),
        )
        .order_by(CollectionTask.last_run_at.asc().nullsfirst(), CollectionTask.created_at.asc())
    )
    result = await session.execute(statement)
    return [(task, workspace) for task, workspace in result.all()]
