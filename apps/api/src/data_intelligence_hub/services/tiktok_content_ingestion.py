"""Ingest normalized TikTok content records into the 12 canonical tables.

Input records are the ``content`` dicts produced by
``collectors.tikhub_social``. The service does two passes:

1. Master data: creators, sounds, hashtags, videos.
2. Observations: snapshots, comments, relations, trends.

This order satisfies the foreign keys. A comment without a video creates a
minimal video row so the relation is not lost.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.collectors.base import CollectorRawRecord
from data_intelligence_hub.repositories.tiktok_content import (
    add_comment_snapshot,
    add_creator_snapshot,
    add_hashtag_snapshot,
    add_trend_topic,
    add_video_hashtag,
    add_video_snapshot,
    get_video,
    upsert_comment,
    upsert_creator,
    upsert_hashtag,
    upsert_sound,
    upsert_video,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionContext:
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    provider: str = "tikhub"
    endpoint_type: str = ""
    schema_version: str = "tikhub.v1"
    run_id: str | None = None
    raw_ref: str | None = None
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    country_code: str = "US"
    period_days: int = 7
    time_window: str = "7d"
    language: str = "unknown"


@dataclass
class IngestionResult:
    creators: int = 0
    creator_snapshots: int = 0
    videos: int = 0
    video_snapshots: int = 0
    comments: int = 0
    comment_snapshots: int = 0
    hashtags: int = 0
    hashtag_snapshots: int = 0
    video_hashtags: int = 0
    trend_topics: int = 0
    sounds: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "creators": self.creators,
            "creator_snapshots": self.creator_snapshots,
            "videos": self.videos,
            "video_snapshots": self.video_snapshots,
            "comments": self.comments,
            "comment_snapshots": self.comment_snapshots,
            "hashtags": self.hashtags,
            "hashtag_snapshots": self.hashtag_snapshots,
            "video_hashtags": self.video_hashtags,
            "trend_topics": self.trend_topics,
            "sounds": self.sounds,
            "skipped": self.skipped,
            "errors": self.errors,
        }


def _content(record: CollectorRawRecord | dict[str, Any]) -> dict[str, Any]:
    if isinstance(record, CollectorRawRecord):
        content = dict(record.content)
        content.setdefault("record_type", record.record_type)
        return content
    if isinstance(record, dict) and isinstance(record.get("content"), dict):
        content = dict(record["content"])
        content.setdefault("record_type", record.get("record_type"))
        return content
    return record


def _captured_at(
    record: CollectorRawRecord | dict[str, Any], context: IngestionContext
) -> datetime:
    if isinstance(record, CollectorRawRecord):
        return record.collected_at
    return context.captured_at


def _dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _duration_ms(value: Any) -> int | None:
    try:
        duration = int(value)
    except (TypeError, ValueError):
        return None
    if duration <= 0:
        return None
    return duration if duration >= 1000 else duration * 1000


def _normalize_name(value: Any) -> str:
    return " ".join(str(value or "").strip().lstrip("#").lower().split())


def _engagement_rate(
    play_count: int | None,
    like_count: int | None,
    comment_count: int | None,
    share_count: int | None,
    collect_count: int | None,
) -> float | None:
    if not play_count or play_count <= 0:
        return None
    total = sum(
        value or 0
        for value in (like_count, comment_count, share_count, collect_count)
    )
    return total / play_count


def _creator_id(content: dict[str, Any]) -> str | None:
    return (
        content.get("author_id")
        or content.get("uid")
        or content.get("creator_id")
    )


def _creator_values(content: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            "unique_id": content.get("author_username") or content.get("unique_id"),
            "nickname": content.get("author_nickname") or content.get("nickname"),
            "sec_uid": content.get("sec_uid"),
            "signature": content.get("signature"),
            "region": content.get("region"),
            "language": content.get("language"),
            "avatar_url": content.get("avatar_url"),
            "follower_count": content.get("follower_count"),
            "following_count": content.get("following_count"),
            "friend_count": content.get("friend_count"),
            "video_count": content.get("video_count"),
            "heart_count": content.get("heart_count"),
            "digg_count": content.get("digg_count"),
            "is_verified": content.get("verified"),
            "is_private": content.get("private_account"),
            "is_seller": content.get("tt_seller"),
            "commerce_user_info": content.get("commerce_user_info"),
            "account_created_at": _dt(content.get("account_created_at")),
            "profile_url": content.get("profile_url"),
            "identity_quality": (
                "exact" if _creator_id(content) else "derived"
            ),
        }.items()
        if value is not None
    }


async def _ensure_creator(
    session: AsyncSession,
    context: IngestionContext,
    content: dict[str, Any],
    captured_at: datetime,
) -> str | None:
    creator_id = _creator_id(content)
    if not creator_id:
        unique_id = content.get("author_username") or content.get("unique_id")
        if not unique_id:
            return None
        creator_id = f"name:{_normalize_name(unique_id)}"
    await upsert_creator(
        session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        creator_id=creator_id,
        values=_creator_values(content),
        provider=context.provider,
        endpoint_type=context.endpoint_type,
        schema_version=context.schema_version,
        captured_at=captured_at,
        run_id=context.run_id,
        raw_ref=context.raw_ref,
    )
    return creator_id


async def _ensure_sound(
    session: AsyncSession,
    context: IngestionContext,
    content: dict[str, Any],
    captured_at: datetime,
) -> str | None:
    sound_id = content.get("music_id") or content.get("sound_id")
    if not sound_id:
        return None
    values = {
        key: value
        for key, value in {
            "title": content.get("music_title") or content.get("title"),
            "title_normalized": _normalize_name(
                content.get("music_title") or content.get("title")
            ),
            "author_name": content.get("music_author") or content.get("author_name"),
            "author_id": content.get("music_author_id"),
            "duration_ms": _duration_ms(content.get("music_duration")),
            "cover_url": content.get("music_cover_url"),
            "audio_url": content.get("music_play_url"),
            "is_original": content.get("music_original"),
            "is_commercial": content.get("is_commercial"),
            "usage_count": content.get("usage_count"),
        }.items()
        if value is not None
    }
    await upsert_sound(
        session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        sound_id=sound_id,
        values=values,
        provider=context.provider,
        endpoint_type=context.endpoint_type,
        schema_version=context.schema_version,
        captured_at=captured_at,
        run_id=context.run_id,
        raw_ref=context.raw_ref,
    )
    return sound_id


async def _ensure_hashtags(
    session: AsyncSession,
    context: IngestionContext,
    content: dict[str, Any],
    video_id: str,
    captured_at: datetime,
    result: IngestionResult,
) -> None:
    hashtags = content.get("hashtags")
    if not isinstance(hashtags, list):
        return
    for position, item in enumerate(hashtags):
        if isinstance(item, dict):
            name = item.get("name") or item.get("cha_name") or item.get("title")
            hashtag_id = item.get("id") or item.get("cid") or item.get("ch_id")
        else:
            name = item
            hashtag_id = None
        normalized = _normalize_name(name)
        if not normalized:
            continue
        hashtag_id = str(hashtag_id) if hashtag_id else f"name:{normalized}"
        await upsert_hashtag(
            session,
            workspace_id=context.workspace_id,
            project_id=context.project_id,
            hashtag_id=hashtag_id,
            values={
                "name_raw": str(name),
                "name_normalized": normalized,
                "identity_source": "platform_id" if not hashtag_id.startswith("name:") else "name",
                "identity_quality": "exact" if not hashtag_id.startswith("name:") else "derived",
            },
            provider=context.provider,
            endpoint_type=context.endpoint_type,
            schema_version=context.schema_version,
            captured_at=captured_at,
            run_id=context.run_id,
            raw_ref=context.raw_ref,
        )
        result.hashtags += 1
        exact_id = hashtag_id != f"name:{normalized}"
        await add_video_hashtag(
            session,
            workspace_id=context.workspace_id,
            project_id=context.project_id,
            video_id=video_id,
            hashtag_id=hashtag_id,
            position=position,
            captured_at=captured_at,
            values={
                "hashtag_name_raw": str(name),
                "hashtag_name_normalized": normalized,
                "match_method": "exact_id" if exact_id else "name_normalized",
                "confidence": 1.0 if exact_id else 0.7,
            },
            provider=context.provider,
            endpoint_type=context.endpoint_type,
            schema_version=context.schema_version,
            run_id=context.run_id,
            raw_ref=context.raw_ref,
        )
        result.video_hashtags += 1


async def _ingest_video(
    session: AsyncSession,
    context: IngestionContext,
    content: dict[str, Any],
    captured_at: datetime,
    result: IngestionResult,
) -> None:
    video_id = content.get("video_id")
    if not video_id:
        result.skipped += 1
        return
    creator_id = await _ensure_creator(session, context, content, captured_at)
    sound_id = await _ensure_sound(session, context, content, captured_at)
    play_count = content.get("play_count")
    like_count = content.get("like_count")
    comment_count = content.get("comment_count")
    share_count = content.get("share_count")
    collect_count = content.get("collect_count")
    await upsert_video(
        session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        video_id=video_id,
        values={
            "creator_id": creator_id,
            "caption": content.get("text"),
            "text_language": content.get("text_language"),
            "published_at": _dt(content.get("created_at")),
            "duration_ms": _duration_ms(content.get("duration")),
            "cover_url": content.get("cover_url"),
            "web_video_url": content.get("web_video_url"),
            "sound_id": sound_id,
            "is_ad": content.get("is_ad"),
            "hashtags": content.get("hashtags"),
        },
        provider=context.provider,
        endpoint_type=context.endpoint_type,
        schema_version=context.schema_version,
        captured_at=captured_at,
        run_id=context.run_id,
        raw_ref=context.raw_ref,
    )
    result.videos += 1
    await add_video_snapshot(
        session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        video_id=video_id,
        captured_at=captured_at,
        values={
            "play_count": play_count,
            "like_count": like_count,
            "comment_count": comment_count,
            "share_count": share_count,
            "collect_count": collect_count,
            "repost_count": content.get("repost_count"),
            "engagement_rate": _engagement_rate(
                play_count, like_count, comment_count, share_count, collect_count
            ),
        },
        provider=context.provider,
        endpoint_type=context.endpoint_type,
        schema_version=context.schema_version,
        run_id=context.run_id,
        raw_ref=context.raw_ref,
    )
    result.video_snapshots += 1
    await _ensure_hashtags(session, context, content, video_id, captured_at, result)


async def _ingest_user(
    session: AsyncSession,
    context: IngestionContext,
    content: dict[str, Any],
    captured_at: datetime,
    result: IngestionResult,
) -> None:
    creator_id = await _ensure_creator(session, context, content, captured_at)
    if not creator_id:
        result.skipped += 1
        return
    result.creators += 1
    await add_creator_snapshot(
        session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        creator_id=creator_id,
        captured_at=captured_at,
        values={
            "follower_count": content.get("follower_count"),
            "following_count": content.get("following_count"),
            "video_count": content.get("video_count"),
            "heart_count": content.get("heart_count"),
            "digg_count": content.get("digg_count"),
        },
        provider=context.provider,
        endpoint_type=context.endpoint_type,
        schema_version=context.schema_version,
        run_id=context.run_id,
        raw_ref=context.raw_ref,
    )
    result.creator_snapshots += 1


async def _ingest_comment(
    session: AsyncSession,
    context: IngestionContext,
    content: dict[str, Any],
    captured_at: datetime,
    result: IngestionResult,
) -> None:
    comment_id = content.get("comment_id")
    video_id = content.get("video_id")
    if not comment_id or not video_id:
        result.skipped += 1
        return
    video = await get_video(
        session, context.workspace_id, context.project_id, video_id
    )
    if video is None:
        await upsert_video(
            session,
            workspace_id=context.workspace_id,
            project_id=context.project_id,
            video_id=video_id,
            values={},
            provider=context.provider,
            endpoint_type=context.endpoint_type,
            schema_version=context.schema_version,
            captured_at=captured_at,
            run_id=context.run_id,
            raw_ref=context.raw_ref,
            quality_flags=["partial_response"],
        )
    creator_id = await _ensure_creator(session, context, content, captured_at)
    await upsert_comment(
        session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        comment_id=comment_id,
        values={
            "video_id": video_id,
            "creator_id": creator_id,
            "author_unique_id": content.get("author_unique_id"),
            "author_nickname": content.get("author_nickname"),
            "parent_comment_id": content.get("parent_comment_id"),
            "root_comment_id": content.get("root_comment_id"),
            "is_reply": content.get("is_reply"),
            "text": content.get("text"),
            "text_language": content.get("text_language"),
            "is_pinned": content.get("is_pinned"),
            "creator_interacted": content.get("creator_interacted"),
            "creator_interaction_type": (
                "liked" if content.get("creator_interacted") else None
            ),
            "published_at": _dt(content.get("published_at")),
        },
        provider=context.provider,
        endpoint_type=context.endpoint_type,
        schema_version=context.schema_version,
        captured_at=captured_at,
        run_id=context.run_id,
        raw_ref=context.raw_ref,
    )
    result.comments += 1
    await add_comment_snapshot(
        session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        comment_id=comment_id,
        captured_at=captured_at,
        values={
            "like_count": content.get("like_count"),
            "reply_count": content.get("reply_count"),
        },
        provider=context.provider,
        endpoint_type=context.endpoint_type,
        schema_version=context.schema_version,
        run_id=context.run_id,
        raw_ref=context.raw_ref,
    )
    result.comment_snapshots += 1


async def _ingest_hashtag(
    session: AsyncSession,
    context: IngestionContext,
    content: dict[str, Any],
    captured_at: datetime,
    result: IngestionResult,
) -> None:
    hashtag_id = content.get("hashtag_id")
    name = content.get("name")
    if not hashtag_id or not name:
        result.skipped += 1
        return
    await upsert_hashtag(
        session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        hashtag_id=hashtag_id,
        values={
            "name_raw": name,
            "name_normalized": _normalize_name(name),
            "description": content.get("description"),
            "identity_source": "platform_id",
            "identity_quality": "exact",
        },
        provider=context.provider,
        endpoint_type=context.endpoint_type,
        schema_version=context.schema_version,
        captured_at=captured_at,
        run_id=context.run_id,
        raw_ref=context.raw_ref,
    )
    result.hashtags += 1


async def _ingest_trend(
    session: AsyncSession,
    context: IngestionContext,
    content: dict[str, Any],
    captured_at: datetime,
    result: IngestionResult,
) -> None:
    trend_type = str(content.get("trend_type") or "")
    name = content.get("name")
    entity_id = content.get("entity_id")
    if not name and not entity_id:
        result.skipped += 1
        return
    if trend_type == "music":
        sound_id = entity_id
        if sound_id:
            await upsert_sound(
                session,
                workspace_id=context.workspace_id,
                project_id=context.project_id,
                sound_id=sound_id,
                values={
                    "title": name,
                    "title_normalized": _normalize_name(name),
                },
                provider=context.provider,
                endpoint_type=context.endpoint_type,
                schema_version=context.schema_version,
                captured_at=captured_at,
                run_id=context.run_id,
                raw_ref=context.raw_ref,
            )
            result.sounds += 1
        topic_id = f"sound:{sound_id}" if sound_id else f"sound:{_normalize_name(name)}"
        topic_type = "sound"
    elif trend_type == "hashtag":
        hashtag_id = entity_id or f"name:{_normalize_name(name)}"
        await upsert_hashtag(
            session,
            workspace_id=context.workspace_id,
            project_id=context.project_id,
            hashtag_id=hashtag_id,
            values={
                "name_raw": name,
                "name_normalized": _normalize_name(name),
                "identity_source": "platform_id" if entity_id else "name",
                "identity_quality": "exact" if entity_id else "derived",
            },
            provider=context.provider,
            endpoint_type=context.endpoint_type,
            schema_version=context.schema_version,
            captured_at=captured_at,
            run_id=context.run_id,
            raw_ref=context.raw_ref,
        )
        result.hashtags += 1
        await add_hashtag_snapshot(
            session,
            workspace_id=context.workspace_id,
            project_id=context.project_id,
            hashtag_id=hashtag_id,
            captured_at=captured_at,
            country_code=context.country_code,
            period_days=context.period_days,
            values={
                "hashtag_name_raw": name,
                "rank": content.get("rank"),
                "post_count": content.get("post_count"),
                "view_count": content.get("view_count"),
            },
            provider=context.provider,
            endpoint_type=context.endpoint_type,
            schema_version=context.schema_version,
            run_id=context.run_id,
            raw_ref=context.raw_ref,
        )
        result.hashtag_snapshots += 1
        topic_id = f"hashtag:{hashtag_id}"
        topic_type = "hashtag"
    else:
        topic_id = f"search:{context.country_code}:{_normalize_name(name)}"
        topic_type = "search_topic"
    await add_trend_topic(
        session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        topic_id=topic_id,
        topic_type=topic_type,
        country_code=context.country_code,
        time_window=context.time_window,
        language=context.language,
        captured_at=captured_at,
        values={
            "topic_name": name,
            "topic_name_normalized": _normalize_name(name),
            "rank": content.get("rank"),
            "post_count": content.get("post_count"),
            "view_count": content.get("view_count"),
            "related_topic_ids": (
                content.get("value", {}).get("topCreators")
                if isinstance(content.get("value"), dict)
                else None
            ),
        },
        provider=context.provider,
        endpoint_type=context.endpoint_type,
        schema_version=context.schema_version,
        run_id=context.run_id,
        raw_ref=context.raw_ref,
    )
    result.trend_topics += 1


async def ingest_tiktok_content(
    session: AsyncSession,
    records: list[CollectorRawRecord | dict[str, Any]],
    context: IngestionContext,
) -> IngestionResult:
    """Write normalized TikTok content into the 12 canonical tables."""
    result = IngestionResult()
    contents: list[tuple[dict[str, Any], datetime]] = []
    for record in records:
        content = _content(record)
        if not isinstance(content, dict):
            result.skipped += 1
            continue
        contents.append((content, _captured_at(record, context)))

    # Pass 1: master data. This satisfies FKs before observations.
    for content, captured_at in contents:
        try:
            record_type = content.get("record_type")
            is_video = record_type == "tiktok_video" or (
                not record_type and content.get("video_id")
            )
            if is_video:
                creator_id = await _ensure_creator(session, context, content, captured_at)
                sound_id = await _ensure_sound(session, context, content, captured_at)
                video_id = content.get("video_id")
                if video_id:
                    await upsert_video(
                        session,
                        workspace_id=context.workspace_id,
                        project_id=context.project_id,
                        video_id=video_id,
                        values={
                            "creator_id": creator_id,
                            "caption": content.get("text"),
                            "text_language": content.get("text_language"),
                            "published_at": _dt(content.get("created_at")),
                            "duration_ms": _duration_ms(content.get("duration")),
                            "cover_url": content.get("cover_url"),
                            "web_video_url": content.get("web_video_url"),
                            "sound_id": sound_id,
                            "is_ad": content.get("is_ad"),
                            "hashtags": content.get("hashtags"),
                        },
                        provider=context.provider,
                        endpoint_type=context.endpoint_type,
                        schema_version=context.schema_version,
                        captured_at=captured_at,
                        run_id=context.run_id,
                        raw_ref=context.raw_ref,
                    )
            elif record_type == "tiktok_user":
                await _ensure_creator(session, context, content, captured_at)
            elif record_type == "tiktok_hashtag":
                hashtag_id = content.get("hashtag_id")
                if hashtag_id and content.get("name"):
                    await upsert_hashtag(
                        session,
                        workspace_id=context.workspace_id,
                        project_id=context.project_id,
                        hashtag_id=hashtag_id,
                        values={
                            "name_raw": content.get("name"),
                            "name_normalized": _normalize_name(content.get("name")),
                            "identity_source": "platform_id",
                            "identity_quality": "exact",
                        },
                        provider=context.provider,
                        endpoint_type=context.endpoint_type,
                        schema_version=context.schema_version,
                        captured_at=captured_at,
                        run_id=context.run_id,
                        raw_ref=context.raw_ref,
                    )
            elif record_type == "tiktok_trend":
                await _ensure_trend_master(session, context, content, captured_at, result)
        except Exception as exc:
            logger.warning("TikTok master ingest failed: %s", exc)
            result.errors.append(f"master:{type(exc).__name__}:{exc}")

    # Pass 2: observations.
    for content, captured_at in contents:
        try:
            record_type = content.get("record_type")
            is_video = record_type == "tiktok_video" or (
                not record_type and content.get("video_id")
            )
            if is_video:
                if content.get("video_id"):
                    await _ingest_video(session, context, content, captured_at, result)
            elif record_type == "tiktok_comment":
                await _ingest_comment(session, context, content, captured_at, result)
            elif record_type == "tiktok_user":
                await _ingest_user(session, context, content, captured_at, result)
            elif record_type == "tiktok_hashtag":
                await _ingest_hashtag(session, context, content, captured_at, result)
            elif record_type == "tiktok_trend":
                await _ingest_trend(session, context, content, captured_at, result)
            else:
                result.skipped += 1
        except Exception as exc:
            logger.warning("TikTok observation ingest failed: %s", exc)
            result.errors.append(f"observation:{type(exc).__name__}:{exc}")

    await session.flush()
    return result


async def _ensure_trend_master(
    session: AsyncSession,
    context: IngestionContext,
    content: dict[str, Any],
    captured_at: datetime,
    result: IngestionResult,
) -> None:
    """Create the master row a trend record references."""
    trend_type = str(content.get("trend_type") or "")
    name = content.get("name")
    entity_id = content.get("entity_id")
    if trend_type == "music" and entity_id:
        await upsert_sound(
            session,
            workspace_id=context.workspace_id,
            project_id=context.project_id,
            sound_id=entity_id,
            values={"title": name, "title_normalized": _normalize_name(name)},
            provider=context.provider,
            endpoint_type=context.endpoint_type,
            schema_version=context.schema_version,
            captured_at=captured_at,
            run_id=context.run_id,
            raw_ref=context.raw_ref,
        )
    elif trend_type == "hashtag" and (entity_id or name):
        hashtag_id = entity_id or f"name:{_normalize_name(name)}"
        await upsert_hashtag(
            session,
            workspace_id=context.workspace_id,
            project_id=context.project_id,
            hashtag_id=hashtag_id,
            values={
                "name_raw": name,
                "name_normalized": _normalize_name(name),
                "identity_source": "platform_id" if entity_id else "name",
                "identity_quality": "exact" if entity_id else "derived",
            },
            provider=context.provider,
            endpoint_type=context.endpoint_type,
            schema_version=context.schema_version,
            captured_at=captured_at,
            run_id=context.run_id,
            raw_ref=context.raw_ref,
        )
    # search_word trends use trend_topic only; no master row is required.
