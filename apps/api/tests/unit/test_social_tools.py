"""social_tools 单测(Plan C D7):Reddit/YouTube 5 工具。

覆盖:必填参数校验缺参即 failed、run_social_tool 未知工具、
MCP server @_tool 注册数 39→44。收集路径(collect_capability)
由 postgres_abi/契约套件覆盖;这里验证 handler 的参数门与注册面。
"""

from __future__ import annotations

import inspect
import uuid
from typing import Any

import pytest

from data_intelligence_hub.services import social_tools
from data_intelligence_hub.services.social_tools import (
    SOCIAL_TOOL_ENDPOINTS,
    TOOL_ENDPOINTS,
    run_social_tool,
)

PROJECT = uuid.uuid4()


@pytest.mark.asyncio
async def test_reddit_search_requires_keyword() -> None:
    result = await run_social_tool("reddit_search", PROJECT, {})
    # _result 语义:无 records 且无 errors = empty(缺参是 metadata 信号,不是运行失败)
    assert result.status == "empty"
    assert result.metadata["error"] == "keyword_required"


@pytest.mark.asyncio
async def test_reddit_search_accepts_query_alias(monkeypatch) -> None:
    """query 是 collect 指令的习惯参数名,接受为 keyword 别名。"""
    captured: dict[str, Any] = {}

    async def fake_collect(project_id, endpoint_type, params, limit, **kw):
        captured["endpoint_type"] = endpoint_type
        captured["params"] = params
        return [{"id": "t3_1"}], {"endpoint_type": endpoint_type, "status": "success"}

    monkeypatch.setattr(social_tools, "_collect", fake_collect)
    result = await run_social_tool("reddit_search", PROJECT, {"query": "momcozy"})
    assert result.status == "success"
    assert captured["endpoint_type"] == "tikhub_reddit_search"
    assert captured["params"]["keyword"] == "momcozy"


@pytest.mark.asyncio
async def test_reddit_subreddit_strips_r_prefix(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_collect(project_id, endpoint_type, params, limit, **kw):
        captured["params"] = params
        return [{"id": "t3_2"}], {"endpoint_type": endpoint_type, "status": "success"}

    monkeypatch.setattr(social_tools, "_collect", fake_collect)
    await run_social_tool(
        "reddit_subreddit_posts", PROJECT, {"subreddit": "r/Momcozy"}
    )
    assert captured["params"]["subreddit"] == "Momcozy"


@pytest.mark.asyncio
async def test_youtube_search_falls_back_to_apify(monkeypatch) -> None:
    """tikhub 空结果时回落 apify_youtube_scraper,run 标 superseded_by。"""
    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_collect(project_id, endpoint_type, params, limit, **kw):
        calls.append((endpoint_type, params))
        if endpoint_type == "tikhub_youtube_search":
            return [], {"endpoint_type": endpoint_type, "status": "empty"}
        return (
            [{"videoId": "v1"}],
            {"endpoint_type": endpoint_type, "status": "success"},
        )

    monkeypatch.setattr(social_tools, "_collect", fake_collect)
    result = await run_social_tool("youtube_search", PROJECT, {"keyword": "white noise"})
    assert [c[0] for c in calls] == ["tikhub_youtube_search", "apify_youtube_scraper"]
    assert result.status == "success"
    assert result.records[0]["videoId"] == "v1"
    assert result.runs[1]["superseded_by"] == "tikhub_youtube_search"


@pytest.mark.asyncio
async def test_unknown_social_tool_raises_value_error() -> None:
    with pytest.raises(ValueError, match="unknown_social_tool"):
        await run_social_tool("nope", PROJECT, {})


def test_tool_endpoints_merge_tiktok_and_social() -> None:
    """合并视图必须包含 TikTok 全部端点映射与 5 个新工具。"""
    for tool_id in SOCIAL_TOOL_ENDPOINTS:
        assert tool_id in TOOL_ENDPOINTS
    assert len(TOOL_ENDPOINTS) >= 16 + 5


def test_mcp_server_registers_44_tools() -> None:
    """@_tool 注册数:39(TikTok+基础)+ 5(D7)= 44。"""
    from data_intelligence_hub.mcp_runtime import server

    src = inspect.getsource(server)
    assert len([1 for line in src.splitlines() if line.startswith("@_tool(")]) == 44
