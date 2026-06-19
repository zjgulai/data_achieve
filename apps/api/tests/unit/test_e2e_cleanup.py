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
    CleaningPlan,
    CollectionTask,
    Dataset,
    DatasetDriftEvent,
    DatasetExportJob,
    DatasetVersion,
    Entity,
    EntitySnapshot,
    Evidence,
    ExtractionPlan,
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
    SiteAnalysis,
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
    assert report.counts["cleaning_plans"] == 1
    assert report.counts["dataset_drift_events"] == 1
    assert report.counts["dataset_export_jobs"] == 1
    assert report.counts["site_analyses"] == 1
    assert report.counts["extraction_plans"] == 1
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
        assert await session.get(CleaningPlan, old_fixture["cleaning_plan_id"]) is None
        assert await session.get(DatasetDriftEvent, old_fixture["dataset_drift_event_id"]) is None
        assert await session.get(DatasetExportJob, old_fixture["dataset_export_job_id"]) is None
        assert await session.get(SiteAnalysis, old_fixture["site_analysis_id"]) is None
        assert await session.get(ExtractionPlan, old_fixture["extraction_plan_id"]) is None
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


@pytest.mark.asyncio
async def test_e2e_cleanup_removes_shared_workspace_dataset_versions_for_e2e_users() -> None:
    session_factory = await _create_session_factory()
    now = datetime.now(UTC)
    old_created_at = now - timedelta(days=8)

    async with session_factory() as session:
        shared_owner = User(
            email="owner@example.com",
            password_hash="hashed-password",
            name="Shared Owner",
            status="active",
            created_at=old_created_at,
            updated_at=old_created_at,
        )
        e2e_user = User(
            email="e2e-shared@example.com",
            password_hash="hashed-password",
            name="E2E Shared User",
            status="active",
            created_at=old_created_at,
            updated_at=old_created_at,
        )
        session.add_all([shared_owner, e2e_user])
        await session.flush()

        shared_workspace = Workspace(
            name="Shared Training Workspace",
            slug="shared-training",
            owner_id=shared_owner.id,
            created_at=old_created_at,
            updated_at=old_created_at,
        )
        session.add(shared_workspace)
        await session.flush()

        shared_member = WorkspaceMember(
            workspace_id=shared_workspace.id,
            user_id=shared_owner.id,
            role="owner",
            created_at=old_created_at,
            updated_at=old_created_at,
        )
        e2e_member = WorkspaceMember(
            workspace_id=shared_workspace.id,
            user_id=e2e_user.id,
            role="member",
            created_at=old_created_at,
            updated_at=old_created_at,
        )
        shared_project = Project(
            workspace_id=shared_workspace.id,
            name="Shared Project",
            description=None,
            domain="ecommerce",
            status="active",
            owner_id=shared_owner.id,
            created_at=old_created_at,
            updated_at=old_created_at,
        )
        session.add_all([shared_member, e2e_member, shared_project])
        await session.flush()

        shared_dataset = Dataset(
            workspace_id=shared_workspace.id,
            project_id=shared_project.id,
            name="Product Dataset 2026-06-18",
            dataset_type="ecommerce_product",
            status="active",
            description="Shared dataset created during production E2E",
            created_at=old_created_at,
            updated_at=old_created_at,
        )
        session.add(shared_dataset)
        await session.flush()

        dataset_version = DatasetVersion(
            dataset_id=shared_dataset.id,
            workspace_id=shared_workspace.id,
            project_id=shared_project.id,
            created_by_user_id=e2e_user.id,
            version_number=1,
            source_task_run_ids=[],
            selected_fields=["title"],
            cleaning_script=["trim title"],
            rows=[{"title": "Demo Carry Bag"}],
            export_preview={"rows": [{"title": "Demo Carry Bag"}]},
            row_count=1,
            average_completeness_percent=100,
            status="saved",
            created_at=old_created_at,
        )
        session.add(dataset_version)
        await session.flush()

        drift_event = DatasetDriftEvent(
            workspace_id=shared_workspace.id,
            project_id=shared_project.id,
            dataset_id=shared_dataset.id,
            dataset_version_id=dataset_version.id,
            event_type="ecommerce_product_drift",
            status="critical",
            thresholds={"completeness_drop_threshold_percent": 10},
            summary={"critical_tasks": 1},
            items=[],
            audit_events=[],
            note="Shared E2E drift",
            created_at=old_created_at,
        )
        export_job = DatasetExportJob(
            workspace_id=shared_workspace.id,
            project_id=shared_project.id,
            dataset_id=shared_dataset.id,
            dataset_version_id=dataset_version.id,
            created_by_user_id=e2e_user.id,
            export_format="json",
            status="success",
            filename="shared.json",
            content_type="application/json",
            artifact_path="/tmp/shared.json",
            artifact_size_bytes=32,
            row_count=1,
            checksum_sha256="1" * 64,
            error_message=None,
            audit_events=[],
            created_at=old_created_at,
            finished_at=old_created_at,
        )
        session.add_all([drift_event, export_job])
        await session.commit()

        ids = {
            "shared_owner_id": shared_owner.id,
            "e2e_user_id": e2e_user.id,
            "shared_workspace_id": shared_workspace.id,
            "shared_project_id": shared_project.id,
            "shared_dataset_id": shared_dataset.id,
            "dataset_version_id": dataset_version.id,
            "drift_event_id": drift_event.id,
            "export_job_id": export_job.id,
            "e2e_member_id": e2e_member.id,
        }

    async with session_factory() as session:
        report = await cleanup_e2e_fixtures(session, dry_run=True, older_than_hours=24 * 7)
        await session.commit()

    assert report.counts["users"] == 1
    assert report.counts["workspaces"] == 0
    assert report.counts["projects"] == 0
    assert report.counts["datasets"] == 0
    assert report.counts["dataset_versions"] == 1
    assert report.counts["dataset_drift_events"] == 1
    assert report.counts["dataset_export_jobs"] == 1
    assert report.samples["users"] == ["e2e-shared@example.com"]

    async with session_factory() as session:
        report = await cleanup_e2e_fixtures(session, dry_run=False, older_than_hours=24 * 7)
        await session.commit()

    assert report.dry_run is False
    async with session_factory() as session:
        assert await session.get(User, ids["e2e_user_id"]) is None
        assert await session.get(WorkspaceMember, ids["e2e_member_id"]) is None
        assert await session.get(DatasetVersion, ids["dataset_version_id"]) is None
        assert await session.get(DatasetDriftEvent, ids["drift_event_id"]) is None
        assert await session.get(DatasetExportJob, ids["export_job_id"]) is None

        assert await session.get(User, ids["shared_owner_id"]) is not None
        assert await session.get(Workspace, ids["shared_workspace_id"]) is not None
        assert await session.get(Project, ids["shared_project_id"]) is not None
        assert await session.get(Dataset, ids["shared_dataset_id"]) is not None


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

    cleaning_plan = CleaningPlan(
        workspace_id=workspace.id,
        project_id=project.id,
        created_by_user_id=user.id,
        name=f"Fixture Cleaning Plan {workspace_slug}",
        version_number=1,
        target="ecommerce_product",
        selected_fields=["title", "price"],
        source_task_run_ids=[str(run.id)],
        rules=[
            {
                "field": "price",
                "operation": "parse_decimal",
                "description": "Parse price.",
            }
        ],
        cleaning_script=["parse price as decimal when present"],
        dry_run_preview={"rows_changed": 0},
        status="draft",
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(cleaning_plan)
    await session.flush()

    dataset_version = DatasetVersion(
        dataset_id=dataset.id,
        workspace_id=workspace.id,
        project_id=project.id,
        created_by_user_id=user.id,
        cleaning_plan_id=cleaning_plan.id,
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

    dataset_export_job = DatasetExportJob(
        workspace_id=workspace.id,
        project_id=project.id,
        dataset_id=dataset.id,
        dataset_version_id=dataset_version.id,
        created_by_user_id=user.id,
        export_format="csv",
        status="success",
        filename=f"{workspace_slug}.csv",
        content_type="text/csv; charset=utf-8",
        artifact_path=f"/tmp/{workspace_slug}.csv",
        artifact_size_bytes=32,
        row_count=1,
        checksum_sha256="0" * 64,
        error_message=None,
        audit_events=[{"event": "fixture"}],
        created_at=created_at,
        finished_at=created_at,
    )
    session.add(dataset_export_job)
    await session.flush()

    site_analysis = SiteAnalysis(
        workspace_id=workspace.id,
        project_id=project.id,
        created_by_user_id=user.id,
        requested_url=f"https://example.com/products/{workspace_slug}",
        target="ecommerce_product",
        status="analyzed",
        authorization_confirmed=True,
        analyzed_at=created_at,
        platform_profile={
            "platform_type": "independent_ecommerce",
            "confidence": 0.9,
            "indicators": ["fixture"],
            "risk_level": "low",
        },
        page_structure={
            "page_type": "product_detail",
            "title": workspace_slug,
            "canonical_url": f"https://example.com/products/{workspace_slug}",
            "script_count": 1,
            "form_count": 0,
            "image_count": 1,
            "product_schema_count": 1,
            "same_origin_link_count": 1,
            "text_sample": workspace_slug,
        },
        field_candidates=[
            {
                "key": "title",
                "label": "Title",
                "value": workspace_slug,
                "data_type": "string",
                "source": "fixture",
                "confidence": 0.9,
                "selected": True,
                "cleaning_rule": "trim",
            }
        ],
        tool_recommendations=[],
        cleaning_plan=[],
        source_draft={
            "type": "ecommerce_product_page",
            "config": {
                "url": f"https://example.com/products/{workspace_slug}",
                "fields": ["title"],
                "platform_hint": "independent_ecommerce",
            },
            "suggested_name": f"Fixture plan {workspace_slug}",
            "schedule_cron": None,
        },
        blocked_reasons=[],
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(site_analysis)
    await session.flush()

    extraction_plan = ExtractionPlan(
        workspace_id=workspace.id,
        project_id=project.id,
        site_analysis_id=site_analysis.id,
        created_by_user_id=user.id,
        name=f"Fixture plan {workspace_slug}",
        version_number=1,
        collector_type="ecommerce_product_page",
        selected_fields=["title"],
        source_draft=site_analysis.source_draft,
        schedule_cron=None,
        status="draft",
        risk_level="low",
        audit_events=[{"event": "fixture"}],
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(extraction_plan)
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
        "cleaning_plan_id": cleaning_plan.id,
        "dataset_version_id": dataset_version.id,
        "dataset_drift_event_id": dataset_drift_event.id,
        "dataset_export_job_id": dataset_export_job.id,
        "site_analysis_id": site_analysis.id,
        "extraction_plan_id": extraction_plan.id,
        "raw_record_id": raw_record.id,
        "entity_id": entity.id,
        "current_snapshot_id": current_snapshot.id,
        "signal_id": signal.id,
        "intelligence_id": intelligence.id,
        "report_id": report.id,
        "alert_rule_id": alert_rule.id,
        "notification_id": notification.id,
    }
