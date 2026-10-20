"""TikTok R1 content canonical models.

The 12 content tables from the R1 schema. SQL types follow the Alembic
migration ``202610190045_tiktok_r1_canonical_tables``. JSON columns use the
generic ``JSON`` type so repository tests can also run on SQLite.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    text as sql_text,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base


class TikTokTenantMixin:
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False
    )


class TikTokGovernanceMixin:
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    endpoint_type: Mapped[str] = mapped_column(String(128), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(64))
    raw_ref: Mapped[str | None] = mapped_column(Text)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_stale: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sql_text("false")
    )
    quality_flags: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, server_default=sql_text("'[]'")
    )


class TikTokMasterTimestampsMixin:
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Creator(TikTokTenantMixin, TikTokGovernanceMixin, TikTokMasterTimestampsMixin, Base):
    __tablename__ = "creator"
    __table_args__ = (
        Index("ix_creator_handle", "workspace_id", "project_id", "unique_id"),
        Index("ix_creator_sec_uid", "workspace_id", "project_id", "sec_uid"),
        Index("ix_creator_region_fans", "region", "follower_count"),
    )

    creator_id: Mapped[str] = mapped_column(Text, primary_key=True)
    sec_uid: Mapped[str | None] = mapped_column(Text)
    unique_id: Mapped[str | None] = mapped_column(Text)
    nickname: Mapped[str | None] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    bio_link: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    follower_count: Mapped[int | None] = mapped_column(BigInteger)
    following_count: Mapped[int | None] = mapped_column(BigInteger)
    friend_count: Mapped[int | None] = mapped_column(BigInteger)
    video_count: Mapped[int | None] = mapped_column(BigInteger)
    heart_count: Mapped[int | None] = mapped_column(BigInteger)
    digg_count: Mapped[int | None] = mapped_column(BigInteger)
    is_verified: Mapped[bool | None] = mapped_column(Boolean)
    is_private: Mapped[bool | None] = mapped_column(Boolean)
    is_seller: Mapped[bool | None] = mapped_column(Boolean)
    commerce_user_info: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    account_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    profile_url: Mapped[str | None] = mapped_column(Text)
    identity_quality: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=sql_text("'exact'")
    )


class CreatorSnapshot(TikTokTenantMixin, TikTokGovernanceMixin, Base):
    __tablename__ = "creator_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "creator_id",
            "captured_at",
            "provider",
            "endpoint_type",
            name="uq_creator_snapshot_observation",
        ),
        Index("ix_creator_snapshot_time", "creator_id", "captured_at"),
    )

    snapshot_id: Mapped[str] = mapped_column(Text, primary_key=True)
    creator_id: Mapped[str] = mapped_column(
        ForeignKey("creator.creator_id"), nullable=False
    )
    follower_count: Mapped[int | None] = mapped_column(BigInteger)
    following_count: Mapped[int | None] = mapped_column(BigInteger)
    video_count: Mapped[int | None] = mapped_column(BigInteger)
    heart_count: Mapped[int | None] = mapped_column(BigInteger)
    digg_count: Mapped[int | None] = mapped_column(BigInteger)
    follower_delta: Mapped[int | None] = mapped_column(BigInteger)
    video_delta: Mapped[int | None] = mapped_column(BigInteger)
    engagement_rate: Mapped[float | None] = mapped_column(Numeric(6, 5))


class Video(TikTokTenantMixin, TikTokGovernanceMixin, TikTokMasterTimestampsMixin, Base):
    __tablename__ = "video"
    __table_args__ = (
        Index("ix_video_creator_time", "creator_id", "published_at"),
        Index("ix_video_sound", "sound_id"),
        Index("ix_video_published", "published_at"),
    )

    video_id: Mapped[str] = mapped_column(Text, primary_key=True)
    creator_id: Mapped[str | None] = mapped_column(ForeignKey("creator.creator_id"))
    caption: Mapped[str | None] = mapped_column(Text)
    text_language: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    cover_url: Mapped[str | None] = mapped_column(Text)
    web_video_url: Mapped[str | None] = mapped_column(Text)
    video_url: Mapped[str | None] = mapped_column(Text)
    video_url_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sound_id: Mapped[str | None] = mapped_column(ForeignKey("sound.sound_id"))
    location_created: Mapped[str | None] = mapped_column(Text)
    is_ad: Mapped[bool | None] = mapped_column(Boolean)
    is_sponsored: Mapped[bool | None] = mapped_column(Boolean)
    ad_flag: Mapped[str | None] = mapped_column(String(16))
    is_slideshow: Mapped[bool | None] = mapped_column(Boolean)
    is_pinned: Mapped[bool | None] = mapped_column(Boolean)
    is_story: Mapped[bool | None] = mapped_column(Boolean)
    has_shop_product: Mapped[bool | None] = mapped_column(Boolean)
    hashtags: Mapped[list[Any] | None] = mapped_column(JSON)
    effect_stickers: Mapped[list[Any] | None] = mapped_column(JSON)
    mentions: Mapped[list[Any] | None] = mapped_column(JSON)
    detailed_mentions: Mapped[list[Any] | None] = mapped_column(JSON)
    slideshow_image_urls: Mapped[list[Any] | None] = mapped_column(JSON)
    media_urls: Mapped[list[Any] | None] = mapped_column(JSON)


class VideoSnapshot(TikTokTenantMixin, TikTokGovernanceMixin, Base):
    __tablename__ = "video_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "video_id",
            "captured_at",
            "provider",
            "endpoint_type",
            name="uq_video_snapshot_observation",
        ),
        Index("ix_video_snapshot_time", "video_id", "captured_at"),
    )

    snapshot_id: Mapped[str] = mapped_column(Text, primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("video.video_id"), nullable=False)
    play_count: Mapped[int | None] = mapped_column(BigInteger)
    like_count: Mapped[int | None] = mapped_column(BigInteger)
    comment_count: Mapped[int | None] = mapped_column(BigInteger)
    share_count: Mapped[int | None] = mapped_column(BigInteger)
    collect_count: Mapped[int | None] = mapped_column(BigInteger)
    repost_count: Mapped[int | None] = mapped_column(BigInteger)
    engagement_rate: Mapped[float | None] = mapped_column(Numeric(6, 5))
    save_rate: Mapped[float | None] = mapped_column(Numeric(6, 5))
    share_rate: Mapped[float | None] = mapped_column(Numeric(6, 5))
    play_delta: Mapped[int | None] = mapped_column(BigInteger)
    like_delta: Mapped[int | None] = mapped_column(BigInteger)
    comment_delta: Mapped[int | None] = mapped_column(BigInteger)
    share_delta: Mapped[int | None] = mapped_column(BigInteger)
    collect_delta: Mapped[int | None] = mapped_column(BigInteger)
    repost_delta: Mapped[int | None] = mapped_column(BigInteger)


class Comment(TikTokTenantMixin, TikTokGovernanceMixin, TikTokMasterTimestampsMixin, Base):
    __tablename__ = "comment"
    __table_args__ = (
        Index("ix_comment_video_time", "video_id", "published_at"),
        Index("ix_comment_parent", "parent_comment_id"),
        Index("ix_comment_creator", "creator_id"),
    )

    comment_id: Mapped[str] = mapped_column(Text, primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("video.video_id"), nullable=False)
    creator_id: Mapped[str | None] = mapped_column(ForeignKey("creator.creator_id"))
    author_unique_id: Mapped[str | None] = mapped_column(Text)
    author_nickname: Mapped[str | None] = mapped_column(Text)
    parent_comment_id: Mapped[str | None] = mapped_column(
        ForeignKey("comment.comment_id", deferrable=True, initially="DEFERRED")
    )
    root_comment_id: Mapped[str | None] = mapped_column(Text)
    is_reply: Mapped[bool | None] = mapped_column(Boolean)
    text: Mapped[str | None] = mapped_column(Text)
    text_language: Mapped[str | None] = mapped_column(Text)
    is_pinned: Mapped[bool | None] = mapped_column(Boolean)
    creator_interacted: Mapped[bool | None] = mapped_column(Boolean)
    creator_interaction_type: Mapped[str | None] = mapped_column(String(16))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    identity_quality: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=sql_text("'exact'")
    )


class CommentSnapshot(TikTokTenantMixin, TikTokGovernanceMixin, Base):
    __tablename__ = "comment_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "comment_id",
            "captured_at",
            "provider",
            "endpoint_type",
            name="uq_comment_snapshot_observation",
        ),
        Index("ix_comment_snapshot_time", "comment_id", "captured_at"),
    )

    snapshot_id: Mapped[str] = mapped_column(Text, primary_key=True)
    comment_id: Mapped[str] = mapped_column(
        ForeignKey("comment.comment_id"), nullable=False
    )
    like_count: Mapped[int | None] = mapped_column(BigInteger)
    reply_count: Mapped[int | None] = mapped_column(BigInteger)
    list_rank: Mapped[int | None] = mapped_column(Integer)
    sample_method: Mapped[str | None] = mapped_column(String(16))


class Hashtag(TikTokTenantMixin, TikTokGovernanceMixin, TikTokMasterTimestampsMixin, Base):
    __tablename__ = "hashtag"
    __table_args__ = (
        Index("ix_hashtag_name", "name_normalized"),
        Index("ix_hashtag_category", "category"),
    )

    hashtag_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name_raw: Mapped[str] = mapped_column(Text, nullable=False)
    name_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    first_market: Mapped[str | None] = mapped_column(Text)
    first_language: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    identity_source: Mapped[str | None] = mapped_column(String(20))
    identity_quality: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=sql_text("'exact'")
    )


class HashtagSnapshot(TikTokTenantMixin, TikTokGovernanceMixin, Base):
    __tablename__ = "hashtag_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "hashtag_id",
            "captured_at",
            "provider",
            "endpoint_type",
            "country_code",
            "period_days",
            name="uq_hashtag_snapshot_observation",
        ),
        Index("ix_hashtag_snapshot_rank", "country_code", "period_days", "rank"),
        Index("ix_hashtag_snapshot_time", "hashtag_id", "captured_at"),
    )

    snapshot_id: Mapped[str] = mapped_column(Text, primary_key=True)
    hashtag_id: Mapped[str] = mapped_column(
        ForeignKey("hashtag.hashtag_id"), nullable=False
    )
    hashtag_name_raw: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer)
    post_count: Mapped[int | None] = mapped_column(BigInteger)
    view_count: Mapped[int | None] = mapped_column(BigInteger)
    trend_state: Mapped[str | None] = mapped_column(String(16))
    industry: Mapped[str | None] = mapped_column(Text)
    rank_change: Mapped[int | None] = mapped_column(Integer)
    post_delta: Mapped[int | None] = mapped_column(BigInteger)
    view_delta: Mapped[int | None] = mapped_column(BigInteger)
    popularity_curve: Mapped[list[Any] | None] = mapped_column(JSON)
    top_creator_ids: Mapped[list[Any] | None] = mapped_column(JSON)


class VideoHashtag(TikTokTenantMixin, TikTokGovernanceMixin, Base):
    __tablename__ = "video_hashtag"
    __table_args__ = (
        UniqueConstraint(
            "video_id",
            "hashtag_id",
            "position",
            "captured_at",
            "provider",
            "endpoint_type",
            name="uq_video_hashtag_observation",
        ),
        Index("ix_video_hashtag_tag", "hashtag_id", "captured_at"),
        Index("ix_video_hashtag_video", "video_id"),
    )

    snapshot_id: Mapped[str] = mapped_column(Text, primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("video.video_id"), nullable=False)
    hashtag_id: Mapped[str] = mapped_column(
        ForeignKey("hashtag.hashtag_id"), nullable=False
    )
    hashtag_name_raw: Mapped[str | None] = mapped_column(Text)
    hashtag_name_normalized: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    match_method: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[float | None] = mapped_column(Numeric(6, 5))


class TrendTopic(TikTokTenantMixin, TikTokGovernanceMixin, Base):
    __tablename__ = "trend_topic"
    __table_args__ = (
        UniqueConstraint(
            "topic_id",
            "captured_at",
            "country_code",
            "time_window",
            "language",
            "provider",
            "endpoint_type",
            name="uq_trend_topic_observation",
        ),
        Index("ix_trend_topic_rank", "country_code", "time_window", "rank"),
        Index("ix_trend_topic_time", "topic_id", "captured_at"),
        Index("ix_trend_topic_hashtag", "linked_hashtag_id"),
    )

    snapshot_id: Mapped[str] = mapped_column(Text, primary_key=True)
    topic_id: Mapped[str] = mapped_column(Text, nullable=False)
    topic_type: Mapped[str] = mapped_column(String(32), nullable=False)
    topic_name: Mapped[str | None] = mapped_column(Text)
    topic_name_normalized: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    language: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'unknown'")
    )
    category_l1: Mapped[str | None] = mapped_column(Text)
    category_l2: Mapped[str | None] = mapped_column(Text)
    time_window: Mapped[str] = mapped_column(String(16), nullable=False)
    period_days: Mapped[int | None] = mapped_column(Integer)
    rank: Mapped[int | None] = mapped_column(Integer)
    rank_change: Mapped[int | None] = mapped_column(Integer)
    popularity_score: Mapped[float | None] = mapped_column(Numeric(18, 4))
    search_volume_label: Mapped[str | None] = mapped_column(Text)
    search_volume_index: Mapped[float | None] = mapped_column(Numeric(18, 4))
    growth_rate: Mapped[float | None] = mapped_column(Numeric(6, 5))
    video_count: Mapped[int | None] = mapped_column(BigInteger)
    linked_hashtag_id: Mapped[str | None] = mapped_column(
        ForeignKey("hashtag.hashtag_id")
    )
    related_topic_ids: Mapped[list[Any] | None] = mapped_column(JSON)
    related_video_ids: Mapped[list[Any] | None] = mapped_column(JSON)
    audience_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    outline_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class Sound(TikTokTenantMixin, TikTokGovernanceMixin, TikTokMasterTimestampsMixin, Base):
    __tablename__ = "sound"
    __table_args__ = (Index("ix_sound_title", "title_normalized"),)

    sound_id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str | None] = mapped_column(Text)
    title_normalized: Mapped[str | None] = mapped_column(Text)
    author_name: Mapped[str | None] = mapped_column(Text)
    author_id: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    cover_url: Mapped[str | None] = mapped_column(Text)
    audio_url: Mapped[str | None] = mapped_column(Text)
    is_original: Mapped[bool | None] = mapped_column(Boolean)
    is_commercial: Mapped[bool | None] = mapped_column(Boolean)
    usage_count: Mapped[int | None] = mapped_column(BigInteger)
    video_count: Mapped[int | None] = mapped_column(BigInteger)


class Transcript(TikTokTenantMixin, TikTokGovernanceMixin, Base):
    __tablename__ = "transcript"
    __table_args__ = (
        UniqueConstraint(
            "video_id",
            "language",
            "transcript_source",
            "content_hash",
            name="uq_transcript_video_language_source_hash",
        ),
        Index("ix_transcript_video", "video_id"),
    )

    transcript_id: Mapped[str] = mapped_column(Text, primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("video.video_id"), nullable=False)
    language: Mapped[str | None] = mapped_column(Text)
    transcript_source: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    segments_json: Mapped[list[Any] | None] = mapped_column(JSON)
    word_count: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    is_auto_generated: Mapped[bool | None] = mapped_column(Boolean)
    confidence: Mapped[float | None] = mapped_column(Numeric(6, 5))
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
