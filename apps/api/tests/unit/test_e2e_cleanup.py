from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.maintenance.e2e_cleanup import cleanup_e2e_fixtures
from data_intelligence_hub.models import (
    AlertEvent,
    AlertRule,
    Base,
    CollectionTask,
    Dataset,
    DatasetDriftEvent,
    DatasetVersion,
    Entity,
    EntitySnapshot,
    Evidence,
    IntelligenceFeedback,
    IntelligenceItem,
    Notification,
    Project,
    RawRecord,
    Report,
    ReportAuditEvent,
    ReportSubscription,
    ReportSubscriptionRun,
    Signal,
    Source,
    TaskRun,
    User,
    Workspace,
    WorkspaceMember,
)


@pytest.mark.asyncio
async def test_e2e_cleanup_dry_run_then_removes_expired_fixture_graph() -> None:
    session_factory = await _create_session_factory()
    now = datetime.now(UTC)

    async with session_factory() as session:
        old_fixture = await _create_fixture_graph(
            session,
            email="e2e-old@example.com",
            workspace_slug="e2e-old",
            created_at=now - timedelta(days=8),
        )
        recent_fixture = await _create_fixture_graph(
            session,
            email="e2e-recent@example.com",
            workspace_slug="e2e-recent",
            created_at=now,
        )
        protected_fixture = await _create_fixture_graph(
            session,
            email="owner@example.com",
            workspace_slug="owner",
            created_at=now - timedelta(days=30),
        )
        await session.commit()

    async with session_factory() as session:
        report = await cleanup_e2e_fixtures(session, dry_run=True, older_than_hours=24 * 7)
        await session.commit()

    assert report.dry_run is True
    assert report.counts["users"] == 1
    assert report.counts["workspaces"] == 1
    assert report.counts["entity_snapshots"] == 2
    assert report.counts["datasets"] == 1
    assert report.counts["dataset_versions"] == 1
    assert report.counts["dataset_drift_events"] == 1
    assert report.counts["alert_events"] == 1
    assert report.samples["users"] == ["e2e-old@example.com"]

    async with session_factory() as session:
        assert await session.get(User, old_fixture["user_id"]) is not None
        report = await cleanup_e2e_fixtures(session, dry_run=False, older_than_hours=24 * 7)
        await session.commit()

    assert report.dry_run is False
    async with session_factory() as session:
        assert await session.get(User, old_fixture["user_id"]) is None
        assert await session.get(Workspace, old_fixture["workspace_id"]) is None
        assert await session.get(Project, old_fixture["project_id"]) is None
        assert await session.get(Source, old_fixture["source_id"]) is None
        assert await session.get(CollectionTask, old_fixture["task_id"]) is None
        assert await session.get(TaskRun, old_fixture["run_id"]) is None
        assert await session.get(Dataset, old_fixture["dataset_id"]) is None
        assert await session.get(DatasetVersion, old_fixture["dataset_version_id"]) is None
        assert await session.get(DatasetDriftEvent, old_fixture["dataset_drift_event_id"]) is None
        assert await session.get(RawRecord, old_fixture["raw_record_id"]) is None
        assert await session.get(Entity, old_fixture["entity_id"]) is None
        assert await session.get(EntitySnapshot, old_fixture["current_snapshot_id"]) is None
        assert await session.get(Signal, old_fixture["signal_id"]) is None
        assert await session.get(IntelligenceItem, old_fixture["intelligence_id"]) is None
        assert await session.get(Report, old_fixture["report_id"]) is None
        assert await session.get(AlertRule, old_fixture["alert_rule_id"]) is None
        assert await session.get(Notification, old_fixture["notification_id"]) is None

        assert await session.get(User, recent_fixture["user_id"]) is not None
        assert await session.get(User, protected_fixture["user_id"]) is not None


async def _create_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _create_fixture_graph(
    session: AsyncSession,
    *,
    email: str,
    workspace_slug: str,
    created_at: datetime,
) -> dict[str, Any]:
    user = User(
        email=email,
        password_hash="hashed-password",
        name="Fixture User",
        status="active",
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(user)
    await session.flush()

    workspace = Workspace(
        name="Fixture Workspace",
        slug=workspace_slug,
        owner_id=user.id,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(workspace)
    await session.flush()

    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role="owner",
        created_at=created_at,
        updated_at=created_at,
    )
    project = Project(
        workspace_id=workspace.id,
        name="Fixture Project",
        description=None,
        domain="osint",
        status="active",
        owner_id=user.id,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add_all([member, project])
    await session.flush()

    source = Source(
        workspace_id=workspace.id,
        project_id=project.id,
        name="Fixture Source",
        type="manual_json",
        url=None,
        config={"entity_type": "github_repo", "json_data": {"full_name": workspace_slug}},
        schedule_cron=None,
        enabled=True,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(source)
    await session.flush()

    task = CollectionTask(
        workspace_id=workspace.id,
        project_id=project.id,
        source_id=source.id,
        collector_type="manual_json",
        name="Fixture Task",
        schedule_cron=None,
        status="enabled",
        config=source.config,
        success_count=1,
        failure_count=0,
        last_run_at=created_at,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(task)
    await session.flush()

    run = TaskRun(
        task_id=task.id,
        workspace_id=workspace.id,
        status="success",
        started_at=created_at,
        finished_at=created_at,
        records_count=1,
        entities_count=1,
        error_message=None,
        error_traceback=None,
        logs=[],
        created_at=created_at,
    )
    session.add(run)
    await session.flush()

    dataset = Dataset(
        workspace_id=workspace.id,
        project_id=project.id,
        name=f"Fixture Dataset {workspace_slug}",
        dataset_type="ecommerce_product",
        status="active",
        description="Fixture dataset",
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(dataset)
    await session.flush()

    dataset_version = DatasetVersion(
        dataset_id=dataset.id,
        workspace_id=workspace.id,
        project_id=project.id,
        created_by_user_id=user.id,
        version_number=1,
        source_task_run_ids=[str(run.id)],
        selected_fields=["title", "price"],
        cleaning_script=["strip title", "parse price"],
        rows=[{"title": workspace_slug, "price": 10}],
        export_preview={"rows": [{"title": workspace_slug, "price": 10}]},
        row_count=1,
        average_completeness_percent=100,
        status="saved",
        created_at=created_at,
    )
    session.add(dataset_version)
    await session.flush()

    dataset_drift_event = DatasetDriftEvent(
        workspace_id=workspace.id,
        project_id=project.id,
        dataset_id=dataset.id,
        dataset_version_id=dataset_version.id,
        event_type="ecommerce_product_drift",
        status="critical",
        thresholds={"completeness_drop_threshold_percent": 10},
        summary={"critical_tasks": 1},
        items=[{"task_id": str(task.id), "status": "critical"}],
        audit_events=[{"event": "fixture"}],
        note="Fixture drift",
        created_at=created_at,
    )
    session.add(dataset_drift_event)
    await session.flush()

    raw_record = RawRecord(
        workspace_id=workspace.id,
        project_id=project.id,
        source_id=source.id,
        task_run_id=run.id,
        record_type="manual_json",
        source_url=None,
        content={"full_name": workspace_slug, "stars": 10},
        content_hash=f"{workspace_slug}-hash",
        screenshot_url=None,
        collected_at=created_at,
        created_at=created_at,
    )
    session.add(raw_record)
    await session.flush()

    entity = Entity(
        workspace_id=workspace.id,
        project_id=project.id,
        entity_type="github_repo",
        external_id=workspace_slug,
        canonical_url=None,
        name=workspace_slug,
        domain="osint",
        latest_snapshot_id=None,
        first_seen_at=created_at,
        last_seen_at=created_at,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(entity)
    await session.flush()

    previous_snapshot = EntitySnapshot(
        entity_id=entity.id,
        raw_record_id=raw_record.id,
        snapshot_data={"stars": 1},
        metrics={"stars": 1},
        captured_at=created_at - timedelta(hours=1),
        created_at=created_at - timedelta(hours=1),
    )
    current_snapshot = EntitySnapshot(
        entity_id=entity.id,
        raw_record_id=raw_record.id,
        snapshot_data={"stars": 10},
        metrics={"stars": 10},
        captured_at=created_at,
        created_at=created_at,
    )
    session.add_all([previous_snapshot, current_snapshot])
    await session.flush()
    entity.latest_snapshot_id = current_snapshot.id

    signal = Signal(
        workspace_id=workspace.id,
        project_id=project.id,
        entity_id=entity.id,
        signal_type="star_growth",
        previous_snapshot_id=previous_snapshot.id,
        current_snapshot_id=current_snapshot.id,
        current_value=10,
        previous_value=1,
        delta=9,
        delta_ratio=9,
        confidence=90,
        severity="medium",
        metadata_json={"metric": "stars"},
        detected_at=created_at,
    )
    intelligence = IntelligenceItem(
        workspace_id=workspace.id,
        project_id=project.id,
        title="Fixture Intelligence",
        summary="Fixture summary",
        intelligence_type="trend",
        status="new",
        impact_score=80,
        confidence_score=90,
        novelty_score=70,
        urgency_score=60,
        final_score=75,
        generated_by="hybrid",
        domain="osint",
        created_at=created_at,
        updated_at=created_at,
    )
    report = Report(
        workspace_id=workspace.id,
        project_id=project.id,
        report_type="daily",
        title="Fixture Report",
        content="# Fixture",
        status="generated",
        period_start=created_at - timedelta(days=1),
        period_end=created_at,
        created_at=created_at,
    )
    alert_rule = AlertRule(
        workspace_id=workspace.id,
        project_id=project.id,
        name="Fixture Alert",
        signal_type="star_growth",
        condition={"field": "severity", "op": "in", "value": ["medium"]},
        channel="in_app",
        enabled=True,
        created_at=created_at,
    )
    session.add_all([signal, intelligence, report, alert_rule])
    await session.flush()

    evidence = Evidence(
        intelligence_id=intelligence.id,
        signal_id=signal.id,
        entity_id=entity.id,
        raw_record_id=raw_record.id,
        evidence_type="signal",
        title="Fixture Evidence",
        url=None,
        excerpt="Fixture",
        highlighted_text=None,
        reference_metadata={"source": "test"},
        created_at=created_at,
    )
    feedback = IntelligenceFeedback(
        intelligence_id=intelligence.id,
        user_id=user.id,
        feedback_type="useful",
        comment=None,
        created_at=created_at,
    )
    report_audit = ReportAuditEvent(
        workspace_id=workspace.id,
        report_id=report.id,
        actor_id=user.id,
        event_type="generated",
        from_status=None,
        to_status="generated",
        metadata_json=None,
        created_at=created_at,
    )
    subscription = ReportSubscription(
        workspace_id=workspace.id,
        user_id=user.id,
        project_id=project.id,
        report_type="daily",
        schedule_time="09:00",
        timezone="Asia/Shanghai",
        channels=["in_app"],
        enabled=True,
        next_run_at=None,
        last_sent_at=None,
        created_at=created_at,
        updated_at=created_at,
    )
    alert_event = AlertEvent(
        rule_id=alert_rule.id,
        signal_id=signal.id,
        status="triggered",
        payload={"signal_type": "star_growth"},
        triggered_at=created_at,
        sent_at=None,
    )
    session.add_all([evidence, feedback, report_audit, subscription, alert_event])
    await session.flush()

    notification = Notification(
        user_id=user.id,
        title="Fixture Notification",
        body="Fixture body",
        notification_type="alert",
        reference_type="alert_event",
        reference_id=alert_event.id,
        is_read=False,
        created_at=created_at,
    )
    session.add(notification)
    await session.flush()

    subscription_run = ReportSubscriptionRun(
        workspace_id=workspace.id,
        subscription_id=subscription.id,
        report_id=report.id,
        trigger_type="manual",
        status="success",
        delivered_channels=["in_app"],
        skipped_channels={},
        error_message=None,
        started_at=created_at,
        finished_at=created_at,
    )
    session.add(subscription_run)
    await session.flush()

    return {
        "user_id": user.id,
        "workspace_id": workspace.id,
        "project_id": project.id,
        "source_id": source.id,
        "task_id": task.id,
        "run_id": run.id,
        "dataset_id": dataset.id,
        "dataset_version_id": dataset_version.id,
        "dataset_drift_event_id": dataset_drift_event.id,
        "raw_record_id": raw_record.id,
        "entity_id": entity.id,
        "current_snapshot_id": current_snapshot.id,
        "signal_id": signal.id,
        "intelligence_id": intelligence.id,
        "report_id": report.id,
        "alert_rule_id": alert_rule.id,
        "notification_id": notification.id,
    }
