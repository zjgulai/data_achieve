"""Tests for routing TikTok CDO intents through the tool layer."""

from __future__ import annotations

from typing import Any

import pytest

from data_intelligence_hub.agents.tiktok_cdo import data_sources, tool_router
from data_intelligence_hub.agents.tiktok_cdo.cleaner import _calc_metrics
from data_intelligence_hub.agents.tiktok_cdo.config import get_cdo_config
from data_intelligence_hub.agents.tiktok_cdo.intent import TikTokIntent
from data_intelligence_hub.services.tiktok_tools import ToolResult


def _intent(action: str, **kwargs: Any) -> TikTokIntent:
    return TikTokIntent(action=action, **kwargs)  # type: ignore[arg-type]


def test_build_tool_call_for_content_actions() -> None:
    assert tool_router.build_tool_call(
        _intent("search", keyword="skincare", limit=5)
    ) == ("tiktok_video_search", {"query": "skincare", "limit": 5})
    tool_id, params = tool_router.build_tool_call(
        _intent("user_posts", username="@alice", limit=3)
    )
    assert tool_id == "tiktok_creator_profile"
    assert params["handle"] == "alice"
    assert params["video_limit"] == 3
    tool_id, params = tool_router.build_tool_call(
        _intent("followers", username="alice", limit=7)
    )
    assert tool_id == "tiktok_creator_profile"
    assert params["include_fans"] is True
    assert params["fan_limit"] == 7


def test_build_tool_call_keeps_legacy_actions_on_direct_path() -> None:
    assert tool_router.build_tool_call(_intent("top_ads", keyword="beauty")) is None
    assert tool_router.build_tool_call(_intent("live", keyword="shoes")) is None
    assert tool_router.build_tool_call(_intent("sentiment", keyword="brand")) is None


def test_adapt_tool_result_filters_by_role() -> None:
    result = ToolResult(
        tool_id="tiktok_creator_profile",
        status="success",
        records=[
            {"_tool_role": "profile", "uid": "u1", "nickname": "Alice"},
            {"_tool_role": "video", "video_id": "v1"},
            {"_tool_role": "fan", "uid": "u2"},
        ],
    )
    adapted = tool_router.adapt_tool_result(
        result, _intent("user_posts", username="alice")
    )
    assert adapted["total"] == 1
    assert adapted["records"][0]["video_id"] == "v1"
    adapted = tool_router.adapt_tool_result(
        result, _intent("followers", username="alice")
    )
    assert adapted["records"][0]["uid"] == "u2"


def test_adapt_tool_result_keeps_failed_error() -> None:
    result = ToolResult(
        tool_id="tiktok_video_search",
        status="failed",
        errors=["tikhub_missing_param"],
    )
    adapted = tool_router.adapt_tool_result(
        result, _intent("search", keyword="x")
    )
    assert adapted["error"] == "tikhub_missing_param"
    assert adapted["records"] == []


def test_tool_routing_flag(monkeypatch) -> None:
    monkeypatch.setenv("LARK_CDO_TOOL_ROUTING", "off")
    get_cdo_config.cache_clear()
    assert not tool_router.tool_routing_enabled(_intent("search", keyword="x"))
    monkeypatch.setenv("LARK_CDO_TOOL_ROUTING", "hybrid")
    monkeypatch.setenv("LARK_CDO_TOOL_ACTIONS", "search,hashtag")
    get_cdo_config.cache_clear()
    assert tool_router.tool_routing_enabled(_intent("search", keyword="x"))
    assert not tool_router.tool_routing_enabled(_intent("creator", username="x"))
    get_cdo_config.cache_clear()


@pytest.mark.asyncio
async def test_gather_data_uses_tool_layer(monkeypatch) -> None:
    monkeypatch.setenv("LARK_CDO_TOOL_ROUTING", "all")
    get_cdo_config.cache_clear()

    async def fake_run(intent, project_id, *, timeout_seconds=None):
        return {
            "records": [{"video_id": "v1"}],
            "total": 1,
            "error": None,
            "tool_id": "tiktok_video_search",
            "status": "success",
            "runs": [],
            "metadata": {},
        }

    monkeypatch.setattr(data_sources, "run_intent_tool", fake_run)

    async def fail_legacy(*args, **kwargs):
        raise AssertionError("legacy path must not run")

    monkeypatch.setattr(data_sources, "_call_tikhub", fail_legacy)
    result = await data_sources.gather_data(_intent("search", keyword="skincare"))
    assert result["records"] == [{"video_id": "v1"}]
    get_cdo_config.cache_clear()


@pytest.mark.asyncio
async def test_gather_data_falls_back_when_tool_fails(monkeypatch) -> None:
    monkeypatch.setenv("LARK_CDO_TOOL_ROUTING", "all")
    get_cdo_config.cache_clear()

    async def failed_tool(intent, project_id, *, timeout_seconds=None):
        return {
            "records": [],
            "total": 0,
            "error": "upstream failed",
            "tool_id": "tiktok_video_search",
            "status": "failed",
            "runs": [],
            "metadata": {},
        }

    async def legacy(endpoint_type, params):
        return {"records": [{"legacy": True}], "endpoint": endpoint_type}

    monkeypatch.setattr(data_sources, "run_intent_tool", failed_tool)
    monkeypatch.setattr(data_sources, "_call_tikhub", legacy)
    result = await data_sources.gather_data(_intent("search", keyword="skincare"))
    assert result["records"] == [{"legacy": True}]
    get_cdo_config.cache_clear()


def test_cleaner_reads_canonical_video_fields() -> None:
    metrics = _calc_metrics(
        {"text": "hello", "play_count": 100, "like_count": 10,
         "comment_count": 2, "share_count": 1},
        "search",
    )
    assert metrics["_plays"] == 100
    assert metrics["_engagement_rate"] == 13.0
