"""Add TikTok R1 canonical tables.

Revision ID: 202610190045
Revises: 202607280044
Create Date: 2026-10-19

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202610190045"
down_revision: str | None = "202607280044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tenant_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
    )


def _governance_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("endpoint_type", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=True),
        sa.Column("raw_ref", sa.Text(), nullable=True),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_stale", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "quality_flags",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def _master_timestamps() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def _tenant_constraints(table: str) -> tuple[sa.Constraint, ...]:
    return (
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=f"fk_{table}_workspace",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=f"fk_{table}_project",
        ),
    )


def _jsonb() -> postgresql.JSONB:
    return postgresql.JSONB()


def upgrade() -> None:
    op.create_table(
        "creator",
        sa.Column("creator_id", sa.Text(), nullable=False),
        sa.Column("sec_uid", sa.Text(), nullable=True),
        sa.Column("unique_id", sa.Text(), nullable=True),
        sa.Column("nickname", sa.Text(), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("bio_link", sa.Text(), nullable=True),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("follower_count", sa.BigInteger(), nullable=True),
        sa.Column("following_count", sa.BigInteger(), nullable=True),
        sa.Column("friend_count", sa.BigInteger(), nullable=True),
        sa.Column("video_count", sa.BigInteger(), nullable=True),
        sa.Column("heart_count", sa.BigInteger(), nullable=True),
        sa.Column("digg_count", sa.BigInteger(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=True),
        sa.Column("is_private", sa.Boolean(), nullable=True),
        sa.Column("is_seller", sa.Boolean(), nullable=True),
        sa.Column("commerce_user_info", _jsonb(), nullable=True),
        sa.Column("account_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("profile_url", sa.Text(), nullable=True),
        sa.Column(
            "identity_quality",
            sa.String(length=20),
            server_default=sa.text("'exact'"),
            nullable=False,
        ),
        *_master_timestamps(),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("creator_id", name="pk_creator"),
        *_tenant_constraints("creator"),
    )
    op.create_index(
        "ix_creator_handle",
        "creator",
        ["workspace_id", "project_id", "unique_id"],
    )
    op.create_index(
        "ix_creator_sec_uid",
        "creator",
        ["workspace_id", "project_id", "sec_uid"],
    )
    op.create_index("ix_creator_region_fans", "creator", ["region", "follower_count"])

    op.create_table(
        "hashtag",
        sa.Column("hashtag_id", sa.Text(), nullable=False),
        sa.Column("name_raw", sa.Text(), nullable=False),
        sa.Column("name_normalized", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("first_market", sa.Text(), nullable=True),
        sa.Column("first_language", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("identity_source", sa.String(length=20), nullable=True),
        sa.Column(
            "identity_quality",
            sa.String(length=20),
            server_default=sa.text("'exact'"),
            nullable=False,
        ),
        *_master_timestamps(),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("hashtag_id", name="pk_hashtag"),
        *_tenant_constraints("hashtag"),
    )
    op.create_index("ix_hashtag_name", "hashtag", ["name_normalized"])
    op.create_index("ix_hashtag_category", "hashtag", ["category"])

    op.create_table(
        "sound",
        sa.Column("sound_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("title_normalized", sa.Text(), nullable=True),
        sa.Column("author_name", sa.Text(), nullable=True),
        sa.Column("author_id", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("cover_url", sa.Text(), nullable=True),
        sa.Column("audio_url", sa.Text(), nullable=True),
        sa.Column("is_original", sa.Boolean(), nullable=True),
        sa.Column("is_commercial", sa.Boolean(), nullable=True),
        sa.Column("usage_count", sa.BigInteger(), nullable=True),
        sa.Column("video_count", sa.BigInteger(), nullable=True),
        *_master_timestamps(),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("sound_id", name="pk_sound"),
        *_tenant_constraints("sound"),
    )
    op.create_index("ix_sound_title", "sound", ["title_normalized"])

    op.create_table(
        "shop",
        sa.Column("shop_key", sa.Text(), nullable=False),
        sa.Column("shop_id", sa.Text(), nullable=True),
        sa.Column("seller_id", sa.Text(), nullable=True),
        sa.Column("shop_name", sa.Text(), nullable=True),
        sa.Column("shop_type", sa.Text(), nullable=True),
        sa.Column("seller_type", sa.Text(), nullable=True),
        sa.Column("region", sa.Text(), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("rating", sa.Numeric(3, 2), nullable=True),
        sa.Column("follower_count", sa.BigInteger(), nullable=True),
        sa.Column("product_count", sa.BigInteger(), nullable=True),
        sa.Column("is_mall_recommended", sa.Boolean(), nullable=True),
        sa.Column("shop_url", sa.Text(), nullable=True),
        sa.Column(
            "identity_quality",
            sa.String(length=20),
            server_default=sa.text("'exact'"),
            nullable=False,
        ),
        *_master_timestamps(),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("shop_key", name="pk_shop"),
        *_tenant_constraints("shop"),
    )
    op.create_index(
        "uq_shop_region_shop_id",
        "shop",
        ["region", "shop_id"],
        unique=True,
        postgresql_where=sa.text("shop_id IS NOT NULL"),
    )
    op.create_index(
        "uq_shop_region_seller_id",
        "shop",
        ["region", "seller_id"],
        unique=True,
        postgresql_where=sa.text("shop_id IS NULL"),
    )

    op.create_table(
        "product",
        sa.Column("product_key", sa.Text(), nullable=False),
        sa.Column("product_id", sa.Text(), nullable=False),
        sa.Column("region", sa.Text(), nullable=False),
        sa.Column("shop_key", sa.Text(), nullable=True),
        sa.Column("shop_id", sa.Text(), nullable=True),
        sa.Column("seller_id", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("brand", sa.Text(), nullable=True),
        sa.Column("category_l1", sa.Text(), nullable=True),
        sa.Column("category_l2", sa.Text(), nullable=True),
        sa.Column("category_l3", sa.Text(), nullable=True),
        sa.Column("category_path", sa.Text(), nullable=True),
        sa.Column("product_url", sa.Text(), nullable=True),
        sa.Column("image_urls", _jsonb(), nullable=True),
        sa.Column("sku_count", sa.Integer(), nullable=True),
        sa.Column("skus_json", _jsonb(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column(
            "identity_quality",
            sa.String(length=20),
            server_default=sa.text("'exact'"),
            nullable=False,
        ),
        *_master_timestamps(),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("product_key", name="pk_product"),
        sa.UniqueConstraint("region", "product_id", name="uq_product_region_id"),
        sa.ForeignKeyConstraint(
            ["shop_key"],
            ["shop.shop_key"],
            name="fk_product_shop",
        ),
        *_tenant_constraints("product"),
    )
    op.create_index("ix_product_shop", "product", ["region", "shop_key"])
    op.create_index("ix_product_category", "product", ["category_l1", "category_l2"])
    op.create_index("ix_product_title", "product", ["title"])

    op.create_table(
        "video",
        sa.Column("video_id", sa.Text(), nullable=False),
        sa.Column("creator_id", sa.Text(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("text_language", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("cover_url", sa.Text(), nullable=True),
        sa.Column("web_video_url", sa.Text(), nullable=True),
        sa.Column("video_url", sa.Text(), nullable=True),
        sa.Column("video_url_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sound_id", sa.Text(), nullable=True),
        sa.Column("location_created", sa.Text(), nullable=True),
        sa.Column("is_ad", sa.Boolean(), nullable=True),
        sa.Column("is_sponsored", sa.Boolean(), nullable=True),
        sa.Column("ad_flag", sa.String(length=16), nullable=True),
        sa.Column("is_slideshow", sa.Boolean(), nullable=True),
        sa.Column("is_pinned", sa.Boolean(), nullable=True),
        sa.Column("is_story", sa.Boolean(), nullable=True),
        sa.Column("has_shop_product", sa.Boolean(), nullable=True),
        sa.Column("hashtags", _jsonb(), nullable=True),
        sa.Column("effect_stickers", _jsonb(), nullable=True),
        sa.Column("mentions", _jsonb(), nullable=True),
        sa.Column("detailed_mentions", _jsonb(), nullable=True),
        sa.Column("slideshow_image_urls", _jsonb(), nullable=True),
        sa.Column("media_urls", _jsonb(), nullable=True),
        *_master_timestamps(),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("video_id", name="pk_video"),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["creator.creator_id"],
            name="fk_video_creator",
        ),
        sa.ForeignKeyConstraint(
            ["sound_id"],
            ["sound.sound_id"],
            name="fk_video_sound",
        ),
        *_tenant_constraints("video"),
    )
    op.create_index("ix_video_creator_time", "video", ["creator_id", "published_at"])
    op.create_index("ix_video_sound", "video", ["sound_id"])
    op.create_index("ix_video_published", "video", ["published_at"])

    op.create_table(
        "comment",
        sa.Column("comment_id", sa.Text(), nullable=False),
        sa.Column("video_id", sa.Text(), nullable=False),
        sa.Column("creator_id", sa.Text(), nullable=True),
        sa.Column("author_unique_id", sa.Text(), nullable=True),
        sa.Column("author_nickname", sa.Text(), nullable=True),
        sa.Column("parent_comment_id", sa.Text(), nullable=True),
        sa.Column("root_comment_id", sa.Text(), nullable=True),
        sa.Column("is_reply", sa.Boolean(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("text_language", sa.Text(), nullable=True),
        sa.Column("is_pinned", sa.Boolean(), nullable=True),
        sa.Column("creator_interacted", sa.Boolean(), nullable=True),
        sa.Column("creator_interaction_type", sa.String(length=16), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "identity_quality",
            sa.String(length=20),
            server_default=sa.text("'exact'"),
            nullable=False,
        ),
        *_master_timestamps(),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("comment_id", name="pk_comment"),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["video.video_id"],
            name="fk_comment_video",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["creator.creator_id"],
            name="fk_comment_creator",
        ),
        sa.ForeignKeyConstraint(
            ["parent_comment_id"],
            ["comment.comment_id"],
            name="fk_comment_parent",
            deferrable=True,
            initially="DEFERRED",
        ),
        *_tenant_constraints("comment"),
    )
    op.create_index("ix_comment_video_time", "comment", ["video_id", "published_at"])
    op.create_index("ix_comment_parent", "comment", ["parent_comment_id"])
    op.create_index("ix_comment_creator", "comment", ["creator_id"])

    op.create_table(
        "transcript",
        sa.Column("transcript_id", sa.Text(), nullable=False),
        sa.Column("video_id", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("transcript_source", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("segments_json", _jsonb(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("is_auto_generated", sa.Boolean(), nullable=True),
        sa.Column("confidence", sa.Numeric(6, 5), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("transcript_id", name="pk_transcript"),
        sa.UniqueConstraint(
            "video_id",
            "language",
            "transcript_source",
            "content_hash",
            name="uq_transcript_video_language_source_hash",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["video.video_id"],
            name="fk_transcript_video",
        ),
        *_tenant_constraints("transcript"),
    )
    op.create_index("ix_transcript_video", "transcript", ["video_id"])

    op.create_table(
        "video_hashtag",
        sa.Column("snapshot_id", sa.Text(), nullable=False),
        sa.Column("video_id", sa.Text(), nullable=False),
        sa.Column("hashtag_id", sa.Text(), nullable=False),
        sa.Column("hashtag_name_raw", sa.Text(), nullable=True),
        sa.Column("hashtag_name_normalized", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("match_method", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Numeric(6, 5), nullable=True),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("snapshot_id", name="pk_video_hashtag"),
        sa.UniqueConstraint(
            "video_id",
            "hashtag_id",
            "position",
            "captured_at",
            "provider",
            "endpoint_type",
            name="uq_video_hashtag_observation",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["video.video_id"],
            name="fk_video_hashtag_video",
        ),
        sa.ForeignKeyConstraint(
            ["hashtag_id"],
            ["hashtag.hashtag_id"],
            name="fk_video_hashtag_hashtag",
        ),
        *_tenant_constraints("video_hashtag"),
    )
    op.create_index("ix_video_hashtag_tag", "video_hashtag", ["hashtag_id", "captured_at"])
    op.create_index("ix_video_hashtag_video", "video_hashtag", ["video_id"])

    op.create_table(
        "trend_topic",
        sa.Column("snapshot_id", sa.Text(), nullable=False),
        sa.Column("topic_id", sa.Text(), nullable=False),
        sa.Column("topic_type", sa.String(length=32), nullable=False),
        sa.Column("topic_name", sa.Text(), nullable=True),
        sa.Column("topic_name_normalized", sa.Text(), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column(
            "language",
            sa.Text(),
            server_default=sa.text("'unknown'"),
            nullable=False,
        ),
        sa.Column("category_l1", sa.Text(), nullable=True),
        sa.Column("category_l2", sa.Text(), nullable=True),
        sa.Column("time_window", sa.String(length=16), nullable=False),
        sa.Column("period_days", sa.Integer(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("rank_change", sa.Integer(), nullable=True),
        sa.Column("popularity_score", sa.Numeric(18, 4), nullable=True),
        sa.Column("search_volume_label", sa.Text(), nullable=True),
        sa.Column("search_volume_index", sa.Numeric(18, 4), nullable=True),
        sa.Column("growth_rate", sa.Numeric(6, 5), nullable=True),
        sa.Column("video_count", sa.BigInteger(), nullable=True),
        sa.Column("linked_hashtag_id", sa.Text(), nullable=True),
        sa.Column("related_topic_ids", _jsonb(), nullable=True),
        sa.Column("related_video_ids", _jsonb(), nullable=True),
        sa.Column("audience_json", _jsonb(), nullable=True),
        sa.Column("outline_json", _jsonb(), nullable=True),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("snapshot_id", name="pk_trend_topic"),
        sa.UniqueConstraint(
            "topic_id",
            "captured_at",
            "country_code",
            "time_window",
            "language",
            "provider",
            "endpoint_type",
            name="uq_trend_topic_observation",
        ),
        sa.ForeignKeyConstraint(
            ["linked_hashtag_id"],
            ["hashtag.hashtag_id"],
            name="fk_trend_topic_hashtag",
        ),
        *_tenant_constraints("trend_topic"),
    )
    op.create_index(
        "ix_trend_topic_rank",
        "trend_topic",
        ["country_code", "time_window", "rank"],
    )
    op.create_index("ix_trend_topic_time", "trend_topic", ["topic_id", "captured_at"])
    op.create_index("ix_trend_topic_hashtag", "trend_topic", ["linked_hashtag_id"])

    op.create_table(
        "creator_snapshot",
        sa.Column("snapshot_id", sa.Text(), nullable=False),
        sa.Column("creator_id", sa.Text(), nullable=False),
        sa.Column("follower_count", sa.BigInteger(), nullable=True),
        sa.Column("following_count", sa.BigInteger(), nullable=True),
        sa.Column("video_count", sa.BigInteger(), nullable=True),
        sa.Column("heart_count", sa.BigInteger(), nullable=True),
        sa.Column("digg_count", sa.BigInteger(), nullable=True),
        sa.Column("follower_delta", sa.BigInteger(), nullable=True),
        sa.Column("video_delta", sa.BigInteger(), nullable=True),
        sa.Column("engagement_rate", sa.Numeric(6, 5), nullable=True),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("snapshot_id", name="pk_creator_snapshot"),
        sa.UniqueConstraint(
            "creator_id",
            "captured_at",
            "provider",
            "endpoint_type",
            name="uq_creator_snapshot_observation",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["creator.creator_id"],
            name="fk_creator_snapshot_creator",
        ),
        *_tenant_constraints("creator_snapshot"),
    )
    op.create_index(
        "ix_creator_snapshot_time",
        "creator_snapshot",
        ["creator_id", "captured_at"],
    )

    op.create_table(
        "video_snapshot",
        sa.Column("snapshot_id", sa.Text(), nullable=False),
        sa.Column("video_id", sa.Text(), nullable=False),
        sa.Column("play_count", sa.BigInteger(), nullable=True),
        sa.Column("like_count", sa.BigInteger(), nullable=True),
        sa.Column("comment_count", sa.BigInteger(), nullable=True),
        sa.Column("share_count", sa.BigInteger(), nullable=True),
        sa.Column("collect_count", sa.BigInteger(), nullable=True),
        sa.Column("repost_count", sa.BigInteger(), nullable=True),
        sa.Column("engagement_rate", sa.Numeric(6, 5), nullable=True),
        sa.Column("save_rate", sa.Numeric(6, 5), nullable=True),
        sa.Column("share_rate", sa.Numeric(6, 5), nullable=True),
        sa.Column("play_delta", sa.BigInteger(), nullable=True),
        sa.Column("like_delta", sa.BigInteger(), nullable=True),
        sa.Column("comment_delta", sa.BigInteger(), nullable=True),
        sa.Column("share_delta", sa.BigInteger(), nullable=True),
        sa.Column("collect_delta", sa.BigInteger(), nullable=True),
        sa.Column("repost_delta", sa.BigInteger(), nullable=True),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("snapshot_id", name="pk_video_snapshot"),
        sa.UniqueConstraint(
            "video_id",
            "captured_at",
            "provider",
            "endpoint_type",
            name="uq_video_snapshot_observation",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["video.video_id"],
            name="fk_video_snapshot_video",
        ),
        *_tenant_constraints("video_snapshot"),
    )
    op.create_index("ix_video_snapshot_time", "video_snapshot", ["video_id", "captured_at"])

    op.create_table(
        "comment_snapshot",
        sa.Column("snapshot_id", sa.Text(), nullable=False),
        sa.Column("comment_id", sa.Text(), nullable=False),
        sa.Column("like_count", sa.BigInteger(), nullable=True),
        sa.Column("reply_count", sa.BigInteger(), nullable=True),
        sa.Column("list_rank", sa.Integer(), nullable=True),
        sa.Column("sample_method", sa.String(length=16), nullable=True),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("snapshot_id", name="pk_comment_snapshot"),
        sa.UniqueConstraint(
            "comment_id",
            "captured_at",
            "provider",
            "endpoint_type",
            name="uq_comment_snapshot_observation",
        ),
        sa.ForeignKeyConstraint(
            ["comment_id"],
            ["comment.comment_id"],
            name="fk_comment_snapshot_comment",
        ),
        *_tenant_constraints("comment_snapshot"),
    )
    op.create_index(
        "ix_comment_snapshot_time",
        "comment_snapshot",
        ["comment_id", "captured_at"],
    )

    op.create_table(
        "hashtag_snapshot",
        sa.Column("snapshot_id", sa.Text(), nullable=False),
        sa.Column("hashtag_id", sa.Text(), nullable=False),
        sa.Column("hashtag_name_raw", sa.Text(), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("period_days", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("post_count", sa.BigInteger(), nullable=True),
        sa.Column("view_count", sa.BigInteger(), nullable=True),
        sa.Column("trend_state", sa.String(length=16), nullable=True),
        sa.Column("industry", sa.Text(), nullable=True),
        sa.Column("rank_change", sa.Integer(), nullable=True),
        sa.Column("post_delta", sa.BigInteger(), nullable=True),
        sa.Column("view_delta", sa.BigInteger(), nullable=True),
        sa.Column("popularity_curve", _jsonb(), nullable=True),
        sa.Column("top_creator_ids", _jsonb(), nullable=True),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("snapshot_id", name="pk_hashtag_snapshot"),
        sa.UniqueConstraint(
            "hashtag_id",
            "captured_at",
            "provider",
            "endpoint_type",
            "country_code",
            "period_days",
            name="uq_hashtag_snapshot_observation",
        ),
        sa.ForeignKeyConstraint(
            ["hashtag_id"],
            ["hashtag.hashtag_id"],
            name="fk_hashtag_snapshot_hashtag",
        ),
        *_tenant_constraints("hashtag_snapshot"),
    )
    op.create_index(
        "ix_hashtag_snapshot_rank",
        "hashtag_snapshot",
        ["country_code", "period_days", "rank"],
    )
    op.create_index(
        "ix_hashtag_snapshot_time",
        "hashtag_snapshot",
        ["hashtag_id", "captured_at"],
    )

    op.create_table(
        "product_snapshot",
        sa.Column("snapshot_id", sa.Text(), nullable=False),
        sa.Column("product_key", sa.Text(), nullable=False),
        sa.Column("product_id", sa.Text(), nullable=False),
        sa.Column("region", sa.Text(), nullable=False),
        sa.Column("price_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("original_price_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("min_price_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("max_price_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("avg_price_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("discount_rate", sa.Numeric(6, 5), nullable=True),
        sa.Column("sale_count", sa.BigInteger(), nullable=True),
        sa.Column("sale_count_30d", sa.BigInteger(), nullable=True),
        sa.Column("sale_delta_7d", sa.BigInteger(), nullable=True),
        sa.Column("gmv_amount_30d", sa.Numeric(18, 4), nullable=True),
        sa.Column("commission_rate", sa.Numeric(6, 5), nullable=True),
        sa.Column("stock_count", sa.BigInteger(), nullable=True),
        sa.Column("review_count", sa.BigInteger(), nullable=True),
        sa.Column("rating", sa.Numeric(3, 2), nullable=True),
        sa.Column("video_count_30d", sa.BigInteger(), nullable=True),
        sa.Column("live_count_30d", sa.BigInteger(), nullable=True),
        sa.Column("ifl_count_30d", sa.BigInteger(), nullable=True),
        sa.Column("is_hot", sa.Boolean(), nullable=True),
        sa.Column("free_shipping", sa.Boolean(), nullable=True),
        sa.Column("shipping_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("is_estimated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("snapshot_id", name="pk_product_snapshot"),
        sa.UniqueConstraint(
            "product_key",
            "captured_at",
            "provider",
            "endpoint_type",
            name="uq_product_snapshot_observation",
        ),
        sa.ForeignKeyConstraint(
            ["product_key"],
            ["product.product_key"],
            name="fk_product_snapshot_product",
        ),
        *_tenant_constraints("product_snapshot"),
    )
    op.create_index(
        "ix_product_snapshot_time",
        "product_snapshot",
        ["product_key", "captured_at"],
    )
    op.create_index(
        "ix_product_snapshot_sales",
        "product_snapshot",
        ["region", "sale_count_30d"],
    )
    op.create_index(
        "ix_product_snapshot_gmv",
        "product_snapshot",
        ["region", "gmv_amount_30d"],
    )

    op.create_table(
        "product_review",
        sa.Column("review_id", sa.Text(), nullable=False),
        sa.Column("product_key", sa.Text(), nullable=False),
        sa.Column("product_id", sa.Text(), nullable=True),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("shop_id", sa.Text(), nullable=True),
        sa.Column("sku_id", sa.Text(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("text_language", sa.Text(), nullable=True),
        sa.Column("review_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_purchase", sa.Boolean(), nullable=True),
        sa.Column("incentivized", sa.Boolean(), nullable=True),
        sa.Column("helpful_count", sa.BigInteger(), nullable=True),
        sa.Column("images", _jsonb(), nullable=True),
        sa.Column("variant", sa.Text(), nullable=True),
        sa.Column("sku_specification", sa.Text(), nullable=True),
        sa.Column("reviewer_name_masked", sa.Text(), nullable=True),
        sa.Column("reviewer_avatar_url", sa.Text(), nullable=True),
        sa.Column("review_country", sa.Text(), nullable=True),
        *_master_timestamps(),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("review_id", name="pk_product_review"),
        sa.ForeignKeyConstraint(
            ["product_key"],
            ["product.product_key"],
            name="fk_product_review_product",
        ),
        *_tenant_constraints("product_review"),
    )
    op.create_index(
        "ix_product_review_time",
        "product_review",
        ["product_key", "review_time"],
    )
    op.create_index("ix_product_review_rating", "product_review", ["rating"])
    op.create_index(
        "ix_product_review_quality",
        "product_review",
        ["verified_purchase", "incentivized"],
    )

    op.create_table(
        "creator_commerce",
        sa.Column("snapshot_id", sa.Text(), nullable=False),
        sa.Column("creator_id", sa.Text(), nullable=False),
        sa.Column("market", sa.String(length=2), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_days", sa.Integer(), nullable=False),
        sa.Column("gmv_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("units_sold", sa.BigInteger(), nullable=True),
        sa.Column("gpm_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("video_gpm_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("live_gpm_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("avg_commission_rate", sa.Numeric(6, 5), nullable=True),
        sa.Column("brand_collaboration_count", sa.Integer(), nullable=True),
        sa.Column("promoted_product_count", sa.Integer(), nullable=True),
        sa.Column("avg_views", sa.BigInteger(), nullable=True),
        sa.Column("avg_likes", sa.BigInteger(), nullable=True),
        sa.Column("avg_comments", sa.BigInteger(), nullable=True),
        sa.Column("avg_shares", sa.BigInteger(), nullable=True),
        sa.Column("engagement_rate", sa.Numeric(6, 5), nullable=True),
        sa.Column("content_frequency", sa.Numeric(18, 4), nullable=True),
        sa.Column("post_rate", sa.Numeric(18, 4), nullable=True),
        sa.Column("rating", sa.Numeric(3, 2), nullable=True),
        sa.Column("promotion_performance_score", sa.Numeric(18, 4), nullable=True),
        sa.Column("follower_count", sa.BigInteger(), nullable=True),
        sa.Column("top_brands", _jsonb(), nullable=True),
        sa.Column("category_list", _jsonb(), nullable=True),
        sa.Column("audience_json", _jsonb(), nullable=True),
        sa.Column("gmv_distribution_json", _jsonb(), nullable=True),
        sa.Column("is_estimated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("snapshot_id", name="pk_creator_commerce"),
        sa.UniqueConstraint(
            "creator_id",
            "market",
            "captured_at",
            "provider",
            "endpoint_type",
            name="uq_creator_commerce_observation",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["creator.creator_id"],
            name="fk_creator_commerce_creator",
        ),
        *_tenant_constraints("creator_commerce"),
    )
    op.create_index(
        "ix_creator_commerce_time",
        "creator_commerce",
        ["creator_id", "captured_at"],
    )

    op.create_table(
        "video_product",
        sa.Column("snapshot_id", sa.Text(), nullable=False),
        sa.Column("video_id", sa.Text(), nullable=False),
        sa.Column("product_key", sa.Text(), nullable=False),
        sa.Column("product_id", sa.Text(), nullable=True),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("relation_type", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Numeric(6, 5), nullable=True),
        sa.Column("match_method", sa.String(length=32), nullable=True),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("snapshot_id", name="pk_video_product"),
        sa.UniqueConstraint(
            "video_id",
            "product_key",
            "relation_type",
            "captured_at",
            "provider",
            "endpoint_type",
            name="uq_video_product_observation",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["video.video_id"],
            name="fk_video_product_video",
        ),
        sa.ForeignKeyConstraint(
            ["product_key"],
            ["product.product_key"],
            name="fk_video_product_product",
        ),
        *_tenant_constraints("video_product"),
    )
    op.create_index("ix_video_product_product", "video_product", ["product_key"])
    op.create_index("ix_video_product_video", "video_product", ["video_id"])

    op.create_table(
        "creator_product",
        sa.Column("snapshot_id", sa.Text(), nullable=False),
        sa.Column("creator_id", sa.Text(), nullable=False),
        sa.Column("product_key", sa.Text(), nullable=False),
        sa.Column("product_id", sa.Text(), nullable=True),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("relation_type", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Numeric(6, 5), nullable=True),
        sa.Column("match_method", sa.String(length=32), nullable=True),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("snapshot_id", name="pk_creator_product"),
        sa.UniqueConstraint(
            "creator_id",
            "product_key",
            "relation_type",
            "captured_at",
            "provider",
            "endpoint_type",
            name="uq_creator_product_observation",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["creator.creator_id"],
            name="fk_creator_product_creator",
        ),
        sa.ForeignKeyConstraint(
            ["product_key"],
            ["product.product_key"],
            name="fk_creator_product_product",
        ),
        *_tenant_constraints("creator_product"),
    )
    op.create_index("ix_creator_product_creator", "creator_product", ["creator_id"])
    op.create_index("ix_creator_product_product", "creator_product", ["product_key"])

    op.create_table(
        "ad",
        sa.Column("ad_id", sa.Text(), nullable=False),
        sa.Column("ad_id_type", sa.String(length=32), nullable=False),
        sa.Column("advertiser_id", sa.Text(), nullable=True),
        sa.Column("advertiser_tt_user_id", sa.Text(), nullable=True),
        sa.Column("advertiser_name", sa.Text(), nullable=True),
        sa.Column("ad_title", sa.Text(), nullable=True),
        sa.Column("ad_text", sa.Text(), nullable=True),
        sa.Column("ad_type", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("audit_status", sa.Text(), nullable=True),
        sa.Column("rejection_info", sa.Text(), nullable=True),
        sa.Column("landing_url", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("target_regions_json", _jsonb(), nullable=True),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("industry", sa.Text(), nullable=True),
        sa.Column("brand_name", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        *_master_timestamps(),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("ad_id", name="pk_ad"),
        *_tenant_constraints("ad"),
    )

    op.create_table(
        "ad_creative",
        sa.Column("creative_id", sa.Text(), nullable=False),
        sa.Column("ad_id", sa.Text(), nullable=False),
        sa.Column("asset_hash", sa.Text(), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("video_url", sa.Text(), nullable=True),
        sa.Column("cover_url", sa.Text(), nullable=True),
        sa.Column("image_urls", _jsonb(), nullable=True),
        sa.Column("headline", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("cta_text", sa.Text(), nullable=True),
        sa.Column("landing_url", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("organic_video_id", sa.Text(), nullable=True),
        sa.Column("transcript_id", sa.Text(), nullable=True),
        sa.Column("performance_score", sa.Numeric(18, 4), nullable=True),
        sa.Column("ctr", sa.Numeric(6, 5), nullable=True),
        sa.Column("likes", sa.BigInteger(), nullable=True),
        sa.Column("comments", sa.BigInteger(), nullable=True),
        sa.Column("shares", sa.BigInteger(), nullable=True),
        sa.Column("cost_score", sa.Numeric(18, 4), nullable=True),
        sa.Column("is_spark_ad", sa.Boolean(), nullable=True),
        sa.Column("impressions_range_json", _jsonb(), nullable=True),
        sa.Column("spend_tier", sa.Text(), nullable=True),
        sa.Column("period_days", sa.Integer(), nullable=True),
        *_tenant_columns(),
        *_governance_columns(),
        sa.PrimaryKeyConstraint("creative_id", name="pk_ad_creative"),
        sa.UniqueConstraint(
            "ad_id",
            "format",
            "asset_hash",
            name="uq_ad_creative_asset",
        ),
        sa.ForeignKeyConstraint(
            ["ad_id"],
            ["ad.ad_id"],
            name="fk_ad_creative_ad",
        ),
        *_tenant_constraints("ad_creative"),
    )


def downgrade() -> None:
    for table in (
        "ad_creative",
        "ad",
        "creator_product",
        "video_product",
        "creator_commerce",
        "product_review",
        "product_snapshot",
        "hashtag_snapshot",
        "comment_snapshot",
        "video_snapshot",
        "creator_snapshot",
        "trend_topic",
        "video_hashtag",
        "transcript",
        "comment",
        "video",
        "product",
        "shop",
        "sound",
        "hashtag",
        "creator",
    ):
        op.drop_table(table)
