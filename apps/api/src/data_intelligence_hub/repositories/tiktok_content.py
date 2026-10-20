"""Repositories for the 12 TikTok R1 content tables.

The functions are intentionally small and tenant-scoped. Snapshot writes are
idempotent by ``snapshot_id``. Master writes use select-then-update-or-insert so
the same code works on PostgreSQL and on the SQLite unit-test path.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


# Backfill sets this flag so an older historical record never overwrites a
# newer live observation. Normal collection keeps the existing overwrite path.
BACKFILL_ONLY_IF_NEWER: ContextVar[bool] = ContextVar(
    "tiktok_backfill_only_if_newer", default=False
)


def make_snapshot_id(
    entity_key: str,
    captured_at: datetime,
    provider: str,
    endpoint_type: str,
    run_id: str | None = None,
) -> str:
    """Stable UUIDv5 for one observation.

    Re-running the same collection with the same entity, capture time, provider,
    endpoint and run id produces the same snapshot id.
    """
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=UTC)
    raw = "|".join(
        [
            entity_key,
            captured_at.astimezone(UTC).isoformat(),
            provider,
            endpoint_type,
            run_id or "",
        ]
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, raw))


def _governance(
    *,
    provider: str,
    endpoint_type: str,
    schema_version: str,
    captured_at: datetime,
    run_id: str | None,
    raw_ref: str | None,
    quality_flags: list[Any] | None,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "endpoint_type": endpoint_type,
        "schema_version": schema_version,
        "captured_at": captured_at,
        "run_id": run_id,
        "raw_ref": raw_ref,
        "is_stale": False,
        "quality_flags": quality_flags or [],
    }


def _check_tenant(obj: Any, workspace_id: uuid.UUID, project_id: uuid.UUID) -> None:
    if obj.workspace_id != workspace_id or obj.project_id != project_id:
        identity = next(
            (
                getattr(obj, key)
                for key in (
                    "creator_id",
                    "video_id",
                    "comment_id",
                    "hashtag_id",
                    "sound_id",
                    "product_key",
                    "shop_key",
                )
                if getattr(obj, key, None) is not None
            ),
            "",
        )
        raise ValueError(
            f"tiktok_entity_belongs_to_another_tenant:{type(obj).__name__}:{identity}"
        )


def _filter_values(
    model: type[Any],
    values: dict[str, Any],
    reserved: set[str],
) -> dict[str, Any]:
    columns = {column.name for column in model.__table__.columns}
    return {
        key: value
        for key, value in values.items()
        if key in columns and key not in reserved
    }


async def _upsert_master(
    session: AsyncSession,
    model: type[Any],
    pk_field: str,
    pk_value: str,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    values: dict[str, Any],
    governance: dict[str, Any],
) -> Any:
    clean_values = _filter_values(
        model,
        values,
        {
            pk_field,
            "workspace_id",
            "project_id",
            "first_seen_at",
            "last_updated_at",
            *governance.keys(),
        },
    )
    obj = await session.get(model, pk_value)
    if obj is None:
        obj = model(
            **{pk_field: pk_value},
            workspace_id=workspace_id,
            project_id=project_id,
            first_seen_at=governance["captured_at"],
            last_updated_at=governance["captured_at"],
            **governance,
            **clean_values,
        )
        session.add(obj)
    else:
        _check_tenant(obj, workspace_id, project_id)
        if (
            BACKFILL_ONLY_IF_NEWER.get()
            and obj.last_updated_at is not None
            and obj.last_updated_at > governance["captured_at"]
        ):
            return obj
        for key, value in clean_values.items():
            setattr(obj, key, value)
        for key, value in governance.items():
            setattr(obj, key, value)
        obj.last_updated_at = governance["captured_at"]
    await session.flush()
    return obj


def _snapshot(
    session: AsyncSession,
    model: type[Any],
    snapshot_id: str,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    governance: dict[str, Any],
    values: dict[str, Any],
) -> Any:
    clean_values = _filter_values(
        model,
        values,
        {"snapshot_id", "workspace_id", "project_id", *governance.keys()},
    )
    obj = model(
        snapshot_id=snapshot_id,
        workspace_id=workspace_id,
        project_id=project_id,
        **governance,
        **clean_values,
    )
    session.add(obj)
    return obj


# ── creator ────────────────────────────────────────────────────────────────


async def get_creator(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    creator_id: str,
) -> Creator | None:
    result = await session.execute(
        select(Creator).where(
            Creator.creator_id == creator_id,
            Creator.workspace_id == workspace_id,
            Creator.project_id == project_id,
        )
    )
    return result.scalar_one_or_none()


async def upsert_creator(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    creator_id: str,
    values: dict[str, Any],
    provider: str,
    endpoint_type: str,
    schema_version: str,
    captured_at: datetime,
    run_id: str | None = None,
    raw_ref: str | None = None,
    quality_flags: list[Any] | None = None,
) -> Creator:
    return await _upsert_master(
        session,
        Creator,
        "creator_id",
        creator_id,
        workspace_id=workspace_id,
        project_id=project_id,
        values=values,
        governance=_governance(
            provider=provider,
            endpoint_type=endpoint_type,
            schema_version=schema_version,
            captured_at=captured_at,
            run_id=run_id,
            raw_ref=raw_ref,
            quality_flags=quality_flags,
        ),
    )


async def add_creator_snapshot(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    creator_id: str,
    captured_at: datetime,
    values: dict[str, Any],
    provider: str,
    endpoint_type: str,
    schema_version: str,
    run_id: str | None = None,
    raw_ref: str | None = None,
    quality_flags: list[Any] | None = None,
) -> CreatorSnapshot:
    snapshot_id = make_snapshot_id(
        creator_id, captured_at, provider, endpoint_type, run_id
    )
    existing = await session.get(CreatorSnapshot, snapshot_id)
    if existing is not None:
        return existing
    obj = _snapshot(
        session,
        CreatorSnapshot,
        snapshot_id,
        workspace_id=workspace_id,
        project_id=project_id,
        governance=_governance(
            provider=provider,
            endpoint_type=endpoint_type,
            schema_version=schema_version,
            captured_at=captured_at,
            run_id=run_id,
            raw_ref=raw_ref,
            quality_flags=quality_flags,
        ),
        values={"creator_id": creator_id, **values},
    )
    await session.flush()
    return obj


async def list_creator_snapshots(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    creator_id: str,
    limit: int = 50,
) -> list[CreatorSnapshot]:
    result = await session.execute(
        select(CreatorSnapshot)
        .where(
            CreatorSnapshot.creator_id == creator_id,
            CreatorSnapshot.workspace_id == workspace_id,
            CreatorSnapshot.project_id == project_id,
        )
        .order_by(CreatorSnapshot.captured_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ── video ──────────────────────────────────────────────────────────────────


async def get_video(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    video_id: str,
) -> Video | None:
    result = await session.execute(
        select(Video).where(
            Video.video_id == video_id,
            Video.workspace_id == workspace_id,
            Video.project_id == project_id,
        )
    )
    return result.scalar_one_or_none()


async def upsert_video(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    video_id: str,
    values: dict[str, Any],
    provider: str,
    endpoint_type: str,
    schema_version: str,
    captured_at: datetime,
    run_id: str | None = None,
    raw_ref: str | None = None,
    quality_flags: list[Any] | None = None,
) -> Video:
    return await _upsert_master(
        session,
        Video,
        "video_id",
        video_id,
        workspace_id=workspace_id,
        project_id=project_id,
        values=values,
        governance=_governance(
            provider=provider,
            endpoint_type=endpoint_type,
            schema_version=schema_version,
            captured_at=captured_at,
            run_id=run_id,
            raw_ref=raw_ref,
            quality_flags=quality_flags,
        ),
    )


async def add_video_snapshot(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    video_id: str,
    captured_at: datetime,
    values: dict[str, Any],
    provider: str,
    endpoint_type: str,
    schema_version: str,
    run_id: str | None = None,
    raw_ref: str | None = None,
    quality_flags: list[Any] | None = None,
) -> VideoSnapshot:
    snapshot_id = make_snapshot_id(video_id, captured_at, provider, endpoint_type, run_id)
    existing = await session.get(VideoSnapshot, snapshot_id)
    if existing is not None:
        return existing
    obj = _snapshot(
        session,
        VideoSnapshot,
        snapshot_id,
        workspace_id=workspace_id,
        project_id=project_id,
        governance=_governance(
            provider=provider,
            endpoint_type=endpoint_type,
            schema_version=schema_version,
            captured_at=captured_at,
            run_id=run_id,
            raw_ref=raw_ref,
            quality_flags=quality_flags,
        ),
        values={"video_id": video_id, **values},
    )
    await session.flush()
    return obj


async def list_video_snapshots(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    video_id: str,
    limit: int = 50,
) -> list[VideoSnapshot]:
    result = await session.execute(
        select(VideoSnapshot)
        .where(
            VideoSnapshot.video_id == video_id,
            VideoSnapshot.workspace_id == workspace_id,
            VideoSnapshot.project_id == project_id,
        )
        .order_by(VideoSnapshot.captured_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ── comment ────────────────────────────────────────────────────────────────


async def get_comment(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    comment_id: str,
) -> Comment | None:
    result = await session.execute(
        select(Comment).where(
            Comment.comment_id == comment_id,
            Comment.workspace_id == workspace_id,
            Comment.project_id == project_id,
        )
    )
    return result.scalar_one_or_none()


async def upsert_comment(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    comment_id: str,
    values: dict[str, Any],
    provider: str,
    endpoint_type: str,
    schema_version: str,
    captured_at: datetime,
    run_id: str | None = None,
    raw_ref: str | None = None,
    quality_flags: list[Any] | None = None,
) -> Comment:
    return await _upsert_master(
        session,
        Comment,
        "comment_id",
        comment_id,
        workspace_id=workspace_id,
        project_id=project_id,
        values=values,
        governance=_governance(
            provider=provider,
            endpoint_type=endpoint_type,
            schema_version=schema_version,
            captured_at=captured_at,
            run_id=run_id,
            raw_ref=raw_ref,
            quality_flags=quality_flags,
        ),
    )


async def add_comment_snapshot(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    comment_id: str,
    captured_at: datetime,
    values: dict[str, Any],
    provider: str,
    endpoint_type: str,
    schema_version: str,
    run_id: str | None = None,
    raw_ref: str | None = None,
    quality_flags: list[Any] | None = None,
) -> CommentSnapshot:
    snapshot_id = make_snapshot_id(
        comment_id, captured_at, provider, endpoint_type, run_id
    )
    existing = await session.get(CommentSnapshot, snapshot_id)
    if existing is not None:
        return existing
    obj = _snapshot(
        session,
        CommentSnapshot,
        snapshot_id,
        workspace_id=workspace_id,
        project_id=project_id,
        governance=_governance(
            provider=provider,
            endpoint_type=endpoint_type,
            schema_version=schema_version,
            captured_at=captured_at,
            run_id=run_id,
            raw_ref=raw_ref,
            quality_flags=quality_flags,
        ),
        values={"comment_id": comment_id, **values},
    )
    await session.flush()
    return obj


async def list_comments_for_video(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    video_id: str,
    limit: int = 100,
    offset: int = 0,
) -> list[Comment]:
    result = await session.execute(
        select(Comment)
        .where(
            Comment.video_id == video_id,
            Comment.workspace_id == workspace_id,
            Comment.project_id == project_id,
        )
        .order_by(Comment.published_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


# ── hashtag ────────────────────────────────────────────────────────────────


async def get_hashtag(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    hashtag_id: str,
) -> Hashtag | None:
    result = await session.execute(
        select(Hashtag).where(
            Hashtag.hashtag_id == hashtag_id,
            Hashtag.workspace_id == workspace_id,
            Hashtag.project_id == project_id,
        )
    )
    return result.scalar_one_or_none()


async def upsert_hashtag(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    hashtag_id: str,
    values: dict[str, Any],
    provider: str,
    endpoint_type: str,
    schema_version: str,
    captured_at: datetime,
    run_id: str | None = None,
    raw_ref: str | None = None,
    quality_flags: list[Any] | None = None,
) -> Hashtag:
    return await _upsert_master(
        session,
        Hashtag,
        "hashtag_id",
        hashtag_id,
        workspace_id=workspace_id,
        project_id=project_id,
        values=values,
        governance=_governance(
            provider=provider,
            endpoint_type=endpoint_type,
            schema_version=schema_version,
            captured_at=captured_at,
            run_id=run_id,
            raw_ref=raw_ref,
            quality_flags=quality_flags,
        ),
    )


async def add_hashtag_snapshot(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    hashtag_id: str,
    captured_at: datetime,
    values: dict[str, Any],
    country_code: str,
    period_days: int,
    provider: str,
    endpoint_type: str,
    schema_version: str,
    run_id: str | None = None,
    raw_ref: str | None = None,
    quality_flags: list[Any] | None = None,
) -> HashtagSnapshot:
    entity_key = f"{hashtag_id}|{country_code}|{period_days}"
    snapshot_id = make_snapshot_id(
        entity_key, captured_at, provider, endpoint_type, run_id
    )
    existing = await session.get(HashtagSnapshot, snapshot_id)
    if existing is not None:
        return existing
    obj = _snapshot(
        session,
        HashtagSnapshot,
        snapshot_id,
        workspace_id=workspace_id,
        project_id=project_id,
        governance=_governance(
            provider=provider,
            endpoint_type=endpoint_type,
            schema_version=schema_version,
            captured_at=captured_at,
            run_id=run_id,
            raw_ref=raw_ref,
            quality_flags=quality_flags,
        ),
        values={
            "hashtag_id": hashtag_id,
            "country_code": country_code,
            "period_days": period_days,
            **values,
        },
    )
    await session.flush()
    return obj


async def list_hashtag_snapshots(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    hashtag_id: str,
    country_code: str | None = None,
    period_days: int | None = None,
    limit: int = 50,
) -> list[HashtagSnapshot]:
    statement = select(HashtagSnapshot).where(
        HashtagSnapshot.hashtag_id == hashtag_id,
        HashtagSnapshot.workspace_id == workspace_id,
        HashtagSnapshot.project_id == project_id,
    )
    if country_code is not None:
        statement = statement.where(HashtagSnapshot.country_code == country_code)
    if period_days is not None:
        statement = statement.where(HashtagSnapshot.period_days == period_days)
    result = await session.execute(
        statement.order_by(HashtagSnapshot.captured_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def add_video_hashtag(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    video_id: str,
    hashtag_id: str,
    position: int,
    captured_at: datetime,
    values: dict[str, Any],
    provider: str,
    endpoint_type: str,
    schema_version: str,
    run_id: str | None = None,
    raw_ref: str | None = None,
    quality_flags: list[Any] | None = None,
) -> VideoHashtag:
    entity_key = f"{video_id}|{hashtag_id}|{position}"
    snapshot_id = make_snapshot_id(
        entity_key, captured_at, provider, endpoint_type, run_id
    )
    existing = await session.get(VideoHashtag, snapshot_id)
    if existing is not None:
        return existing
    obj = _snapshot(
        session,
        VideoHashtag,
        snapshot_id,
        workspace_id=workspace_id,
        project_id=project_id,
        governance=_governance(
            provider=provider,
            endpoint_type=endpoint_type,
            schema_version=schema_version,
            captured_at=captured_at,
            run_id=run_id,
            raw_ref=raw_ref,
            quality_flags=quality_flags,
        ),
        values={
            "video_id": video_id,
            "hashtag_id": hashtag_id,
            "position": position,
            **values,
        },
    )
    await session.flush()
    return obj


# ── trend topic ────────────────────────────────────────────────────────────


async def add_trend_topic(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    topic_id: str,
    topic_type: str,
    country_code: str,
    time_window: str,
    language: str,
    captured_at: datetime,
    values: dict[str, Any],
    provider: str,
    endpoint_type: str,
    schema_version: str,
    run_id: str | None = None,
    raw_ref: str | None = None,
    quality_flags: list[Any] | None = None,
) -> TrendTopic:
    entity_key = f"{topic_id}|{country_code}|{time_window}|{language}"
    snapshot_id = make_snapshot_id(
        entity_key, captured_at, provider, endpoint_type, run_id
    )
    existing = await session.get(TrendTopic, snapshot_id)
    if existing is not None:
        return existing
    obj = _snapshot(
        session,
        TrendTopic,
        snapshot_id,
        workspace_id=workspace_id,
        project_id=project_id,
        governance=_governance(
            provider=provider,
            endpoint_type=endpoint_type,
            schema_version=schema_version,
            captured_at=captured_at,
            run_id=run_id,
            raw_ref=raw_ref,
            quality_flags=quality_flags,
        ),
        values={
            "topic_id": topic_id,
            "topic_type": topic_type,
            "country_code": country_code,
            "time_window": time_window,
            "language": language,
            **values,
        },
    )
    await session.flush()
    return obj


async def list_trend_topics(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    country_code: str,
    time_window: str,
    limit: int = 100,
) -> list[TrendTopic]:
    result = await session.execute(
        select(TrendTopic)
        .where(
            TrendTopic.country_code == country_code,
            TrendTopic.time_window == time_window,
            TrendTopic.workspace_id == workspace_id,
            TrendTopic.project_id == project_id,
        )
        .order_by(TrendTopic.captured_at.desc(), TrendTopic.rank.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ── sound ──────────────────────────────────────────────────────────────────


async def get_sound(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    sound_id: str,
) -> Sound | None:
    result = await session.execute(
        select(Sound).where(
            Sound.sound_id == sound_id,
            Sound.workspace_id == workspace_id,
            Sound.project_id == project_id,
        )
    )
    return result.scalar_one_or_none()


async def upsert_sound(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    sound_id: str,
    values: dict[str, Any],
    provider: str,
    endpoint_type: str,
    schema_version: str,
    captured_at: datetime,
    run_id: str | None = None,
    raw_ref: str | None = None,
    quality_flags: list[Any] | None = None,
) -> Sound:
    return await _upsert_master(
        session,
        Sound,
        "sound_id",
        sound_id,
        workspace_id=workspace_id,
        project_id=project_id,
        values=values,
        governance=_governance(
            provider=provider,
            endpoint_type=endpoint_type,
            schema_version=schema_version,
            captured_at=captured_at,
            run_id=run_id,
            raw_ref=raw_ref,
            quality_flags=quality_flags,
        ),
    )


# ── transcript ─────────────────────────────────────────────────────────────


async def get_transcript(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    transcript_id: str,
) -> Transcript | None:
    result = await session.execute(
        select(Transcript).where(
            Transcript.transcript_id == transcript_id,
            Transcript.workspace_id == workspace_id,
            Transcript.project_id == project_id,
        )
    )
    return result.scalar_one_or_none()


async def upsert_transcript(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    transcript_id: str,
    values: dict[str, Any],
    provider: str,
    endpoint_type: str,
    schema_version: str,
    captured_at: datetime,
    run_id: str | None = None,
    raw_ref: str | None = None,
    quality_flags: list[Any] | None = None,
) -> Transcript:
    obj = await session.get(Transcript, transcript_id)
    governance = _governance(
        provider=provider,
        endpoint_type=endpoint_type,
        schema_version=schema_version,
        captured_at=captured_at,
        run_id=run_id,
        raw_ref=raw_ref,
        quality_flags=quality_flags,
    )
    clean_values = _filter_values(
        Transcript,
        values,
        {"transcript_id", "workspace_id", "project_id", *governance.keys()},
    )
    if obj is None:
        obj = Transcript(
            transcript_id=transcript_id,
            workspace_id=workspace_id,
            project_id=project_id,
            **governance,
            **clean_values,
        )
        session.add(obj)
    else:
        _check_tenant(obj, workspace_id, project_id)
        for key, value in clean_values.items():
            setattr(obj, key, value)
        for key, value in governance.items():
            setattr(obj, key, value)
    await session.flush()
    return obj
