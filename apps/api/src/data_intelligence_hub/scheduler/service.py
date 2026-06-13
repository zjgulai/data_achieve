from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from data_intelligence_hub.models.scheduler import SchedulerLease
from data_intelligence_hub.models.task import CollectionTask
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.reports import list_due_report_subscriptions
from data_intelligence_hub.scheduler.cron import UnsupportedCronExpression, is_schedule_due
from data_intelligence_hub.services.collector_service import execute_collection_task
from data_intelligence_hub.services.report_service import execute_report_subscription

logger = structlog.get_logger(__name__)
SCHEDULER_LEASE_NAME = "collection_scheduler_tick"


@dataclass(frozen=True)
class SchedulerTickResult:
    lock_acquired: bool
    scanned: int
    due: int
    started: int
    skipped_running: int
    skipped_invalid_schedule: int
    report_subscriptions_scanned: int
    report_subscriptions_due: int
    report_subscriptions_started: int
    report_subscriptions_skipped_running: int


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
        self._owner_id = str(uuid.uuid4())
        self._lease_ttl_seconds = max(int(poll_interval_seconds * 3), 300)
        self._loop_task: asyncio.Task[None] | None = None
        self._running_task_ids: set[uuid.UUID] = set()
        self._running_report_subscription_ids: set[uuid.UUID] = set()

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
        current_time = _as_utc(now or self._clock())
        scanned = 0
        due = 0
        started = 0
        skipped_running = 0
        skipped_invalid_schedule = 0
        report_subscriptions_scanned = 0
        report_subscriptions_due = 0
        report_subscriptions_started = 0
        report_subscriptions_skipped_running = 0

        async with self._session_factory() as session:
            lock_acquired = await _acquire_scheduler_lease(
                session=session,
                lease_name=SCHEDULER_LEASE_NAME,
                owner_id=self._owner_id,
                now=current_time,
                ttl_seconds=self._lease_ttl_seconds,
            )
            if not lock_acquired:
                logger.info(
                    "collection_scheduler_tick_skipped_locked",
                    lease_name=SCHEDULER_LEASE_NAME,
                )
                return _empty_tick_result(lock_acquired=False)

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

            report_subscription_candidates = await list_due_report_subscriptions(
                session,
                current_time,
            )
            report_subscriptions_scanned = len(report_subscription_candidates)
            for subscription, workspace, user in report_subscription_candidates:
                if subscription.id in self._running_report_subscription_ids:
                    report_subscriptions_skipped_running += 1
                    continue

                report_subscriptions_due += 1
                self._running_report_subscription_ids.add(subscription.id)
                try:
                    await execute_report_subscription(
                        session=session,
                        subscription=subscription,
                        workspace=workspace,
                        user=user,
                        now=current_time,
                    )
                    report_subscriptions_started += 1
                except Exception:
                    logger.exception(
                        "report_subscription_scheduler_failed",
                        subscription_id=str(subscription.id),
                    )
                finally:
                    self._running_report_subscription_ids.discard(subscription.id)

        return SchedulerTickResult(
            lock_acquired=True,
            scanned=scanned,
            due=due,
            started=started,
            skipped_running=skipped_running,
            skipped_invalid_schedule=skipped_invalid_schedule,
            report_subscriptions_scanned=report_subscriptions_scanned,
            report_subscriptions_due=report_subscriptions_due,
            report_subscriptions_started=report_subscriptions_started,
            report_subscriptions_skipped_running=report_subscriptions_skipped_running,
        )

    async def _run_forever(self) -> None:
        while True:
            try:
                result = await self.tick()
                logger.info(
                    "collection_scheduler_tick_completed",
                    lock_acquired=result.lock_acquired,
                    scanned=result.scanned,
                    due=result.due,
                    started=result.started,
                    skipped_running=result.skipped_running,
                    skipped_invalid_schedule=result.skipped_invalid_schedule,
                    report_subscriptions_scanned=result.report_subscriptions_scanned,
                    report_subscriptions_due=result.report_subscriptions_due,
                    report_subscriptions_started=result.report_subscriptions_started,
                    report_subscriptions_skipped_running=(
                        result.report_subscriptions_skipped_running
                    ),
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


async def _acquire_scheduler_lease(
    session: AsyncSession,
    lease_name: str,
    owner_id: str,
    now: datetime,
    ttl_seconds: int,
) -> bool:
    expires_at = now + timedelta(seconds=ttl_seconds)
    statement = select(SchedulerLease).where(SchedulerLease.name == lease_name).with_for_update()
    result = await session.execute(statement)
    lease = result.scalar_one_or_none()
    if lease is None:
        session.add(
            SchedulerLease(
                name=lease_name,
                owner_id=owner_id,
                expires_at=expires_at,
                updated_at=now,
            )
        )
    else:
        lease_expires_at = _as_utc(lease.expires_at)
        if lease.owner_id != owner_id and lease_expires_at > now:
            await session.rollback()
            return False
        lease.owner_id = owner_id
        lease.expires_at = expires_at
        lease.updated_at = now

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return False
    return True


def _empty_tick_result(lock_acquired: bool) -> SchedulerTickResult:
    return SchedulerTickResult(
        lock_acquired=lock_acquired,
        scanned=0,
        due=0,
        started=0,
        skipped_running=0,
        skipped_invalid_schedule=0,
        report_subscriptions_scanned=0,
        report_subscriptions_due=0,
        report_subscriptions_started=0,
        report_subscriptions_skipped_running=0,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
