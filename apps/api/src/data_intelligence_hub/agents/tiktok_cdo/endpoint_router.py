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
                {"keyword": kw, "count": limit, "cursor": 0},
            )
        ]

    if action == "hashtag":
        return [
            (
                "tikhub_tiktok_hashtag_posts",
                {"name": kw, "count": limit, "cursor": 0},
            )
        ]

    if action == "user_posts":
        return [
            (
                "tikhub_tiktok_user_posts",
                {"sec_user_id": username, "count": limit, "cursor": 0},
            )
        ]

    if action == "top_ads":
        return [
            (
                "tikhub_tiktok_top_ads",
                {
                    "industry_key": "",
                    "keyword": kw,
                    "period": 7,
                    "count": limit,
                },
            )
        ]

    if action == "ads_search":
        return [
            (
                "tikhub_tiktok_ads_search",
                {"keyword": kw, "count": limit, "cursor": 0},
            )
        ]

    if action == "creator":
        # 并发调两个端点
        return [
            (
                "tikhub_tiktok_creator_info",
                {"sec_user_id": username or kw},
            ),
            (
                "tikhub_tiktok_creator_insights",
                {"sec_user_id": username or kw},
            ),
        ]

    if action == "followers":
        return [
            (
                "tikhub_tiktok_user_followers",
                {"sec_user_id": username or kw, "count": limit, "cursor": 0},
            )
        ]

    if action == "live":
        return [
            (
                "tikhub_tiktok_live_search",
                {"keyword": kw, "count": limit, "cursor": 0},
            )
        ]

    # sentiment 由 data_sources.py 直接走 Exa，这里返回空
    return []
