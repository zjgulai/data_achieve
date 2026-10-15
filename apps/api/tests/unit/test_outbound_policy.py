"""外访策略必须在实例化/联网之前拒绝，不能接受调用方自报批准。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.collectors.registry import build_collector
from data_intelligence_hub.core.config import Settings, get_settings


@pytest.fixture(autouse=True)
def isolated_policy(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("COLLECTION_NETWORK_MODE", raising=False)
    monkeypatch.delenv("COLLECTION_HTTP_GRANTS", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_local_collection_defaults_to_offline() -> None:
    with pytest.raises(CollectorError, match="collection_policy_denied"):
        build_collector("apify_actor", {"actor_id": "owner/actor", "actor_input": {}})


@pytest.mark.parametrize(
    "collector_type",
    [
        "aliens_eye_basic",
        "aliens_eye_advanced",
        "aliens_eye_recurse",
        "aliens_eye_batch",
        "maigret",
        "sherlock",
        "blackbird_username_osint",
        "spiderfoot_domain_osint",
        "robin_darkweb_search",
        "browser_use_task",
        "playwright_browser",
    ],
)
def test_uncontrolled_collectors_cannot_be_unlocked_by_request(
    monkeypatch: pytest.MonkeyPatch,
    collector_type: str,
) -> None:
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    get_settings.cache_clear()
    with pytest.raises(CollectorError, match="collection_policy_denied"):
        build_collector(
            collector_type,
            {
                "approved": True,
                "safety_approved": True,
                "allowed_domains": ["example.com"],
                "max_requests": 1,
                "sites": ["GitHub"],
                "endpoint_type": "manual_json",
            },
        )


def test_manual_json_remains_available_offline() -> None:
    collector = build_collector("manual_json", {"records": []})
    assert collector.collector_type == "manual_json"


def test_unknown_network_mode_does_not_silently_enable_network() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, collection_network_mode="unrestricted")


def test_restricted_generic_web_requires_server_grant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    get_settings.cache_clear()
    with pytest.raises(CollectorError, match="collection_policy_denied"):
        build_collector("generic_web", {"url": "https://example.com", "approved": True})
