"""Ingest normalized TikTok content records into the 12 canonical tables.

Input records are the ``content`` dicts produced by
``collectors.tikhub_social``. The service does two passes:

1. Master data: creators, sounds, hashtags, videos.
2. Observations: snapshots, comments, relations, trends.

This order satisfies the foreign keys. A comment without a video creates a
minimal video row so the relation is not lost.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.collectors.base import CollectorRawRecord
from data_intelligence_hub.repositories.tiktok_commerce import (
    add_creator_commerce,
    add_product_snapshot,
    make_product_key,
    make_shop_key,
    upsert_product,
    upsert_product_review,
    upsert_shop,
)
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
    upsert_transcript,
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
    transcripts: int = 0
    shops: int = 0
    products: int = 0
    product_snapshots: int = 0
    product_reviews: int = 0
    creator_commerce: int = 0
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
            "transcripts": self.transcripts,
            "shops": self.shops,
            "products": self.products,
            "product_snapshots": self.product_snapshots,
            "product_reviews": self.product_reviews,
            "creator_commerce": self.creator_commerce,
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


def _pick(content: dict[str, Any], *keys: str) -> Any:
    raw = content.get("raw")
    raw = raw if isinstance(raw, dict) else {}
    for source in (content, raw):
        for key in keys:
            value = source.get(key)
            if value is not None and value != "":
                return value
    return None


def _money(value: Any) -> float | None:
    """Apify shop actors return {value, currency} for money fields."""
    if isinstance(value, dict):
        value = value.get("value") or value.get("amount") or value.get("price")
    if value is None or value == "":
        return None
    text = str(value).replace("$", "").replace(",", "").strip()
    multiplier = 1
    if text and text[-1].upper() in {"K", "M", "B"}:
        multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[
            text[-1].upper()
        ]
        text = text[:-1]
    try:
        return float(text) * multiplier
    except (TypeError, ValueError):
        return None


def _count(value: Any) -> int | None:
    """Parse '1,234', '192.98K', '1.2M' and numeric objects."""
    if isinstance(value, dict):
        value = value.get("value") or value.get("count") or value.get("sold_count")
    if value is None or value == "":
        return None
    text = str(value).strip().replace(",", "")
    multiplier = 1
    if text and text[-1].upper() in {"K", "M", "B"}:
        multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[
            text[-1].upper()
        ]
        text = text[:-1]
    try:
        return int(float(text) * multiplier)
    except (TypeError, ValueError):
        return None


def _review_count(content: dict[str, Any]) -> int | None:
    value = _pick(content, "review_count", "reviewsCount", "reviewCount")
    if value is None:
        rating = _pick(content, "rating", "product_rating")
        if isinstance(rating, dict):
            value = rating.get("reviewCount") or rating.get("review_count")
    return _count(value)


def _rating(value: Any) -> float | None:
    """Some actors return {score, reviewCount} for rating."""
    if isinstance(value, dict):
        value = value.get("score") or value.get("rating") or value.get("value")
    return _money(value)


def _currency(content: dict[str, Any]) -> str | None:
    value = _pick(content, "currency")
    if isinstance(value, dict):
        return _safe_text(value.get("currency"))
    if value:
        return _safe_text(value)
    for key in (
        "price_amount",
        "original_price_amount",
        "price",
        "salePrice",
        "original_price",
    ):
        raw = _pick(content, key)
        if isinstance(raw, dict):
            return _safe_text(raw.get("currency"))
    return None


def _rate(value: Any) -> float | None:
    """Normalize percent values (0-100) to rates (0-1)."""
    if value is None or value == "":
        return None
    try:
        number = float(str(value).replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return None
    return number / 100 if abs(number) > 1 else number


def _commerce_region(content: dict[str, Any], context: IngestionContext) -> str:
    return str(
        _pick(content, "region", "country_code")
        or context.country_code
        or "US"
    ).upper()


def _commerce_product_id(content: dict[str, Any]) -> str | None:
    value = _pick(content, "product_id", "productId", "id")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _product_key_for(content: dict[str, Any], context: IngestionContext) -> str | None:
    product_id = _commerce_product_id(content)
    if product_id is None:
        return None
    return make_product_key(_commerce_region(content, context), product_id)


def _commerce_seller(content: dict[str, Any]) -> dict[str, Any]:
    raw = content.get("raw")
    for source in (content, raw if isinstance(raw, dict) else {}):
        seller = source.get("seller")
        if isinstance(seller, dict):
            return seller
    return {}


def _commerce_shop_identity(
    content: dict[str, Any], region: str
) -> tuple[str | None, str | None, str | None]:
    seller = _commerce_seller(content)
    shop_id = _pick(content, "shop_id") or seller.get("shop_id")
    seller_id = (
        _pick(content, "seller_id")
        or seller.get("seller_id")
        or seller.get("id")
    )
    shop_name = (
        _pick(content, "shop_name", "seller_name")
        or seller.get("shop_name")
        or seller.get("seller_name")
        or seller.get("name")
        or (seller if isinstance(seller, str) else None)
    )
    if shop_id or seller_id:
        shop_key = make_shop_key(region, _safe_text(shop_id), _safe_text(seller_id))
    elif shop_name:
        shop_key = f"name:{region}:{_normalize_name(shop_name)}"
    else:
        return None, None, None
    return shop_key, _safe_text(shop_id), _safe_text(seller_id)


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


async def _ensure_commerce_shop(
    session: AsyncSession,
    context: IngestionContext,
    content: dict[str, Any],
    captured_at: datetime,
) -> str | None:
    region = _commerce_region(content, context)
    shop_key, shop_id, seller_id = _commerce_shop_identity(content, region)
    if shop_key is None:
        return None
    await upsert_shop(
        session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        shop_key=shop_key,
        values={
            "shop_id": shop_id,
            "seller_id": seller_id,
            "shop_name": _safe_text(
                _pick(content, "shop_name", "seller_name")
                or _commerce_seller(content).get("shop_name")
                or _commerce_seller(content).get("name")
            ),
            "shop_type": _safe_text(_pick(content, "shop_type")),
            "seller_type": _safe_text(_pick(content, "seller_type")),
            "region": region,
            "logo_url": _safe_text(
                _pick(content, "shop_logo_url", "shop_logo")
            ),
            "rating": _pick(content, "shop_rating"),
            "follower_count": _pick(content, "shop_follower_count"),
            "product_count": _pick(content, "shop_product_count"),
            "is_mall_recommended": _pick(content, "is_mall_recommended"),
            "shop_url": _pick(content, "shop_url"),
            "identity_quality": "partial" if shop_id is None else "exact",
        },
        provider=context.provider,
        endpoint_type=context.endpoint_type,
        schema_version=context.schema_version,
        captured_at=captured_at,
        run_id=context.run_id,
        raw_ref=context.raw_ref,
    )
    return shop_key


async def _ensure_commerce_product(
    session: AsyncSession,
    context: IngestionContext,
    content: dict[str, Any],
    captured_at: datetime,
) -> str | None:
    product_key = _product_key_for(content, context)
    if product_key is None:
        return None
    region = _commerce_region(content, context)
    shop_key = await _ensure_commerce_shop(session, context, content, captured_at)
    await upsert_product(
        session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        product_key=product_key,
        values={
            "product_id": _commerce_product_id(content),
            "region": region,
            "shop_key": shop_key,
            "shop_id": _pick(content, "shop_id"),
            "seller_id": _pick(content, "seller_id"),
            "title": _safe_text(
                _pick(content, "title", "product_name", "productName", "text")
            ),
            "description": _safe_text(
                _pick(content, "description", "product_desc")
            ),
            "brand": _safe_text(_pick(content, "brand")),
            "category_l1": _safe_text(
                _pick(content, "category_l1", "category1")
            ),
            "category_l2": _safe_text(
                _pick(content, "category_l2", "category2")
            ),
            "category_l3": _safe_text(
                _pick(content, "category_l3", "category3")
            ),
            "category_path": _safe_text(
                _pick(content, "category_path", "categories")
            ),
            "product_url": _safe_text(
                _pick(content, "product_url", "url")
            ),
            "image_urls": _pick(content, "image_urls", "images"),
            "sku_count": _pick(content, "sku_count"),
            "skus_json": _pick(content, "skus_json", "skus"),
            "currency": _currency(content),
            "is_active": _pick(content, "is_active", "product_status"),
            "identity_quality": "exact",
        },
        provider=context.provider,
        endpoint_type=context.endpoint_type,
        schema_version=context.schema_version,
        captured_at=captured_at,
        run_id=context.run_id,
        raw_ref=context.raw_ref,
    )
    return product_key


def _ensure_creator_identity(
    content: dict[str, Any], context: IngestionContext
) -> str | None:
    creator_id = _pick(content, "creator_id", "author_id", "uid", "user_id")
    if creator_id is not None:
        return str(creator_id)
    unique_id = _pick(content, "unique_id", "username", "handle", "author_username")
    if unique_id:
        return f"name:{_normalize_name(unique_id)}"
    return None


async def _ensure_creator_commerce_master(
    session: AsyncSession,
    context: IngestionContext,
    content: dict[str, Any],
    captured_at: datetime,
) -> str | None:
    creator_id = _ensure_creator_identity(content, context)
    if creator_id is None:
        return None
    await upsert_creator(
        session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        creator_id=creator_id,
        values={
            key: value
            for key, value in {
                "unique_id": _pick(content, "unique_id", "username", "handle"),
                "nickname": _pick(content, "nickname", "nick_name"),
                "avatar_url": _pick(content, "avatar_url", "avatar"),
                "signature": _pick(content, "signature", "bio"),
                "follower_count": _pick(content, "follower_count", "fans"),
                "region": _commerce_region(content, context),
                "is_seller": _pick(content, "is_seller", "tt_seller"),
                "identity_quality": "exact" if _pick(
                    content, "creator_id", "author_id", "uid", "user_id"
                ) else "derived",
            }.items()
            if value is not None
        },
        provider=context.provider,
        endpoint_type=context.endpoint_type,
        schema_version=context.schema_version,
        captured_at=captured_at,
        run_id=context.run_id,
        raw_ref=context.raw_ref,
    )
    return creator_id


async def _ingest_commerce_product(
    session: AsyncSession,
    context: IngestionContext,
    content: dict[str, Any],
    captured_at: datetime,
    result: IngestionResult,
) -> None:
    product_key = _product_key_for(content, context)
    if product_key is None:
        result.skipped += 1
        return
    region = _commerce_region(content, context)
    price = _money(_pick(content, "price_amount", "price", "real_price", "salePrice"))
    original = _money(
        _pick(content, "original_price_amount", "original_price", "originalPrice")
    )
    await add_product_snapshot(
        session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        product_key=product_key,
        product_id=str(_commerce_product_id(content)),
        region=region,
        captured_at=captured_at,
        values={
            "price_amount": price,
            "original_price_amount": original,
            "min_price_amount": _money(
                _pick(content, "min_price_amount", "min_price")
            ),
            "max_price_amount": _money(
                _pick(content, "max_price_amount", "max_price")
            ),
            "avg_price_amount": _money(
                _pick(content, "avg_price_amount", "avg_price")
            ),
            "currency": _currency(content),
            "sale_count": _count(
                _pick(content, "sale_count", "sale_cnt", "saleCount", "sales")
            ),
            "sale_count_30d": _count(
                _pick(content, "sale_count_30d", "sale_30d_cnt", "saleCount30d")
            ),
            "gmv_amount_30d": _money(
                _pick(content, "gmv_amount_30d", "gmv_30d_amt", "gmv30d", "gmv")
            ),
            "commission_rate": _rate(
                _pick(content, "commission_rate", "commission")
            ),
            "stock_count": _count(
                _pick(
                    content, "stock_count", "total_stock_cnt",
                    "availableQuantity", "stock"
                )
            ),
            "review_count": _review_count(content),
            "rating": _rating(
                _pick(content, "rating", "product_rating", "stars", "score")
            ),
            "video_count_30d": _count(
                _pick(content, "video_count_30d", "video_30d_cnt")
            ),
            "live_count_30d": _count(
                _pick(content, "live_count_30d", "live_30d_cnt")
            ),
            "ifl_count_30d": _count(
                _pick(content, "ifl_count_30d", "ifl_30d_cnt")
            ),
            "is_hot": _pick(content, "is_hot"),
            "free_shipping": _pick(content, "free_shipping"),
            "shipping_price": _money(_pick(content, "shipping_price")),
            "is_estimated": bool(
                _pick(content, "is_estimated", "gmv_amount_30d", "gmv_30d_amt")
            ),
        },
        provider=context.provider,
        endpoint_type=context.endpoint_type,
        schema_version=context.schema_version,
        run_id=context.run_id,
        raw_ref=context.raw_ref,
    )
    result.product_snapshots += 1


async def _ingest_product_review(
    session: AsyncSession,
    context: IngestionContext,
    content: dict[str, Any],
    captured_at: datetime,
    result: IngestionResult,
) -> None:
    review_id = _pick(content, "review_id")
    product_key = _product_key_for(content, context)
    if review_id is None or product_key is None:
        result.skipped += 1
        return
    await upsert_product_review(
        session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        review_id=str(review_id),
        values={
            "product_key": product_key,
            "product_id": _commerce_product_id(content),
            "region": _commerce_region(content, context),
            "shop_id": _pick(content, "shop_id"),
            "sku_id": _pick(content, "sku_id"),
            "rating": _pick(content, "rating", "review_rating"),
            "text": _pick(content, "text", "review_text") or "",
            "text_language": _pick(content, "text_language", "review_language"),
            "review_time": _dt(_pick(content, "review_time")),
            "verified_purchase": _pick(
                content, "verified_purchase", "is_verified_purchase"
            ),
            "incentivized": _pick(
                content, "incentivized", "is_incentivized_review"
            ),
            "helpful_count": _pick(content, "helpful_count"),
            "images": _pick(content, "images", "review_images"),
            "variant": _pick(content, "variant"),
            "sku_specification": _pick(content, "sku_specification"),
            "reviewer_name_masked": _pick(
                content, "reviewer_name_masked", "reviewer_name"
            ),
            "reviewer_avatar_url": _pick(content, "reviewer_avatar_url"),
            "review_country": _pick(content, "review_country"),
        },
        provider=context.provider,
        endpoint_type=context.endpoint_type,
        schema_version=context.schema_version,
        captured_at=captured_at,
        run_id=context.run_id,
        raw_ref=context.raw_ref,
    )
    result.product_reviews += 1


async def _ingest_creator_commerce(
    session: AsyncSession,
    context: IngestionContext,
    content: dict[str, Any],
    captured_at: datetime,
    result: IngestionResult,
) -> None:
    creator_id = _ensure_creator_identity(content, context)
    if creator_id is None:
        result.skipped += 1
        return
    market = _commerce_region(content, context)
    await add_creator_commerce(
        session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        creator_id=creator_id,
        market=market,
        captured_at=captured_at,
        values={
            "period_days": 30,
            "window_start": captured_at - timedelta(days=30),
            "window_end": captured_at,
            "gmv_amount": _pick(content, "gmv_amount", "gmv"),
            "currency": _pick(content, "currency"),
            "units_sold": _pick(content, "units_sold", "unitsSold"),
            "gpm_amount": _pick(content, "gpm_amount", "gpm"),
            "video_gpm_amount": _pick(content, "video_gpm_amount"),
            "live_gpm_amount": _pick(content, "live_gpm_amount"),
            "avg_commission_rate": _rate(
                _pick(content, "avg_commission_rate", "commission_rate")
            ),
            "brand_collaboration_count": _pick(
                content, "brand_collaboration_count"
            ),
            "promoted_product_count": _pick(
                content, "promoted_product_count", "product_count"
            ),
            "avg_views": _pick(content, "avg_views"),
            "avg_likes": _pick(content, "avg_likes"),
            "avg_comments": _pick(content, "avg_comments"),
            "avg_shares": _pick(content, "avg_shares"),
            "engagement_rate": _rate(_pick(content, "engagement_rate")),
            "content_frequency": _pick(content, "content_frequency"),
            "post_rate": _pick(content, "post_rate"),
            "rating": _pick(content, "rating"),
            "promotion_performance_score": _pick(
                content, "promotion_performance_score"
            ),
            "follower_count": _pick(content, "follower_count", "fans"),
            "top_brands": _pick(content, "top_brands"),
            "category_list": _pick(content, "category_list"),
            "audience_json": _pick(content, "audience_json"),
            "gmv_distribution_json": _pick(content, "gmv_distribution_json"),
            "is_estimated": bool(_pick(content, "is_estimated", "gmv_amount")),
        },
        provider=context.provider,
        endpoint_type=context.endpoint_type,
        schema_version=context.schema_version,
        run_id=context.run_id,
        raw_ref=context.raw_ref,
    )
    result.creator_commerce += 1


def _effective_record_type(
    content: dict[str, Any], context: IngestionContext
) -> str | None:
    """Map provider record types onto the commerce ingestion routes.

    Apify infers ``tiktok_shop_product`` for every Shop actor, and the creator
    commerce actor is inferred as ``tiktok_video``. The actor id is the only
    reliable discriminator.
    """
    actor = str(content.get("actor_id") or "")
    if "tiktok-shop-creators" in actor:
        return "tiktok_creator_commerce"
    if "tiktok-shop" in actor:
        return "tiktok_product"
    record_type = content.get("record_type")
    if record_type == "tiktok_shop_product":
        return "tiktok_product"
    return record_type


def _is_transcript_content(
    content: dict[str, Any], context: IngestionContext
) -> bool:
    """Apify transcript items arrive as tiktok_video records with raw text."""
    if not isinstance(content.get("raw"), dict):
        return False
    return (
        content.get("schema_version") == "apify_tiktok_video.v1"
        or context.endpoint_type == "apify_tiktok_transcript_extractor"
    )


def _transcript_video_values(raw: dict[str, Any]) -> dict[str, Any]:
    video_meta = raw.get("videoMeta")
    video_meta = video_meta if isinstance(video_meta, dict) else {}
    challenges = raw.get("hashtags")
    hashtags = [
        str(item.get("name"))
        for item in (challenges if isinstance(challenges, list) else [])
        if isinstance(item, dict) and item.get("name")
    ]
    return {
        key: value
        for key, value in {
            "caption": raw.get("text"),
            "text_language": raw.get("textLanguage"),
            "published_at": _dt(raw.get("createTimeISO")),
            "duration_ms": _duration_ms(video_meta.get("duration")),
            "cover_url": video_meta.get("coverUrl"),
            "web_video_url": raw.get("webVideoUrl"),
            "is_ad": raw.get("isAd"),
            "hashtags": hashtags or None,
        }.items()
        if value is not None
    }


async def _ensure_transcript_master(
    session: AsyncSession,
    context: IngestionContext,
    content: dict[str, Any],
    captured_at: datetime,
) -> str | None:
    raw = content.get("raw")
    raw = raw if isinstance(raw, dict) else {}
    video_id = str(raw.get("id") or raw.get("videoId") or "").strip()
    if not video_id:
        return None
    author = raw.get("authorMeta")
    author = author if isinstance(author, dict) else {}
    creator_id = str(author.get("id") or "").strip() or None
    if creator_id:
        await upsert_creator(
            session,
            workspace_id=context.workspace_id,
            project_id=context.project_id,
            creator_id=creator_id,
            values={
                key: value
                for key, value in {
                    "unique_id": author.get("name"),
                    "nickname": author.get("nickName"),
                    "avatar_url": author.get("avatar"),
                    "signature": author.get("signature"),
                    "follower_count": author.get("fans"),
                    "following_count": author.get("following"),
                    "heart_count": author.get("heart"),
                    "video_count": author.get("video"),
                    "is_verified": author.get("verified"),
                    "profile_url": author.get("profileUrl"),
                    "identity_quality": "exact",
                }.items()
                if value is not None
            },
            provider=context.provider,
            endpoint_type=context.endpoint_type,
            schema_version=context.schema_version,
            captured_at=captured_at,
            run_id=context.run_id,
            raw_ref=context.raw_ref,
        )
    values = _transcript_video_values(raw)
    values["creator_id"] = creator_id
    await upsert_video(
        session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        video_id=video_id,
        values=values,
        provider=context.provider,
        endpoint_type=context.endpoint_type,
        schema_version=context.schema_version,
        captured_at=captured_at,
        run_id=context.run_id,
        raw_ref=context.raw_ref,
    )
    return video_id


async def _ingest_transcript(
    session: AsyncSession,
    context: IngestionContext,
    content: dict[str, Any],
    captured_at: datetime,
    result: IngestionResult,
) -> None:
    raw = content.get("raw")
    raw = raw if isinstance(raw, dict) else {}
    video_id = str(raw.get("id") or raw.get("videoId") or "").strip()
    text = str(content.get("text") or raw.get("text") or "").strip()
    if not video_id or not text:
        result.skipped += 1
        return
    language = str(raw.get("textLanguage") or "unknown")
    source = "third_party_asr"
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    transcript_id = hashlib.sha1(
        "\x1f".join((video_id, language, source, content_hash)).encode("utf-8")
    ).hexdigest()
    video_meta = raw.get("videoMeta")
    video_meta = video_meta if isinstance(video_meta, dict) else {}
    await upsert_transcript(
        session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        transcript_id=transcript_id,
        values={
            "video_id": video_id,
            "language": language,
            "transcript_source": source,
            "text": text,
            "word_count": len(text.split()),
            "duration_ms": _duration_ms(video_meta.get("duration")),
            "is_auto_generated": True,
            "content_hash": content_hash,
            "source_url": raw.get("webVideoUrl"),
        },
        provider=context.provider,
        endpoint_type=context.endpoint_type,
        schema_version=context.schema_version,
        captured_at=captured_at,
        run_id=context.run_id,
        raw_ref=context.raw_ref,
    )
    result.transcripts += 1


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
            record_type = _effective_record_type(content, context)
            is_video = record_type == "tiktok_video" or (
                not record_type and content.get("video_id")
            )
            if _is_transcript_content(content, context):
                await _ensure_transcript_master(session, context, content, captured_at)
            elif is_video:
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
            elif record_type == "tiktok_product":
                product_key = await _ensure_commerce_product(
                    session, context, content, captured_at
                )
                if product_key is not None:
                    result.products += 1
                    result.shops += 1 if _pick(content, "shop_id", "seller_id") else 0
            elif record_type == "tiktok_product_review":
                # Reviews may arrive without a prior product run.
                await _ensure_commerce_product(session, context, content, captured_at)
            elif record_type == "tiktok_creator_commerce":
                await _ensure_creator_commerce_master(
                    session, context, content, captured_at
                )
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
            record_type = _effective_record_type(content, context)
            is_video = record_type == "tiktok_video" or (
                not record_type and content.get("video_id")
            )
            if _is_transcript_content(content, context):
                await _ingest_transcript(
                    session, context, content, captured_at, result
                )
            elif is_video:
                if content.get("video_id"):
                    await _ingest_video(session, context, content, captured_at, result)
            elif record_type == "tiktok_comment":
                await _ingest_comment(session, context, content, captured_at, result)
            elif record_type == "tiktok_user":
                await _ingest_user(session, context, content, captured_at, result)
            elif record_type == "tiktok_product":
                await _ingest_commerce_product(
                    session, context, content, captured_at, result
                )
            elif record_type == "tiktok_product_review":
                await _ingest_product_review(
                    session, context, content, captured_at, result
                )
            elif record_type == "tiktok_creator_commerce":
                await _ingest_creator_commerce(
                    session, context, content, captured_at, result
                )
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
