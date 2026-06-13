from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import (
    Base,
    CollectionTask,
    Entity,
    EntitySnapshot,
    Project,
    RawRecord,
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
)


def test_demo_seed_covers_navigation_domains() -> None:
    context = _build_context()

    assert set(context.project_ids) == {"osint", "ecommerce", "social", "competitor"}
    assert set(context.source_ids) == {"osint", "amazon", "social", "competitor"}
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
