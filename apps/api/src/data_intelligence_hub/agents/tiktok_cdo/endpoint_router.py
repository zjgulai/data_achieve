"""
将 TikTokIntent 映射到实际采集端点参数。
返回 list[tuple[str, dict]]，每项是 (endpoint_type, params)。
"""

from __future__ import annotations

from typing import Any

from .intent import TikTokIntent


def build_collect_params(intent: TikTokIntent) -> list[tuple[str, dict[str, Any]]]:
    """根据 intent.action 构造采集参数列表。
    
    返回 [(endpoint_type, params), ...]，大多数 action 只有一个端点，
    creator 并发调两个端点。
    """
    action = intent.action
    kw = intent.keyword or ""
    username = intent.username or ""
    limit = intent.limit

    if action == "search":
        return [
            (
                "tikhub_tiktok_video_search",
                {"keyword": kw, "max_items": limit},
            )
        ]

    if action == "hashtag":
        ch_id = (intent.extra or {}).get("ch_id")
        return [
            (
                "tikhub_tiktok_hashtag_posts",
                {"ch_id": ch_id or kw, "max_items": limit},
            )
        ]

    if action == "user_posts":
        return [
            (
                "tikhub_tiktok_user_posts",
                {"unique_id": username, "max_items": limit},
            )
        ]

    if action == "top_ads":
        return [
            (
                "tikhub_tiktok_top_ads",
                {"keyword": kw, "period": 7, "max_items": limit},
            )
        ]

    if action == "ads_search":
        # The search endpoint requires material_id. Without one, use the top
        # ads list and let the cleaner filter by keyword.
        return [
            (
                "tikhub_tiktok_top_ads",
                {"keyword": kw, "period": 7, "max_items": limit},
            )
        ]

    if action == "creator":
        return [
            (
                "tikhub_tiktok_creator_info",
                {"creator_uid": username or kw, "max_items": limit},
            ),
            (
                "tikhub_tiktok_creator_insights",
                {"keyword": username or kw, "max_items": limit},
            ),
        ]

    if action == "followers":
        return [
            (
                "tikhub_tiktok_user_followers",
                {"unique_id": username or kw, "max_items": limit},
            )
        ]

    if action == "live":
        return [
            (
                "tikhub_tiktok_live_search",
                {"keyword": kw, "max_items": limit},
            )
        ]

    # sentiment 由 data_sources.py 直接走 Exa，这里返回空
    return []
