"""Backfill tests for historical TikTok RawRecords."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.tiktok_content import (
    Creator,
    Transcript,
    Video,
    VideoSnapshot,
)
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services.tiktok_content_backfill import (
    BackfillFilters,
    BackfillReport,
    backfill_tiktok_content,
)

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
TABLES = [
    "users",
    "workspaces",
    "projects",
    "sources",
    "collection_tasks",
    "task_runs",
    "raw_records",
    "creator",
    "creator_snapshot",
    "video",
    "video_snapshot",
    "comment",
    "comment_snapshot",
    "hashtag",
    "hashtag_snapshot",
    "video_hashtag",
    "trend_topic",
    "sound",
    "transcript",
]


@pytest_asyncio.fixture()
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [Base.metadata.tables[name] for name in TABLES]
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection, tables=tables
            )
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def _seed(
    db: AsyncSession,
    *,
    collector_type: str = "tikhub_social",
    endpoint_type: str = "tikhub_tiktok_video_detail",
    content: dict | None = None,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    db.add(
        User(
            id=user_id,
            email=f"{user_id}@example.com",
            password_hash="x",
            name="Tester",
            status="active",
        )
    )
    db.add(
        Workspace(
            id=workspace_id,
            name="ws",
            slug=f"ws-{workspace_id}",
            owner_id=user_id,
        )
    )
    db.add(
        Project(
            id=project_id,
            workspace_id=workspace_id,
            name="p",
            domain="tiktok",
            status="active",
            owner_id=user_id,
        )
    )
    await db.flush()
    source = Source(
        workspace_id=workspace_id,
        project_id=project_id,
        name="source",
        type=collector_type,
        config={},
    )
    db.add(source)
    await db.flush()
    task = CollectionTask(
        workspace_id=workspace_id,
        project_id=project_id,
        source_id=source.id,
        collector_type=collector_type,
        name="task",
        status="enabled",
        config={"endpoint_type": endpoint_type, "country_code": "US"},
    )
    db.add(task)
    await db.flush()
    run = TaskRun(
        task_id=task.id,
        workspace_id=workspace_id,
        status="success",
        started_at=NOW,
        records_count=1,
        entities_count=0,
        logs=[],
        created_at=NOW,
    )
    db.add(run)
    await db.flush()
    db.add(
        RawRecord(
            workspace_id=workspace_id,
            project_id=project_id,
            source_id=source.id,
            task_run_id=run.id,
            record_type="tiktok_video",
            content=content
            or {
                "provider": "tikhub",
                "collector_type": endpoint_type,
                "schema_version": "tikhub_tiktok_video.v1",
                "video_id": "v1",
                "text": "hello",
                "author_id": "u1",
                "author_username": "alice",
                "play_count": 100,
                "like_count": 10,
                "comment_count": 2,
                "share_count": 1,
                "collect_count": 3,
            },
            content_hash=f"hash-{uuid.uuid4()}",
            collected_at=NOW,
            created_at=NOW,
        )
    )
    await db.commit()
    return workspace_id, project_id, run.id


def test_report_counts_cross_tenant_conflicts() -> None:
    class _Result:
        errors = [
            "master:ValueError:tiktok_entity_belongs_to_another_tenant:Creator:u1"
        ]

        def as_dict(self):
            return {"creators": 0, "errors": self.errors}

    report = BackfillReport()
    report.add_result(_Result())
    assert report.cross_tenant_conflicts == 1


@pytest.mark.asyncio
async def test_dry_run_writes_nothing(session: AsyncSession) -> None:
    workspace_id, project_id, _ = await _seed(session)
    report = await backfill_tiktok_content(
        session,
        filters=BackfillFilters(workspace_id=workspace_id, project_id=project_id),
        dry_run=True,
    )
    assert report.eligible_records == 1
    assert report.projected_records == 0
    assert await session.scalar(select(func.count()).select_from(Video)) == 0


@pytest.mark.asyncio
async def test_backfill_writes_canonical_rows(session: AsyncSession) -> None:
    workspace_id, project_id, run_id = await _seed(session)
    report = await backfill_tiktok_content(
        session,
        filters=BackfillFilters(workspace_id=workspace_id, project_id=project_id),
        dry_run=False,
    )
    assert report.projected_records == 1
    assert report.failed_records == 0
    video = await session.get(Video, "v1")
    assert video is not None
    snapshot = await session.scalar(select(VideoSnapshot))
    assert snapshot is not None
    assert snapshot.run_id == str(run_id)
    assert snapshot.raw_ref is not None
    assert await session.get(Creator, "u1") is not None


@pytest.mark.asyncio
async def test_backfill_is_idempotent(session: AsyncSession) -> None:
    workspace_id, project_id, _ = await _seed(session)
    filters = BackfillFilters(workspace_id=workspace_id, project_id=project_id)
    await backfill_tiktok_content(session, filters=filters, dry_run=False)
    await backfill_tiktok_content(session, filters=filters, dry_run=False)
    assert await session.scalar(select(func.count()).select_from(VideoSnapshot)) == 1


@pytest.mark.asyncio
async def test_non_content_endpoint_is_excluded(session: AsyncSession) -> None:
    workspace_id, project_id, _ = await _seed(
        session,
        endpoint_type="tikhub_tiktok_video_search",
        content={
            "provider": "tikhub",
            "collector_type": "tikhub_tiktok_video_search",
            "schema_version": "tikhub_tiktok_video.v1",
            "video_id": "v2",
        },
    )
    report = await backfill_tiktok_content(
        session,
        filters=BackfillFilters(workspace_id=workspace_id, project_id=project_id),
        dry_run=False,
    )
    assert report.eligible_records == 0
    assert await session.scalar(select(func.count()).select_from(Video)) == 0


@pytest.mark.asyncio
async def test_apify_transcript_backfill(session: AsyncSession) -> None:
    workspace_id, project_id, _ = await _seed(
        session,
        collector_type="apify_actor",
        endpoint_type="apify_tiktok_transcript_extractor",
        content={
            "provider": "apify",
            "actor_id": "clockworks/tiktok-transcript-extractor",
            "schema_version": "apify_tiktok_video.v1",
            "text": "spoken words",
            "raw": {
                "id": "v3",
                "text": "spoken words",
                "textLanguage": "en",
                "authorMeta": {"id": "u3", "name": "bob"},
                "videoMeta": {"duration": 10},
            },
        },
    )
    report = await backfill_tiktok_content(
        session,
        filters=BackfillFilters(workspace_id=workspace_id, project_id=project_id),
        dry_run=False,
    )
    assert report.projected_records == 1
    assert await session.scalar(select(Transcript)) is not None
