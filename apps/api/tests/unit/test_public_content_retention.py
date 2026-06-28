from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.maintenance.public_content_retention import (
    cleanup_retained_public_content_assets,
)
from data_intelligence_hub.models import (
    Base,
    CollectionTask,
    Dataset,
    DatasetDriftEvent,
    DatasetExportJob,
    DatasetVersion,
    Entity,
    EntitySnapshot,
    Notification,
    Project,
    RawRecord,
    Report,
    ReportAuditEvent,
    Source,
    TaskRun,
    User,
    Workspace,
    WorkspaceMember,
)


@pytest.mark.asyncio
async def test_retained_public_content_cleanup_dry_run_then_removes_expired_asset_graph(
    tmp_path: Path,
) -> None:
    session_factory = await _create_session_factory()
    now = datetime.now(UTC)
    export_root = tmp_path / "exports"
    export_root.mkdir()

    async with session_factory() as session:
        old_fixture = await _create_public_content_fixture(
            session,
            email="retained-public-content-old@example.com",
            slug="retained-old",
            created_at=now - timedelta(days=8),
            export_root=export_root,
        )
        recent_fixture = await _create_public_content_fixture(
            session,
            email="retained-public-content-recent@example.com",
            slug="retained-recent",
            created_at=now,
            export_root=export_root,
        )
        protected_fixture = await _create_public_content_fixture(
            session,
            email="e2e-old@example.com",
            slug="e2e-old",
            created_at=now - timedelta(days=8),
            export_root=export_root,
        )
        await session.commit()

    async with session_factory() as session:
        report = await cleanup_retained_public_content_assets(
            session,
            dry_run=True,
            older_than_hours=24 * 7,
            export_root=export_root,
        )
        await session.commit()

    assert report.dry_run is True
    assert report.counts["users"] == 1
    assert report.counts["workspaces"] == 1
    assert report.counts["sources"] == 1
    assert report.counts["collection_tasks"] == 1
    assert report.counts["task_runs"] == 1
    assert report.counts["raw_records"] == 1
    assert report.counts["entities"] == 1
    assert report.counts["entity_snapshots"] == 1
    assert report.counts["datasets"] == 1
    assert report.counts["dataset_versions"] == 1
    assert report.counts["dataset_drift_events"] == 1
    assert report.counts["dataset_export_jobs"] == 1
    assert report.counts["reports"] == 1
    assert report.counts["report_audit_events"] == 1
    assert report.counts["notifications"] == 1
    assert report.counts["export_artifact_files"] == 1
    assert report.counts["export_artifact_path_violations"] == 0
    assert report.samples["users"] == ["retained-public-content-old@example.com"]
    assert report.policy["cleanup_ready"] is True
    assert old_fixture["artifact_path"].is_file()

    async with session_factory() as session:
        assert await session.get(User, old_fixture["user_id"]) is not None
        report = await cleanup_retained_public_content_assets(
            session,
            dry_run=False,
            older_than_hours=24 * 7,
            export_root=export_root,
        )
        await session.commit()

    assert report.dry_run is False
    assert not old_fixture["artifact_path"].exists()
    async with session_factory() as session:
        assert await session.get(User, old_fixture["user_id"]) is None
        assert await session.get(Workspace, old_fixture["workspace_id"]) is None
        assert await session.get(Source, old_fixture["source_id"]) is None
        assert await session.get(CollectionTask, old_fixture["task_id"]) is None
        assert await session.get(TaskRun, old_fixture["task_run_id"]) is None
        assert await session.get(RawRecord, old_fixture["raw_record_id"]) is None
        assert await session.get(Entity, old_fixture["entity_id"]) is None
        assert await session.get(EntitySnapshot, old_fixture["snapshot_id"]) is None
        assert await session.get(Dataset, old_fixture["dataset_id"]) is None
        assert await session.get(DatasetVersion, old_fixture["dataset_version_id"]) is None
        assert await session.get(DatasetDriftEvent, old_fixture["drift_event_id"]) is None
        assert await session.get(DatasetExportJob, old_fixture["export_job_id"]) is None
        assert await session.get(Report, old_fixture["report_id"]) is None
        assert await session.get(ReportAuditEvent, old_fixture["report_audit_event_id"]) is None
        assert await session.get(Notification, old_fixture["notification_id"]) is None

        assert await session.get(User, recent_fixture["user_id"]) is not None
        assert await session.get(User, protected_fixture["user_id"]) is not None
    assert recent_fixture["artifact_path"].is_file()
    assert protected_fixture["artifact_path"].is_file()


@pytest.mark.asyncio
async def test_retained_public_content_cleanup_blocks_export_artifact_outside_root(
    tmp_path: Path,
) -> None:
    session_factory = await _create_session_factory()
    now = datetime.now(UTC)
    export_root = tmp_path / "exports"
    export_root.mkdir()
    outside_artifact = tmp_path / "outside.csv"

    async with session_factory() as session:
        fixture = await _create_public_content_fixture(
            session,
            email="retained-public-content-outside@example.com",
            slug="retained-outside",
            created_at=now - timedelta(days=8),
            export_root=export_root,
            artifact_path=outside_artifact,
        )
        await session.commit()

    async with session_factory() as session:
        report = await cleanup_retained_public_content_assets(
            session,
            dry_run=True,
            older_than_hours=24 * 7,
            export_root=export_root,
        )

    assert report.counts["dataset_export_jobs"] == 1
    assert report.counts["export_artifact_files"] == 0
    assert report.counts["export_artifact_path_violations"] == 1
    assert report.policy["cleanup_ready"] is False

    async with session_factory() as session:
        with pytest.raises(RuntimeError, match="outside_root"):
            await cleanup_retained_public_content_assets(
                session,
                dry_run=False,
                older_than_hours=24 * 7,
                export_root=export_root,
            )
        await session.rollback()

    assert outside_artifact.is_file()
    async with session_factory() as session:
        assert await session.get(User, fixture["user_id"]) is not None
        assert await session.get(DatasetExportJob, fixture["export_job_id"]) is not None


@pytest.mark.asyncio
async def test_retained_public_content_cleanup_follows_member_workspace_lineage(
    tmp_path: Path,
) -> None:
    session_factory = await _create_session_factory()
    now = datetime.now(UTC)
    export_root = tmp_path / "exports"
    export_root.mkdir()

    async with session_factory() as session:
        fixture = await _create_public_content_fixture(
            session,
            email="retained-public-content-member@example.com",
            slug="retained-member",
            created_at=now - timedelta(days=8),
            export_root=export_root,
            workspace_owner_email="shared-owner@example.com",
            include_refresh_run=True,
        )
        await session.commit()

    async with session_factory() as session:
        report = await cleanup_retained_public_content_assets(
            session,
            dry_run=True,
            older_than_hours=24 * 7,
            export_root=export_root,
        )

    assert report.counts["users"] == 1
    assert report.counts["workspaces"] == 0
    assert report.counts["workspace_members"] == 1
    assert report.counts["projects"] == 0
    assert report.counts["sources"] == 1
    assert report.counts["collection_tasks"] == 1
    assert report.counts["task_runs"] == 2
    assert report.counts["raw_records"] == 2
    assert report.counts["entities"] == 2
    assert report.counts["entity_snapshots"] == 2
    assert report.counts["datasets"] == 1
    assert report.counts["dataset_versions"] == 1
    assert report.counts["dataset_export_jobs"] == 1
    assert report.counts["reports"] == 1
    assert report.counts["report_audit_events"] == 1
    assert report.counts["notifications"] == 1

    async with session_factory() as session:
        report = await cleanup_retained_public_content_assets(
            session,
            dry_run=False,
            older_than_hours=24 * 7,
            export_root=export_root,
        )
        await session.commit()

    assert report.dry_run is False
    assert not fixture["artifact_path"].exists()
    async with session_factory() as session:
        assert await session.get(User, fixture["user_id"]) is None
        assert await session.get(WorkspaceMember, fixture["member_id"]) is None
        assert await session.get(Source, fixture["source_id"]) is None
        assert await session.get(CollectionTask, fixture["task_id"]) is None
        assert await session.get(TaskRun, fixture["task_run_id"]) is None
        assert await session.get(TaskRun, fixture["refresh_task_run_id"]) is None
        assert await session.get(RawRecord, fixture["raw_record_id"]) is None
        assert await session.get(RawRecord, fixture["refresh_raw_record_id"]) is None
        assert await session.get(Entity, fixture["entity_id"]) is None
        assert await session.get(Entity, fixture["refresh_entity_id"]) is None
        assert await session.get(EntitySnapshot, fixture["snapshot_id"]) is None
        assert await session.get(EntitySnapshot, fixture["refresh_snapshot_id"]) is None
        assert await session.get(Dataset, fixture["dataset_id"]) is None
        assert await session.get(DatasetVersion, fixture["dataset_version_id"]) is None
        assert await session.get(DatasetExportJob, fixture["export_job_id"]) is None
        assert await session.get(Report, fixture["report_id"]) is None
        assert await session.get(ReportAuditEvent, fixture["report_audit_event_id"]) is None
        assert await session.get(Notification, fixture["notification_id"]) is None

        assert await session.get(User, fixture["workspace_owner_id"]) is not None
        assert await session.get(Workspace, fixture["workspace_id"]) is not None
        assert await session.get(Project, fixture["project_id"]) is not None
        assert await session.get(WorkspaceMember, fixture["owner_member_id"]) is not None


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


async def _create_public_content_fixture(
    session: AsyncSession,
    *,
    email: str,
    slug: str,
    created_at: datetime,
    export_root: Path,
    artifact_path: Path | None = None,
    workspace_owner_email: str | None = None,
    include_refresh_run: bool = False,
) -> dict[str, Any]:
    user = User(
        email=email,
        password_hash="hashed-password",
        name="Retained Public Content",
        status="active",
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(user)
    await session.flush()

    workspace_owner = user
    owner_member = None
    if workspace_owner_email is not None:
        workspace_owner = User(
            email=workspace_owner_email,
            password_hash="hashed-password",
            name="Shared Workspace Owner",
            status="active",
            created_at=created_at,
            updated_at=created_at,
        )
        session.add(workspace_owner)
        await session.flush()

    workspace = Workspace(
        name=f"Workspace {slug}",
        slug=slug,
        owner_id=workspace_owner.id,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(workspace)
    await session.flush()

    if workspace_owner.id != user.id:
        owner_member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=workspace_owner.id,
            role="owner",
            created_at=created_at,
            updated_at=created_at,
        )
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role="owner" if workspace_owner.id == user.id else "member",
        created_at=created_at,
        updated_at=created_at,
    )
    project = Project(
        workspace_id=workspace.id,
        name=f"Project {slug}",
        description=None,
        domain="osint",
        status="active",
        owner_id=workspace_owner.id,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add_all([item for item in (owner_member, member, project) if item is not None])
    await session.flush()

    source = Source(
        workspace_id=workspace.id,
        project_id=project.id,
        name=f"Source {slug}",
        type="public_feed",
        url="https://hnrss.org/frontpage",
        config={"feed_url": "https://hnrss.org/frontpage"},
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
        collector_type="public_feed",
        name=f"Task {slug}",
        schedule_cron=None,
        status="enabled",
        config={"schedule_policy": "manual_refresh_only"},
        success_count=1,
        failure_count=0,
        last_run_at=created_at,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(task)
    await session.flush()

    task_run = TaskRun(
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
    session.add(task_run)
    await session.flush()

    raw_record = RawRecord(
        workspace_id=workspace.id,
        project_id=project.id,
        source_id=source.id,
        task_run_id=task_run.id,
        record_type="public_feed",
        source_url="https://hnrss.org/frontpage",
        content={"entries": [{"title": slug, "link": f"https://example.com/{slug}"}]},
        content_hash=f"{slug}-hash",
        screenshot_url=None,
        collected_at=created_at,
        created_at=created_at,
    )
    session.add(raw_record)
    await session.flush()

    entity = Entity(
        workspace_id=workspace.id,
        project_id=project.id,
        entity_type="public_content",
        external_id=f"https://example.com/{slug}",
        canonical_url=f"https://example.com/{slug}",
        name=slug,
        domain="osint",
        latest_snapshot_id=None,
        first_seen_at=created_at,
        last_seen_at=created_at,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(entity)
    await session.flush()

    snapshot = EntitySnapshot(
        entity_id=entity.id,
        raw_record_id=raw_record.id,
        snapshot_data={"title": slug},
        metrics={"row_count": 1},
        captured_at=created_at,
        created_at=created_at,
    )
    session.add(snapshot)
    await session.flush()
    entity.latest_snapshot_id = snapshot.id

    refresh_task_run = None
    refresh_raw_record = None
    refresh_entity = None
    refresh_snapshot = None
    if include_refresh_run:
        refresh_created_at = created_at + timedelta(minutes=5)
        refresh_task_run = TaskRun(
            task_id=task.id,
            workspace_id=workspace.id,
            status="success",
            started_at=refresh_created_at,
            finished_at=refresh_created_at,
            records_count=1,
            entities_count=1,
            error_message=None,
            error_traceback=None,
            logs=[],
            created_at=refresh_created_at,
        )
        session.add(refresh_task_run)
        await session.flush()

        refresh_raw_record = RawRecord(
            workspace_id=workspace.id,
            project_id=project.id,
            source_id=source.id,
            task_run_id=refresh_task_run.id,
            record_type="public_feed",
            source_url="https://hnrss.org/frontpage",
            content={
                "entries": [
                    {
                        "title": f"{slug} refresh",
                        "link": f"https://example.com/{slug}/refresh",
                    }
                ]
            },
            content_hash=f"{slug}-refresh-hash",
            screenshot_url=None,
            collected_at=refresh_created_at,
            created_at=refresh_created_at,
        )
        session.add(refresh_raw_record)
        await session.flush()

        refresh_entity = Entity(
            workspace_id=workspace.id,
            project_id=project.id,
            entity_type="public_content",
            external_id=f"https://example.com/{slug}/refresh",
            canonical_url=f"https://example.com/{slug}/refresh",
            name=f"{slug} refresh",
            domain="osint",
            latest_snapshot_id=None,
            first_seen_at=refresh_created_at,
            last_seen_at=refresh_created_at,
            created_at=refresh_created_at,
            updated_at=refresh_created_at,
        )
        session.add(refresh_entity)
        await session.flush()

        refresh_snapshot = EntitySnapshot(
            entity_id=refresh_entity.id,
            raw_record_id=refresh_raw_record.id,
            snapshot_data={"title": f"{slug} refresh"},
            metrics={"row_count": 1},
            captured_at=refresh_created_at,
            created_at=refresh_created_at,
        )
        session.add(refresh_snapshot)
        await session.flush()
        refresh_entity.latest_snapshot_id = refresh_snapshot.id

    dataset = Dataset(
        workspace_id=workspace.id,
        project_id=project.id,
        name=f"Dataset {slug}",
        dataset_type="public_content_update",
        status="active",
        description="Retained public content dataset",
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
        cleaning_plan_id=None,
        version_number=1,
        source_task_run_ids=[str(task_run.id)],
        selected_fields=["title", "link"],
        cleaning_script=["trim title"],
        rows=[
            {
                "values": {
                    "title": slug,
                    "link": f"https://example.com/{slug}",
                },
                "missing_fields": [],
            }
        ],
        export_preview={"rows": [{"title": slug, "link": f"https://example.com/{slug}"}]},
        row_count=1,
        average_completeness_percent=100,
        status="saved",
        created_at=created_at,
    )
    session.add(dataset_version)
    await session.flush()

    drift_event = DatasetDriftEvent(
        workspace_id=workspace.id,
        project_id=project.id,
        dataset_id=dataset.id,
        dataset_version_id=dataset_version.id,
        event_type="public_content_drift",
        status="ok",
        thresholds={"content_hash_required": True},
        summary={"checked_tasks": 1},
        items=[],
        audit_events=[],
        note="Retained public content drift",
        created_at=created_at,
    )
    session.add(drift_event)
    await session.flush()

    target_artifact = artifact_path or export_root / workspace.slug / f"{slug}.csv"
    target_artifact.parent.mkdir(parents=True, exist_ok=True)
    target_artifact.write_text("title,link\nRetained,https://example.com\n", encoding="utf-8")
    export_job = DatasetExportJob(
        workspace_id=workspace.id,
        project_id=project.id,
        dataset_id=dataset.id,
        dataset_version_id=dataset_version.id,
        created_by_user_id=user.id,
        export_format="csv",
        status="success",
        filename=f"{slug}.csv",
        content_type="text/csv; charset=utf-8",
        artifact_path=str(target_artifact),
        artifact_size_bytes=target_artifact.stat().st_size,
        row_count=1,
        checksum_sha256="0" * 64,
        error_message=None,
        audit_events=[],
        created_at=created_at,
        finished_at=created_at,
    )
    session.add(export_job)
    await session.flush()

    report = Report(
        workspace_id=workspace.id,
        project_id=project.id,
        report_type="public_content",
        title=f"Report {slug}",
        content="# Public content report",
        status="generated",
        period_start=created_at - timedelta(days=1),
        period_end=created_at,
        created_at=created_at,
    )
    session.add(report)
    await session.flush()

    report_audit_event = ReportAuditEvent(
        workspace_id=workspace.id,
        report_id=report.id,
        actor_id=user.id,
        event_type="public_content_report_asset_created",
        from_status=None,
        to_status="generated",
        metadata_json=None,
        created_at=created_at,
    )
    notification = Notification(
        user_id=user.id,
        title="Retained public content",
        body="Retained canary notification",
        notification_type="system",
        reference_type="report",
        reference_id=report.id,
        is_read=False,
        created_at=created_at,
    )
    session.add_all([report_audit_event, notification])
    await session.flush()

    return {
        "user_id": user.id,
        "workspace_owner_id": workspace_owner.id,
        "workspace_id": workspace.id,
        "member_id": member.id,
        "owner_member_id": owner_member.id if owner_member is not None else member.id,
        "project_id": project.id,
        "source_id": source.id,
        "task_id": task.id,
        "task_run_id": task_run.id,
        "refresh_task_run_id": refresh_task_run.id if refresh_task_run is not None else task_run.id,
        "raw_record_id": raw_record.id,
        "refresh_raw_record_id": (
            refresh_raw_record.id if refresh_raw_record is not None else raw_record.id
        ),
        "entity_id": entity.id,
        "refresh_entity_id": refresh_entity.id if refresh_entity is not None else entity.id,
        "snapshot_id": snapshot.id,
        "refresh_snapshot_id": (
            refresh_snapshot.id if refresh_snapshot is not None else snapshot.id
        ),
        "dataset_id": dataset.id,
        "dataset_version_id": dataset_version.id,
        "drift_event_id": drift_event.id,
        "export_job_id": export_job.id,
        "artifact_path": target_artifact,
        "report_id": report.id,
        "report_audit_event_id": report_audit_event.id,
        "notification_id": notification.id,
    }
