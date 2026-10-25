"""用户可见的「能力」「详情」必须与预检接受同一份参数契约。

2026-10 final polish：帮助文案此前直接渲染目录声明，于是
`能力 tikhub_bilibili_comments` 告诉用户填 `oid`，预检却按采集器口径
要求 `bvid 或 video_id` 并拒绝 `oid`。用户照着帮助填，必然失败。

本文件只打真实目录 + 真实采集器（与 `test_shusuo_param_compat.py` 同一口径），
把「帮助里写的」与「预检真的接受的」逐项对齐。
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import pytest

from data_intelligence_hub.agents.shusuo import capabilities as shusuo_capabilities
from data_intelligence_hub.agents.shusuo import intents as shusuo_intents
from data_intelligence_hub.agents.shusuo.collector_params import contract_for
from data_intelligence_hub.platform_packages.models import PackageEndpoint
from data_intelligence_hub.platform_packages.service import (
    CapabilityNotFoundError,
    get_platform_package_catalog,
)
from data_intelligence_hub.platform_packages.status import EndpointAvailability

DRIFT_ENDPOINTS = (
    "tikhub_bilibili_comments",
    "tikhub_tiktok_ads_search",
    "tikhub_tiktok_creator_info",
    "tikhub_tiktok_live_user",
)

# 四个漂移端点的预期文案：必填按别名组渲染；目录残余键不得出现。
EXPECTED = {
    "tikhub_bilibili_comments": {
        "required": "bvid 或 video_id",
        "optional": (),
        "must_not_appear": ("oid", "page"),
    },
    "tikhub_tiktok_ads_search": {
        "required": "material_id",
        "optional": ("country_code", "industry"),
        "must_not_appear": ("keyword", "period"),
    },
    "tikhub_tiktok_creator_info": {
        "required": "creator_uid",
        "optional": (),
        "must_not_appear": ("unique_id",),
    },
    "tikhub_tiktok_live_user": {
        "required": "creator_uid",
        "optional": (),
        "must_not_appear": ("unique_id",),
    },
}


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
    """真实目录 + 真实采集器；只把环境派生的可用性钉成 verified。"""
    endpoints = asyncio.run(_catalog_endpoints())

    async def fake_get_capability(endpoint_type: str) -> PackageEndpoint:
        endpoint = endpoints.get(endpoint_type)
        if endpoint is None:
            raise CapabilityNotFoundError(endpoint_type)
        return endpoint.model_copy(update={"policy_block_reason": None})

    async def fake_live_status(*, force: bool = False):
        del force
        return {name: _verified(name) for name in endpoints}

    monkeypatch.setattr(shusuo_capabilities, "get_capability", fake_get_capability)
    monkeypatch.setattr(shusuo_capabilities, "live_status", fake_live_status)
    return endpoints


def _has_word(text: str, word: str) -> bool:
    """按标识符边界判断，避免 `video_id` 里的 `oid` 之类误判。"""
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(word)}(?![A-Za-z0-9_])", text) is not None


def _describe_field(text: str, label: str) -> str:
    prefix = f"{label}："
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    return ""


def _optional_keys(describe: str) -> tuple[str, ...]:
    raw = _describe_field(describe, "可选参数")
    if not raw or raw == "无":
        return ()
    return tuple(part.strip() for part in re.split(r"[、,]", raw) if part.strip())


async def _preflight(endpoint_type: str, params: dict[str, Any]):
    return await shusuo_capabilities.preflight_proposal(
        shusuo_intents.Proposal(
            endpoint_type=endpoint_type, params=params, title="帮助契约"
        )
    )


@pytest.mark.parametrize("endpoint_type", DRIFT_ENDPOINTS)
async def test_capability_list_does_not_advertise_catalog_only_keys(
    real_catalog: dict[str, PackageEndpoint], endpoint_type: str
) -> None:
    """「能力 <端点>」列表里的必填必须来自契约，不是目录。"""
    text = await shusuo_capabilities.capabilities_text(endpoint_type)
    expected = EXPECTED[endpoint_type]
    assert endpoint_type in text
    assert expected["required"] in text
    for key in expected["must_not_appear"]:
        assert not _has_word(text, key), f"{endpoint_type} 的能力列表仍在展示 {key}:\n{text}"


@pytest.mark.parametrize("endpoint_type", DRIFT_ENDPOINTS)
async def test_describe_matches_expected_contract(
    real_catalog: dict[str, PackageEndpoint], endpoint_type: str
) -> None:
    text = await shusuo_capabilities.describe_text(endpoint_type)
    expected = EXPECTED[endpoint_type]
    assert _describe_field(text, "必填参数") == expected["required"]
    assert _optional_keys(text) == expected["optional"]
    for key in expected["must_not_appear"]:
        assert not _has_word(text, key), f"{endpoint_type} 的详情仍在展示 {key}:\n{text}"


@pytest.mark.parametrize("endpoint_type", DRIFT_ENDPOINTS)
async def test_advertised_required_aliases_are_accepted_by_preflight(
    real_catalog: dict[str, PackageEndpoint], endpoint_type: str
) -> None:
    """帮助里列出的每个必填别名，预检都必须接受。"""
    endpoint = real_catalog[endpoint_type]
    contract = contract_for(
        endpoint_type, endpoint.required_params, endpoint.optional_params
    )
    assert contract.required_groups, f"{endpoint_type} 没有必填组，测试前提失效"
    groups = contract.required_groups
    for index, group in enumerate(groups):
        for key in group:
            # 其余每组补首个候选键，只让当前组由被测别名满足。
            params = {other[0]: "probe-value" for i, other in enumerate(groups) if i != index}
            params[key] = "probe-value"
            result = await _preflight(endpoint_type, params)
            assert result.allowed is True, (
                f"{endpoint_type} 拒绝了自己宣传的 {key}: {result.errors}"
            )


@pytest.mark.parametrize("endpoint_type", DRIFT_ENDPOINTS)
async def test_advertised_optional_keys_are_accepted_by_preflight(
    real_catalog: dict[str, PackageEndpoint], endpoint_type: str
) -> None:
    """「可选参数」里写一个，预检就必须接受一个；未写的不许悄悄生效。"""
    text = await shusuo_capabilities.describe_text(endpoint_type)
    endpoint = real_catalog[endpoint_type]
    contract = contract_for(
        endpoint_type, endpoint.required_params, endpoint.optional_params
    )
    base = {group[0]: "probe-value" for group in contract.required_groups}
    for key in _optional_keys(text):
        value: Any = 10 if key in {"max_items", "maxItems"} else "probe-value"
        result = await _preflight(endpoint_type, {**base, key: value})
        assert result.allowed is True, (
            f"{endpoint_type} 宣传了不可用的可选参数 {key}: {result.errors}"
        )


@pytest.mark.parametrize("endpoint_type", DRIFT_ENDPOINTS)
async def test_hidden_catalog_keys_are_really_rejected(
    real_catalog: dict[str, PackageEndpoint], endpoint_type: str
) -> None:
    """帮助不展示这些键的前提，是预检真的拒绝它们（否则是欠宣传）。"""
    endpoint = real_catalog[endpoint_type]
    contract = contract_for(
        endpoint_type, endpoint.required_params, endpoint.optional_params
    )
    base = {group[0]: "probe-value" for group in contract.required_groups}
    for key in EXPECTED[endpoint_type]["must_not_appear"]:
        result = await _preflight(endpoint_type, {**base, key: "probe-value"})
        assert result.allowed is False, f"{endpoint_type} 其实接受 {key}，帮助不该隐藏它"
        assert any(key in error for error in result.errors), result.errors


async def test_normal_non_drift_endpoint_is_unchanged(
    real_catalog: dict[str, PackageEndpoint],
) -> None:
    """非漂移端点保持原样：Exa 搜索没有别名，必填仍是 query，可选仍是目录声明。"""
    endpoint = real_catalog["exa_search_auto"]
    text = await shusuo_capabilities.describe_text("exa_search_auto")
    assert _describe_field(text, "必填参数") == "query"
    assert set(_optional_keys(text)) == set(endpoint.optional_params)

    listing = await shusuo_capabilities.capabilities_text("exa_search_auto")
    assert "必填：query" in listing


async def test_non_drift_tikhub_endpoint_keeps_catalog_keys(
    real_catalog: dict[str, PackageEndpoint],
) -> None:
    """非漂移 TikHub 端点：目录声明的必填与可选仍在，只是多了别名组写法。"""
    text = await shusuo_capabilities.describe_text("tikhub_reddit_search")
    required = _describe_field(text, "必填参数")
    assert "keyword" in required
    assert "query" in required
    assert "max_items" in _optional_keys(text)


async def test_endpoint_without_required_params_says_none(
    real_catalog: dict[str, PackageEndpoint],
) -> None:
    """无必填端点仍写「无」，且目录声明的可选参数一个不少。"""
    endpoint = real_catalog["tikhub_x_trending"]
    assert endpoint.required_params == ()
    text = await shusuo_capabilities.describe_text("tikhub_x_trending")
    assert _describe_field(text, "必填参数") == "无"
    assert set(_optional_keys(text)) == set(endpoint.optional_params)


@pytest.mark.parametrize("endpoint_type", DRIFT_ENDPOINTS)
async def test_help_optional_keys_never_include_required_aliases(
    real_catalog: dict[str, PackageEndpoint], endpoint_type: str
) -> None:
    """必填组里的别名不能又出现在可选里（同一键两种身份会让用户困惑）。"""
    endpoint = real_catalog[endpoint_type]
    contract = contract_for(
        endpoint_type, endpoint.required_params, endpoint.optional_params
    )
    required_keys = {key for group in contract.required_groups for key in group}
    text = await shusuo_capabilities.describe_text(endpoint_type)
    assert not required_keys & set(_optional_keys(text))


async def test_describe_optional_keys_are_sorted(
    real_catalog: dict[str, PackageEndpoint],
) -> None:
    """可选参数顺序确定：两次渲染完全一致，且按字典序。"""
    first = _optional_keys(await shusuo_capabilities.describe_text("exa_search_auto"))
    second = _optional_keys(await shusuo_capabilities.describe_text("exa_search_auto"))
    assert first == second
    assert list(first) == sorted(first)
