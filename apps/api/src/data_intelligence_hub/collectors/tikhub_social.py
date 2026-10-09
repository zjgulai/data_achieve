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
        "/api/v1/weibo/web_v2/fetch_user_posts",
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
    "tikhub_wechat_search",
    "tikhub_douyin_video_search",
})


# ---------------------------------------------------------------------------
# Response extraction
# ---------------------------------------------------------------------------


def _deep_find_dicts(node: Any, key: str) -> list[dict[str, Any]]:
    """按 key 深度优先收集整棵响应树里的所有 dict。

    上游改版会改变嵌套层级（YouTube 的 `contents` 曾是 list，现为 dict，视频
    藏在 `videoRenderer` 里），按固定路径取值会静默返回空列表。深度查找对
    层级变化免疫，失效的只剩"上游重命名"这一种情况。
    """
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        value = node.get(key)
        if isinstance(value, dict):
            found.append(value)
        for child in node.values():
            found.extend(_deep_find_dicts(child, key))
    elif isinstance(node, list):
        for child in node:
            found.extend(_deep_find_dicts(child, key))
    return found


def _deep_find_typename(node: Any, typename: str) -> list[dict[str, Any]]:
    """收集 `__typename == typename` 的 dict（Reddit 的 GraphQL 风格响应用）。"""
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if node.get("__typename") == typename:
            found.append(node)
        for child in node.values():
            found.extend(_deep_find_typename(child, typename))
    elif isinstance(node, list):
        for child in node:
            found.extend(_deep_find_typename(child, typename))
    return found


def _extract_items(data: dict[str, Any], platform: str) -> list[dict[str, Any]]:
    inner = data.get("data")

    if platform == "youtube":
        # web_v2/get_channel_videos → data.videos (list)
        # web_v2/get_general_search → data.contents (dict → videoRenderer)
        if isinstance(inner, dict):
            videos = inner.get("videos")
            if isinstance(videos, list) and videos:
                return videos
            contents = inner.get("contents")
            if isinstance(contents, list) and contents:
                return contents
            # web_v2/get_video_comments → data.comments (list)
            comments = inner.get("comments")
            if isinstance(comments, list) and comments:
                return comments
        return _deep_find_dicts(inner, "videoRenderer")

    if platform == "reddit":
        # fetch_dynamic_search → data.search (list，或 dict → SearchPost.post)
        # fetch_subreddit_feed → data.subredditV3.elements.edges[].node (CellGroup，
        #   帖子内容散在 cells[] 里：TitleCell/MetadataCell/PreviewTextCell/ActionCell)
        if isinstance(inner, list):
            return inner
        if isinstance(inner, dict):
            search = inner.get("search")
            if isinstance(search, list) and search:
                return search
            posts = inner.get("posts")
            if isinstance(posts, list) and posts:
                return posts
            # fetch_post_comments → data.postInfoById（单条帖子 + commentForest）
            post_info = inner.get("postInfoById")
            if isinstance(post_info, dict) and post_info:
                forest = post_info.get("commentForest")
                if isinstance(forest, list) and forest:
                    return forest
                return [post_info]
            # fetch_popular_feed → data.popularfeed.postsInfoByIds (list)
            popular = inner.get("popularfeed")
            if isinstance(popular, dict):
                popular_posts = popular.get("postsInfoByIds")
                if isinstance(popular_posts, list) and popular_posts:
                    return popular_posts
        search_posts = [
            node["post"]
            for node in _deep_find_typename(inner, "SearchPost")
            if isinstance(node.get("post"), dict)
        ]
        if search_posts:
            return search_posts
        return _deep_find_typename(inner, "CellGroup")

    if platform == "x":
        # fetch_search_timeline → data.timeline (list)
        # fetch_user_post_tweet → data.timeline or data (list)
        if isinstance(inner, list):
            return inner
        if isinstance(inner, dict):
            timeline = inner.get("timeline")
            if isinstance(timeline, list):
                return timeline
            # fetch_trending → data.trends (list of {name, description, context})
            trends = inner.get("trends")
            if isinstance(trends, list) and trends:
                return trends
            # fetch_user_followers → data.followers (list)
            followers = inner.get("followers")
            if isinstance(followers, list) and followers:
                return followers
        return []

    if platform in ("tiktok", "tiktok_shop"):
        # 注意 TIKHUB_ENDPOINT_MAP 里 tikhub_tiktok_shop_products 的 platform 是
        # "tiktok_shop"，不是 "tiktok" —— 只判 "tiktok" 会漏掉它。
        if isinstance(inner, list):
            return inner
        if isinstance(inner, dict):
            for key in ("aweme_list", "item_list", "items", "video_list", "result_list", "followers"):
                candidate = inner.get(key)
                if isinstance(candidate, list) and candidate:
                    return candidate
            deeper = inner.get("data")
            if isinstance(deeper, list) and deeper:
                # fetch_live_search_result → data.data (list)
                return deeper
            if isinstance(deeper, dict):
                # shop/fetch_search_products_list → data.data.products
                # ads/get_top_ads_spotlight → data.data.materials
                for key in ("products", "materials", "items", "list"):
                    candidate = deeper.get(key)
                    if isinstance(candidate, list) and candidate:
                        return candidate
                # get_ads_detail → data.data 是单个广告对象
                # fetch_live_room_info → data.data 是单个直播间对象
                if isinstance(deeper, dict) and any(
                    deeper.get(k) is not None
                    for k in ("id", "id_str", "room_id", "ad_title", "owner")
                ):
                    return [deeper]
        return []

    if platform == "lemon8":
        # fetch_discover_tab → data.data (list)
        # fetch_search → data.data (list)
        # fetch_user_profile → data.data 是单个用户对象
        if isinstance(inner, list):
            return inner
        if isinstance(inner, dict):
            deeper = inner.get("data")
            if isinstance(deeper, list) and deeper:
                return deeper
            for key in ("items", "posts", "notes", "list"):
                candidate = inner.get(key)
                if isinstance(candidate, list) and candidate:
                    return candidate
            if isinstance(deeper, dict) and (
                deeper.get("user_id") or deeper.get("media_id") or deeper.get("name")
            ):
                return [deeper]
        return []

    if platform == "threads":
        # fetch_user_posts → data.mediaData.edges[].node
        # fetch_post_comments → data.edges[].node（含 thread_items）
        if isinstance(inner, list):
            return inner
        if isinstance(inner, dict):
            media = inner.get("mediaData")
            if isinstance(media, dict) and isinstance(media.get("edges"), list):
                nodes = [e.get("node") for e in media["edges"] if isinstance(e, dict)]
                return [n for n in nodes if isinstance(n, dict)]
            edges = inner.get("edges")
            if isinstance(edges, list) and edges:
                nodes = [e.get("node") for e in edges if isinstance(e, dict)]
                return [n for n in nodes if isinstance(n, dict)]
        return []

    if platform == "linkedin":
        if isinstance(inner, list):
            return inner
        if isinstance(inner, dict):
            for key in ("posts", "items", "results"):
                candidate = inner.get(key)
                if isinstance(candidate, list) and candidate:
                    return candidate
            # get_company_profile → data 就是单个公司对象
            if inner.get("name") or inner.get("id"):
                return [inner]
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
            # 这些平台的响应常常再套一层或两层 data / results，条目数组藏在里面：
            #   bilibili fetch_user_videos → data.item
            #   douyin   fetch_hot_search_list → data.data.word_list
            #   douyin   fetch_brand_hot_..._detail → data.brand_list
            #   weibo    fetch_user_posts → data.data.list
            #   wechat   fetch_search → data.results.data
            scopes: list[dict[str, Any]] = [inner]
            for key in ("data", "results"):
                for scope in list(scopes):
                    nested = scope.get(key)
                    if isinstance(nested, dict):
                        scopes.append(nested)
            for scope in scopes:
                for key in (
                    "aweme_list", "item_list", "items", "item", "video_list",
                    "list", "result_list", "statuses", "cards", "answer_list",
                    "search_result", "result", "videos", "brand_list",
                    "trending_list", "word_list", "comments", "mixFeeds",
                    "feeds", "data",
                ):
                    candidate = scope.get(key)
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


def _runs_text(block: Any) -> str | None:
    """YouTube 文本节点：`{"runs": [{"text": ...}]}` 或 `{"simpleText": ...}`。"""
    if not isinstance(block, dict):
        return None
    runs = block.get("runs")
    if isinstance(runs, list):
        joined = "".join(
            str(run.get("text") or "") for run in runs if isinstance(run, dict)
        ).strip()
        if joined:
            return joined
    simple = block.get("simpleText")
    if isinstance(simple, str) and simple.strip():
        return simple.strip()
    return None


def _normalize_youtube_video(
    item: dict[str, Any], collector_type: str
) -> CollectorRawRecord | None:
    video_id = _safe_str(item.get("videoId"))
    if video_id is None:
        # get_channel_videos 等的条目形状不同，交回通用归一化，避免丢记录。
        return _normalize_generic(item, "youtube", collector_type)
    title = _runs_text(item.get("title"))
    return CollectorRawRecord(
        record_type="youtube_video",
        source_url=f"https://www.youtube.com/watch?v={video_id}",
        content={
            "provider": "tikhub",
            "platform": "youtube",
            "collector_type": collector_type,
            "schema_version": "tikhub_youtube.v2",
            "video_id": video_id,
            "text": title or "",
            "channel": _runs_text(item.get("ownerText") or item.get("longBylineText")),
            "published_time": _runs_text(item.get("publishedTimeText")),
            "view_count_text": _runs_text(item.get("viewCountText")),
            "raw": item,
        },
        collected_at=datetime.now(UTC),
    )


def _normalize_threads_item(
    item: dict[str, Any], collector_type: str
) -> CollectorRawRecord | None:
    """Threads 的帖子/评论节点：正文在 thread_items[0].post.caption.text。"""
    thread_items = item.get("thread_items")
    post = (
        thread_items[0].get("post")
        if thread_items and isinstance(thread_items[0], dict)
        else {}
    )
    if not isinstance(post, dict):
        post = {}
    caption = post.get("caption") if isinstance(post.get("caption"), dict) else {}
    text = _safe_str(caption.get("text"))
    code = _safe_str(post.get("code"))
    user = post.get("user") if isinstance(post.get("user"), dict) else {}
    username = _safe_str(user.get("username"))
    if text is None and code is None:
        return _normalize_generic(item, "threads", collector_type)
    return CollectorRawRecord(
        record_type="threads_post",
        source_url=(
            f"https://www.threads.com/@{username}/post/{code}" if code else None
        ),
        content={
            "provider": "tikhub",
            "platform": "threads",
            "collector_type": collector_type,
            "schema_version": "tikhub_threads.v2",
            "text": text or "",
            "post_id": _safe_str(post.get("id") or item.get("id")),
            "code": code,
            "author": username,
            "raw": item,
        },
        collected_at=datetime.now(UTC),
    )


def _normalize_tiktok_user(
    item: dict[str, Any], collector_type: str
) -> CollectorRawRecord | None:
    """fetch_user_follower_list 的条目：完整 TikTok 用户对象。

    这类条目没有 aweme_id/video_id，落到 _normalize_tiktok_video 会全部返回 None，
    采集器于是报 "tikhub_normalize_all_failed"（提取到 20 条却 0 条入库）。
    """
    unique_id = _safe_str(item.get("unique_id"))
    nickname = _safe_str(item.get("nickname"))
    if unique_id is None and nickname is None:
        return _normalize_generic(item, "tiktok", collector_type)
    return CollectorRawRecord(
        record_type="tiktok_user",
        source_url=f"https://www.tiktok.com/@{unique_id}" if unique_id else None,
        content={
            "provider": "tikhub",
            "platform": "tiktok",
            "collector_type": collector_type,
            "schema_version": "tikhub_tiktok_user.v1",
            "text": nickname or unique_id or "",
            "unique_id": unique_id,
            "nickname": nickname,
            "uid": _safe_str(item.get("uid")),
            "sec_uid": _safe_str(item.get("sec_uid")),
            "signature": _safe_str(item.get("signature")),
            "follower_count": _safe_int(item.get("follower_count")),
            "raw": item,
        },
        collected_at=datetime.now(UTC),
    )


def _normalize_tiktok_live(
    item: dict[str, Any], collector_type: str
) -> CollectorRawRecord | None:
    """fetch_live_search_result 的条目。两种形状：

    - ``{"type": 1, "lives": {"aweme_id", "author": {...}}}``（绝大多数）
    - ``{"type": 2, "anchor": {"owner_user_info": {...}, "live_info": {...}}}``
    """
    anchor = item.get("anchor") if isinstance(item.get("anchor"), dict) else {}
    lives = item.get("lives") if isinstance(item.get("lives"), dict) else {}
    owner = lives.get("author") if isinstance(lives.get("author"), dict) else {}
    if not owner:
        owner = anchor.get("owner_user_info") if isinstance(anchor.get("owner_user_info"), dict) else {}
    if not owner:
        # fetch_live_room_info → 单个直播间对象，主播在 item["owner"]
        owner = item.get("owner") if isinstance(item.get("owner"), dict) else {}
    nickname = _safe_str(owner.get("nickname"))
    uid = _safe_str(owner.get("uid") or owner.get("id_str"))
    if nickname is None and uid is None:
        return _normalize_generic(item, "tiktok", collector_type)
    room_id = (
        _safe_str(lives.get("aweme_id"))
        or _safe_str(anchor.get("room_id"))
        or _safe_str(item.get("id_str"))
        or _safe_str(item.get("id"))
    )
    return CollectorRawRecord(
        record_type="tiktok_live",
        source_url=f"https://www.tiktok.com/@{nickname}/live" if nickname else None,
        content={
            "provider": "tikhub",
            "platform": "tiktok",
            "collector_type": collector_type,
            "schema_version": "tikhub_tiktok_live.v1",
            "text": nickname or _safe_str(item.get("title")) or uid or "",
            "uid": uid,
            "nickname": nickname,
            "title": _safe_str(item.get("title")),
            "room_id": room_id,
            "live_info": anchor.get("live_info") or lives,
            "raw": item,
        },
        collected_at=datetime.now(UTC),
    )


def _normalize_tiktok_product(
    item: dict[str, Any], collector_type: str
) -> CollectorRawRecord | None:
    """shop/fetch_search_products_list 的条目：product_id / title / seo_url / price。"""
    product_id = _safe_str(item.get("product_id"))
    title = _safe_str(item.get("title"))
    if product_id is None and title is None:
        return _normalize_generic(item, "tiktok", collector_type)
    price = item.get("product_price_info")
    return CollectorRawRecord(
        record_type="tiktok_shop_product",
        source_url=_safe_str(item.get("seo_url")),
        content={
            "provider": "tikhub",
            "platform": "tiktok",
            "collector_type": collector_type,
            "schema_version": "tikhub_tiktok_shop_product.v1",
            "product_id": product_id,
            "text": title or "",
            "price": price,
            "sold_info": item.get("sold_info"),
            "seller_info": item.get("seller_info"),
            "url": _safe_str(item.get("seo_url")),
            "raw": item,
        },
        collected_at=datetime.now(UTC),
    )


def _normalize_tiktok_ad(
    item: dict[str, Any], collector_type: str
) -> CollectorRawRecord | None:
    """ads/get_top_ads_spotlight 的条目：id / highlight / ctr / cost / video_info。"""
    ad_id = _safe_str(item.get("id"))
    highlight = _safe_str(item.get("highlight") or item.get("highlight_text"))
    if ad_id is None and highlight is None:
        return _normalize_generic(item, "tiktok", collector_type)
    return CollectorRawRecord(
        record_type="tiktok_ad",
        source_url=None,
        content={
            "provider": "tikhub",
            "platform": "tiktok",
            "collector_type": collector_type,
            "schema_version": "tikhub_tiktok_ad.v1",
            "material_id": ad_id,
            "text": highlight or "",
            "ctr": item.get("ctr"),
            "cost": item.get("cost"),
            "like_count": item.get("like"),
            "video_info": item.get("video_info"),
            "raw": item,
        },
        collected_at=datetime.now(UTC),
    )


def _normalize_youtube_comment(
    item: dict[str, Any], collector_type: str
) -> CollectorRawRecord | None:
    """web_v2/get_video_comments 的条目形状：comment_id / content / like_count。

    评论在 data.comments，字段是 snake_case（和 channel videos 的 video_id 一样），
    而 _normalize_youtube_video 只认 videoId，整批会落到通用归一化里。
    """
    comment_id = _safe_str(item.get("comment_id") or item.get("commentId"))
    if comment_id is None:
        return _normalize_generic(item, "youtube", collector_type)
    content = item.get("content")
    text = _safe_str(content) or _runs_text(content) or ""
    return CollectorRawRecord(
        record_type="youtube_comment",
        source_url=None,
        content={
            "provider": "tikhub",
            "platform": "youtube",
            "collector_type": collector_type,
            "schema_version": "tikhub_youtube_comment.v1",
            "comment_id": comment_id,
            "text": text,
            "published_time": _safe_str(item.get("published_time")),
            "like_count": _safe_int(item.get("like_count")),
            "reply_count": _safe_int(item.get("reply_count")),
            "reply_level": item.get("reply_level"),
            "raw": item,
        },
        collected_at=datetime.now(UTC),
    )


def _normalize_x_trend(
    item: dict[str, Any], collector_type: str
) -> CollectorRawRecord | None:
    """fetch_trending 的条目形状：{name, description, context}。"""
    name = _safe_str(item.get("name"))
    if name is None:
        return _normalize_generic(item, "x", collector_type)
    return CollectorRawRecord(
        record_type="trend",
        source_url=None,
        content={
            "provider": "tikhub",
            "platform": "x",
            "collector_type": collector_type,
            "schema_version": "tikhub_x_trend.v1",
            "text": name,
            "description": _safe_str(item.get("description")),
            "context": item.get("context"),
            "raw": item,
        },
        collected_at=datetime.now(UTC),
    )


def _reddit_cell(node: dict[str, Any], typename: str) -> dict[str, Any]:
    """从 CellGroup.cells / crosspostCells 里取出指定 __typename 的 cell。"""
    for key in ("cells", "crosspostCells"):
        for cell in node.get(key) or []:
            if isinstance(cell, dict) and cell.get("__typename") == typename:
                return cell
    return {}


def _normalize_reddit_subreddit_post(
    item: dict[str, Any], collector_type: str
) -> CollectorRawRecord | None:
    """fetch_subreddit_feed 的 CellGroup 形态。

    上游返回的是 UI 结构：groupId 形如 ``t3_1wxjay5``，标题在 TitleCell.title，
    作者/时间在 MetadataCell，正文摘要可选在 PreviewTextCell.text，
    互动数在 ActionCell。按固定路径取 item.get("title") 只会得到空记录。
    """
    group_id = _safe_str(item.get("groupId")) or ""
    post_id = group_id[3:] if group_id.startswith("t3_") else group_id
    title = _safe_str(_reddit_cell(item, "TitleCell").get("title"))
    meta = _reddit_cell(item, "MetadataCell")
    preview = _reddit_cell(item, "PreviewTextCell")
    action = _reddit_cell(item, "ActionCell")
    source_url = (
        f"https://www.reddit.com/comments/{post_id}" if post_id else None
    )
    if title is None and source_url is None:
        return None
    return CollectorRawRecord(
        record_type="reddit_post",
        source_url=source_url,
        content={
            "record_type": "reddit_post",
            "schema_version": "tikhub_reddit.v2",
            "platform": "reddit",
            "post_id": post_id or None,
            "text": title,
            "body": _safe_str(preview.get("text")),
            "author": _safe_str(meta.get("authorName")),
            "created_at": _safe_str(meta.get("createdAt")),
            "score": action.get("score"),
            "comment_count": action.get("commentCount"),
            "url": source_url,
            "collector_type": collector_type,
            "raw": item,
        },
        collected_at=datetime.now(UTC),
    )


def _normalize_reddit_post(
    item: dict[str, Any], collector_type: str
) -> CollectorRawRecord | None:
    title = _safe_str(item.get("postTitle") or item.get("title"))
    permalink = _safe_str(item.get("permalink"))
    # fetch_popular_feed 的条目只有 id（如 "1abcde"），没有 permalink / url
    post_id = _safe_str(item.get("id"))
    source_url = (
        _safe_str(item.get("url"))
        or (f"https://www.reddit.com{permalink}" if permalink else None)
        or (f"https://www.reddit.com/comments/{post_id}" if post_id else None)
    )
    if title is None and source_url is None:
        return _normalize_generic(item, "reddit", collector_type)
    content_block = item.get("content")
    body = _safe_str(content_block.get("markdown")) if isinstance(content_block, dict) else None
    author_info = item.get("authorInfo")
    subreddit = item.get("subreddit")
    return CollectorRawRecord(
        record_type="reddit_post",
        source_url=source_url,
        content={
            "provider": "tikhub",
            "platform": "reddit",
            "collector_type": collector_type,
            "schema_version": "tikhub_reddit.v2",
            "text": (title or "")[:2000],
            "body": (body or "")[:2000],
            "subreddit": _safe_str(subreddit.get("name")) if isinstance(subreddit, dict) else None,
            "author": _safe_str(author_info.get("name")) if isinstance(author_info, dict) else None,
            "score": _safe_int(item.get("score")),
            "comment_count": _safe_int(item.get("commentCount")),
            "created_at": _safe_ts(item.get("createdAt")),
            "raw": item,
        },
        collected_at=datetime.now(UTC),
    )


def _normalize_item(
    item: dict[str, Any],
    platform: str,
    collector_type: str,
) -> CollectorRawRecord | None:
    if platform in ("tiktok", "tiktok_shop"):
        if item.get("product_id"):
            return _normalize_tiktok_product(item, collector_type)
        if (
            isinstance(item.get("anchor"), dict)
            or isinstance(item.get("lives"), dict)
            or isinstance(item.get("owner"), dict)
        ):
            return _normalize_tiktok_live(item, collector_type)
        if item.get("highlight") or (item.get("id") and item.get("video_info")):
            return _normalize_tiktok_ad(item, collector_type)
        if item.get("unique_id") or item.get("sec_uid"):
            # fetch_user_follower_list 的条目是完整用户对象
            return _normalize_tiktok_user(item, collector_type)
        return _normalize_tiktok_video(item, collector_type)
    if platform == "instagram":
        return _normalize_instagram_post(item, collector_type)
    if platform == "xiaohongshu":
        return _normalize_xiaohongshu_note(item, collector_type)
    if platform == "youtube":
        if item.get("comment_id") or item.get("commentId"):
            return _normalize_youtube_comment(item, collector_type)
        return _normalize_youtube_video(item, collector_type)
    if platform == "reddit":
        if item.get("__typename") == "CellGroup":
            return _normalize_reddit_subreddit_post(item, collector_type)
        return _normalize_reddit_post(item, collector_type)
    if platform == "x" and item.get("name") and item.get("context") is not None:
        # fetch_trending 的条目形状：{name, description, context}
        return _normalize_x_trend(item, collector_type)
    if platform == "threads" and isinstance(item.get("thread_items"), list):
        return _normalize_threads_item(item, collector_type)
    if platform in (
        "x", "douyin", "bilibili", "weibo", "kuaishou", "wechat", "zhihu",
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
        # 官方 spec 的 body 必填 material_id（缺失即 422），industry / country_code 有默认值。
        return {
            "material_id": config.get("material_id") or "",
            "industry": config.get("industry") or "25308000000",
            "country_code": config.get("country_code") or "US",
        }
    if endpoint_type == "tikhub_tiktok_top_ads":
        return {}
    if endpoint_type == "tikhub_tiktok_ads_detail":
        return {"ads_id": config.get("ads_id") or config.get("ad_id") or ""}
    if endpoint_type == "tikhub_tiktok_ads_keyword_suggest":
        # 官方 spec 的 body 收 query / count / scenario / country_code
        return {
            "query": config.get("keyword") or config.get("query") or "",
            "count": max_items,
            "country_code": config.get("country_code") or "US",
        }
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
                if endpoint_type in _TIKHUB_POST_ENDPOINTS:
                    data = await _tikhub_post(client, endpoint_path, test_params, api_key)
                else:
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
