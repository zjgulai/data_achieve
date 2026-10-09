"""/api/quick-collect 的 Apify 入参装配契约。

背景（2026-10-09 生产实测）：Apify Actor 的 inputSchema 是
``additionalProperties: false``，多一个键、少一个必填键都会让整单 400。而
quick-collect 的装配逻辑曾用一个"元键"黑名单把 ``query`` / ``url`` / ``keyword``
等也一并剔除，导致调用方传的 ``query`` 被静默丢弃 —— apify/rag-web-browser
因此报 "Field input.query is required"。这组测试守住：

1. 只有采集开关不透传，其余键一律进 actor_input；
2. 调用方入参覆盖端点缺省值；
3. 目录里暴露的每个 Apify 端点都必须能在 _APIFY_ENDPOINT_DEFAULTS 里找到归属。
"""

from __future__ import annotations

import pytest

from data_intelligence_hub.api.routes.collectors import get_collector_catalog
from data_intelligence_hub.api.routes.quick_collect import (
    _APIFY_ENDPOINT_DEFAULTS,
    _APIFY_META_KEYS,
    _ENDPOINT_TO_COLLECTOR,
    build_apify_actor_input,
)

# Actor inputSchema 里真实存在、但曾被当成 quick-collect 元键剔除的入参名。
ACTOR_INPUT_KEYS = (
    "query",
    "url",
    "keyword",
    "domain",
    "app_id",
    "asin",
    "location",
    "username",
    "profile",
    "handle",
    "startUrls",
    "inputs",
    "productUrls",
)


def test_meta_keys_only_hold_collector_knobs() -> None:
    assert _APIFY_META_KEYS == {
        "maxItems",
        "max_items",
        "max_total_charge_usd",
        "run_timeout_seconds",
    }


@pytest.mark.parametrize("key", ACTOR_INPUT_KEYS)
def test_actor_input_keys_are_forwarded(key: str) -> None:
    """回归：这些键必须原样进入 actor_input，不能再被静默丢弃。"""
    marker = "sentinel-value"
    assert build_apify_actor_input({}, {key: marker}) == {key: marker}


def test_collector_knobs_are_not_forwarded() -> None:
    built = build_apify_actor_input(
        {"startUrls": [{"url": "https://example.com"}]},
        {
            "maxItems": 5,
            "max_items": 5,
            "max_total_charge_usd": 0.5,
            "run_timeout_seconds": 60,
            "searchTerms": ["python"],
        },
    )
    assert built == {
        "startUrls": [{"url": "https://example.com"}],
        "searchTerms": ["python"],
    }


def test_caller_params_override_endpoint_defaults() -> None:
    built = build_apify_actor_input({"queries": "default"}, {"queries": "override"})
    assert built == {"queries": "override"}


def test_rag_web_browser_query_survives() -> None:
    """具体回归用例：apify_rag_web_browser 的必填键就是 query。"""
    _, base_input = _APIFY_ENDPOINT_DEFAULTS["apify_rag_web_browser"]
    built = build_apify_actor_input(
        base_input, {"query": "python programming", "maxItems": 3}
    )
    assert built["query"] == "python programming"
    assert built["maxResults"] == 1
    assert "maxItems" not in built


async def test_every_catalog_apify_endpoint_has_defaults() -> None:
    """目录里暴露的 Apify 端点都必须在 _APIFY_ENDPOINT_DEFAULTS 里有归属。

    缺一条就会在 quick-collect 上退回成 "Collector ... is not available" 之类的
    硬伤 —— 这类 bug 曾在非 Apify 端点出现过。
    """
    catalog = await get_collector_catalog()
    catalog_apify = {
        endpoint.endpoint_type
        for group in catalog.collectors
        for endpoint in group.endpoints
        if endpoint.endpoint_type.startswith("apify_")
    }
    assert catalog_apify, "catalog 里应当有 Apify 端点"
    assert catalog_apify <= set(_APIFY_ENDPOINT_DEFAULTS)


def test_defaults_are_all_known_endpoints() -> None:
    unknown = set(_APIFY_ENDPOINT_DEFAULTS) - set(_ENDPOINT_TO_COLLECTOR)
    assert not unknown, f"_APIFY_ENDPOINT_DEFAULTS 指向未知端点: {sorted(unknown)}"


def test_defaults_all_map_to_apify_actor_collector() -> None:
    wrong = {
        endpoint: _ENDPOINT_TO_COLLECTOR[endpoint]
        for endpoint in _APIFY_ENDPOINT_DEFAULTS
        if _ENDPOINT_TO_COLLECTOR.get(endpoint) != "apify_actor"
    }
    assert not wrong, f"以下端点未映射到 apify_actor: {wrong}"


def test_defaults_use_canonical_actor_id_form() -> None:
    for endpoint, (actor_id, base_input) in _APIFY_ENDPOINT_DEFAULTS.items():
        assert "/" in actor_id, f"{endpoint}: actor_id 必须是 'username/name' 形式"
        assert actor_id == actor_id.strip()
        assert isinstance(base_input, dict), f"{endpoint}: base_input 必须是 dict"
