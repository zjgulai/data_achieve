"""费用口径与预计数量的契约测试。

费用只有带具体金额才算已知：`按事件计费`、`按结果计费`、`按量`、`按上游`
和任何没有金额的自由文本都是"费用未知"。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from data_intelligence_hub.agents.shusuo import capabilities as shusuo_capabilities
from data_intelligence_hub.agents.shusuo import intents as shusuo_intents
from data_intelligence_hub.platform_packages.models import PackageEndpoint
from data_intelligence_hub.platform_packages.service import get_platform_package_catalog
from data_intelligence_hub.platform_packages.status import EndpointAvailability


def _catalog_endpoints() -> dict[str, PackageEndpoint]:
    catalog = asyncio.run(get_platform_package_catalog())
    endpoints: dict[str, PackageEndpoint] = {}
    for package in catalog.packages:
        for endpoint in package.endpoints:
            endpoints.setdefault(endpoint.endpoint_type, endpoint)
    return endpoints


def _endpoint(cost_hint: str | None, optional: tuple[str, ...] = ("max_items",)) -> PackageEndpoint:
    return PackageEndpoint(
        capability_id="demo_endpoint",
        canonical_capability_id="demo_endpoint",
        is_alias_view=False,
        endpoint_type="demo_endpoint",
        label="demo",
        platform="test",
        description="test",
        status="verified",
        required_params=("query",),
        optional_params=optional,
        cost_hint=cost_hint,
        provider="test",
        provider_group="test",
        provider_label="test",
        content_type="post",
        method="GET",
        param_fields={},
        policy_block_reason=None,
    )


def _available(endpoint_type: str = "demo_endpoint") -> EndpointAvailability:
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


def _install(monkeypatch, endpoint: PackageEndpoint) -> None:
    monkeypatch.setattr(
        shusuo_capabilities, "get_capability", AsyncMock(return_value=endpoint)
    )
    monkeypatch.setattr(
        shusuo_capabilities,
        "live_status",
        AsyncMock(return_value={endpoint.endpoint_type: _available(endpoint.endpoint_type)}),
    )


async def _run(monkeypatch, cost_hint: str | None) -> shusuo_capabilities.PreflightResult:
    _install(monkeypatch, _endpoint(cost_hint))
    proposal = shusuo_intents.Proposal(
        endpoint_type="demo_endpoint", params={"query": "AI"}, title="费用口径"
    )
    return await shusuo_capabilities.preflight_proposal(proposal)


@pytest.mark.parametrize(
    "cost_hint",
    [
        None,
        "",
        "   ",
        "按事件计费",
        "按结果计费",
        "按量",
        "按上游",
        "按上游实际计费",
        "按次",
        "见上游定价页",
        "价格随用量浮动",
        "~按事件计费",
        "费用未知",
    ],
)
async def test_generic_cost_hints_are_unknown(monkeypatch, cost_hint: str | None) -> None:
    result = await _run(monkeypatch, cost_hint)
    assert result.cost_notice == "费用未知，按上游实际计费"
    assert result.warnings == ("费用未知，按上游实际计费。",)


@pytest.mark.parametrize(
    "cost_hint",
    [
        "$0.001/条",
        "~$0.001/条",
        "$0.007/query",
        "$0.0004/条",
        "$0.5+",
        "0.002 美元/条",
    ],
)
async def test_concrete_amount_cost_hints_are_known(monkeypatch, cost_hint: str) -> None:
    result = await _run(monkeypatch, cost_hint)
    assert result.cost_notice == f"费用约 {cost_hint}"
    assert result.warnings == ()


async def test_known_cost_notice_has_no_duplicated_wording(monkeypatch) -> None:
    result = await _run(monkeypatch, "~$0.001/条")
    assert "费用：费用约" not in result.cost_notice
    assert "费用约 按" not in result.cost_notice


# ---------------------------------------------------------------------------
# 预计数量：账号画像端点不能一律报 1 条
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected_endpoint", "expected"),
    [
        ("账号 tiktok nike", "apify_tiktok_media_profile_scraper", 10),
        ("账号 instagram nike", "apify_instagram_profile_scraper", 10),
        # X 账号的 `maxItems` 到不了 Actor，缺省上限 3 条；报 10 就是谎报。
        ("账号 x naval", "apify_twitter_user_scraper", 3),
    ],
)
def test_account_profile_estimate_is_not_hardcoded_to_one(
    text: str, expected_endpoint: str, expected: int
) -> None:
    proposal = shusuo_intents.build_proposal(text)
    assert not isinstance(proposal, str)
    assert proposal.endpoint_type == expected_endpoint
    assert proposal.estimated_items == expected


@pytest.mark.parametrize(
    ("text", "expected_endpoint"),
    [
        ("账号 tiktok nike", "apify_tiktok_media_profile_scraper"),
        ("账号 instagram nike", "apify_instagram_profile_scraper"),
    ],
)
def test_account_profile_passes_result_limit_param(
    text: str, expected_endpoint: str
) -> None:
    """数量要真的传下去：只改卡片上的数字是谎报。"""
    proposal = shusuo_intents.build_proposal(text)
    assert not isinstance(proposal, str)
    assert proposal.endpoint_type == expected_endpoint
    endpoint = _catalog_endpoints()[expected_endpoint]
    limit_keys = {"maxItems", "resultsPerPage", "resultsLimit"} & set(
        endpoint.optional_params
    )
    assert limit_keys, f"{expected_endpoint} 目录未声明结果数量参数"
    passed = limit_keys & set(proposal.params)
    assert passed, f"{expected_endpoint} 的预计数量没有传到采集参数：{proposal.params}"
    for key in passed:
        assert proposal.params[key] == proposal.estimated_items


def test_x_account_uses_generic_fetch_cap_instead_of_actor_dropped_key() -> None:
    """X 账号：`maxItems` 会被采集开关剥掉，改用通用抓取上限 `max_items`。"""
    proposal = shusuo_intents.build_proposal("账号 x naval")
    assert not isinstance(proposal, str)
    assert "maxItems" not in proposal.params
    assert proposal.params["max_items"] == 10
    assert proposal.estimated_items == 3


# ---------------------------------------------------------------------------
# 预计数量必须等于 actor_input 的真实上限
# ---------------------------------------------------------------------------

# Actor 侧真正限制产出的键。`maxItems` 在 quick-collect 层是采集开关
# （`_APIFY_META_KEYS` 会把同名的调用方参数剥掉），所以它进不进 actor_input
# 取决于端点缺省 input，而不是调用方传了什么。
RESULT_LIMIT_KEYS = frozenset({"maxItems", "resultsPerPage", "resultsLimit"})

ACCOUNT_CASES = {
    "apify_tiktok_media_profile_scraper": "账号 tiktok nike",
    "apify_instagram_profile_scraper": "账号 instagram nike",
    "apify_twitter_user_scraper": "账号 x naval",
}


def _actor_cap(proposal: shusuo_intents.Proposal) -> int:
    """独立算一遍真实上限：actor_input 里的数量键与抓取上限取小。"""
    from data_intelligence_hub.services.quick_collect_service import (
        build_collector_config,
    )

    config = build_collector_config(proposal.endpoint_type, "apify_actor", proposal.params)
    caps = [
        value
        for key, value in (config.get("actor_input") or {}).items()
        if key in RESULT_LIMIT_KEYS and isinstance(value, int) and not isinstance(value, bool)
    ]
    fetch_cap = config.get("max_items")
    if isinstance(fetch_cap, int) and not isinstance(fetch_cap, bool):
        caps.append(fetch_cap)
    assert caps, f"{proposal.endpoint_type} 没有数量上限可核对"
    return min(caps)


@pytest.mark.parametrize(
    ("endpoint_type", "text"),
    sorted(ACCOUNT_CASES.items()),
)
def test_account_estimate_equals_real_actor_cap(endpoint_type: str, text: str) -> None:
    """卡片上的「预计记录数」必须等于 actor_input 的实际上限。"""
    proposal = shusuo_intents.build_proposal(text)
    assert not isinstance(proposal, str)
    assert proposal.endpoint_type == endpoint_type
    assert proposal.estimated_items == _actor_cap(proposal), (
        f"{endpoint_type} 预计 {proposal.estimated_items} 条，实际上限 {_actor_cap(proposal)} 条，"
        f"参数：{proposal.params}"
    )


def test_x_account_estimate_reflects_actor_default() -> None:
    """X 账号：Actor 缺省 input 把 maxItems 钉在 3，卡片不能报 10。"""
    proposal = shusuo_intents.build_proposal("账号 x naval")
    assert not isinstance(proposal, str)
    assert proposal.endpoint_type == "apify_twitter_user_scraper"
    assert proposal.estimated_items == 3


@pytest.mark.parametrize(
    ("text", "limit_key"),
    [
        ("账号 tiktok nike", "resultsPerPage"),
        ("账号 instagram nike", "resultsLimit"),
    ],
)
def test_result_limit_key_reaches_actor_input(text: str, limit_key: str) -> None:
    """TikTok / Instagram 的 10 条要真的进 actor_input，才配写 10。"""
    from data_intelligence_hub.services.quick_collect_service import (
        build_collector_config,
    )

    proposal = shusuo_intents.build_proposal(text)
    assert not isinstance(proposal, str)
    config = build_collector_config(proposal.endpoint_type, "apify_actor", proposal.params)
    assert config["actor_input"][limit_key] == 10
    assert proposal.estimated_items == 10


def test_x_account_does_not_persist_actor_dropped_key() -> None:
    """X 账号：`maxItems` 到不了 Actor，就不要写进提案参数。"""
    proposal = shusuo_intents.build_proposal("账号 x naval")
    assert not isinstance(proposal, str)
    assert "maxItems" not in proposal.params
    assert proposal.params.get("max_items") == 10


def test_x_account_smaller_limit_still_honors_fetch_cap() -> None:
    """用户要 2 条：抓取上限跟着降到 2，预计就是 2。"""
    proposal = shusuo_intents.build_proposal("账号 x naval max_items=2")
    assert not isinstance(proposal, str)
    assert proposal.estimated_items == 2



def test_price_endpoint_estimate_is_single_product() -> None:
    """价格追踪确实只有一个商品：预计 1 条是真实的，不是硬编码。"""
    proposal = shusuo_intents.build_proposal("价格 B000000001")
    assert not isinstance(proposal, str)
    assert proposal.endpoint_type == "apify_amazon_price_tracker"
    assert proposal.estimated_items == 1
    assert len(proposal.params["products"]) == 1


def test_quantity_error_names_the_key() -> None:
    result = shusuo_intents.build_proposal("搜 reddit AI max_items=51")
    assert isinstance(result, str)
    assert "max_items" in result
    assert "1 到 50" in result


async def test_preflight_quantity_error_names_the_key(monkeypatch) -> None:
    _install(monkeypatch, _endpoint("~$0.001/条"))
    proposal = shusuo_intents.Proposal(
        endpoint_type="demo_endpoint",
        params={"query": "AI", "max_items": 51},
        title="数量越界",
    )
    result = await shusuo_capabilities.preflight_proposal(proposal)
    assert result.errors == ("参数 max_items 必须在 1 到 50 之间。",)
