"""Route TikTok CDO intents to the TikTok tool layer.

The CDO agent still owns intent parsing and card rendering. This module maps
actions to tools and adapts ``ToolResult`` records to the shape the cleaner
and card builder expect.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from data_intelligence_hub.services.tiktok_tools import ToolResult, run_tiktok_tool

from .config import get_cdo_config
from .intent import TikTokIntent

TOOL_ACTIONS = {
    "search",
    "hashtag",
    "user_posts",
    "creator",
    "followers",
}

_ROLE_FOR_ACTION = {
    "user_posts": "video",
    "creator": "profile",
    "followers": "fan",
}


def build_tool_call(intent: TikTokIntent) -> tuple[str, dict[str, Any]] | None:
    """Return (tool_id, params) for actions the tool layer can serve."""
    keyword = intent.keyword or ""
    handle = (intent.username or "").lstrip("@")
    limit = intent.limit
    if intent.action == "search":
        return ("tiktok_video_search", {"query": keyword, "limit": limit})
    if intent.action == "hashtag":
        ch_id = (intent.extra or {}).get("ch_id")
        params: dict[str, Any] = {"hashtag": keyword, "limit": limit}
        if ch_id:
            params["ch_id"] = ch_id
        return ("tiktok_hashtag_videos", params)
    if intent.action == "user_posts":
        return (
            "tiktok_creator_profile",
            {
                "handle": handle,
                "include_videos": True,
                "video_limit": limit,
                "include_fans": False,
            },
        )
    if intent.action == "creator":
        return (
            "tiktok_creator_profile",
            {
                "handle": handle or keyword,
                "include_videos": False,
                "include_fans": False,
            },
        )
    if intent.action == "followers":
        return (
            "tiktok_creator_profile",
            {
                "handle": handle or keyword,
                "include_videos": False,
                "include_fans": True,
                "fan_limit": limit,
            },
        )
    return None


def tool_routing_enabled(intent: TikTokIntent) -> bool:
    config = get_cdo_config()
    if config.tool_routing == "off":
        return False
    if intent.action not in TOOL_ACTIONS:
        return False
    if config.tool_routing == "hybrid":
        return intent.action in config.tool_actions
    return True


def _filter_records(
    records: list[dict[str, Any]], intent: TikTokIntent
) -> list[dict[str, Any]]:
    role = _ROLE_FOR_ACTION.get(intent.action)
    if role is None:
        return records
    filtered = [record for record in records if record.get("_tool_role") == role]
    return filtered or records


def adapt_tool_result(
    result: ToolResult, intent: TikTokIntent
) -> dict[str, Any]:
    records = _filter_records(result.records, intent)
    error = None
    if result.status == "failed":
        error = "; ".join(result.errors) or "tool_failed"
    elif result.status == "empty":
        error = None
    return {
        "records": records,
        "total": len(records),
        "error": error,
        "tool_id": result.tool_id,
        "status": result.status,
        "runs": result.runs,
        "metadata": result.metadata,
    }


async def run_intent_tool(
    intent: TikTokIntent,
    project_id: uuid.UUID,
    *,
    timeout_seconds: float | None = None,
) -> dict[str, Any] | None:
    call = build_tool_call(intent)
    if call is None:
        return None
    tool_id, params = call
    config = get_cdo_config()
    timeout = timeout_seconds or config.tool_timeout_seconds
    try:
        result = await asyncio.wait_for(
            run_tiktok_tool(tool_id, project_id, params), timeout=timeout
        )
    except TimeoutError:
        return {
            "records": [],
            "total": 0,
            "error": "采集超时，请稍后重试",
            "tool_id": tool_id,
            "status": "failed",
            "runs": [],
            "metadata": {},
        }
    return adapt_tool_result(result, intent)
