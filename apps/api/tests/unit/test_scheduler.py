from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import (
    Base,
    CollectionTask,
    Notification,
    Project,
    Report,
    ReportAuditEvent,
    ReportSubscription,
    ReportSubscriptionRun,
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

    assert result.report_subscriptions_scanned == 1
    assert result.report_subscriptions_due == 1
    assert result.report_subscriptions_started == 1
    assert result.report_subscriptions_skipped_running == 0

    async with session_factory() as session:
        reports = list((await session.execute(select(Report))).scalars().all())
        notifications = list((await session.execute(select(Notification))).scalars().all())
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
    assert len(notifications) == 1
    assert notifications[0].notification_type == "report_ready"
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


async def _create_session_factory() -> async_sessionmaker:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _create_collection_task(
    session,
    schedule_cron: str,
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


async def _create_report_subscription(
    session,
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
