"""Tests for the TikTok content ingestion service (SQLite async)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.tiktok_content import (
    Comment,
    CommentSnapshot,
    Creator,
    CreatorSnapshot,
    Hashtag,
    HashtagSnapshot,
    Sound,
    Transcript,
    TrendTopic,
    Video,
    VideoHashtag,
    VideoSnapshot,
)
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services.collector_service import (
    _ingest_tiktok_content_if_needed,
)
from data_intelligence_hub.services.tiktok_content_ingestion import (
    IngestionContext,
    ingest_tiktok_content,
)

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
TABLES = [
    "users",
    "workspaces",
    "projects",
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


async def _seed_tenant(db: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    db.add(
        User(
            id=user_id,
            email=f"{user_id}@example.com",
            password_hash="hash",
            name="Tester",
            status="active",
        )
    )
    db.add(
        Workspace(
            id=workspace_id,
            name="TikTok",
            slug=f"tiktok-{workspace_id}",
            owner_id=user_id,
        )
    )
    db.add(
        Project(
            id=project_id,
            workspace_id=workspace_id,
            name="Content",
            domain="tiktok",
            status="active",
            owner_id=user_id,
        )
    )
    await db.commit()
    return workspace_id, project_id


def _context(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    endpoint_type: str = "tikhub_tiktok_video_detail",
) -> IngestionContext:
    return IngestionContext(
        workspace_id=workspace_id,
        project_id=project_id,
        endpoint_type=endpoint_type,
        schema_version="tikhub_tiktok_video.v1",
        captured_at=NOW,
        country_code="US",
        period_days=7,
        time_window="7d",
        language="en",
    )


def _video_content() -> dict:
    return {
        "record_type": "tiktok_video",
        "provider": "tikhub",
        "platform": "tiktok",
        "schema_version": "tikhub_tiktok_video.v1",
        "video_id": "v1",
        "text": "hello",
        "text_language": "en",
        "author_id": "u1",
        "author_username": "alice",
        "author_nickname": "Alice",
        "created_at": "2026-10-19T11:00:00+00:00",
        "play_count": 100,
        "like_count": 10,
        "comment_count": 2,
        "share_count": 1,
        "collect_count": 3,
        "duration": 15000,
        "cover_url": "https://cover",
        "music_id": "m1",
        "music_title": "song",
        "music_author": "artist",
        "hashtags": ["newborn"],
        "is_ad": False,
    }


@pytest.mark.asyncio
async def test_ingest_video_writes_master_snapshot_and_relation(
    session: AsyncSession,
) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    result = await ingest_tiktok_content(
        session, [_video_content()], _context(workspace_id, project_id)
    )
    await session.commit()

    assert result.videos == 1
    assert result.video_snapshots == 1
    assert result.hashtags == 1
    assert result.video_hashtags == 1
    assert not result.errors

    video = await session.get(Video, "v1")
    assert video is not None
    assert video.caption == "hello"
    assert video.duration_ms == 15000
    creator = await session.get(Creator, "u1")
    assert creator is not None
    assert creator.unique_id == "alice"
    sound = await session.get(Sound, "m1")
    assert sound is not None
    hashtag = await session.get(Hashtag, "name:newborn")
    assert hashtag is not None
    assert hashtag.identity_quality == "derived"
    assert await session.scalar(select(func.count()).select_from(VideoSnapshot)) == 1
    assert await session.scalar(select(func.count()).select_from(VideoHashtag)) == 1


@pytest.mark.asyncio
async def test_ingest_accepts_collector_raw_record(session: AsyncSession) -> None:
    from data_intelligence_hub.collectors.base import CollectorRawRecord

    workspace_id, project_id = await _seed_tenant(session)
    record = CollectorRawRecord(
        record_type="tiktok_video",
        source_url="https://www.tiktok.com/@alice/video/v1",
        content=_video_content(),
        collected_at=NOW,
    )
    result = await ingest_tiktok_content(
        session, [record], _context(workspace_id, project_id)
    )
    await session.commit()
    assert result.videos == 1
    assert await session.get(Video, "v1") is not None


@pytest.mark.asyncio
async def test_ingest_user_creates_creator_snapshot(session: AsyncSession) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    content = {
        "record_type": "tiktok_user",
        "provider": "tikhub",
        "schema_version": "tikhub_tiktok_user.v2",
        "uid": "u1",
        "unique_id": "alice",
        "nickname": "Alice",
        "follower_count": 50,
        "following_count": 5,
        "video_count": 10,
        "heart_count": 500,
    }
    result = await ingest_tiktok_content(
        session,
        [content],
        _context(workspace_id, project_id, "tikhub_tiktok_user_profile_web"),
    )
    await session.commit()

    assert result.creators == 1
    assert result.creator_snapshots == 1
    assert await session.scalar(select(func.count()).select_from(Creator)) == 1
    assert await session.scalar(select(func.count()).select_from(CreatorSnapshot)) == 1


@pytest.mark.asyncio
async def test_ingest_comment_creates_minimal_video(session: AsyncSession) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    content = {
        "record_type": "tiktok_comment",
        "provider": "tikhub",
        "schema_version": "tikhub_tiktok_comment.v1",
        "comment_id": "c1",
        "video_id": "v-missing",
        "author_id": "u2",
        "author_unique_id": "bob",
        "author_nickname": "Bob",
        "text": "nice",
        "text_language": "en",
        "like_count": 3,
        "reply_count": 0,
        "is_pinned": False,
        "creator_interacted": False,
        "published_at": "2026-10-19T11:30:00+00:00",
    }
    result = await ingest_tiktok_content(
        session,
        [content],
        _context(workspace_id, project_id, "tikhub_tiktok_comments_app"),
    )
    await session.commit()

    assert result.comments == 1
    assert result.comment_snapshots == 1
    video = await session.get(Video, "v-missing")
    assert video is not None
    assert video.caption is None
    comment = await session.get(Comment, "c1")
    assert comment is not None
    assert comment.text == "nice"
    assert await session.scalar(select(func.count()).select_from(CommentSnapshot)) == 1


@pytest.mark.asyncio
async def test_ingest_hashtag_and_search_trends(session: AsyncSession) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    context = _context(workspace_id, project_id, "tikhub_tiktok_ads_trends")
    contents = [
        {
            "record_type": "tiktok_trend",
            "provider": "tikhub",
            "schema_version": "tikhub_tiktok_trend.v1",
            "trend_type": "hashtag",
            "entity_id": "h1",
            "name": "newborn",
            "rank": 1,
            "post_count": 10,
            "view_count": 1000,
            "value": {"topCreators": ["u1"]},
        },
        {
            "record_type": "tiktok_trend",
            "provider": "tikhub",
            "schema_version": "tikhub_tiktok_trend.v1",
            "trend_type": "search_word",
            "name": "stroller",
            "value": {},
        },
    ]
    result = await ingest_tiktok_content(session, contents, context)
    await session.commit()

    assert result.hashtags == 1
    assert result.hashtag_snapshots == 1
    assert result.trend_topics == 2
    assert await session.scalar(select(func.count()).select_from(HashtagSnapshot)) == 1
    assert await session.scalar(select(func.count()).select_from(TrendTopic)) == 2


@pytest.mark.asyncio
async def test_ingest_music_trend_creates_sound(session: AsyncSession) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    content = {
        "record_type": "tiktok_trend",
        "provider": "tikhub",
        "schema_version": "tikhub_tiktok_trend.v1",
        "trend_type": "music",
        "entity_id": "m1",
        "name": "song",
        "value": {"trend": 1},
    }
    result = await ingest_tiktok_content(
        session,
        [content],
        _context(workspace_id, project_id, "tikhub_tiktok_music_chart"),
    )
    await session.commit()

    assert result.sounds == 1
    assert result.trend_topics == 1
    sound = await session.get(Sound, "m1")
    assert sound is not None
    assert sound.title == "song"


@pytest.mark.asyncio
async def test_ingest_is_idempotent(session: AsyncSession) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    context = _context(workspace_id, project_id)
    for _ in range(2):
        await ingest_tiktok_content(session, [_video_content()], context)
        await session.commit()

    assert await session.scalar(select(func.count()).select_from(Video)) == 1
    assert await session.scalar(select(func.count()).select_from(VideoSnapshot)) == 1
    assert await session.scalar(select(func.count()).select_from(Creator)) == 1
    assert await session.scalar(select(func.count()).select_from(Hashtag)) == 1
    assert await session.scalar(select(func.count()).select_from(VideoHashtag)) == 1


@pytest.mark.asyncio
async def test_collector_service_projects_tiktok_content(session: AsyncSession) -> None:
    from types import SimpleNamespace

    from data_intelligence_hub.collectors.base import CollectorRawRecord

    workspace_id, project_id = await _seed_tenant(session)
    task = CollectionTask(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        source_id=uuid.uuid4(),
        collector_type="tikhub_social",
        name="test",
        status="enabled",
        config={"endpoint_type": "tikhub_tiktok_video_detail"},
    )
    run = TaskRun(
        id=uuid.uuid4(),
        task_id=task.id,
        workspace_id=workspace_id,
        status="running",
        started_at=NOW,
        records_count=0,
        entities_count=0,
        logs=[],
        created_at=NOW,
    )
    record = CollectorRawRecord(
        record_type="tiktok_video",
        source_url=None,
        content=_video_content(),
        collected_at=NOW,
    )
    result = await _ingest_tiktok_content_if_needed(
        session=session,
        workspace=SimpleNamespace(id=workspace_id),
        task=task,
        run=run,
        raw_records=[record],
    )
    await session.commit()
    assert result is not None
    assert result.videos == 1
    assert await session.get(Video, "v1") is not None


@pytest.mark.asyncio
async def test_collector_service_projects_apify_transcript(
    session: AsyncSession,
) -> None:
    from types import SimpleNamespace

    from data_intelligence_hub.collectors.base import CollectorRawRecord

    workspace_id, project_id = await _seed_tenant(session)
    task = CollectionTask(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        source_id=uuid.uuid4(),
        collector_type="apify_actor",
        name="transcript",
        status="enabled",
        config={"endpoint_type": "apify_tiktok_transcript_extractor"},
    )
    run = TaskRun(
        id=uuid.uuid4(),
        task_id=task.id,
        workspace_id=workspace_id,
        status="running",
        started_at=NOW,
        records_count=0,
        entities_count=0,
        logs=[],
        created_at=NOW,
    )
    raw = {
        "id": "v-transcript",
        "text": "spoken words",
        "textLanguage": "en",
        "authorMeta": {"id": "u1", "name": "alice"},
        "videoMeta": {"duration": 10},
    }
    record = CollectorRawRecord(
        record_type="tiktok_video",
        source_url=None,
        content={
            "provider": "apify",
            "schema_version": "apify_tiktok_video.v1",
            "text": raw["text"],
            "raw": raw,
        },
        collected_at=NOW,
    )
    result = await _ingest_tiktok_content_if_needed(
        session=session,
        workspace=SimpleNamespace(id=workspace_id),
        task=task,
        run=run,
        raw_records=[record],
    )
    await session.commit()
    assert result is not None
    assert result.transcripts == 1
    assert await session.scalar(select(Transcript)) is not None


@pytest.mark.asyncio
async def test_ingest_apify_transcript_writes_transcript(
    session: AsyncSession,
) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    raw = {
        "id": "7670318941658483981",
        "text": "hello world from transcript",
        "textLanguage": "en",
        "createTimeISO": "2026-08-04T23:15:18.000Z",
        "authorMeta": {
            "id": "7527113447973487646",
            "name": "summercooljinny",
            "nickName": "Jinny",
            "fans": 115300,
        },
        "videoMeta": {"duration": 76, "coverUrl": "https://cover"},
        "webVideoUrl": "https://www.tiktok.com/@summercooljinny/video/7670318941658483981",
    }
    content = {
        "record_type": "tiktok_video",
        "provider": "apify",
        "platform": "tiktok",
        "schema_version": "apify_tiktok_video.v1",
        "text": raw["text"],
        "raw": raw,
    }
    result = await ingest_tiktok_content(
        session,
        [{"record_type": "tiktok_video", "content": content}],
        IngestionContext(
            workspace_id=workspace_id,
            project_id=project_id,
            provider="apify",
            endpoint_type="apify_tiktok_transcript_extractor",
            schema_version="apify_tiktok_video.v1",
            captured_at=NOW,
        ),
    )
    assert result.transcripts == 1
    transcript = await session.scalar(select(Transcript))
    assert transcript is not None
    assert transcript.video_id == raw["id"]
    assert transcript.text == raw["text"]
    assert transcript.language == "en"
    assert transcript.transcript_source == "third_party_asr"
    assert await session.get(Video, raw["id"]) is not None


@pytest.mark.asyncio
async def test_ingest_skips_analytics(session: AsyncSession) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    result = await ingest_tiktok_content(
        session,
        [
            {
                "record_type": "tiktok_analytics",
                "provider": "tikhub",
                "analytics_type": "fake_views",
                "video_id": "v1",
            }
        ],
        _context(workspace_id, project_id, "tikhub_tiktok_fake_views"),
    )
    assert result.skipped == 1
    assert not result.errors
