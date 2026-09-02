"""TikHub REST API collector.

Supports TikTok / Instagram / Xiaohongshu via TikHub's public API.
Requires TIKHUB_API_KEY environment variable.

collector_type = "tikhub_social"
Endpoint is selected via config["endpoint_type"].
"""

from __future__ import annotations

import asyncio
import os
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from data_intelligence_hub.collectors.base import (
    BaseCollector,
    CollectionResult,
    CollectorError,
    CollectorRawRecord,
    CollectorTestResult,
    collector_http_error_message,
    collector_log,
    require_text,
)

TIKHUB_BASE_URL = "https://api.tikhub.io"
TIKHUB_TIMEOUT = 30.0
TIKHUB_MAX_RETRY = 2
TIKHUB_RETRY_BACKOFF: tuple[float, float] = (1.0, 3.0)
TIKHUB_MAX_ITEMS_LIMIT = 100

# endpoint_type → (path, record_type, platform)
TIKHUB_ENDPOINT_MAP: dict[str, tuple[str, str, str]] = {
    "tikhub_tiktok_video_search": (
        "/api/v1/tiktok/app/v3/fetch_video_search_result",
        "tiktok_video",
        "tiktok",
    ),
    "tikhub_tiktok_user_posts": (
        "/api/v1/tiktok/app/v3/fetch_user_post_videos_v2",
        "tiktok_video",
        "tiktok",
    ),
    "tikhub_tiktok_hashtag_posts": (
        "/api/v1/tiktok/app/v3/fetch_hashtag_video_list",
        "tiktok_video",
        "tiktok",
    ),
    "tikhub_instagram_user_posts": (
        "/api/v1/instagram/v1/fetch_user_posts",
        "instagram_post",
        "instagram",
    ),
    "tikhub_instagram_search": (
        "/api/v1/instagram/v2/general_search",
        "instagram_post",
        "instagram",
    ),
    "tikhub_xiaohongshu_search": (
        "/api/v1/xiaohongshu/app_v2/search_notes",
        "xiaohongshu_note",
        "xiaohongshu",
    ),
    "tikhub_youtube_search": (
        "/api/v1/youtube/web_v2/get_general_search",
        "youtube_video",
        "youtube",
    ),
    "tikhub_youtube_channel_videos": (
        "/api/v1/youtube/web_v2/get_channel_videos",
        "youtube_video",
        "youtube",
    ),
    "tikhub_reddit_search": (
        "/api/v1/reddit/app/fetch_dynamic_search",
        "reddit_post",
        "reddit",
    ),
    "tikhub_reddit_subreddit_posts": (
        "/api/v1/reddit/app/fetch_subreddit_feed",
        "reddit_post",
        "reddit",
    ),
    "tikhub_x_search": (
        "/api/v1/twitter/web/fetch_search_timeline",
        "twitter_post",
        "x",
    ),
    "tikhub_x_user_tweets": (
        "/api/v1/twitter/web/fetch_user_post_tweet",
        "twitter_post",
        "x",
    ),

    # ── 抖音 (Douyin) ──────────────────────────────────────────────────────────
    "tikhub_douyin_video_search": (
        "/api/v1/douyin/search/fetch_video_search_v1",
        "douyin_video",
        "douyin",
    ),
    "tikhub_douyin_user_posts": (
        "/api/v1/douyin/app/v3/fetch_user_post_videos",
        "douyin_video",
        "douyin",
    ),
    "tikhub_douyin_hot_search": (
        "/api/v1/douyin/app/v3/fetch_hot_search_list",
        "douyin_trend",
        "douyin",
    ),
    "tikhub_douyin_comments": (
        "/api/v1/douyin/web/fetch_video_comments",
        "douyin_comment",
        "douyin",
    ),
    # ── B站 (Bilibili) ─────────────────────────────────────────────────────────
    "tikhub_bilibili_video_search": (
        "/api/v1/bilibili/web/fetch_general_search",
        "bilibili_video",
        "bilibili",
    ),
    "tikhub_bilibili_user_videos": (
        "/api/v1/bilibili/app/fetch_user_videos",
        "bilibili_video",
        "bilibili",
    ),
    "tikhub_bilibili_comments": (
        "/api/v1/bilibili/app/fetch_video_comments",
        "bilibili_comment",
        "bilibili",
    ),
    # ── 微博 (Weibo) ───────────────────────────────────────────────────────────
    "tikhub_weibo_search": (
        "/api/v1/weibo/app/fetch_search_all",
        "weibo_post",
        "weibo",
    ),
    "tikhub_weibo_user_posts": (
        "/api/v1/weibo/web/fetch_user_posts",
        "weibo_post",
        "weibo",
    ),
    # ── 快手 (Kuaishou) ────────────────────────────────────────────────────────
    "tikhub_kuaishou_search": (
        "/api/v1/kuaishou/app/search_video_v2",
        "kuaishou_video",
        "kuaishou",
    ),
    "tikhub_kuaishou_user_posts": (
        "/api/v1/kuaishou/app/fetch_user_post_v2",
        "kuaishou_video",
        "kuaishou",
    ),
    # ── 微信 (WeChat) ──────────────────────────────────────────────────────────
    "tikhub_wechat_search": (
        "/api/v1/wechat_search/v2/fetch_search",
        "wechat_article",
        "wechat",
    ),
    "tikhub_wechat_channels_video": (
        "/api/v1/wechat_channels/v2/fetch_user_videos",
        "wechat_video",
        "wechat",
    ),
    # ── 知乎 (Zhihu) ───────────────────────────────────────────────────────────
    "tikhub_zhihu_search": (
        "/api/v1/zhihu/web/fetch_salt_search_v3",
        "zhihu_post",
        "zhihu",
    ),
    "tikhub_zhihu_question_answers": (
        "/api/v1/zhihu/web/fetch_question_answers",
        "zhihu_answer",
        "zhihu",
    ),
    # ── 抖音品牌热榜 ─────────────────────────────────────────────────────────
    "tikhub_douyin_brand_hot_search": (
        "/api/v1/douyin/app/v3/fetch_brand_hot_search_list_detail",
        "douyin_trend",
        "douyin",
    ),
    # ── YouTube (alias) ────────────────────────────────────────────────────
    "tikhub_youtube_video_search": (
        "/api/v1/youtube/web_v2/get_general_search",
        "youtube_video",
        "youtube",
    ),
    # ── Threads ────────────────────────────────────────────────────────────
    "tikhub_threads_search": (
        "/api/v1/threads/web/search_top",
        "threads_post",
        "threads",
    ),
    "tikhub_threads_user_posts": (
        "/api/v1/threads/web/fetch_user_posts",
        "threads_post",
        "threads",
    ),
    "tikhub_threads_post_comments": (
        "/api/v1/threads/web/fetch_post_comments",
        "threads_post",
        "threads",
    ),
    # ── LinkedIn ───────────────────────────────────────────────────────────
    "tikhub_linkedin_user_posts": (
        "/api/v1/linkedin/web_v2/get_user_posts",
        "linkedin_post",
        "linkedin",
    ),
    "tikhub_linkedin_company_profile": (
        "/api/v1/linkedin/web_v2/get_company_profile",
        "linkedin_post",
        "linkedin",
    ),
    "tikhub_linkedin_company_posts": (
        "/api/v1/linkedin/web_v2/get_company_posts",
        "linkedin_post",
        "linkedin",
    ),
    "tikhub_linkedin_search_jobs": (
        "/api/v1/linkedin/web_v2/search_jobs",
        "linkedin_job",
        "linkedin",
    ),
    "tikhub_linkedin_job_detail": (
        "/api/v1/linkedin/web_v2/get_job_detail",
        "linkedin_job",
        "linkedin",
    ),
    "tikhub_linkedin_post_comments": (
        "/api/v1/linkedin/web_v2/get_post_comments",
        "linkedin_post",
        "linkedin",
    ),
    # ── Lemon8 ────────────────────────────────────────────────────────────
    "tikhub_lemon8_search": (
        "/api/v1/lemon8/app/fetch_search",
        "lemon8_post",
        "lemon8",
    ),
    "tikhub_lemon8_user_posts": (
        "/api/v1/lemon8/app/fetch_user_profile",
        "lemon8_post",
        "lemon8",
    ),
    "tikhub_lemon8_trending": (
        "/api/v1/lemon8/app/fetch_discover_tab",
        "lemon8_post",
        "lemon8",
    ),
    # ── TikTok Ads ────────────────────────────────────────────────────────
    "tikhub_tiktok_ads_search": (
        "/api/v1/tiktok/ads/get_recommended_ads",
        "tiktok_ad",
        "tiktok",
    ),
    "tikhub_tiktok_top_ads": (
        "/api/v1/tiktok/ads/get_top_ads_spotlight",
        "tiktok_ad",
        "tiktok",
    ),
    "tikhub_tiktok_ads_detail": (
        "/api/v1/tiktok/ads/get_ads_detail",
        "tiktok_ad",
        "tiktok",
    ),
    "tikhub_tiktok_ads_keyword_suggest": (
        "/api/v1/tiktok/ads/get_query_suggestions",
        "tiktok_ad",
        "tiktok",
    ),
    # ── TikTok Shop ───────────────────────────────────────────────────────
    "tikhub_tiktok_shop_products": (
        "/api/v1/tiktok/shop/web/fetch_search_products_list",
        "tiktok_shop_product",
        "tiktok_shop",
    ),
    # ── TikTok Creator ────────────────────────────────────────────────────
    "tikhub_tiktok_creator_info": (
        "/api/v1/tiktok/app/v3/fetch_creator_info",
        "tiktok_video",
        "tiktok",
    ),
    "tikhub_tiktok_creator_insights": (
        "/api/v1/tiktok/app/v3/fetch_creator_search_insights",
        "tiktok_video",
        "tiktok",
    ),
    "tikhub_tiktok_creator_insights_trend": (
        "/api/v1/tiktok/app/v3/fetch_creator_search_insights_trend",
        "tiktok_video",
        "tiktok",
    ),
    "tikhub_tiktok_creator_account_health": (
        "/api/v1/tiktok/creator/get_account_health_status",
        "tiktok_video",
        "tiktok",
    ),
    # ── TikTok Live ───────────────────────────────────────────────────────
    "tikhub_tiktok_live_search": (
        "/api/v1/tiktok/app/v3/fetch_live_search_result",
        "tiktok_video",
        "tiktok",
    ),
    "tikhub_tiktok_live_room_detail": (
        "/api/v1/tiktok/app/v3/fetch_live_room_info",
        "tiktok_video",
        "tiktok",
    ),
    "tikhub_tiktok_live_user": (
        "/api/v1/tiktok/app/v3/fetch_creator_info",
        "tiktok_video",
        "tiktok",
    ),
    # ── TikTok trending / followers ───────────────────────────────────────
    "tikhub_youtube_trending": (
        "/api/v1/youtube/web_v2/get_general_search",
        "youtube_video",
        "youtube",
    ),
    "tikhub_reddit_trending": (
        "/api/v1/reddit/app/fetch_popular_feed",
        "reddit_post",
        "reddit",
    ),
    "tikhub_x_trending": (
        "/api/v1/twitter/web/fetch_trending",
        "twitter_post",
        "x",
    ),
    "tikhub_tiktok_user_followers": (
        "/api/v1/tiktok/app/v3/fetch_user_follower_list",
        "tiktok_video",
        "tiktok",
    ),
    "tikhub_instagram_user_followers": (
        "/api/v1/instagram/v2/fetch_user_followers",
        "instagram_post",
        "instagram",
    ),
    "tikhub_x_user_followers": (
        "/api/v1/twitter/web/fetch_user_followers",
        "twitter_post",
        "x",
    ),
    "tikhub_instagram_post_comments": (
        "/api/v1/instagram/v2/fetch_post_comments",
        "instagram_post",
        "instagram",
    ),
    "tikhub_youtube_video_comments": (
        "/api/v1/youtube/web_v2/get_video_comments",
        "youtube_video",
        "youtube",
    ),
    "tikhub_reddit_post_comments": (
        "/api/v1/reddit/app/fetch_post_comments",
        "reddit_post",
        "reddit",
    ),
}


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _get_api_key() -> str:
    key = os.getenv("TIKHUB_API_KEY", "").strip()
    if not key:
        raise CollectorError("tikhub_api_key_missing: TIKHUB_API_KEY env var not set")
    return key


def _tikhub_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": "DataIntelligenceHub/1.0",
    }


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _is_retryable(exc: httpx.HTTPError) -> bool:
    if isinstance(exc, httpx.TimeoutException | httpx.NetworkError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


async def _tikhub_get(
    client: httpx.AsyncClient,
    path: str,
    params: dict[str, Any],
    api_key: str,
) -> dict[str, Any]:
    url = f"{TIKHUB_BASE_URL}{path}"
    last_exc: Exception | None = None
    for attempt in range(TIKHUB_MAX_RETRY + 1):
        try:
            resp = await client.get(
                url,
                params={k: v for k, v in params.items() if v is not None},
                headers=_tikhub_headers(api_key),
                timeout=TIKHUB_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                raise CollectorError("tikhub_response_invalid: expected JSON object")
            return data
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt < TIKHUB_MAX_RETRY and _is_retryable(exc):
                await asyncio.sleep(TIKHUB_RETRY_BACKOFF[attempt])
                continue
            raise CollectorError(collector_http_error_message(exc)) from exc
    raise CollectorError(f"tikhub_retry_exhausted: {last_exc}")


async def _tikhub_post(
    client: httpx.AsyncClient,
    path: str,
    body: dict[str, Any],
    api_key: str,
) -> dict[str, Any]:
    url = f"{TIKHUB_BASE_URL}{path}"
    last_exc: Exception | None = None
    for attempt in range(TIKHUB_MAX_RETRY + 1):
        try:
            resp = await client.post(
                url,
                json={k: v for k, v in body.items() if v is not None},
                headers=_tikhub_headers(api_key),
                timeout=TIKHUB_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                raise CollectorError("tikhub_response_invalid: expected JSON object")
            return data
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt < TIKHUB_MAX_RETRY and _is_retryable(exc):
                await asyncio.sleep(TIKHUB_RETRY_BACKOFF[attempt])
                continue
            raise CollectorError(collector_http_error_message(exc)) from exc
    raise CollectorError(f"tikhub_retry_exhausted: {last_exc}")


_TIKHUB_POST_ENDPOINTS: frozenset[str] = frozenset({
    "tikhub_tiktok_ads_search",
    "tikhub_tiktok_top_ads",
    "tikhub_tiktok_ads_detail",
    "tikhub_tiktok_ads_keyword_suggest",
    "tikhub_tiktok_creator_account_health",
    "tikhub_wechat_channels_video",
    "tikhub_douyin_video_search",
})


# ---------------------------------------------------------------------------
# Response extraction
# ---------------------------------------------------------------------------


def _extract_items(data: dict[str, Any], platform: str) -> list[dict[str, Any]]:
    inner = data.get("data")

    if platform == "youtube":
        # web_v2/get_general_search → data.contents (nested)
        # web_v2/get_channel_videos → data.videos
        if isinstance(inner, dict):
            videos = inner.get("videos")
            if isinstance(videos, list):
                return videos
            contents = inner.get("contents")
            if isinstance(contents, list):
                return contents
        return []

    if platform == "reddit":
        # fetch_dynamic_search → data.search (list)
        # fetch_subreddit_feed → data (list)
        if isinstance(inner, list):
            return inner
        if isinstance(inner, dict):
            search = inner.get("search")
            if isinstance(search, list):
                return search
            posts = inner.get("posts")
            if isinstance(posts, list):
                return posts
        return []

    if platform == "x":
        # fetch_search_timeline → data.timeline (list)
        # fetch_user_post_tweet → data.timeline or data (list)
        if isinstance(inner, list):
            return inner
        if isinstance(inner, dict):
            timeline = inner.get("timeline")
            if isinstance(timeline, list):
                return timeline
        return []

    if platform == "xiaohongshu":
        if isinstance(inner, dict):
            deeper = inner.get("data")
            if isinstance(deeper, dict):
                candidate = deeper.get("items")
                if isinstance(candidate, list):
                    return candidate
            for key in ("items", "note_list", "result_list"):
                candidate = inner.get(key)
                if isinstance(candidate, list):
                    return candidate
        return []

    if platform == "instagram":
        if isinstance(inner, dict):
            deeper = inner.get("data")
            if isinstance(deeper, list):
                return deeper
            if isinstance(deeper, dict):
                candidate = deeper.get("items")
                if isinstance(candidate, list):
                    return candidate
            for key in ("items", "medias", "results", "users"):
                candidate = inner.get(key)
                if isinstance(candidate, list):
                    return candidate
        if isinstance(inner, list):
            return inner
        return []

    if platform in ("douyin", "bilibili", "weibo", "kuaishou", "wechat", "zhihu"):
        if isinstance(inner, list):
            return inner
        if isinstance(inner, dict):
            for key in (
                "aweme_list", "item_list", "items", "video_list", "data",
                "list", "result_list", "statuses", "cards", "answer_list",
                "search_result", "result", "videos",
            ):
                candidate = inner.get(key)
                if isinstance(candidate, list) and candidate:
                    return candidate
        return []

    if isinstance(inner, list):
        return inner
    if not isinstance(inner, dict):
        return []

    search_items = inner.get("search_item_list")
    if isinstance(search_items, list) and search_items:
        return [item.get("aweme_info") or item for item in search_items if isinstance(item, dict)]

    for key in ("aweme_list", "item_list", "items", "video_list", "note_list", "result_list"):
        candidate = inner.get(key)
        if isinstance(candidate, list):
            return candidate
    return []


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _safe_str(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _safe_ts(value: Any) -> str | None:
    """Unix timestamp or ISO string → ISO 8601 string."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value, tz=UTC).isoformat()
        except (OSError, OverflowError, ValueError):
            return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _extract_hashtags(text: str) -> list[str]:
    return re.findall(r"#(\w+)", text)[:20]


# ---------------------------------------------------------------------------
# Platform-specific normalizers
# ---------------------------------------------------------------------------


def _normalize_tiktok_video(
    item: dict[str, Any], collector_type: str
) -> CollectorRawRecord | None:
    video_id = (
        item.get("aweme_id")
        or item.get("id")
        or (_safe_str((item.get("video") or {}).get("id")))
    )
    if not isinstance(video_id, str) or not video_id.strip():
        return None
    video_id = video_id.strip()

    desc = str(item.get("desc") or item.get("text") or "")
    author: dict[str, Any] = item.get("author") or {}
    stats: dict[str, Any] = item.get("statistics") or item.get("stats") or {}
    video_meta: dict[str, Any] = item.get("video") or {}
    cover_urls: list[Any] = (video_meta.get("cover") or {}).get("url_list") or []
    music: dict[str, Any] = item.get("music") or {}
    challenges: list[Any] = item.get("cha_list") or item.get("challenges") or []

    return CollectorRawRecord(
        record_type="tiktok_video",
        source_url=(
            f"https://www.tiktok.com/@{author.get('unique_id', 'unknown')}/video/{video_id}"
        ),
        content={
            "provider": "tikhub",
            "platform": "tiktok",
            "collector_type": collector_type,
            "schema_version": "tikhub_tiktok_video.v1",
            "video_id": video_id,
            "text": desc[:2000],
            "author_id": _safe_str(author.get("uid") or author.get("id")) or "",
            "author_username": _safe_str(author.get("unique_id")) or "",
            "author_nickname": _safe_str(author.get("nickname")) or "",
            "created_at": _safe_ts(item.get("create_time")),
            "play_count": _safe_int(stats.get("play_count")),
            "like_count": _safe_int(stats.get("digg_count") or stats.get("like_count")),
            "comment_count": _safe_int(stats.get("comment_count")),
            "share_count": _safe_int(stats.get("share_count")),
            "collect_count": _safe_int(stats.get("collect_count")),
            "duration": _safe_int(video_meta.get("duration")),
            "cover_url": _safe_str(cover_urls[0] if cover_urls else None),
            "music_title": _safe_str(music.get("title")),
            "hashtags": [
                str(ch.get("cha_name") or ch.get("title") or "")
                for ch in challenges
                if isinstance(ch, dict)
            ][:20],
            "raw": item,
        },
        collected_at=datetime.now(UTC),
    )


def _normalize_instagram_post(
    item: dict[str, Any], collector_type: str
) -> CollectorRawRecord | None:
    post_id_raw = item.get("id") or item.get("pk") or item.get("shortcode")
    if post_id_raw is None:
        return None
    post_id = str(post_id_raw).strip()
    if not post_id:
        return None

    shortcode = _safe_str(item.get("shortcode") or item.get("code")) or post_id
    caption_raw = item.get("caption")
    caption = (
        caption_raw.get("text")
        if isinstance(caption_raw, dict)
        else str(caption_raw or "")
    )
    user: dict[str, Any] = item.get("user") or item.get("owner") or {}

    return CollectorRawRecord(
        record_type="instagram_post",
        source_url=f"https://www.instagram.com/p/{shortcode}/",
        content={
            "provider": "tikhub",
            "platform": "instagram",
            "collector_type": collector_type,
            "schema_version": "tikhub_instagram_post.v1",
            "post_id": post_id,
            "shortcode": shortcode,
            "caption": str(caption or "")[:2000],
            "author_id": _safe_str(user.get("pk") or user.get("id")) or "",
            "author_username": _safe_str(user.get("username")) or "",
            "media_type": _safe_str(item.get("media_type") or item.get("type")),
            "like_count": _safe_int(item.get("like_count")),
            "comment_count": _safe_int(item.get("comment_count")),
            "taken_at": _safe_ts(item.get("taken_at")),
            "hashtags": _extract_hashtags(str(caption or "")),
            "raw": item,
        },
        collected_at=datetime.now(UTC),
    )


def _normalize_xiaohongshu_note(
    item: dict[str, Any], collector_type: str
) -> CollectorRawRecord | None:
    note: dict[str, Any] = item.get("note") or item.get("noteCard") or item
    note_id = _safe_str(
        note.get("id")
        or note.get("noteId")
        or item.get("id")
        or item.get("note_id")
    )
    if not note_id:
        return None

    title = str(note.get("title") or note.get("displayTitle") or "")
    desc = str(note.get("desc") or note.get("description") or "")
    user: dict[str, Any] = note.get("user") or {}
    user_id = _safe_str(user.get("userid") or user.get("userId") or user.get("user_id")) or ""

    return CollectorRawRecord(
        record_type="xiaohongshu_note",
        source_url=f"https://www.xiaohongshu.com/explore/{note_id}",
        content={
            "provider": "tikhub",
            "platform": "xiaohongshu",
            "collector_type": collector_type,
            "schema_version": "tikhub_xiaohongshu_note.v1",
            "note_id": note_id,
            "title": title[:500],
            "desc": desc[:2000],
            "author_id": user_id,
            "author_nickname": _safe_str(user.get("nickname")) or "",
            "like_count": _safe_int(note.get("liked_count") or note.get("like_count")),
            "comment_count": _safe_int(note.get("comments_count") or note.get("comment_count")),
            "collect_count": _safe_int(note.get("collected_count") or note.get("collect_count")),
            "note_type": _safe_str(note.get("type")),
            "raw": item,
        },
        collected_at=datetime.now(UTC),
    )


def _normalize_item(
    item: dict[str, Any],
    platform: str,
    collector_type: str,
) -> CollectorRawRecord | None:
    if platform == "tiktok":
        return _normalize_tiktok_video(item, collector_type)
    if platform == "instagram":
        return _normalize_instagram_post(item, collector_type)
    if platform == "xiaohongshu":
        return _normalize_xiaohongshu_note(item, collector_type)
    if platform in (
        "youtube", "reddit", "x", "douyin", "bilibili", "weibo", "kuaishou", "wechat", "zhihu",
        "threads", "linkedin", "lemon8", "tiktok_shop",
    ):
        return _normalize_generic(item, platform, collector_type)
    return None


def _normalize_generic(
    item: dict[str, Any],
    platform: str,
    collector_type: str,
) -> CollectorRawRecord | None:
    if not item:
        return None
    for key in ("url", "postUrl", "videoUrl", "link"):
        val = item.get(key)
        if isinstance(val, str) and val.startswith("http"):
            source_url = val
            break
    else:
        source_url = None
    for key in ("text", "title", "body", "description", "caption", "snippet"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            text = val.strip()[:2000]
            break
    else:
        text = ""
    record_type_map = {
        "youtube": "youtube_video",
        "reddit": "reddit_post",
        "x": "twitter_post",
        "threads": "threads_post",
        "linkedin": "linkedin_post",
        "lemon8": "lemon8_post",
        "tiktok_shop": "tiktok_shop_product",
    }
    return CollectorRawRecord(
        record_type=record_type_map.get(platform, "social_post"),
        source_url=source_url,
        content={
            "provider": "tikhub",
            "platform": platform,
            "collector_type": collector_type,
            "schema_version": f"tikhub_{platform}.v1",
            "text": text,
            "raw": item,
        },
        collected_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Request param builder
# ---------------------------------------------------------------------------


def _build_params(config: dict[str, Any], max_items: int) -> dict[str, Any]:
    endpoint_type: str = config["endpoint_type"]

    if endpoint_type == "tikhub_tiktok_video_search":
        return {
            "keyword": config.get("keyword") or "",
            "count": max_items,
            "cursor": config.get("cursor") or 0,
            "sort_type": config.get("sort_type") or 0,
        }
    if endpoint_type == "tikhub_tiktok_user_posts":
        return {
            "unique_id": config.get("unique_id") or config.get("username") or "",
            "sec_user_id": config.get("sec_user_id") or "",
            "count": max_items,
            "max_cursor": config.get("max_cursor") or 0,
        }
    if endpoint_type == "tikhub_tiktok_hashtag_posts":
        return {
            "ch_id": config.get("ch_id") or config.get("hashtag_id") or "",
            "count": max_items,
            "cursor": config.get("cursor") or 0,
        }
    if endpoint_type == "tikhub_instagram_user_posts":
        return {
            "user_id": config.get("user_id") or "",
            "count": max_items,
            "max_id": config.get("max_id"),
        }
    if endpoint_type == "tikhub_instagram_search":
        return {
            "keyword": config.get("keyword") or "",
            "pagination_token": config.get("pagination_token"),
        }
    if endpoint_type == "tikhub_xiaohongshu_search":
        return {
            "keyword": config.get("keyword") or "",
            "page": config.get("page") or 1,
            "sort_type": config.get("sort_type") or "general",
            "note_type": config.get("note_type") or "不限",
            "source": config.get("source") or "explore_feed",
        }
    if endpoint_type == "tikhub_youtube_search":
        return {
            "search_query": config.get("keyword") or config.get("query") or "",
        }
    if endpoint_type == "tikhub_youtube_channel_videos":
        return {
            "channel_id": config.get("channel_id") or "",
        }
    if endpoint_type == "tikhub_reddit_search":
        return {
            "query": config.get("keyword") or config.get("query") or "",
            "search_type": "post",
        }
    if endpoint_type == "tikhub_reddit_subreddit_posts":
        return {
            "subreddit_name": config.get("subreddit") or "",
        }
    if endpoint_type == "tikhub_x_search":
        return {
            "keyword": config.get("keyword") or config.get("query") or "",
        }
    if endpoint_type == "tikhub_x_user_tweets":
        return {
            "screen_name": config.get("username") or config.get("screen_name") or "",
        }
    # ── 抖音 (Douyin) ──────────────────────────────────────────────────────────
    if endpoint_type == "tikhub_douyin_video_search":
        return {
            "keyword": config.get("keyword") or "",
        }
    if endpoint_type == "tikhub_douyin_user_posts":
        return {
            "sec_user_id": config.get("sec_user_id") or config.get("user_id") or "",
            "max_cursor": config.get("max_cursor") or 0,
            "count": max_items,
        }
    if endpoint_type == "tikhub_douyin_hot_search":
        return {}
    if endpoint_type == "tikhub_douyin_comments":
        return {
            "aweme_id": config.get("aweme_id") or config.get("video_id") or "",
            "count": max_items,
            "cursor": config.get("cursor") or 0,
        }
    if endpoint_type == "tikhub_douyin_brand_hot_search":
        return {"category_id": config.get("category_id") or 10}
    # ── B站 (Bilibili) ─────────────────────────────────────────────────────────
    if endpoint_type == "tikhub_bilibili_video_search":
        return {
            "keyword": config.get("keyword") or "",
            "order": config.get("order") or "totalrank",
            "page": config.get("page") or 1,
            "page_size": min(max_items, 20),
        }
    if endpoint_type == "tikhub_bilibili_user_videos":
        return {
            "user_id": str(config.get("mid") or config.get("uid") or config.get("user_id") or ""),
        }
    if endpoint_type == "tikhub_bilibili_comments":
        return {
            "bvid": config.get("bvid") or config.get("video_id") or "",
        }
    if endpoint_type == "tikhub_weibo_search":
        return {
            "query": config.get("keyword") or config.get("query") or "",
        }
    if endpoint_type == "tikhub_weibo_user_posts":
        return {
            "uid": config.get("uid") or config.get("user_id") or "",
            "page": config.get("page") or 1,
        }
    if endpoint_type == "tikhub_kuaishou_search":
        return {
            "keyword": config.get("keyword") or "",
        }
    if endpoint_type == "tikhub_kuaishou_user_posts":
        return {
            "user_id": config.get("user_id") or config.get("userId") or "",
        }
    if endpoint_type == "tikhub_wechat_search":
        return {
            "keyword": config.get("keyword") or "",
        }
    if endpoint_type == "tikhub_wechat_channels_video":
        return {
            "username": config.get("username") or "",
        }
        return {
            "keyword": config.get("keyword") or "",
        }
    if endpoint_type == "tikhub_zhihu_search":
        return {"keyword": config.get("keyword") or ""}
    if endpoint_type == "tikhub_zhihu_question_answers":
        return {
            "question_id": config.get("question_id") or "",
            "offset": config.get("offset") or 0,
            "limit": max_items,
        }
    if endpoint_type == "tikhub_youtube_video_search":
        return {"search_query": config.get("keyword") or config.get("query") or ""}
    if endpoint_type == "tikhub_threads_search":
        return {"query": config.get("keyword") or config.get("query") or ""}
    if endpoint_type == "tikhub_threads_user_posts":
        return {"user_id": config.get("user_id") or config.get("username") or ""}
    if endpoint_type == "tikhub_threads_post_comments":
        return {"post_id": config.get("post_id") or "", "count": max_items}
    if endpoint_type == "tikhub_linkedin_user_posts":
        url = config.get("url") or config.get("username") or ""
        if url and not url.startswith("http"):
            url = f"https://www.linkedin.com/in/{url}/"
        return {"url": url}
    if endpoint_type == "tikhub_linkedin_company_profile":
        url = config.get("url") or config.get("company_username") or config.get("company_name") or ""
        if url and not url.startswith("http"):
            url = f"https://www.linkedin.com/company/{url}/"
        return {"url": url}
    if endpoint_type == "tikhub_linkedin_company_posts":
        url = config.get("url") or config.get("company_username") or config.get("company_name") or ""
        if url and not url.startswith("http"):
            url = f"https://www.linkedin.com/company/{url}/"
        return {"url": url}
    if endpoint_type == "tikhub_linkedin_search_jobs":
        keywords = config.get("keyword") or config.get("keywords") or ""
        return {"keywords": keywords}
    if endpoint_type == "tikhub_linkedin_job_detail":
        url = config.get("url") or config.get("job_id") or ""
        if url and not url.startswith("http"):
            url = f"https://www.linkedin.com/jobs/view/{url}/"
        return {"url": url}
    if endpoint_type == "tikhub_linkedin_post_comments":
        urn = config.get("urn") or config.get("post_urn") or config.get("post_id") or ""
        return {"urn": urn}
    if endpoint_type == "tikhub_lemon8_search":
        return {"query": config.get("keyword") or config.get("query") or ""}
    if endpoint_type == "tikhub_lemon8_user_posts":
        return {"user_id": config.get("user_id") or config.get("username") or ""}
    if endpoint_type == "tikhub_lemon8_trending":
        return {}
    if endpoint_type == "tikhub_tiktok_ads_search":
        return {}
    if endpoint_type == "tikhub_tiktok_top_ads":
        return {}
    if endpoint_type == "tikhub_tiktok_ads_detail":
        return {"ads_id": config.get("ads_id") or config.get("ad_id") or ""}
    if endpoint_type == "tikhub_tiktok_ads_keyword_suggest":
        return {}
    if endpoint_type == "tikhub_tiktok_shop_products":
        return {"search_word": config.get("keyword") or config.get("search_word") or ""}
    if endpoint_type == "tikhub_tiktok_creator_info":
        return {"creator_uid": config.get("creator_uid") or config.get("unique_id") or config.get("username") or ""}
    if endpoint_type == "tikhub_tiktok_creator_insights":
        return {"keyword": config.get("keyword") or config.get("unique_id") or ""}
    if endpoint_type == "tikhub_tiktok_creator_insights_trend":
        return {"query_id_str": config.get("query_id_str") or config.get("keyword") or "7555720035176562699"}
    if endpoint_type == "tikhub_tiktok_creator_account_health":
        return {}
    if endpoint_type == "tikhub_tiktok_live_search":
        return {"keyword": config.get("keyword") or ""}
    if endpoint_type == "tikhub_tiktok_live_room_detail":
        return {"room_id": config.get("room_id") or ""}
    if endpoint_type == "tikhub_tiktok_live_user":
        return {"creator_uid": config.get("creator_uid") or config.get("unique_id") or ""}
    if endpoint_type == "tikhub_youtube_trending":
        return {"search_query": config.get("keyword") or "trending"}
    if endpoint_type == "tikhub_reddit_trending":
        return {}
    if endpoint_type == "tikhub_x_trending":
        return {}
    if endpoint_type == "tikhub_tiktok_user_followers":
        return {"sec_user_id": config.get("sec_user_id") or config.get("unique_id") or "", "count": max_items}
    if endpoint_type == "tikhub_instagram_user_followers":
        return {"user_id": config.get("user_id") or "", "count": max_items}
    if endpoint_type == "tikhub_x_user_followers":
        screen_name = config.get("username") or config.get("screen_name") or ""
        return {"screen_name": screen_name}
    if endpoint_type == "tikhub_instagram_post_comments":
        code_or_url = config.get("code_or_url") or config.get("shortcode") or config.get("post_id") or ""
        return {"code_or_url": code_or_url}
    if endpoint_type == "tikhub_youtube_video_comments":
        return {"video_id": config.get("video_id") or ""}
    if endpoint_type == "tikhub_reddit_post_comments":
        return {"post_id": config.get("post_id") or ""}
    return {}


# ---------------------------------------------------------------------------
# Collector class
# ---------------------------------------------------------------------------


class TikHubSocialCollector(BaseCollector):
    """TikHub REST API collector for TikTok / Instagram / Xiaohongshu.

    Required config keys:
        endpoint_type: one of TIKHUB_ENDPOINT_MAP keys
        + endpoint-specific params (keyword, username, etc.)

    Optional config keys:
        max_items: int  (default 20, max 100)
    """

    collector_type = "tikhub_social"

    def validate_config(self) -> dict[str, Any]:
        endpoint_type = require_text(self.config, "endpoint_type")
        if endpoint_type not in TIKHUB_ENDPOINT_MAP:
            raise CollectorError(
                f"tikhub_endpoint_type_unknown: {endpoint_type!r}. "
                f"Supported: {sorted(TIKHUB_ENDPOINT_MAP)}"
            )
        max_items_raw = self.config.get("max_items")
        max_items = min(
            int(max_items_raw) if isinstance(max_items_raw, (int, str)) else 20,
            TIKHUB_MAX_ITEMS_LIMIT,
        )
        return {**self.config, "endpoint_type": endpoint_type, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        config = self.validate_config()
        endpoint_type: str = config["endpoint_type"]
        endpoint_path, _, platform = TIKHUB_ENDPOINT_MAP[endpoint_type]
        api_key = _get_api_key()
        test_params = _build_params({**config, "max_items": 1}, max_items=1)
        logs: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient() as client:
                data = await _tikhub_get(client, endpoint_path, test_params, api_key)
            items = _extract_items(data, platform)
            msg = f"TikHub endpoint {endpoint_type!r} reachable; got {len(items)} items."
            logs.append(collector_log("tikhub_test", msg))
            return CollectorTestResult(status="ok", message=msg, logs=logs)
        except CollectorError as exc:
            msg = f"TikHub test failed: {exc}"
            logs.append(collector_log("tikhub_test_failed", msg, level="error"))
            return CollectorTestResult(status="failed", message=msg, logs=logs)

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        endpoint_type: str = config["endpoint_type"]
        endpoint_path, _record_type, platform = TIKHUB_ENDPOINT_MAP[endpoint_type]
        max_items: int = config["max_items"]

        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        raw_records: list[CollectorRawRecord] = []

        try:
            api_key = _get_api_key()
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("tikhub_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        params = _build_params(config, max_items=max_items)
        logs.append(
            collector_log(
                "tikhub_collect_start",
                f"endpoint={endpoint_type}, max_items={max_items}",
            )
        )

        try:
            async with httpx.AsyncClient() as client:
                if endpoint_type in _TIKHUB_POST_ENDPOINTS:
                    data = await _tikhub_post(client, endpoint_path, params, api_key)
                else:
                    data = await _tikhub_get(client, endpoint_path, params, api_key)
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("tikhub_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        items = _extract_items(data, platform)
        logs.append(collector_log("tikhub_items_received", f"raw_count={len(items)}"))

        for item in items[:max_items]:
            if not isinstance(item, dict):
                continue
            record = _normalize_item(item, platform, endpoint_type)
            if record is not None:
                raw_records.append(record)

        logs.append(
            collector_log(
                "tikhub_collect_done",
                f"normalized={len(raw_records)}/{len(items)} items for {platform}",
            )
        )

        if items and not raw_records:
            errors.append(
                f"tikhub_normalize_all_failed: {len(items)} items received but 0 normalized"
            )

        return CollectionResult(raw_records=raw_records, logs=logs, errors=errors)
