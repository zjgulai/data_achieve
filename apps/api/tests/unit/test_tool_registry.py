"""工具策略注册表完整性。

全部 36 个内部 MCP 工具必须有策略；执行工具必须有项目绑定与额度规则。
"""

from __future__ import annotations

import pytest

from data_intelligence_hub.mcp_runtime.server import mcp_server
from data_intelligence_hub.mcp_runtime.tool_registry import (
    PRESETS,
    TOOL_POLICIES,
    get_policy,
)

EXPECTED_TOOLS = {
    "list_platforms",
    "list_capabilities",
    "describe_capability",
    "get_playbook",
    "collect",
    "web_search",
    "web_fetch",
    "answer",
    "deep_research",
    "create_monitor",
    "list_monitors",
    "workspace_answer",
    "deep_research_start",
    "deep_research_check",
    "enrich_list",
    "enrichment_check",
    "get_run",
    "list_records",
    "stop",
    "balance",
    "tiktok_trend_rank",
    "tiktok_hashtag_videos",
    "tiktok_video_search",
    "tiktok_video_detail",
    "tiktok_video_comments",
    "tiktok_creator_profile",
    "tiktok_creator_search",
    "tiktok_transcript",
    "tiktok_product_search",
    "tiktok_product_detail",
    "tiktok_product_reviews",
    "tiktok_creator_commerce",
    "tiktok_video_products",
    "tiktok_creator_showcase",
    "tiktok_ads_top",
    "tiktok_ads_detail",
}


def test_registry_covers_exactly_36_tools() -> None:
    assert len(TOOL_POLICIES) == 36
    assert set(TOOL_POLICIES) == EXPECTED_TOOLS


@pytest.mark.anyio
async def test_registry_matches_mcp_server_registration() -> None:
    tools = await mcp_server.list_tools()
    names = {tool.name for tool in tools}
    assert names == set(TOOL_POLICIES)


def test_every_tool_is_registered() -> None:
    for name in EXPECTED_TOOLS:
        assert get_policy(name).name == name


def test_execute_tools_require_project_and_quota() -> None:
    execute_tools = {
        "collect",
        "web_search",
        "web_fetch",
        "answer",
        "deep_research",
        "deep_research_start",
        "create_monitor",
        *{
            f"tiktok_{n}"
            for n in (
                "trend_rank",
                "hashtag_videos",
                "video_search",
                "video_detail",
                "video_comments",
                "creator_profile",
                "creator_search",
                "transcript",
                "product_search",
                "product_detail",
                "product_reviews",
                "creator_commerce",
                "video_products",
                "creator_showcase",
                "ads_top",
                "ads_detail",
            )
        },
    }
    for name in execute_tools:
        policy = get_policy(name)
        assert policy.access_mode == "execute", name
        assert policy.requires_project is True, name
        assert policy.consumes_quota == "per_call", name
    # enrich_list 按 spec §3.4 记 per_row_worker：提交扣 0，worker 逐行扣。
    enrich_policy = get_policy("enrich_list")
    assert enrich_policy.access_mode == "execute"
    assert enrich_policy.requires_project is True
    assert enrich_policy.consumes_quota == "per_row_worker"


def test_read_tools_consume_no_quota() -> None:
    read_tools = {
        "list_platforms",
        "list_capabilities",
        "describe_capability",
        "get_playbook",
        "get_run",
        "list_records",
        "deep_research_check",
        "enrichment_check",
        "list_monitors",
        "balance",
    }
    for name in read_tools:
        policy = get_policy(name)
        assert policy.access_mode == "read", name
        assert policy.consumes_quota == "none", name


def test_control_tools() -> None:
    policy = get_policy("stop")
    assert policy.access_mode == "control"
    assert policy.consumes_quota == "none"
    assert policy.cancellable is True


def test_presets_expand_to_registered_tools() -> None:
    registered = set(TOOL_POLICIES)
    for preset_name, tools in {
        "readonly_discovery": (
            "list_platforms",
            "list_capabilities",
            "describe_capability",
            "get_playbook",
            "get_run",
            "list_records",
            "balance",
            "deep_research_check",
            "enrichment_check",
            "list_monitors",
        ),
        "search_research": (
            "web_search",
            "web_fetch",
            "answer",
            "workspace_answer",
            "deep_research",
            "deep_research_start",
            "enrich_list",
        ),
        "tiktok": tuple(sorted(n for n in TOOL_POLICIES if n.startswith("tiktok_"))) + ("collect",),
        "ops_query": ("stop",),
    }.items():
        assert set(tools) <= registered, preset_name
        assert preset_name in PRESETS, preset_name


def test_unknown_tool_raises() -> None:
    with pytest.raises(KeyError):
        get_policy("no_such_tool")
