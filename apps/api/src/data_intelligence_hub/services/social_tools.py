"""Reddit / YouTube MCP 工具(Plan C 冲刺 D7)。

与 tiktok_tools 同构:TOOL_HANDLERS + TOOL_ENDPOINTS + run_social_tool。
薄封装——每工具一个主端点,参数直传;归一化交给端点的
collector(tikhub_social 已有 reddit 归一化)。不引入新表、不改契约。

Reddit 3 工具:search / subreddit_posts / post_comments(P3 DOM 通道与
confidence 标记在 NB-2026-11-15,见 Plan C §4)。
YouTube 2 工具:search / channel_videos(字幕走 apify_youtube_scraper
的 downloadSubtitles,暂不单列)。
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from data_intelligence_hub.services.tiktok_tools import (
    TOOL_ENDPOINTS as _TIKTOK_ENDPOINTS,
)
from data_intelligence_hub.services.tiktok_tools import (
    ToolResult,  # re-export
    _collect,
    _limit,
    _result,
)

SOCIAL_TOOL_ENDPOINTS: dict[str, tuple[str, ...]] = {
    "reddit_search": ("tikhub_reddit_search",),
    "reddit_subreddit_posts": ("tikhub_reddit_subreddit_posts",),
    "reddit_post_comments": ("tikhub_reddit_post_comments",),
    "youtube_search": ("tikhub_youtube_search", "apify_youtube_scraper"),
    "youtube_channel_videos": ("tikhub_youtube_channel_videos",),
}

# 合并视图:MCP 端点白名单校验(assert_endpoints_allowed)按它判定。
TOOL_ENDPOINTS: dict[str, tuple[str, ...]] = {**_TIKTOK_ENDPOINTS, **SOCIAL_TOOL_ENDPOINTS}


async def reddit_search(project_id: uuid.UUID, params: dict[str, Any]) -> ToolResult:
    limit = _limit(params)
    keyword = str(params.get("keyword") or params.get("query") or "").strip()
    if not keyword:
        return _result("reddit_search", [], [], metadata={"error": "keyword_required"})
    records, run = await _collect(
        project_id,
        "tikhub_reddit_search",
        {"keyword": keyword, "max_items": limit},
        limit,
    )
    return _result("reddit_search", records, [run])


async def reddit_subreddit_posts(
    project_id: uuid.UUID, params: dict[str, Any]
) -> ToolResult:
    limit = _limit(params)
    subreddit = str(params.get("subreddit") or "").strip().lstrip("r/")
    if not subreddit:
        return _result(
            "reddit_subreddit_posts", [], [], metadata={"error": "subreddit_required"}
        )
    records, run = await _collect(
        project_id,
        "tikhub_reddit_subreddit_posts",
        {"subreddit": subreddit, "max_items": limit},
        limit,
    )
    return _result("reddit_subreddit_posts", records, [run])


async def reddit_post_comments(
    project_id: uuid.UUID, params: dict[str, Any]
) -> ToolResult:
    limit = _limit(params)
    post_id = str(params.get("post_id") or "").strip()
    if not post_id:
        return _result(
            "reddit_post_comments", [], [], metadata={"error": "post_id_required"}
        )
    records, run = await _collect(
        project_id,
        "tikhub_reddit_post_comments",
        {"post_id": post_id, "max_items": limit},
        limit,
    )
    return _result("reddit_post_comments", records, [run])


async def youtube_search(project_id: uuid.UUID, params: dict[str, Any]) -> ToolResult:
    limit = _limit(params)
    keyword = str(params.get("keyword") or params.get("query") or "").strip()
    if not keyword:
        return _result("youtube_search", [], [], metadata={"error": "keyword_required"})
    # 主:tikhub(轻);备:apify_youtube_scraper(searchQueries)。
    records, run = await _collect(
        project_id,
        "tikhub_youtube_search",
        {"keyword": keyword, "max_items": limit},
        limit,
    )
    if not records:
        apify_records, apify_run = await _collect(
            project_id,
            "apify_youtube_scraper",
            {"searchQueries": keyword, "maxResults": limit},
            limit,
            role="secondary",
        )
        apify_run["superseded_by"] = "tikhub_youtube_search"
        return _result("youtube_search", apify_records or records, [run, apify_run])
    return _result("youtube_search", records, [run])


async def youtube_channel_videos(
    project_id: uuid.UUID, params: dict[str, Any]
) -> ToolResult:
    limit = _limit(params)
    channel_id = str(params.get("channel_id") or params.get("channel") or "").strip()
    if not channel_id:
        return _result(
            "youtube_channel_videos", [], [], metadata={"error": "channel_id_required"}
        )
    records, run = await _collect(
        project_id,
        "tikhub_youtube_channel_videos",
        {"channel_id": channel_id, "max_items": limit},
        limit,
    )
    return _result("youtube_channel_videos", records, [run])


SOCIAL_TOOL_HANDLERS: dict[
    str, Callable[[uuid.UUID, dict[str, Any]], Coroutine[Any, Any, ToolResult]]
] = {
    "reddit_search": reddit_search,
    "reddit_subreddit_posts": reddit_subreddit_posts,
    "reddit_post_comments": reddit_post_comments,
    "youtube_search": youtube_search,
    "youtube_channel_videos": youtube_channel_videos,
}


async def run_social_tool(
    tool_id: str,
    project_id: uuid.UUID,
    params: dict[str, Any],
    *,
    workspace_id: uuid.UUID | None = None,
) -> ToolResult:
    """与 run_tiktok_tool 同构的入口(mcp_runtime 调用它)。"""
    from data_intelligence_hub.services.tiktok_tools import (
        _CURRENT_TOOL_CALL,
        _CURRENT_WORKSPACE_ID,
        _summarize_params,
    )

    handler = SOCIAL_TOOL_HANDLERS.get(tool_id)
    if handler is None:
        raise ValueError(f"unknown_social_tool: {tool_id}")
    tool_call_id = f"tc_{uuid.uuid4().hex[:12]}"
    token = _CURRENT_TOOL_CALL.set(
        {
            "tool_call_id": tool_call_id,
            "tool_id": tool_id,
            "label": tool_id,
            "params": _summarize_params(params),
        }
    )
    workspace_token = _CURRENT_WORKSPACE_ID.set(workspace_id)
    try:
        result: ToolResult = await handler(project_id, params)
        return result
    except ValueError as exc:
        return ToolResult(
            tool_id=tool_id,
            status="failed",
            errors=[str(exc)],
            tool_call_id=tool_call_id,
        )
    finally:
        _CURRENT_TOOL_CALL.reset(token)
        _CURRENT_WORKSPACE_ID.reset(workspace_token)
