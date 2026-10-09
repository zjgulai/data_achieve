from __future__ import annotations

import httpx

from .config import get_cdo_settings
from .models import CollectRequest, JsonValue, TikTokIntent


def build_collect_request(intent: TikTokIntent) -> CollectRequest:
    settings = get_cdo_settings()
    endpoint, params = _endpoint_and_params(intent)
    return {
        "project_id": settings.lark_cdo_project_id,
        "endpoint_type": endpoint,
        "params": params,
    }


def _endpoint_and_params(intent: TikTokIntent) -> tuple[str, dict[str, JsonValue]]:
    match intent.action:
        case "search":
            return "tikhub_tiktok_video_search", {
                "keyword": intent.keyword,
                "max_items": intent.limit,
            }
        case "hashtag":
            return "tikhub_tiktok_hashtag_posts", {
                "ch_id": intent.keyword,
                "max_items": intent.limit,
            }
        case "user_posts":
            return "tikhub_tiktok_user_posts", {
                "unique_id": intent.username,
                "max_items": intent.limit,
            }
        case "top_ads":
            return "tikhub_tiktok_top_ads", {"keyword": intent.keyword, "max_items": intent.limit}
        case "creator":
            return "tikhub_tiktok_creator_info", {"unique_id": intent.username or intent.keyword}
        case "live":
            return "tikhub_tiktok_live_search", {
                "keyword": intent.keyword,
                "max_items": intent.limit,
            }
        case "sentiment":
            return "exa_search_news", {
                "query": f"TikTok {intent.keyword} 舆情 新闻",
                "num_results": intent.limit,
            }


async def collect(intent: TikTokIntent) -> dict[str, JsonValue]:
    settings = get_cdo_settings()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.internal_api_base}/api/quick-collect",
            json=build_collect_request(intent),
        )
        response.raise_for_status()
        payload: dict[str, JsonValue] = response.json()
        return payload
