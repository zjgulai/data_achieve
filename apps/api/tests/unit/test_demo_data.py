from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

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
)
from data_intelligence_hub.seed.demo_data import (
    DOMAIN_FRESHNESS_TARGETS,
    _build_context,
    _delete_legacy_demo_records,
    _id,
    _merge_collection_layer,
    _merge_dataset_layer,
    _merge_entity_layer,
    _merge_identity,
    _merge_intelligence_layer,
    _merge_projects,
    _merge_reports_alerts_notifications,
    cleanup_demo_noise,
)


def test_demo_seed_covers_navigation_domains() -> None:
    context = _build_context()

    assert set(context.project_ids) == {"osint", "ecommerce", "social", "competitor"}
    assert set(context.source_ids) == {"osint", "amazon", "social", "competitor"}
    assert set(context.dataset_ids) == {"ecommerce-tools"}
    assert set(context.dataset_version_ids) == {"ecommerce-tools-v1"}
    assert set(context.intelligence_ids) == {
        "osint-scrapy-momentum",
        "amazon-margin-risk",
        "social-method-window",
        "competitor-landing-shift",
    }


def test_demo_freshness_targets_are_collector_backed() -> None:
    assert set(DOMAIN_FRESHNESS_TARGETS) == {"osint", "ecommerce", "social", "competitor"}

    for target in DOMAIN_FRESHNESS_TARGETS.values():
        assert target["collector_type"] in {
            "github_repo",
            "github_topic",
            "generic_web",
            "manual_json",
        }
        assert 1 <= target["target_hours"] <= 24
        assert target["platforms"]


@pytest.mark.asyncio
async def test_demo_collection_tasks_use_auto_freshness_policy() -> None:
    context = _build_context()
    now = datetime.now(UTC)
    session_factory = await _create_demo_cleanup_session_factory()
    async with session_factory() as session:
        await _merge_identity(
            session,
            context,
            "owner@example.com",
            "strong-password",
            "Owner",
            now,
        )
        await _merge_projects(session, context, now)
        await _merge_collection_layer(session, context, now)
        await session.commit()

    async with session_factory() as session:
        tasks = [
            task
            for task_id in context.task_ids.values()
            if (task := await session.get(CollectionTask, task_id)) is not None
        ]

    assert len(tasks) == 4
    assert {task.config["schedule_policy"] for task in tasks if task.config is not None} == {
        "auto_freshness"
    }


@pytest.mark.asyncio
async def test_demo_seed_includes_product_dataset_asset() -> None:
    session_factory = await _create_demo_cleanup_session_factory()
    context = _build_context()
    now = datetime(2026, 6, 18, 10, 0, tzinfo=UTC)
    async with session_factory() as session:
        await _seed_curated_demo(session, now)
        await session.commit()

    async with session_factory() as session:
        dataset = await session.get(Dataset, context.dataset_ids["ecommerce-tools"])
        version = await session.get(
            DatasetVersion,
            context.dataset_version_ids["ecommerce-tools-v1"],
        )
        drift_event = await session.get(
            DatasetDriftEvent,
            context.dataset_drift_event_ids["ecommerce-tools-field-gap"],
        )

    assert dataset is not None
    assert dataset.name == "电商平台采集工具与 SOP 数据集"
    assert dataset.dataset_type == "ecommerce_product"
    assert version is not None
    assert version.dataset_id == dataset.id
    assert version.row_count == 2
    assert version.average_completeness_percent == 92
    assert version.selected_fields == [
        "title",
        "price",
        "sku",
        "canonical_url",
        "method_quality",
        "collection_methods",
    ]
    assert version.rows[0]["values"]["title"] == "Amazon BSR + Keepa 价格排名雷达"
    assert version.rows[1]["missing_fields"] == ["price"]
    assert version.export_preview["schema"]["primary_key"] == "canonical_url"
    assert drift_event is not None
    assert drift_event.dataset_version_id == version.id
    assert drift_event.status == "warning"
    assert drift_event.summary["missing_field_tasks"] == 1


@pytest.mark.asyncio
async def test_curated_demo_visible_copy_is_not_demo_or_sample_copy() -> None:
    session_factory = await _create_demo_cleanup_session_factory()
    now = datetime(2026, 6, 14, 10, 0, tzinfo=UTC)
    async with session_factory() as session:
        await _seed_curated_demo(session, now)
        visible_texts = await _curated_demo_visible_texts(session)

    forbidden_terms = ("sample", "demo-", "demo_", "placeholder", "示例", "样本")
    offenders = [
        text
        for text in visible_texts
        if any(term in text.lower() for term in forbidden_terms)
    ]

    assert offenders == []


@pytest.mark.asyncio
async def test_legacy_demo_cleanup_clears_latest_snapshot_reference() -> None:
    session_factory = await _create_demo_cleanup_session_factory()
    async with session_factory() as session:
        await _create_legacy_demo_snapshot_reference(session)
        await session.commit()

    async with session_factory() as session:
        await _delete_legacy_demo_records(session)
        await session.commit()

    async with session_factory() as session:
        assert await session.get(EntitySnapshot, _id("snapshot-tiktok-current")) is None
        assert await session.get(Entity, _id("entity-tiktok-creator")) is None
        assert await session.get(TaskRun, _id("run-tiktok-manual-failed")) is None
        assert await session.get(Source, _id("source-legacy-extra")) is None
        assert await session.get(Project, _id("project-content")) is None


@pytest.mark.asyncio
async def test_demo_noise_cleanup_dry_run_then_removes_runtime_noise() -> None:
    session_factory = await _create_demo_cleanup_session_factory()
    context = _build_context()
    now = datetime(2026, 6, 14, 10, 0, tzinfo=UTC)
    async with session_factory() as session:
        await _seed_curated_demo(session, now)
        await _create_runtime_noise(session, now)
        await session.commit()

    async with session_factory() as session:
        report = await cleanup_demo_noise(session, dry_run=True)
        await session.commit()

    assert report.dry_run is True
    assert report.counts["task_runs"] == 1
    assert report.counts["raw_records"] == 1
    assert report.counts["entity_snapshots"] == 1
    assert report.counts["signals"] == 1
    assert report.counts["intelligence_items"] == 1
    assert report.counts["reports"] == 1
    assert (
        "Portable Air Quality Filter has a data quality anomaly"
        in report.samples["intelligence_items"]
    )

    async with session_factory() as session:
        assert await session.get(IntelligenceItem, _id("noise-intelligence")) is not None
        report = await cleanup_demo_noise(session, dry_run=False)
        await session.commit()

    assert report.dry_run is False
    async with session_factory() as session:
        assert await session.get(TaskRun, _id("noise-run")) is None
        assert await session.get(RawRecord, _id("noise-raw")) is None
        assert await session.get(EntitySnapshot, _id("noise-snapshot")) is None
        assert await session.get(Signal, _id("noise-signal")) is None
        assert await session.get(IntelligenceItem, _id("noise-intelligence")) is None
        assert await session.get(Report, _id("noise-report")) is None
        assert await session.get(AlertRule, _id("noise-alert-rule")) is None
        assert await session.get(Notification, _id("noise-notification")) is None

        curated_intelligence = await session.get(
            IntelligenceItem,
            context.intelligence_ids["amazon-margin-risk"],
        )
        curated_task = await session.get(CollectionTask, context.task_ids["amazon"])
        curated_entity = await session.get(Entity, context.entity_ids["amazon-product"])

    assert curated_intelligence is not None
    assert curated_task is not None
    assert curated_task.schedule_cron is None
    assert curated_entity is not None
    assert curated_entity.latest_snapshot_id == context.snapshot_ids["amazon-current"]


async def _create_demo_cleanup_session_factory() -> async_sessionmaker[AsyncSession]:
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


async def _seed_curated_demo(session: AsyncSession, now: datetime) -> None:
    context = _build_context()
    await _merge_identity(session, context, "owner@example.com", "strong-password", "Owner", now)
    await _merge_projects(session, context, now)
    await _merge_collection_layer(session, context, now)
    await _merge_entity_layer(session, context, now)
    await _merge_dataset_layer(session, context, now)
    await _merge_intelligence_layer(session, context, now)
    await _merge_reports_alerts_notifications(session, context, now)


async def _curated_demo_visible_texts(session: AsyncSession) -> list[str]:
    visible_texts: list[str] = []

    for model, fields in (
        (Source, ("name", "url")),
        (CollectionTask, ("name", "collector_type", "status")),
        (Dataset, ("name", "dataset_type", "status", "description")),
        (Entity, ("name", "canonical_url", "external_id", "entity_type")),
        (IntelligenceItem, ("title", "summary", "intelligence_type", "domain")),
        (Evidence, ("title", "url", "excerpt", "highlighted_text")),
        (Report, ("title", "content", "report_type", "status")),
        (AlertRule, ("name", "signal_type", "channel")),
        (Notification, ("title", "body", "notification_type", "reference_type")),
    ):
        rows = (await session.scalars(select(model))).all()
        for row in rows:
            for field in fields:
                value = getattr(row, field)
                if value:
                    visible_texts.append(str(value))

    raw_records = (await session.scalars(select(RawRecord))).all()
    for raw_record in raw_records:
        if raw_record.source_url:
            visible_texts.append(raw_record.source_url)
        visible_texts.append(
            json.dumps(_without_internal_dataset_marker(raw_record.content), ensure_ascii=False)
        )

    alert_events = (await session.scalars(select(AlertEvent))).all()
    for alert_event in alert_events:
        visible_texts.append(
            json.dumps(_without_internal_dataset_marker(alert_event.payload), ensure_ascii=False)
        )

    return visible_texts


def _without_internal_dataset_marker(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_internal_dataset_marker(item)
            for key, item in value.items()
            if key != "dataset"
        }
    if isinstance(value, list):
        return [_without_internal_dataset_marker(item) for item in value]
    return value


async def _create_runtime_noise(session: AsyncSession, now: datetime) -> None:
    context = _build_context()
    project_id = context.project_ids["ecommerce"]
    source_id = context.source_ids["amazon"]
    task_id = context.task_ids["amazon"]
    run_id = _id("noise-run")
    raw_record_id = _id("noise-raw")
    entity_id = context.entity_ids["amazon-product"]
    snapshot_id = _id("noise-snapshot")
    signal_id = _id("noise-signal")
    intelligence_id = _id("noise-intelligence")
    report_id = _id("noise-report")
    alert_rule_id = _id("noise-alert-rule")

    session.add(
        TaskRun(
            id=run_id,
            task_id=task_id,
            workspace_id=context.workspace_id,
            status="failed",
            started_at=now,
            finished_at=now,
            records_count=1,
            entities_count=1,
            error_message="runtime demo noise",
            error_traceback=None,
            logs=[],
            created_at=now,
        )
    )
    await session.flush()

    session.add(
        RawRecord(
            id=raw_record_id,
            workspace_id=context.workspace_id,
            project_id=project_id,
            source_id=source_id,
            task_run_id=run_id,
            record_type="metric_snapshot",
            source_url="https://www.amazon.com/dp/noise",
            content={"name": "Portable Air Quality Filter", "price": None},
            content_hash="noise-runtime-hash",
            screenshot_url=None,
            collected_at=now,
            created_at=now,
        )
    )
    await session.flush()

    session.add(
        EntitySnapshot(
            id=snapshot_id,
            entity_id=entity_id,
            raw_record_id=raw_record_id,
            snapshot_data={"metrics": {"price": None}},
            metrics={"price": None},
            captured_at=now,
            created_at=now,
        )
    )
    await session.flush()

    entity = await session.get(Entity, entity_id)
    assert entity is not None
    entity.latest_snapshot_id = snapshot_id
    await session.flush()

    session.add(
        Signal(
            id=signal_id,
            workspace_id=context.workspace_id,
            project_id=project_id,
            entity_id=entity_id,
            signal_type="data_quality_anomaly",
            previous_snapshot_id=context.snapshot_ids["amazon-current"],
            current_snapshot_id=snapshot_id,
            current_value=0.6,
            previous_value=None,
            delta=None,
            delta_ratio=None,
            confidence=80.0,
            severity="medium",
            metadata_json={"task_id": str(task_id), "task_run_id": str(run_id)},
            detected_at=now,
        )
    )
    await session.flush()

    session.add(
        IntelligenceItem(
            id=intelligence_id,
            workspace_id=context.workspace_id,
            project_id=project_id,
            title="Portable Air Quality Filter has a data quality anomaly",
            summary="runtime demo noise",
            intelligence_type="anomaly",
            status="new",
            impact_score=56.15,
            confidence_score=56.15,
            novelty_score=56.15,
            urgency_score=56.15,
            final_score=56.15,
            generated_by="hybrid",
            domain="ecommerce",
            created_at=now,
            updated_at=now,
        )
    )
    await session.flush()

    session.add(
        Evidence(
            id=_id("noise-evidence"),
            intelligence_id=intelligence_id,
            signal_id=signal_id,
            entity_id=entity_id,
            raw_record_id=raw_record_id,
            evidence_type="signal",
            title="Signal data_quality_anomaly",
            url=None,
            excerpt="runtime demo noise",
            highlighted_text=None,
            reference_metadata={"dataset": "demo_runtime_noise"},
            created_at=now,
        )
    )
    await session.flush()

    session.add(
        Report(
            id=report_id,
            workspace_id=context.workspace_id,
            project_id=project_id,
            report_type="daily",
            title="Runtime noise report",
            content="runtime demo noise",
            status="generated",
            period_start=now - timedelta(days=1),
            period_end=now,
            created_at=now,
        )
    )
    await session.flush()

    session.add(
        ReportAuditEvent(
            id=_id("noise-report-audit"),
            workspace_id=context.workspace_id,
            report_id=report_id,
            actor_id=context.user_id,
            event_type="generated",
            from_status=None,
            to_status="generated",
            metadata_json=None,
            created_at=now,
        )
    )
    session.add(
        ReportSubscription(
            id=_id("noise-report-subscription"),
            workspace_id=context.workspace_id,
            user_id=context.user_id,
            project_id=project_id,
            report_type="daily",
            schedule_time="09:30",
            timezone="Asia/Shanghai",
            channels=["in_app"],
            enabled=True,
            next_run_at=now,
            last_sent_at=None,
            created_at=now,
            updated_at=now,
        )
    )
    await session.flush()

    session.add(
        ReportSubscriptionRun(
            id=_id("noise-report-subscription-run"),
            workspace_id=context.workspace_id,
            subscription_id=_id("noise-report-subscription"),
            report_id=report_id,
            trigger_type="manual",
            status="success",
            delivered_channels=["in_app"],
            skipped_channels={},
            error_message=None,
            started_at=now,
            finished_at=now,
        )
    )
    session.add(
        AlertRule(
            id=alert_rule_id,
            workspace_id=context.workspace_id,
            project_id=project_id,
            name="Runtime noise alert rule",
            signal_type="data_quality_anomaly",
            condition={"field": "recent_failure_rate", "op": "gte", "value": 0.3},
            channel="in_app",
            enabled=True,
            created_at=now,
        )
    )
    await session.flush()

    session.add(
        AlertEvent(
            id=_id("noise-alert-event"),
            rule_id=alert_rule_id,
            signal_id=signal_id,
            status="triggered",
            payload={"title": "runtime demo noise"},
            triggered_at=now,
            sent_at=None,
        )
    )
    session.add(
        Notification(
            id=_id("noise-notification"),
            user_id=context.user_id,
            title="Runtime demo noise",
            body="runtime demo noise",
            notification_type="report_ready",
            reference_type="report",
            reference_id=report_id,
            is_read=False,
            created_at=now,
        )
    )
    await session.flush()


async def _create_legacy_demo_snapshot_reference(session: AsyncSession) -> None:
    now = datetime(2026, 6, 13, 10, 0, tzinfo=UTC)
    user_id = _id("user-owner")
    workspace_id = _id("workspace-main")
    project_id = _id("project-content")
    source_id = _id("source-tiktok")
    extra_source_id = _id("source-legacy-extra")
    task_id = _id("task-tiktok")
    run_id = _id("run-tiktok-success")
    manual_run_id = _id("run-tiktok-manual-failed")
    raw_record_id = _id("raw-tiktok-current")
    entity_id = _id("entity-tiktok-creator")
    snapshot_id = _id("snapshot-tiktok-current")

    session.add(
        User(
            id=user_id,
            email="legacy-owner@example.com",
            password_hash="hashed-password",
            name="Legacy Owner",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    await session.flush()

    session.add(
        Workspace(
            id=workspace_id,
            name="Legacy Workspace",
            slug="legacy-workspace",
            owner_id=user_id,
            created_at=now,
            updated_at=now,
        )
    )
    await session.flush()

    session.add(
        Project(
            id=project_id,
            workspace_id=workspace_id,
            name="Legacy Content Project",
            description="Legacy demo project",
            domain="content",
            status="active",
            owner_id=user_id,
            created_at=now,
            updated_at=now,
        )
    )
    await session.flush()

    session.add(
        Source(
            id=source_id,
            workspace_id=workspace_id,
            project_id=project_id,
            name="Legacy TikTok Source",
            type="manual_json",
            url=None,
            config={},
            schedule_cron=None,
            enabled=True,
            created_at=now,
            updated_at=now,
        )
    )
    await session.flush()

    session.add(
        Source(
            id=extra_source_id,
            workspace_id=workspace_id,
            project_id=project_id,
            name="Legacy Extra Source",
            type="manual_json",
            url=None,
            config={},
            schedule_cron=None,
            enabled=False,
            created_at=now,
            updated_at=now,
        )
    )
    await session.flush()

    session.add(
        CollectionTask(
            id=task_id,
            workspace_id=workspace_id,
            project_id=project_id,
            source_id=source_id,
            collector_type="manual_json",
            name="Legacy TikTok Task",
            schedule_cron=None,
            status="enabled",
            config={},
            success_count=1,
            failure_count=0,
            last_run_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    await session.flush()

    session.add(
        TaskRun(
            id=run_id,
            task_id=task_id,
            workspace_id=workspace_id,
            status="success",
            started_at=now,
            finished_at=now,
            records_count=1,
            entities_count=1,
            error_message=None,
            error_traceback=None,
            logs=[],
            created_at=now,
        )
    )
    await session.flush()

    session.add(
        TaskRun(
            id=manual_run_id,
            task_id=task_id,
            workspace_id=workspace_id,
            status="failed",
            started_at=now,
            finished_at=now,
            records_count=0,
            entities_count=0,
            error_message="Collector config field is required: entity_type",
            error_traceback=None,
            logs=[],
            created_at=now,
        )
    )
    await session.flush()

    session.add(
        RawRecord(
            id=raw_record_id,
            workspace_id=workspace_id,
            project_id=project_id,
            source_id=source_id,
            task_run_id=run_id,
            record_type="manual_json",
            source_url=None,
            content={"legacy": True},
            content_hash="legacy-tiktok-current",
            screenshot_url=None,
            collected_at=now,
            created_at=now,
        )
    )
    await session.flush()

    entity = Entity(
        id=entity_id,
        workspace_id=workspace_id,
        project_id=project_id,
        entity_type="creator",
        external_id="legacy-tiktok-creator",
        canonical_url=None,
        name="Legacy TikTok Creator",
        domain="content",
        latest_snapshot_id=None,
        first_seen_at=now,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(entity)
    await session.flush()

    session.add(
        EntitySnapshot(
            id=snapshot_id,
            entity_id=entity_id,
            raw_record_id=raw_record_id,
            snapshot_data={"legacy": True},
            metrics={"views": 1},
            captured_at=now,
            created_at=now,
        )
    )
    await session.flush()

    entity.latest_snapshot_id = snapshot_id
    await session.flush()
