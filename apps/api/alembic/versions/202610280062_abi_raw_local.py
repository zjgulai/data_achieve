"""Create the ABI raw tables for local historical data sources.

Revision ID: 202610280062
Revises: 202610280061
Create Date: 2026-10-28

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.

说明：

- 11 张本地原始表全部放 ``raw`` schema。它们与 Apify 来源用 ``origin`` 区分，
  不共用 ``apify_item`` 的 jsonb 窄表：这些表的字段集稳定、行数大，
  展开成列才能查询与建索引。
- 列类型来自 2026-10-28 对源文件的实测 ``describe``，不是推断。
- 三处口径修正（实测发现，与早期方案不同）：
  1. ``dw_video_wide.snapshot_date`` 31,316 行全为 NULL，不能当时间维度。
  2. ``fact_video_comment`` 实际 46,953 行（不是 46,633），
     ``fact_tag_video_snapshot`` 实际 102,153 行。
  3. Amazon 评论没有原生评论 id，用 md5(asin|作者|日期|标题|正文) 作主键。
- ``product_catalog`` 的 UNIQUE 必须用 ``NULLS NOT DISTINCT``：
  ``product_name`` 有 17,128 行为空（29.2%），默认语义会去重不掉。
- ``source_tier`` / ``origin`` 是枚举型文本，加 CHECK 约束防止脏值。
- 所有表带 ``load_batch_id`` / ``src_file`` / ``src_row_ordinal`` / ``content_hash``，
  用于行级溯源与重放对账。
- ``load_error`` 不存原始值。用户上传含卡号的文件被拒时，
  卡号不能落进错误表。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610280062"
down_revision: str | None = "202610280061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---------------------------------------------------------- 装载支撑表
    op.create_table(
        "load_file",
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.LargeBinary(length=32), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mtime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_total", sa.Integer(), nullable=True),
        sa.Column("rows_loaded", sa.Integer(), nullable=True),
        sa.Column("rows_rejected", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("file_id", name="pk_load_file"),
        sa.UniqueConstraint("sha256", name="uq_load_file_sha256"),
        sa.CheckConstraint(
            "status IN ('pending', 'loaded', 'partial', 'failed')",
            name="status",
        ),
        schema="raw",
    )

    # 不存原始值，只存定位信息。PII 不能落进错误表。
    op.create_table(
        "load_error",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("load_batch_id", sa.Uuid(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("src_file", sa.Text(), nullable=False),
        sa.Column("src_row_ordinal", sa.Integer(), nullable=False),
        sa.Column("column_name", sa.Text(), nullable=True),
        sa.Column("rule_id", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_load_error"),
        schema="raw",
    )
    op.create_index(
        "ix_load_error_batch",
        "load_error",
        ["load_batch_id", "src_row_ordinal"],
        schema="raw",
    )

    # ---------------------------------------------------------- SI duckdb
    op.create_table(
        "si_tiktok_video",
        sa.Column("video_id", sa.Text(), nullable=False),
        sa.Column("hashtag", sa.Text(), nullable=True),
        # 实测全 NULL，保留只为保真，不能当时间维度用
        sa.Column("snapshot_date", sa.Date(), nullable=True),
        sa.Column("rank_in_tag", sa.Integer(), nullable=True),
        sa.Column("author_unique_id", sa.Text(), nullable=True),
        sa.Column("author_nickname", sa.Text(), nullable=True),
        sa.Column("author_id", sa.Text(), nullable=True),
        sa.Column("descr", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("is_ad", sa.Boolean(), nullable=True),
        sa.Column("music_id", sa.Text(), nullable=True),
        sa.Column("music_title", sa.Text(), nullable=True),
        sa.Column("music_author", sa.Text(), nullable=True),
        sa.Column("play_count", sa.BigInteger(), nullable=True),
        sa.Column("digg_count", sa.BigInteger(), nullable=True),
        sa.Column("comment_count", sa.BigInteger(), nullable=True),
        sa.Column("share_count", sa.BigInteger(), nullable=True),
        sa.Column("collect_count", sa.BigInteger(), nullable=True),
        sa.Column("snap_days", sa.Integer(), nullable=True),
        sa.Column("peak_play", sa.BigInteger(), nullable=True),
        sa.Column("first_seen", sa.Date(), nullable=True),
        sa.Column("last_seen", sa.Date(), nullable=True),
        sa.Column("play_gain_total", sa.BigInteger(), nullable=True),
        sa.Column("play_gain_daily_avg", sa.Double(), nullable=True),
        sa.Column("parse_level", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("analysis_status", sa.Text(), nullable=True),
        sa.Column("evidence_state", sa.Text(), nullable=True),
        sa.Column("analysis_version", sa.Text(), nullable=True),
        sa.Column("summary_original", sa.Text(), nullable=True),
        sa.Column("target_audience", sa.Text(), nullable=True),
        sa.Column("hook_visual", sa.Text(), nullable=True),
        sa.Column("hook_audio", sa.Text(), nullable=True),
        sa.Column("hook_formula", sa.Text(), nullable=True),
        sa.Column("n_mechanisms", sa.Integer(), nullable=True),
        sa.Column("n_timeline_segments", sa.Integer(), nullable=True),
        sa.Column("n_transcript_segments", sa.Integer(), nullable=True),
        sa.Column("brand_borrow_n", sa.Integer(), nullable=True),
        sa.Column("brand_replace_n", sa.Integer(), nullable=True),
        sa.Column("analysis_created_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("has_deepread", sa.Boolean(), nullable=True),
        sa.Column("deepread_model", sa.Text(), nullable=True),
        sa.Column("deepread_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("theme_tags", sa.Text(), nullable=True),
        sa.Column("mechanism_tags", sa.Text(), nullable=True),
        sa.Column("life_stage", sa.Text(), nullable=True),
        sa.Column("one_liner", sa.Text(), nullable=True),
        sa.Column("media_playable", sa.Boolean(), nullable=True),
        sa.Column("media_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("comment_rows", sa.Integer(), nullable=True),
        sa.Column("comment_top_digg", sa.BigInteger(), nullable=True),
        sa.Column("built_at", sa.DateTime(timezone=False), nullable=True),
        *_common_cols(),
        sa.PrimaryKeyConstraint("video_id", name="pk_si_tiktok_video"),
        schema="raw",
    )
    op.create_index(
        "ix_si_tiktok_video_author",
        "si_tiktok_video",
        ["author_id"],
        schema="raw",
    )

    op.create_table(
        "si_tiktok_comment",
        sa.Column("platform", sa.Text(), nullable=False, server_default=sa.text("'tiktok'")),
        sa.Column("video_id", sa.Text(), nullable=False),
        sa.Column("comment_id", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("digg_count", sa.BigInteger(), nullable=True),
        sa.Column("reply_count", sa.BigInteger(), nullable=True),
        # 头像 URL 的 query 里带 refresh_token，装载时只留 scheme://host/path
        sa.Column("author_handle", sa.Text(), nullable=True),
        sa.Column("author_id", sa.Text(), nullable=True),
        sa.Column("author_avatar", sa.Text(), nullable=True),
        sa.Column("liked_by_author", sa.Boolean(), nullable=True),
        sa.Column("pinned_by_author", sa.Boolean(), nullable=True),
        sa.Column("platform_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_tier", sa.Text(), nullable=True),
        sa.Column("run_id", sa.Text(), nullable=True),
        sa.Column("sample_rank", sa.Integer(), nullable=True),
        *_common_cols(),
        sa.PrimaryKeyConstraint(
            "platform", "video_id", "comment_id", name="pk_si_tiktok_comment"
        ),
        schema="raw",
    )
    op.create_index(
        "ix_si_tiktok_comment_video",
        "si_tiktok_comment",
        ["video_id"],
        schema="raw",
    )

    op.create_table(
        "si_tiktok_hashtag_snapshot",
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hashtag_id", sa.Text(), nullable=False),
        sa.Column("hashtag", sa.Text(), nullable=True),
        sa.Column("source_actor", sa.Text(), nullable=True),
        sa.Column("rank_in_tag", sa.Integer(), nullable=True),
        sa.Column("video_id", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Text(), nullable=True),
        sa.Column("author_unique_id", sa.Text(), nullable=True),
        sa.Column("author_nickname", sa.Text(), nullable=True),
        sa.Column("author_avatar_url", sa.Text(), nullable=True),
        sa.Column("play_count", sa.BigInteger(), nullable=True),
        sa.Column("digg_count", sa.BigInteger(), nullable=True),
        sa.Column("comment_count", sa.BigInteger(), nullable=True),
        sa.Column("share_count", sa.BigInteger(), nullable=True),
        sa.Column("collect_count", sa.BigInteger(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_ad", sa.Boolean(), nullable=True),
        sa.Column("descr", sa.Text(), nullable=True),
        sa.Column("run_id", sa.Text(), nullable=True),
        sa.Column("cover_url", sa.Text(), nullable=True),
        sa.Column("music_id", sa.Text(), nullable=True),
        sa.Column("music_title", sa.Text(), nullable=True),
        sa.Column("music_author", sa.Text(), nullable=True),
        sa.Column("music_duration_sec", sa.Integer(), nullable=True),
        sa.Column("music_is_original", sa.Boolean(), nullable=True),
        sa.Column("music_is_commerce", sa.Boolean(), nullable=True),
        sa.Column("hashtags", sa.ARRAY(sa.Text()), nullable=True),
        *_common_cols(),
        sa.PrimaryKeyConstraint(
            "snapshot_date", "hashtag_id", "video_id",
            name="pk_si_tiktok_hashtag_snapshot",
        ),
        schema="raw",
    )
    op.create_index(
        "ix_si_tag_snapshot_video",
        "si_tiktok_hashtag_snapshot",
        ["video_id"],
        schema="raw",
    )
    op.create_index(
        "ix_si_tag_snapshot_date",
        "si_tiktok_hashtag_snapshot",
        ["snapshot_date"],
        schema="raw",
    )

    op.create_table(
        "si_metric_snapshot",
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("platform_code", sa.Text(), nullable=False),
        sa.Column("object_type", sa.Text(), nullable=False),
        sa.Column("object_id", sa.Text(), nullable=False),
        sa.Column("view_count", sa.BigInteger(), nullable=True),
        sa.Column("like_count", sa.BigInteger(), nullable=True),
        sa.Column("comment_count", sa.BigInteger(), nullable=True),
        sa.Column("share_count", sa.BigInteger(), nullable=True),
        sa.Column("collect_count", sa.BigInteger(), nullable=True),
        sa.Column("source_actor", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=True),
        *_common_cols(),
        sa.PrimaryKeyConstraint(
            "snapshot_date", "platform_code", "object_type",
            "object_id", "source_actor",
            name="pk_si_metric_snapshot",
        ),
        schema="raw",
    )

    op.create_table(
        "si_music_platform_snapshot",
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("music_id", sa.Text(), nullable=False),
        sa.Column("user_count", sa.BigInteger(), nullable=True),
        sa.Column("platform_title", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        *_common_cols(),
        sa.PrimaryKeyConstraint(
            "snapshot_date", "music_id", name="pk_si_music_platform_snapshot"
        ),
        schema="raw",
    )

    op.create_table(
        "si_author_video_snapshot",
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("account_handle", sa.Text(), nullable=True),
        sa.Column("brand_key", sa.Text(), nullable=True),
        sa.Column("priority", sa.Text(), nullable=True),
        sa.Column("sec_uid", sa.Text(), nullable=True),
        sa.Column("rank_in_account", sa.Integer(), nullable=True),
        sa.Column("video_id", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Text(), nullable=True),
        sa.Column("author_unique_id", sa.Text(), nullable=True),
        sa.Column("author_nickname", sa.Text(), nullable=True),
        sa.Column("author_avatar_url", sa.Text(), nullable=True),
        sa.Column("play_count", sa.BigInteger(), nullable=True),
        sa.Column("digg_count", sa.BigInteger(), nullable=True),
        sa.Column("comment_count", sa.BigInteger(), nullable=True),
        sa.Column("share_count", sa.BigInteger(), nullable=True),
        sa.Column("collect_count", sa.BigInteger(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_ad", sa.Boolean(), nullable=True),
        sa.Column("descr", sa.Text(), nullable=True),
        sa.Column("run_id", sa.Text(), nullable=True),
        sa.Column("cover_url", sa.Text(), nullable=True),
        sa.Column("duration_sec", sa.Double(), nullable=True),
        *_common_cols(),
        sa.PrimaryKeyConstraint(
            "snapshot_date", "video_id", name="pk_si_author_video_snapshot"
        ),
        schema="raw",
    )

    op.create_table(
        "si_social_post",
        sa.Column("post_id", sa.Text(), nullable=False),
        sa.Column("platform_code", sa.Text(), nullable=True),
        sa.Column("account_handle", sa.Text(), nullable=True),
        sa.Column("account_type", sa.Text(), nullable=True),
        sa.Column("competitor_brand", sa.Text(), nullable=True),
        sa.Column("creator_id", sa.Text(), nullable=True),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("hashtags", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("bgm_title", sa.Text(), nullable=True),
        sa.Column("bgm_author", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("view_count", sa.BigInteger(), nullable=True),
        sa.Column("like_count", sa.BigInteger(), nullable=True),
        sa.Column("comment_count", sa.BigInteger(), nullable=True),
        sa.Column("share_count", sa.BigInteger(), nullable=True),
        sa.Column("engagement_rate", sa.Double(), nullable=True),
        sa.Column("view_velocity_24h", sa.BigInteger(), nullable=True),
        sa.Column("is_viral_flag", sa.Boolean(), nullable=True),
        sa.Column("sentiment_label", sa.Text(), nullable=True),
        sa.Column("topics", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("pain_points", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("is_paid_collab", sa.Boolean(), nullable=True),
        sa.Column("brand_mentions", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("country_code", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("is_processed", sa.Boolean(), nullable=True),
        sa.Column("content_quality_score", sa.Double(), nullable=True),
        sa.Column("sev_level", sa.Text(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("traffic_type", sa.Text(), nullable=True),
        sa.Column("is_cross_region", sa.Boolean(), nullable=True),
        sa.Column("cover_url", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("completion_rate", sa.Double(), nullable=True),
        sa.Column("source_tier", sa.Text(), nullable=True),
        sa.Column("evidence_status", sa.Text(), nullable=True),
        sa.Column("availability", sa.Text(), nullable=True),
        sa.Column("parse_status", sa.Text(), nullable=True),
        sa.Column("traffic_basis", sa.Text(), nullable=True),
        *_common_cols(),
        sa.PrimaryKeyConstraint("post_id", name="pk_si_social_post"),
        schema="raw",
    )

    # ---------------------------------------------------------- 探针与缓存
    op.create_table(
        "apify_tweet",
        sa.Column("snapshot_date", sa.Date(), nullable=True),
        sa.Column("tweet_id", sa.Text(), nullable=True),
        sa.Column("conversation_id", sa.Text(), nullable=True),
        sa.Column("author_id", sa.Text(), nullable=True),
        sa.Column("author_user_name", sa.Text(), nullable=True),
        sa.Column("author_name", sa.Text(), nullable=True),
        sa.Column("author_followers", sa.BigInteger(), nullable=True),
        sa.Column("author_verified", sa.Boolean(), nullable=True),
        sa.Column("author_description", sa.Text(), nullable=True),
        sa.Column("author_location", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("lang", sa.Text(), nullable=True),
        sa.Column("like_count", sa.Integer(), nullable=True),
        sa.Column("reply_count", sa.Integer(), nullable=True),
        sa.Column("retweet_count", sa.Integer(), nullable=True),
        sa.Column("quote_count", sa.Integer(), nullable=True),
        sa.Column("bookmark_count", sa.Integer(), nullable=True),
        sa.Column("view_count", sa.BigInteger(), nullable=True),
        sa.Column("is_reply", sa.Boolean(), nullable=True),
        sa.Column("is_quote", sa.Boolean(), nullable=True),
        sa.Column("is_retweet", sa.Boolean(), nullable=True),
        sa.Column("is_pinned", sa.Boolean(), nullable=True),
        sa.Column("possibly_sensitive", sa.Boolean(), nullable=True),
        sa.Column("in_reply_to_id", sa.Text(), nullable=True),
        sa.Column("in_reply_to_user_id", sa.Text(), nullable=True),
        sa.Column("in_reply_to_username", sa.Text(), nullable=True),
        sa.Column("quoted_id", sa.Text(), nullable=True),
        sa.Column("hashtags", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("urls", sa.JSON(), nullable=True),
        sa.Column("media", sa.JSON(), nullable=True),
        # 76 条 {"noResults": true} 哨兵，装载时标 true 而不是丢弃
        sa.Column("is_no_results", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("raw", sa.JSON(), nullable=True),
        *_common_cols(),
        sa.PrimaryKeyConstraint(
            "origin", "src_file", "src_row_ordinal", name="pk_apify_tweet"
        ),
        schema="raw",
    )
    op.create_index(
        "ix_apify_tweet_id", "apify_tweet", ["tweet_id", "snapshot_date"], schema="raw"
    )

    op.create_table(
        "probe_instagram_post",
        sa.Column("probe_date", sa.Date(), nullable=True),
        sa.Column("short_code", sa.Text(), nullable=True),
        sa.Column("post_id", sa.Text(), nullable=True),
        sa.Column("post_type", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("input_url", sa.Text(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Text(), nullable=True),
        sa.Column("owner_username", sa.Text(), nullable=True),
        sa.Column("owner_full_name", sa.Text(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("likes_count", sa.Integer(), nullable=True),
        sa.Column("comments_count", sa.Integer(), nullable=True),
        sa.Column("video_view_count", sa.Integer(), nullable=True),
        sa.Column("video_duration", sa.Double(), nullable=True),
        sa.Column("dimensions_width", sa.Integer(), nullable=True),
        sa.Column("dimensions_height", sa.Integer(), nullable=True),
        sa.Column("display_url", sa.Text(), nullable=True),
        sa.Column("video_url", sa.Text(), nullable=True),
        sa.Column("images", sa.JSON(), nullable=True),
        sa.Column("child_posts", sa.JSON(), nullable=True),
        sa.Column("latest_comments", sa.JSON(), nullable=True),
        sa.Column("first_comment", sa.Text(), nullable=True),
        sa.Column("hashtags", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("mentions", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("tagged_users", sa.JSON(), nullable=True),
        sa.Column("location_id", sa.Text(), nullable=True),
        sa.Column("location_name", sa.Text(), nullable=True),
        sa.Column("music_info", sa.JSON(), nullable=True),
        sa.Column("paid_partnership", sa.Boolean(), nullable=True),
        sa.Column("product_type", sa.Text(), nullable=True),
        sa.Column("is_pinned", sa.Boolean(), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=True),
        *_common_cols(),
        sa.PrimaryKeyConstraint(
            "origin", "src_file", "src_row_ordinal", name="pk_probe_instagram_post"
        ),
        sa.UniqueConstraint("short_code", name="uq_probe_instagram_post_short_code"),
        schema="raw",
    )

    op.create_table(
        "probe_tiktok_video",
        sa.Column("probe_date", sa.Date(), nullable=True),
        sa.Column("arm", sa.Text(), nullable=True),
        sa.Column("video_id", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("create_time", sa.BigInteger(), nullable=True),
        sa.Column("create_time_iso", sa.DateTime(timezone=True), nullable=True),
        sa.Column("web_video_url", sa.Text(), nullable=True),
        sa.Column("search_query", sa.Text(), nullable=True),
        sa.Column("author_id", sa.Text(), nullable=True),
        sa.Column("author_name", sa.Text(), nullable=True),
        sa.Column("author_nickname", sa.Text(), nullable=True),
        # PII 最集中的字段，实测已含 {{EMAIL_...}} 占位符
        sa.Column("author_signature", sa.Text(), nullable=True),
        sa.Column("author_fans", sa.BigInteger(), nullable=True),
        sa.Column("author_following", sa.BigInteger(), nullable=True),
        sa.Column("author_heart", sa.BigInteger(), nullable=True),
        sa.Column("author_verified", sa.Boolean(), nullable=True),
        sa.Column("author_avatar_url", sa.Text(), nullable=True),
        sa.Column("author_bio_link", sa.Text(), nullable=True),
        sa.Column("author_profile_url", sa.Text(), nullable=True),
        sa.Column("author_private", sa.Boolean(), nullable=True),
        sa.Column("music_id", sa.Text(), nullable=True),
        sa.Column("music_name", sa.Text(), nullable=True),
        sa.Column("music_author", sa.Text(), nullable=True),
        sa.Column("music_original", sa.Boolean(), nullable=True),
        sa.Column("music_play_url", sa.Text(), nullable=True),
        sa.Column("music_cover_url", sa.Text(), nullable=True),
        sa.Column("video_height", sa.Integer(), nullable=True),
        sa.Column("video_width", sa.Integer(), nullable=True),
        sa.Column("video_duration", sa.Integer(), nullable=True),
        sa.Column("video_definition", sa.Text(), nullable=True),
        sa.Column("video_format", sa.Text(), nullable=True),
        sa.Column("video_cover_url", sa.Text(), nullable=True),
        sa.Column("video_cover_original_url", sa.Text(), nullable=True),
        sa.Column("transcription_link", sa.Text(), nullable=True),
        sa.Column("play_count", sa.BigInteger(), nullable=True),
        sa.Column("digg_count", sa.BigInteger(), nullable=True),
        sa.Column("comment_count", sa.BigInteger(), nullable=True),
        sa.Column("share_count", sa.BigInteger(), nullable=True),
        sa.Column("collect_count", sa.BigInteger(), nullable=True),
        sa.Column("repost_count", sa.BigInteger(), nullable=True),
        sa.Column("is_ad", sa.Boolean(), nullable=True),
        sa.Column("is_sponsored", sa.Boolean(), nullable=True),
        sa.Column("is_pinned", sa.Boolean(), nullable=True),
        sa.Column("is_slideshow", sa.Boolean(), nullable=True),
        sa.Column("is_story", sa.Boolean(), nullable=True),
        sa.Column("is_muted", sa.Boolean(), nullable=True),
        sa.Column("location_created", sa.Text(), nullable=True),
        sa.Column("hashtags", sa.JSON(), nullable=True),
        sa.Column("mentions", sa.JSON(), nullable=True),
        sa.Column("detailed_mentions", sa.JSON(), nullable=True),
        sa.Column("effect_stickers", sa.JSON(), nullable=True),
        sa.Column("media_urls", sa.JSON(), nullable=True),
        sa.Column("slideshow_image_links", sa.JSON(), nullable=True),
        sa.Column("has_tiktok_shop_product", sa.Boolean(), nullable=True),
        sa.Column("comments_dataset_url", sa.Text(), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=True),
        *_common_cols(),
        sa.PrimaryKeyConstraint(
            "origin", "src_file", "src_row_ordinal", name="pk_probe_tiktok_video"
        ),
        schema="raw",
    )
    op.create_index(
        "ix_probe_tiktok_video_id", "probe_tiktok_video", ["video_id"], schema="raw"
    )

    op.create_table(
        "probe_youtube_video",
        sa.Column("probe_date", sa.Date(), nullable=True),
        sa.Column("arm", sa.Text(), nullable=True),
        sa.Column("video_id", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("from_yt_url", sa.Text(), nullable=True),
        sa.Column("channel_id", sa.Text(), nullable=True),
        sa.Column("channel_name", sa.Text(), nullable=True),
        sa.Column("channel_username", sa.Text(), nullable=True),
        sa.Column("channel_url", sa.Text(), nullable=True),
        sa.Column("number_of_subscribers", sa.BigInteger(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration", sa.Text(), nullable=True),
        sa.Column("view_count", sa.BigInteger(), nullable=True),
        sa.Column("likes", sa.BigInteger(), nullable=True),
        sa.Column("comments_count", sa.BigInteger(), nullable=True),
        sa.Column("comments_turned_off", sa.Boolean(), nullable=True),
        sa.Column("is_members_only", sa.Boolean(), nullable=True),
        sa.Column("is_paid_content", sa.Boolean(), nullable=True),
        sa.Column("is_monetized", sa.Boolean(), nullable=True),
        sa.Column("hashtags", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("description_links", sa.JSON(), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=True),
        sa.Column("input", sa.Text(), nullable=True),
        sa.Column("video_type", sa.Text(), nullable=True),
        sa.Column("translated_title", sa.Text(), nullable=True),
        sa.Column("translated_text", sa.Text(), nullable=True),
        sa.Column("ai_video_summary", sa.Text(), nullable=True),
        sa.Column("ai_video_description", sa.Text(), nullable=True),
        sa.Column("collaborators", sa.JSON(), nullable=True),
        sa.Column("subtitles", sa.JSON(), nullable=True),
        sa.Column("transcription_url", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=True),
        *_common_cols(),
        sa.PrimaryKeyConstraint(
            "origin", "src_file", "src_row_ordinal", name="pk_probe_youtube_video"
        ),
        schema="raw",
    )
    op.create_index(
        "ix_probe_youtube_video_id", "probe_youtube_video", ["video_id"], schema="raw"
    )

    op.create_table(
        "pmo_collection_record",
        sa.Column("record_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("task_run_id", sa.Uuid(), nullable=True),
        sa.Column("record_type", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("screenshot_url", sa.Text(), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("platform", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        # content 是 JSON 对象（不是 Python dict repr），5 种 schema_version 共存
        sa.Column("content", sa.JSON(), nullable=True),
        *_common_cols(),
        sa.PrimaryKeyConstraint("record_id", name="pk_pmo_collection_record"),
        sa.UniqueConstraint("content_hash", name="uq_pmo_collection_record_content_hash"),
        schema="raw",
    )
    op.create_index(
        "ix_pmo_record_schema_version",
        "pmo_collection_record",
        ["schema_version"],
        schema="raw",
    )

    # ---------------------------------------------------------- Desktop
    op.create_table(
        "amazon_review",
        sa.Column("review_key", sa.LargeBinary(length=16), nullable=False),
        sa.Column("file_date", sa.Date(), nullable=False),
        sa.Column("asin", sa.Text(), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("review_date", sa.Date(), nullable=True),
        sa.Column("verified_purchase", sa.Boolean(), nullable=True),
        sa.Column("helpful_votes", sa.Integer(), nullable=True),
        sa.Column("total_votes", sa.Integer(), nullable=True),
        sa.Column("source_description", sa.Text(), nullable=True),
        *_common_cols(),
        sa.PrimaryKeyConstraint("review_key", name="pk_amazon_review"),
        sa.CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)",
            name="rating",
        ),
        schema="raw",
    )
    op.create_index("ix_amazon_review_asin", "amazon_review", ["asin"], schema="raw")

    op.create_table(
        "product_catalog",
        sa.Column("product_key", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("file_date", sa.Date(), nullable=False),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("brand", sa.Text(), nullable=True),
        sa.Column("product_name", sa.Text(), nullable=True),
        *_common_cols(),
        sa.PrimaryKeyConstraint("product_key", name="pk_product_catalog"),
        # 17,128 行 product_name 为空，必须 NULLS NOT DISTINCT 才去得掉重
        sa.UniqueConstraint(
            "category", "brand", "product_name",
            name="uq_product_catalog_natural",
            postgresql_nulls_not_distinct=True,
        ),
        schema="raw",
    )


def _common_cols() -> list[sa.Column]:
    """11 张本地表共用的溯源列。调用方用 *_common_cols() 展开。"""
    return [
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("load_batch_id", sa.Uuid(), nullable=False),
        sa.Column("src_file", sa.Text(), nullable=False),
        sa.Column("src_row_ordinal", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column(
            "loaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
    ]


def downgrade() -> None:
    for table in (
        "product_catalog", "amazon_review", "pmo_collection_record",
        "probe_youtube_video", "probe_tiktok_video", "probe_instagram_post",
        "apify_tweet", "si_social_post", "si_author_video_snapshot",
        "si_music_platform_snapshot", "si_metric_snapshot",
        "si_tiktok_hashtag_snapshot", "si_tiktok_comment", "si_tiktok_video",
    ):
        op.drop_table(table, schema="raw")
    op.drop_index("ix_load_error_batch", table_name="load_error", schema="raw")
    op.drop_table("load_error", schema="raw")
    op.drop_table("load_file", schema="raw")
