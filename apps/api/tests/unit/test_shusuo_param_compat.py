"""实盘目录 × 采集器实现的参数兼容回归。

合成 `PackageEndpoint` 测不出参数漂移：漂移发生在真实目录与真实采集器之间
（2026-10 final review：`tikhub_bilibili_comments` 目录声明 `oid`，采集器读
`bvid|video_id`；`tikhub_tiktok_creator_info` 目录声明 `unique_id`，采集器读
`creator_uid`）。本文件只打真实目录 + 真实采集器，不用桩数据。

`live_status` 用固定 verified 替身：本文件校验的是参数契约，不是可用性。
"""

from __future__ import annotations

from typing import Any

import pytest

from data_intelligence_hub.agents.shusuo import capabilities as shusuo_capabilities
from data_intelligence_hub.agents.shusuo import intents as shusuo_intents
from data_intelligence_hub.platform_packages.models import PackageEndpoint
from data_intelligence_hub.platform_packages.service import (
    CapabilityNotFoundError,
    get_platform_package_catalog,
)
from data_intelligence_hub.platform_packages.status import EndpointAvailability

# 意图层会产出的全部端点（intents.py 七类场景 + 账号画像）。
INTENT_ENDPOINTS = (
    "exa_search_auto",
    "exa_search_news",
    "tikhub_tiktok_video_search",
    "tikhub_douyin_video_search",
    "tikhub_xiaohongshu_search",
    "tikhub_weibo_search",
    "tikhub_bilibili_video_search",
    "tikhub_youtube_search",
    "tikhub_instagram_search",
    "tikhub_x_search",
    "tikhub_reddit_search",
    "tikhub_douyin_hot_search",
    "tikhub_x_trending",
    "tikhub_youtube_trending",
    "tikhub_reddit_trending",
    "apify_tiktok_comments_scraper",
    "tikhub_reddit_post_comments",
    "tikhub_youtube_video_comments",
    "apify_tiktok_media_profile_scraper",
    "apify_instagram_profile_scraper",
    "apify_twitter_user_scraper",
    "apify_aliexpress_product_search_v2",
    "apify_amazon_price_tracker",
)

# 审阅点名的四个硬漂移端点（目录声明 ≠ 采集器消费）。
DRIFT_ENDPOINTS = (
    "tikhub_bilibili_comments",
    "tikhub_tiktok_ads_search",
    "tikhub_tiktok_creator_info",
    "tikhub_tiktok_live_user",
)


async def _catalog_endpoints() -> dict[str, PackageEndpoint]:
    catalog = await get_platform_package_catalog()
    endpoints: dict[str, PackageEndpoint] = {}
    for package in catalog.packages:
        for endpoint in package.endpoints:
            endpoints.setdefault(endpoint.endpoint_type, endpoint)
    return endpoints


def _verified(endpoint_type: str) -> EndpointAvailability:
    return EndpointAvailability(
        endpoint_type=endpoint_type,
        availability="verified",
        missing_configuration=(),
        last_test_status=None,
        last_test_at=None,
        last_records_count=None,
        last_error_message=None,
        policy_block_reason=None,
    )


@pytest.fixture
def real_catalog(monkeypatch) -> dict[str, PackageEndpoint]:
    """真实目录 + 真实采集器，只把环境派生的可用性钉成 verified。

    测试环境是 offline，`host_block_reason` 会给每个端点打策略阻断；
    本文件校验参数与费用契约，不校验出口策略，因此把这两个环境维度固定下来：
    `policy_block_reason` 置空，`live_status` 返回 verified。
    """
    endpoints = asyncio_run(_catalog_endpoints())

    async def fake_get_capability(endpoint_type: str) -> PackageEndpoint:
        endpoint = endpoints.get(endpoint_type)
        if endpoint is None:
            raise CapabilityNotFoundError(endpoint_type)
        return endpoint.model_copy(update={"policy_block_reason": None})

    async def fake_live_status(*, force: bool = False):
        del force
        return {
            name: _verified(name)
            for name in endpoints
        }

    monkeypatch.setattr(shusuo_capabilities, "get_capability", fake_get_capability)
    monkeypatch.setattr(shusuo_capabilities, "live_status", fake_live_status)
    return endpoints


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


async def _preflight(endpoint_type: str, params: dict[str, Any]):
    proposal = shusuo_intents.Proposal(
        endpoint_type=endpoint_type,
        params=params,
        title=f"{endpoint_type} 兼容性",
    )
    return await shusuo_capabilities.preflight_proposal(proposal)


async def test_intent_endpoints_exist_in_real_catalog() -> None:
    endpoints = await _catalog_endpoints()
    missing = [name for name in INTENT_ENDPOINTS if name not in endpoints]
    assert not missing, f"意图层引用了目录里不存在的端点: {missing}"


async def test_intent_emitted_proposals_pass_preflight_on_real_catalog(
    real_catalog: dict[str, PackageEndpoint],
) -> None:
    """意图层真实产出的提案必须能通过真实目录 + 真实采集器的预检。"""
    broken: dict[str, tuple[str, ...]] = {}
    for endpoint_type in INTENT_ENDPOINTS:
        signal = await _proposal_signal(endpoint_type, real_catalog[endpoint_type])
        result = await _preflight(endpoint_type, signal)
        if not result.allowed:
            broken[endpoint_type] = result.errors
    assert not broken, f"意图端点被预检拒绝: {broken}"


async def _proposal_signal(
    endpoint_type: str, endpoint: PackageEndpoint
) -> dict[str, Any]:
    """按「目录 + 采集器」契约给每组必填一个值；数量键按目录声明补。"""
    from data_intelligence_hub.agents.shusuo.collector_params import contract_for

    contract = contract_for(
        endpoint_type, endpoint.required_params, endpoint.optional_params
    )
    accepted = set(contract.accepted)
    params: dict[str, Any] = {}
    for group in contract.required_groups:
        params[group[0]] = ["https://example.com/x"] if group[0] in {
            "postURLs",
            "profiles",
            "usernames",
            "twitterHandles",
            "queries",
            "products",
        } else "probe-value"
    if "max_items" in accepted:
        params["max_items"] = 10
    if "num_results" in accepted:
        params["num_results"] = 10
    if "commentsPerPost" in accepted:
        params["commentsPerPost"] = 10
    return params


@pytest.mark.parametrize(
    ("endpoint_type", "params"),
    [
        # 四个硬漂移端点：用采集器实际消费的键。
        ("tikhub_bilibili_comments", {"bvid": "BV1xx411c7mD"}),
        ("tikhub_bilibili_comments", {"video_id": "BV1xx411c7mD"}),
        ("tikhub_tiktok_ads_search", {"material_id": "1234567890"}),
        ("tikhub_tiktok_creator_info", {"creator_uid": "1234567890"}),
        ("tikhub_tiktok_live_user", {"creator_uid": "1234567890"}),
        # 采集器声明式别名（_TIKHUB_REQUIRED_PARAMS 的组内候选键）。
        ("tikhub_reddit_search", {"query": "AI"}),
        ("tikhub_x_search", {"query": "AI"}),
        ("tikhub_youtube_search", {"query": "AI"}),
        ("tikhub_weibo_search", {"query": "科技"}),
        ("tikhub_tiktok_user_posts", {"username": "nike"}),
        ("tikhub_tiktok_user_posts", {"sec_user_id": "MS4wLjABAAAA"}),
        ("tikhub_youtube_video_comments", {"video_id": "dQw4w9WgXcQ"}),
        ("tikhub_douyin_comments", {"video_id": "7300000000000000000"}),
        ("tikhub_lemon8_search", {"query": "咖啡"}),
        ("tikhub_threads_search", {"query": "coffee"}),
        # 采集器消费、目录未声明的配置键。
        ("tikhub_bilibili_video_search", {"keyword": "数码", "order": "pubdate"}),
        ("tikhub_xiaohongshu_search", {"keyword": "露营", "sort_type": "popularity"}),
    ],
)
async def test_collector_documented_keys_are_accepted(
    real_catalog: dict[str, PackageEndpoint], endpoint_type: str, params: dict[str, Any]
) -> None:
    result = await _preflight(endpoint_type, params)
    assert result.allowed is True, result.errors
    assert result.errors == ()


async def test_catalog_drift_required_group_reports_collector_keys(
    real_catalog: dict[str, PackageEndpoint],
) -> None:
    """bilibili 评论：缺参提示采集器的键，而不是目录里会被丢弃的 oid。"""
    result = await _preflight("tikhub_bilibili_comments", {})
    assert result.allowed is False
    joined = " ".join(result.errors)
    assert "bvid" in joined
    assert "video_id" in joined
    assert "oid" not in joined


async def test_catalog_only_key_rejected_when_collector_drops_it(
    real_catalog: dict[str, PackageEndpoint],
) -> None:
    """目录喊 oid、采集器白名单里没有 oid：必须当未知参数拒绝，不能放过。"""
    result = await _preflight("tikhub_bilibili_comments", {"oid": "12345"})
    assert result.allowed is False
    assert "未知参数：oid" in result.errors


async def test_unknown_parameter_still_rejected(real_catalog: dict[str, PackageEndpoint]) -> None:
    result = await _preflight(
        "tikhub_reddit_search", {"keyword": "AI", "totally_unknown": 1}
    )
    assert result.allowed is False
    assert "未知参数：totally_unknown" in result.errors


@pytest.mark.parametrize(
    ("params", "expected_fragment"),
    [
        ({"keyword": "AI", "max_items": 0}, "参数 max_items 必须在 1 到 50 之间。"),
        ({"keyword": "AI", "max_items": 51}, "参数 max_items 必须在 1 到 50 之间。"),
    ],
)
async def test_quantity_bounds_still_enforced_with_key_name(
    real_catalog: dict[str, PackageEndpoint], params: dict[str, Any], expected_fragment: str
) -> None:
    result = await _preflight("tikhub_reddit_search", params)
    assert result.allowed is False
    assert expected_fragment in result.errors


async def test_arbitrary_keys_are_not_globally_allowed(
    real_catalog: dict[str, PackageEndpoint],
) -> None:
    """不能为了方便把任意键放行：这个键在任何采集器里都不存在。"""
    for endpoint_type in ("tikhub_tiktok_video_search", "exa_search_auto"):
        result = await _preflight(
            endpoint_type, {"keyword": "x", "query": "x", "bogus_key": 1}
        )
        assert result.allowed is False
        assert any("bogus_key" in error for error in result.errors)


# ---------------------------------------------------------------------------
# 费用口径：必须用真实目录的 cost_hint
# ---------------------------------------------------------------------------


async def test_cost_notice_uses_real_catalog_hints(
    real_catalog: dict[str, PackageEndpoint],
) -> None:
    """逐端点核对真实 cost_hint 的渲染：泛化措辞一律费用未知。"""
    catalog = real_catalog
    unknown_suffixes = ("按事件计费", "按结果计费", "按量", "按上游")
    problems: dict[str, str] = {}
    for endpoint_type in INTENT_ENDPOINTS:
        endpoint = catalog[endpoint_type]
        hint = (endpoint.cost_hint or "").strip()
        params = await _proposal_signal(endpoint_type, endpoint)
        result = await _preflight(endpoint_type, params)
        notice = result.cost_notice
        if not hint or hint.startswith(unknown_suffixes):
            if notice != "费用未知，按上游实际计费":
                problems[endpoint_type] = f"{hint!r} -> {notice!r}"
            if result.warnings != ("费用未知，按上游实际计费。",):
                problems[endpoint_type] = f"{hint!r} 缺费用未知警告: {result.warnings}"
        else:
            if "费用约 按" in notice or "费用：费用约" in notice:
                problems[endpoint_type] = f"{hint!r} -> {notice!r}"
            if "费用未知" in notice:
                problems[endpoint_type] = f"{hint!r} 被误判为未知 -> {notice!r}"
            if not notice.startswith("费用约 "):
                problems[endpoint_type] = f"{hint!r} -> {notice!r}"
    assert not problems, problems
