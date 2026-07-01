from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.collectors.manual_json import ManualJsonCollector
from data_intelligence_hub.models import (
    Base,
    CollectionTask,
    Notification,
    Project,
    Report,
    ReportAuditEvent,
    ReportSubscription,
    ReportSubscriptionRun,
    SchedulerLease,
    SchedulerTick,
    Source,
    TaskRun,
    User,
    Workspace,
    WorkspaceMember,
)
from data_intelligence_hub.scheduler.cron import (
    UnsupportedCronExpression,
    cron_interval,
    is_schedule_due,
)
from data_intelligence_hub.scheduler.service import CollectionScheduler
from data_intelligence_hub.services.exceptions import TaskAlreadyRunningError


def test_cron_interval_supports_mvp_schedules() -> None:
    assert cron_interval("* * * * *") == timedelta(minutes=1)
    assert cron_interval("*/30 * * * *") == timedelta(minutes=30)
    assert cron_interval("0 */2 * * *") == timedelta(hours=2)
    assert cron_interval("0 8 * * *") == timedelta(days=1)


def test_schedule_due_uses_last_run_boundary() -> None:
    now = datetime(2026, 6, 13, 10, 0, tzinfo=UTC)

    assert is_schedule_due("*/30 * * * *", None, now) is True
    assert is_schedule_due("*/30 * * * *", now - timedelta(minutes=31), now) is True
    assert is_schedule_due("*/30 * * * *", now - timedelta(minutes=29), now) is False
    assert is_schedule_due(None, now - timedelta(days=1), now) is False


def test_cron_interval_rejects_unsupported_expressions() -> None:
    with pytest.raises(UnsupportedCronExpression):
        cron_interval("bad")
    with pytest.raises(UnsupportedCronExpression):
        cron_interval("0 8 1 * *")


@pytest.mark.asyncio
async def test_scheduler_tick_runs_due_collection_task() -> None:
    session_factory = await _create_session_factory()
    async with session_factory() as session:
        await _create_collection_task(session, schedule_cron="* * * * *")
        await session.commit()

    scheduler = CollectionScheduler(
        session_factory=session_factory,
        poll_interval_seconds=60,
        clock=lambda: datetime.now(UTC),
    )
    result = await scheduler.tick()

    assert result.lock_acquired is True
    assert result.scanned == 1
    assert result.due == 1
    assert result.started == 1
    assert result.skipped_invalid_schedule == 0

    async with session_factory() as session:
        runs = list((await session.execute(select(TaskRun))).scalars().all())
        task = (await session.execute(select(CollectionTask))).scalar_one()

    assert len(runs) == 1
    assert runs[0].status == "success"
    assert runs[0].records_count == 1
    assert task.last_run_at is not None
    assert task.success_count == 1

    async with session_factory() as session:
        tick = (await session.execute(select(SchedulerTick))).scalar_one()

    assert tick.status == "completed"
    assert tick.lock_acquired is True
    assert tick.scanned == 1
    assert tick.due == 1
    assert tick.started == 1
    assert tick.task_errors == 0


@pytest.mark.asyncio
async def test_scheduler_tick_merges_source_payload_with_task_metadata() -> None:
    session_factory = await _create_session_factory()
    async with session_factory() as session:
        await _create_collection_task(
            session,
            schedule_cron="* * * * *",
            task_config={
                "freshness_target_hours": 6,
                "schedule_policy": "manual_refresh_only",
            },
        )
        await session.commit()

    scheduler = CollectionScheduler(
        session_factory=session_factory,
        poll_interval_seconds=60,
        clock=lambda: datetime.now(UTC),
    )
    result = await scheduler.tick()

    assert result.started == 1

    async with session_factory() as session:
        run = (await session.execute(select(TaskRun))).scalar_one()
        task = (await session.execute(select(CollectionTask))).scalar_one()

    assert run.status == "success"
    assert run.records_count == 1
    assert run.entities_count == 1
    assert run.error_message is None
    assert task.success_count == 1
    assert task.failure_count == 0


@pytest.mark.asyncio
async def test_scheduler_tick_runs_due_auto_freshness_task_without_cron() -> None:
    now = datetime(2026, 6, 14, 10, 0, tzinfo=UTC)
    session_factory = await _create_session_factory()
    async with session_factory() as session:
        await _create_collection_task(
            session,
            schedule_cron=None,
            last_run_at=now - timedelta(hours=7),
            task_config={
                "freshness_target_hours": 6,
                "schedule_policy": "auto_freshness",
            },
        )
        await session.commit()

    scheduler = CollectionScheduler(
        session_factory=session_factory,
        poll_interval_seconds=60,
        clock=lambda: now,
    )
    result = await scheduler.tick()

    assert result.scanned == 1
    assert result.due == 1
    assert result.started == 1


@pytest.mark.asyncio
async def test_scheduler_tick_skips_manual_refresh_task_without_cron() -> None:
    now = datetime(2026, 6, 14, 10, 0, tzinfo=UTC)
    session_factory = await _create_session_factory()
    async with session_factory() as session:
        await _create_collection_task(
            session,
            schedule_cron=None,
            last_run_at=now - timedelta(hours=7),
            task_config={
                "freshness_target_hours": 6,
                "schedule_policy": "manual_refresh_only",
            },
        )
        await session.commit()

    scheduler = CollectionScheduler(
        session_factory=session_factory,
        poll_interval_seconds=60,
        clock=lambda: now,
    )
    result = await scheduler.tick()

    assert result.scanned == 1
    assert result.due == 0
    assert result.started == 0

    async with session_factory() as session:
        runs = list((await session.execute(select(TaskRun))).scalars().all())

    assert runs == []


@pytest.mark.asyncio
async def test_scheduler_tick_retries_failed_auto_freshness_task_after_delay() -> None:
    now = datetime(2026, 6, 14, 10, 0, tzinfo=UTC)
    failed_at = now - timedelta(minutes=20)
    session_factory = await _create_session_factory()
    async with session_factory() as session:
        task = await _create_collection_task(
            session,
            schedule_cron=None,
            last_run_at=failed_at,
            task_config={
                "freshness_target_hours": 6,
                "max_retry_attempts": 2,
                "retry_delay_minutes": 15,
                "retry_attempts_used": 1,
                "schedule_policy": "auto_freshness",
            },
        )
        session.add(
            TaskRun(
                task_id=task.id,
                workspace_id=task.workspace_id,
                status="failed",
                started_at=failed_at - timedelta(seconds=3),
                finished_at=failed_at,
                records_count=0,
                entities_count=0,
                error_message="upstream failed",
                error_traceback=None,
                logs=[],
                created_at=failed_at,
            )
        )
        await session.commit()

    scheduler = CollectionScheduler(
        session_factory=session_factory,
        poll_interval_seconds=60,
        clock=lambda: now,
    )
    result = await scheduler.tick()

    assert result.due == 1
    assert result.started == 1

    async with session_factory() as session:
        runs = list((await session.execute(select(TaskRun))).scalars().all())
        task = (await session.execute(select(CollectionTask))).scalar_one()

    assert len(runs) == 2
    assert {run.status for run in runs} == {"failed", "success"}
    assert task.success_count == 1
    assert task.config is not None
    assert task.config["retry_attempts_used"] == 0


@pytest.mark.asyncio
async def test_scheduler_tick_skips_auto_freshness_task_after_retry_budget() -> None:
    now = datetime(2026, 6, 14, 10, 0, tzinfo=UTC)
    failed_at = now - timedelta(minutes=20)
    session_factory = await _create_session_factory()
    async with session_factory() as session:
        task = await _create_collection_task(
            session,
            schedule_cron=None,
            last_run_at=failed_at,
            task_config={
                "freshness_target_hours": 6,
                "max_retry_attempts": 2,
                "retry_attempts_used": 2,
                "retry_delay_minutes": 15,
                "schedule_policy": "auto_freshness",
            },
        )
        session.add(
            TaskRun(
                task_id=task.id,
                workspace_id=task.workspace_id,
                status="failed",
                started_at=failed_at - timedelta(seconds=3),
                finished_at=failed_at,
                records_count=0,
                entities_count=0,
                error_message="upstream failed",
                error_traceback=None,
                logs=[],
                created_at=failed_at,
            )
        )
        await session.commit()

    scheduler = CollectionScheduler(
        session_factory=session_factory,
        poll_interval_seconds=60,
        clock=lambda: now,
    )
    result = await scheduler.tick()

    assert result.scanned == 1
    assert result.due == 0
    assert result.started == 0

    async with session_factory() as session:
        runs = list((await session.execute(select(TaskRun))).scalars().all())
        task = (await session.execute(select(CollectionTask))).scalar_one()

    assert len(runs) == 1
    assert task.config is not None
    assert task.config["retry_attempts_used"] == 2


@pytest.mark.asyncio
async def test_scheduler_tick_counts_task_lock_conflict_as_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = await _create_session_factory()
    async with session_factory() as session:
        await _create_collection_task(session, schedule_cron="* * * * *")
        await session.commit()

    async def raise_running(*_args: object, **_kwargs: object) -> None:
        raise TaskAlreadyRunningError

    monkeypatch.setattr(
        "data_intelligence_hub.scheduler.service.execute_collection_task",
        raise_running,
    )

    scheduler = CollectionScheduler(
        session_factory=session_factory,
        poll_interval_seconds=60,
        clock=lambda: datetime.now(UTC),
    )
    result = await scheduler.tick()

    assert result.due == 1
    assert result.started == 0
    assert result.skipped_running == 1
    assert result.task_errors == 0


@pytest.mark.asyncio
async def test_scheduler_tick_fails_task_run_after_collector_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = await _create_session_factory()
    async with session_factory() as session:
        await _create_collection_task(
            session,
            schedule_cron="* * * * *",
            task_config={
                "entity_type": "product",
                "json_data": {"name": "Slow Demo", "price": 12},
                "run_timeout_seconds": 0.1,
            },
        )
        await session.commit()

    async def slow_collect(_self: ManualJsonCollector) -> object:
        await asyncio.sleep(1)
        raise AssertionError("slow collector should time out before returning")

    monkeypatch.setattr(ManualJsonCollector, "collect", slow_collect)

    scheduler = CollectionScheduler(
        session_factory=session_factory,
        poll_interval_seconds=60,
        clock=lambda: datetime.now(UTC),
    )
    result = await scheduler.tick()

    assert result.due == 1
    assert result.started == 1
    assert result.task_errors == 0

    async with session_factory() as session:
        run = (await session.execute(select(TaskRun))).scalar_one()
        task = (await session.execute(select(CollectionTask))).scalar_one()

    assert run.status == "failed"
    assert run.error_message == "collection_timeout: collector exceeded 0.1s"
    assert any(log.get("failure_reason") == "timeout" for log in run.logs)
    assert task.status == "enabled"
    assert task.failure_count == 1
    assert task.config is not None
    assert task.config["retry_attempts_used"] == 1


@pytest.mark.asyncio
async def test_scheduler_tick_skips_invalid_schedule() -> None:
    session_factory = await _create_session_factory()
    async with session_factory() as session:
        await _create_collection_task(session, schedule_cron="invalid")
        await session.commit()

    scheduler = CollectionScheduler(
        session_factory=session_factory,
        poll_interval_seconds=60,
        clock=lambda: datetime.now(UTC),
    )
    result = await scheduler.tick()

    assert result.lock_acquired is True
    assert result.scanned == 1
    assert result.started == 0
    assert result.skipped_invalid_schedule == 1

    async with session_factory() as session:
        runs = list((await session.execute(select(TaskRun))).scalars().all())

    assert runs == []


@pytest.mark.asyncio
async def test_scheduler_tick_runs_due_report_subscription() -> None:
    now = datetime(2026, 6, 13, 9, 0, tzinfo=UTC)
    session_factory = await _create_session_factory()
    async with session_factory() as session:
        subscription_id = await _create_report_subscription(
            session,
            next_run_at=now - timedelta(minutes=1),
        )
        await session.commit()

    scheduler = CollectionScheduler(
        session_factory=session_factory,
        poll_interval_seconds=60,
        clock=lambda: now,
    )
    result = await scheduler.tick()

    assert result.lock_acquired is True
    assert result.report_subscriptions_scanned == 1
    assert result.report_subscriptions_due == 1
    assert result.report_subscriptions_started == 1
    assert result.report_subscriptions_skipped_running == 0

    async with session_factory() as session:
        reports = list((await session.execute(select(Report))).scalars().all())
        notifications = list(
            (
                await session.execute(
                    select(Notification).order_by(Notification.created_at, Notification.id)
                )
            )
            .scalars()
            .all()
        )
        audit_events = list(
            (await session.execute(select(ReportAuditEvent).order_by(ReportAuditEvent.created_at)))
            .scalars()
            .all()
        )
        subscription = (
            await session.execute(
                select(ReportSubscription).where(ReportSubscription.id == subscription_id)
            )
        ).scalar_one()
        subscription_runs = list(
            (await session.execute(select(ReportSubscriptionRun))).scalars().all()
        )

    assert len(reports) == 1
    assert reports[0].status == "sent"
    assert len(subscription_runs) == 1
    assert subscription_runs[0].trigger_type == "scheduled"
    assert subscription_runs[0].status == "partial_success"
    assert subscription_runs[0].report_id == reports[0].id
    assert subscription_runs[0].delivered_channels == ["in_app"]
    assert subscription_runs[0].skipped_channels == {"email": "smtp_not_configured"}
    notifications_by_type = {
        notification.notification_type: notification for notification in notifications
    }
    assert set(notifications_by_type) == {"report_ready", "task_failed"}
    assert "smtp_not_configured" in notifications_by_type["task_failed"].body
    assert [event.event_type for event in audit_events] == [
        "generated",
        "sent",
        "send_skipped",
        "subscription_executed",
    ]
    assert audit_events[1].metadata_json is not None
    assert '"channel": "in_app"' in audit_events[1].metadata_json
    assert audit_events[2].metadata_json is not None
    assert "smtp_not_configured" in audit_events[2].metadata_json
    assert subscription.last_sent_at is not None
    last_sent_at = subscription.last_sent_at
    if last_sent_at.tzinfo is None:
        last_sent_at = last_sent_at.replace(tzinfo=UTC)
    assert last_sent_at == now
    assert subscription.next_run_at is not None
    next_run_at = subscription.next_run_at
    if next_run_at.tzinfo is None:
        next_run_at = next_run_at.replace(tzinfo=UTC)
    assert next_run_at > now


@pytest.mark.asyncio
async def test_scheduler_tick_skips_when_another_owner_holds_lease() -> None:
    now = datetime(2026, 6, 13, 10, 0, tzinfo=UTC)
    session_factory = await _create_session_factory()
    async with session_factory() as session:
        await _create_collection_task(session, schedule_cron="* * * * *")
        await session.commit()

    first_scheduler = CollectionScheduler(
        session_factory=session_factory,
        poll_interval_seconds=60,
        clock=lambda: now,
    )
    second_scheduler = CollectionScheduler(
        session_factory=session_factory,
        poll_interval_seconds=60,
        clock=lambda: now,
    )

    first_result = await first_scheduler.tick()
    second_result = await second_scheduler.tick()

    assert first_result.lock_acquired is True
    assert second_result.lock_acquired is False
    assert second_result.scanned == 0
    assert second_result.started == 0

    async with session_factory() as session:
        leases = list((await session.execute(select(SchedulerLease))).scalars().all())
        runs = list((await session.execute(select(TaskRun))).scalars().all())
        ticks = list(
            (await session.execute(select(SchedulerTick).order_by(SchedulerTick.finished_at)))
            .scalars()
            .all()
        )

    assert len(leases) == 1
    assert len(runs) == 1
    assert [tick.status for tick in ticks] == ["completed", "skipped_locked"]


async def _create_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _create_collection_task(
    session: AsyncSession,
    schedule_cron: str | None,
    last_run_at: datetime | None = None,
    task_config: dict[str, object] | None = None,
) -> CollectionTask:
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    source_id = uuid.uuid4()
    task_id = uuid.uuid4()

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
        name="Scheduler Workspace",
        slug=f"scheduler-{workspace_id}",
        owner_id=user_id,
        created_at=now,
        updated_at=now,
    )
    project = Project(
        id=project_id,
        workspace_id=workspace_id,
        name="Scheduler Project",
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
        id=task_id,
        workspace_id=workspace_id,
        project_id=project_id,
        source_id=source_id,
        collector_type="manual_json",
        name="Manual JSON Task",
        schedule_cron=schedule_cron,
        status="enabled",
        config=task_config
        or {"entity_type": "product", "json_data": {"name": "Demo", "price": 12}},
        success_count=0,
        failure_count=0,
        last_run_at=last_run_at,
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


async def _create_report_subscription(
    session: AsyncSession,
    next_run_at: datetime,
) -> uuid.UUID:
    current_time = datetime(2026, 6, 13, 8, 0, tzinfo=UTC)
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    subscription_id = uuid.uuid4()

    user = User(
        id=user_id,
        email=f"{user_id}@example.com",
        password_hash="hash",
        name="Owner",
        status="active",
        created_at=current_time,
        updated_at=current_time,
    )
    workspace = Workspace(
        id=workspace_id,
        name="Report Scheduler Workspace",
        slug=f"report-scheduler-{workspace_id}",
        owner_id=user_id,
        created_at=current_time,
        updated_at=current_time,
    )
    subscription = ReportSubscription(
        id=subscription_id,
        workspace_id=workspace_id,
        user_id=user_id,
        project_id=None,
        report_type="daily",
        schedule_time="09:00",
        timezone="UTC",
        channels=["in_app", "email"],
        enabled=True,
        next_run_at=next_run_at,
        last_sent_at=None,
        created_at=current_time,
        updated_at=current_time,
    )
    session.add_all(
        [
            user,
            workspace,
            WorkspaceMember(
                workspace_id=workspace_id,
                user_id=user_id,
                role="owner",
                created_at=current_time,
                updated_at=current_time,
            ),
            subscription,
        ]
    )
    await session.flush()
    return subscription_id
