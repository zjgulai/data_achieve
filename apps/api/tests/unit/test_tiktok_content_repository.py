"""Repository tests for the 12 TikTok content tables (SQLite async)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.tiktok_content import (
    Comment,
    Creator,
    Hashtag,
    TrendTopic,
    Video,
)
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.tiktok_content import (
    add_comment_snapshot,
    add_creator_snapshot,
    add_hashtag_snapshot,
    add_trend_topic,
    add_video_hashtag,
    add_video_snapshot,
    get_creator,
    list_comments_for_video,
    list_creator_snapshots,
    list_hashtag_snapshots,
    list_trend_topics,
    list_video_snapshots,
    make_snapshot_id,
    upsert_comment,
    upsert_creator,
    upsert_hashtag,
    upsert_sound,
    upsert_transcript,
    upsert_video,
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


@pytest.mark.asyncio
async def test_creator_upsert_and_snapshot_idempotent(session: AsyncSession) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    creator = await upsert_creator(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        creator_id="u1",
        values={"unique_id": "alice", "nickname": "Alice", "follower_count": 10},
        provider="tikhub",
        endpoint_type="tikhub_tiktok_user_profile_web",
        schema_version="tikhub_tiktok_user.v2",
        captured_at=NOW,
    )
    assert creator.follower_count == 10
    await session.commit()

    creator = await upsert_creator(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        creator_id="u1",
        values={"follower_count": 11},
        provider="tikhub",
        endpoint_type="tikhub_tiktok_user_profile_web",
        schema_version="tikhub_tiktok_user.v2",
        captured_at=NOW,
    )
    assert creator.follower_count == 11
    assert creator.first_seen_at == NOW
    await session.commit()

    for _ in range(2):
        await add_creator_snapshot(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            creator_id="u1",
            captured_at=NOW,
            values={"follower_count": 11, "engagement_rate": 0.05},
            provider="tikhub",
            endpoint_type="tikhub_tiktok_user_profile_web",
            schema_version="tikhub_tiktok_user.v2",
        )
        await session.commit()

    snapshots = await list_creator_snapshots(
        session, workspace_id, project_id, "u1"
    )
    assert len(snapshots) == 1
    assert snapshots[0].follower_count == 11

    loaded = await get_creator(session, workspace_id, project_id, "u1")
    assert loaded is not None
    assert loaded.unique_id == "alice"


@pytest.mark.asyncio
async def test_video_comment_hashtag_flow(session: AsyncSession) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    await upsert_hashtag(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        hashtag_id="h1",
        values={"name_raw": "newborn", "name_normalized": "newborn"},
        provider="tikhub",
        endpoint_type="tikhub_tiktok_hashtag_detail_app",
        schema_version="tikhub_tiktok_hashtag.v1",
        captured_at=NOW,
    )
    await upsert_sound(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        sound_id="m1",
        values={"title": "song", "author_name": "artist"},
        provider="tikhub",
        endpoint_type="tikhub_tiktok_music_chart",
        schema_version="tikhub_tiktok_trend.v1",
        captured_at=NOW,
    )
    await upsert_video(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        video_id="v1",
        values={
            "caption": "hello",
            "creator_id": None,
            "sound_id": "m1",
            "hashtags": ["newborn"],
        },
        provider="tikhub",
        endpoint_type="tikhub_tiktok_video_detail",
        schema_version="tikhub_tiktok_video.v1",
        captured_at=NOW,
    )
    await add_video_snapshot(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        video_id="v1",
        captured_at=NOW,
        values={"play_count": 100, "like_count": 10},
        provider="tikhub",
        endpoint_type="tikhub_tiktok_video_detail",
        schema_version="tikhub_tiktok_video.v1",
    )
    await upsert_comment(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        comment_id="c1",
        values={
            "video_id": "v1",
            "text": "nice",
            "is_pinned": True,
            "creator_interacted": True,
            "parent_comment_id": None,
        },
        provider="tikhub",
        endpoint_type="tikhub_tiktok_comments_app",
        schema_version="tikhub_tiktok_comment.v1",
        captured_at=NOW,
    )
    await add_comment_snapshot(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        comment_id="c1",
        captured_at=NOW,
        values={"like_count": 2, "reply_count": 0},
        provider="tikhub",
        endpoint_type="tikhub_tiktok_comments_app",
        schema_version="tikhub_tiktok_comment.v1",
    )
    await add_video_hashtag(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        video_id="v1",
        hashtag_id="h1",
        position=0,
        captured_at=NOW,
        values={"hashtag_name_raw": "newborn", "hashtag_name_normalized": "newborn"},
        provider="tikhub",
        endpoint_type="tikhub_tiktok_video_detail",
        schema_version="tikhub_tiktok_video.v1",
    )
    await session.commit()

    video = await session.get(Video, "v1")
    assert video is not None
    comments = await list_comments_for_video(
        session, workspace_id, project_id, "v1"
    )
    assert len(comments) == 1
    assert comments[0].text == "nice"
    snapshots = await list_video_snapshots(session, workspace_id, project_id, "v1")
    assert len(snapshots) == 1
    assert snapshots[0].play_count == 100


@pytest.mark.asyncio
async def test_hashtag_snapshot_filter(session: AsyncSession) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    await upsert_hashtag(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        hashtag_id="h1",
        values={"name_raw": "newborn", "name_normalized": "newborn"},
        provider="tikhub",
        endpoint_type="tikhub_tiktok_hashtag_detail_app",
        schema_version="tikhub_tiktok_hashtag.v1",
        captured_at=NOW,
    )
    for country, period in (("US", 7), ("US", 30), ("GB", 7)):
        await add_hashtag_snapshot(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            hashtag_id="h1",
            captured_at=NOW,
            values={"rank": 1, "post_count": 10},
            country_code=country,
            period_days=period,
            provider="tikhub",
            endpoint_type="tikhub_tiktok_ads_trends",
            schema_version="tikhub_tiktok_trend.v1",
        )
    await session.commit()

    us7 = await list_hashtag_snapshots(
        session, workspace_id, project_id, "h1", "US", 7
    )
    assert len(us7) == 1
    us_all = await list_hashtag_snapshots(
        session, workspace_id, project_id, "h1", "US"
    )
    assert len(us_all) == 2


@pytest.mark.asyncio
async def test_trend_topic_and_transcript(session: AsyncSession) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    await add_trend_topic(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        topic_id="t1",
        topic_type="search_topic",
        country_code="US",
        time_window="7d",
        language="en",
        captured_at=NOW,
        values={"topic_name": "stroller", "growth_rate": 0.2},
        provider="tikhub",
        endpoint_type="tikhub_tiktok_trending_searchwords",
        schema_version="tikhub_tiktok_trend.v1",
    )
    await add_trend_topic(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        topic_id="t1",
        topic_type="search_topic",
        country_code="US",
        time_window="7d",
        language="en",
        captured_at=NOW,
        values={"topic_name": "stroller", "growth_rate": 0.2},
        provider="tikhub",
        endpoint_type="tikhub_tiktok_trending_searchwords",
        schema_version="tikhub_tiktok_trend.v1",
    )
    await upsert_video(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        video_id="v1",
        values={"caption": "hello"},
        provider="tikhub",
        endpoint_type="tikhub_tiktok_video_detail",
        schema_version="tikhub_tiktok_video.v1",
        captured_at=NOW,
    )
    await upsert_transcript(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        transcript_id="tr1",
        values={
            "video_id": "v1",
            "transcript_source": "creator_caption",
            "text": "hello",
            "content_hash": "hash",
        },
        provider="tikhub",
        endpoint_type="tikhub_tiktok_video_detail",
        schema_version="tikhub_tiktok_transcript.v1",
        captured_at=NOW,
    )
    await session.commit()

    topics = await list_trend_topics(
        session, workspace_id, project_id, "US", "7d"
    )
    assert len(topics) == 1
    assert topics[0].topic_name == "stroller"


@pytest.mark.asyncio
async def test_tenant_isolation(session: AsyncSession) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    await upsert_creator(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        creator_id="u1",
        values={"unique_id": "alice"},
        provider="tikhub",
        endpoint_type="tikhub_tiktok_user_profile_web",
        schema_version="tikhub_tiktok_user.v2",
        captured_at=NOW,
    )
    await session.commit()

    with pytest.raises(ValueError, match="another_tenant"):
        await upsert_creator(
            session,
            workspace_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            creator_id="u1",
            values={"unique_id": "alice"},
            provider="tikhub",
            endpoint_type="tikhub_tiktok_user_profile_web",
            schema_version="tikhub_tiktok_user.v2",
            captured_at=NOW,
        )


@pytest.mark.asyncio
async def test_upsert_filters_reserved_and_unknown_values(session: AsyncSession) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    creator = await upsert_creator(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        creator_id="u1",
        values={
            "unique_id": "alice",
            "provider": "should-not-overwrite",
            "raw": {"ignored": True},
            "unknown_field": 1,
        },
        provider="tikhub",
        endpoint_type="tikhub_tiktok_user_profile_web",
        schema_version="tikhub_tiktok_user.v2",
        captured_at=NOW,
    )
    assert creator.provider == "tikhub"
    assert creator.unique_id == "alice"
    assert not hasattr(creator, "unknown_field")


def test_snapshot_id_is_stable() -> None:
    first = make_snapshot_id("v1", NOW, "tikhub", "tikhub_tiktok_video_detail", "r1")
    second = make_snapshot_id("v1", NOW, "tikhub", "tikhub_tiktok_video_detail", "r1")
    other = make_snapshot_id("v1", NOW, "tikhub", "tikhub_tiktok_user_posts_web", "r1")
    assert first == second
    assert first != other


def test_model_tables_are_registered() -> None:
    names = {
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
    }
    assert names <= set(Base.metadata.tables)
    assert Creator.__tablename__ == "creator"
    assert Video.__tablename__ == "video"
    assert Comment.__tablename__ == "comment"
    assert Hashtag.__tablename__ == "hashtag"
    assert TrendTopic.__tablename__ == "trend_topic"
