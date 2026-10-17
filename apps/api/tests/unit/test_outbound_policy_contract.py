"""Regression checks for policy classification and trusted approval input."""

from __future__ import annotations

import json

import pytest

from data_intelligence_hub.collectors.outbound_policy import (
    GUARDED_HTTP_COLLECTORS,
    OFFLINE_COLLECTORS,
    PROVIDER_API_COLLECTORS,
    UNSUPPORTED_COLLECTORS,
    canonical_host,
)
from data_intelligence_hub.collectors.registry import COLLECTOR_REGISTRY
from data_intelligence_hub.core.config import get_settings


def test_every_registered_collector_has_an_explicit_policy() -> None:
    groups = [
        OFFLINE_COLLECTORS,
        GUARDED_HTTP_COLLECTORS,
        PROVIDER_API_COLLECTORS,
        UNSUPPORTED_COLLECTORS,
    ]
    classified = set().union(*groups)
    assert set(COLLECTOR_REGISTRY) == classified
    assert sum(map(len, groups)) == len(classified)


@pytest.mark.parametrize(
    "value",
    [
        "*.example.com",
        "com",
        "example.com:443",
        "https://example.com",
        "127.0.0.1",
        "::1",
        "user@example.com",
        "x.onion",
        " x.com",
    ],
)
def test_approval_host_rejects_wildcards_ips_and_urls(value: str) -> None:
    with pytest.raises(ValueError):
        canonical_host(value)


def test_exact_host_is_normalized_consistently() -> None:
    assert canonical_host("EXAMPLE.COM.") == "example.com"
    assert canonical_host("bücher.example") == "xn--bcher-kva.example"


def test_host_level_check_blocks_unapproved_fixed_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """固定目标不在批准列表时，目录必须如实阻断。

    类型级检查只回答「这个 collector 有没有有效批准」，不看具体主机。
    只做类型级判断会把未批准的主机显示成可用，用户点采集才失败。
    """
    from data_intelligence_hub.collectors.outbound_policy import host_block_reason

    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    monkeypatch.setenv(
        "COLLECTION_HTTP_GRANTS",
        json.dumps(
            [
                {
                    "collector_type": "public_feed",
                    "hosts": ["approved.example"],
                    "expires_at": "2099-01-01T00:00:00Z",
                }
            ]
        ),
    )
    get_settings.cache_clear()
    try:
        assert host_block_reason("public_feed", "https://approved.example/feed") is None
        reason = host_block_reason("public_feed", "https://other.example/feed")
        assert reason is not None
        assert reason.startswith("outbound_domain_denied:")
        assert "other.example" in reason
    finally:
        get_settings.cache_clear()


def test_host_level_check_ignores_target_supplied_by_caller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """目标由调用方传入时无法预判，按类型级结论处理。"""
    from data_intelligence_hub.collectors.outbound_policy import host_block_reason

    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    monkeypatch.setenv("COLLECTION_HTTP_GRANTS", "[]")
    get_settings.cache_clear()
    try:
        reason = host_block_reason("public_feed", None)
        assert reason is not None
        assert reason.startswith("collection_policy_denied:")
    finally:
        get_settings.cache_clear()


def test_host_level_check_does_not_gate_non_http_collectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider API 类不走域名批准，不该因 URL 被拦。"""
    from data_intelligence_hub.collectors.outbound_policy import host_block_reason

    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    monkeypatch.setenv("COLLECTION_HTTP_GRANTS", "[]")
    get_settings.cache_clear()
    try:
        assert host_block_reason("exa_search", "https://api.exa.ai/search") is None
    finally:
        get_settings.cache_clear()
