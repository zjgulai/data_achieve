from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from data_intelligence_hub.api.routes.collectors import get_collector_catalog
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.platform_packages.builder import build_platform_package_catalog
from data_intelligence_hub.platform_packages.status import (
    EndpointEvidence,
    build_provider_status,
)


@pytest.fixture(autouse=True)
def restricted_catalog(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """目录页跑在 restricted 模式：provider_api 采集器可列目录，不触发离线拒绝。

    这些用例只验证"配置门控 / 证据分级"的纯函数逻辑，不联网；不固定模式的话，
    默认 offline 会把整张目录标成 policy config-gated，覆盖掉被测的可用性分级。
    新增的 policy 维度安全断言由父会话单独管理，本文件不重复。
    """
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    monkeypatch.delenv("COLLECTION_HTTP_GRANTS", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_provider_status_distinguishes_configuration_and_failures() -> None:
    source = asyncio.run(get_collector_catalog())
    catalog = build_platform_package_catalog(source)
    status = build_provider_status(
        catalog,
        configured={"TIKHUB_API_KEY": True, "APIFY_API_TOKEN": False},
        evidence={
            "tikhub_tiktok_video_search": EndpointEvidence(
                status="failed",
                error_message="upstream_timeout",
            )
        },
    )
    by_endpoint = {item.endpoint_type: item for item in status.endpoints}

    assert by_endpoint["apify_tiktok_scraper"].availability == "config-gated"
    assert by_endpoint["tikhub_tiktok_video_search"].availability == "degraded"
    assert by_endpoint["pypi_search"].availability == "disabled"
    # 无实测证据不得谎报 verified（本用例的 evidence 未覆盖 github_repo）
    assert by_endpoint["github_repo"].availability == "untested"
    assert by_endpoint["github_repo"].last_test_status is None


def test_provider_status_marks_verified_only_with_success_evidence() -> None:
    source = asyncio.run(get_collector_catalog())
    catalog = build_platform_package_catalog(source)
    status = build_provider_status(
        catalog,
        configured={"TIKHUB_API_KEY": True},
        evidence={
            "tikhub_tiktok_video_search": EndpointEvidence(
                status="success",
                records_count=3,
            )
        },
    )
    by_endpoint = {item.endpoint_type: item for item in status.endpoints}
    verified = by_endpoint["tikhub_tiktok_video_search"]
    assert verified.availability == "verified"
    assert verified.last_test_status == "success"
    assert verified.last_records_count == 3


def test_provider_status_treats_success_without_records_as_empty() -> None:
    source = asyncio.run(get_collector_catalog())
    catalog = build_platform_package_catalog(source)
    status = build_provider_status(
        catalog,
        configured={"TIKHUB_API_KEY": True},
        evidence={
            "tikhub_tiktok_video_search": EndpointEvidence(
                status="success",
                records_count=0,
            )
        },
    )
    by_endpoint = {item.endpoint_type: item for item in status.endpoints}
    assert by_endpoint["tikhub_tiktok_video_search"].availability == "empty"


def test_provider_status_marks_stale_verified_evidence() -> None:
    """SP-65:verified 证据超过 14 天 TTL 只降 freshness,不改 availability。

    availability 语义(最近一次实测成功)被数说 commands/MCP collect/
    platform-packages 路由依赖;时效判定走独立派生字段,行为兼容。
    """
    from datetime import UTC, datetime, timedelta

    source = asyncio.run(get_collector_catalog())
    catalog = build_platform_package_catalog(source)
    now = datetime.now(UTC)
    status = build_provider_status(
        catalog,
        configured={"TIKHUB_API_KEY": True},
        evidence={
            "tikhub_tiktok_video_search": EndpointEvidence(
                status="success",
                records_count=3,
                finished_at=now - timedelta(days=20),
            )
        },
        now=now,
    )
    endpoint = {item.endpoint_type: item for item in status.endpoints}[
        "tikhub_tiktok_video_search"
    ]
    # availability 不变(兼容),时效走 evidence_freshness
    assert endpoint.availability == "verified"
    assert endpoint.evidence_freshness == "stale"


def test_provider_status_marks_fresh_verified_evidence() -> None:
    from datetime import UTC, datetime, timedelta

    source = asyncio.run(get_collector_catalog())
    catalog = build_platform_package_catalog(source)
    now = datetime.now(UTC)
    status = build_provider_status(
        catalog,
        configured={"TIKHUB_API_KEY": True},
        evidence={
            "tikhub_tiktok_video_search": EndpointEvidence(
                status="success",
                records_count=3,
                finished_at=now - timedelta(days=2),
            )
        },
        now=now,
    )
    endpoint = {item.endpoint_type: item for item in status.endpoints}[
        "tikhub_tiktok_video_search"
    ]
    assert endpoint.availability == "verified"
    assert endpoint.evidence_freshness == "fresh"


def test_provider_status_non_verified_has_no_freshness() -> None:
    from datetime import UTC, datetime, timedelta

    source = asyncio.run(get_collector_catalog())
    catalog = build_platform_package_catalog(source)
    now = datetime.now(UTC)
    status = build_provider_status(
        catalog,
        configured={"TIKHUB_API_KEY": True},
        evidence={
            "tikhub_tiktok_video_search": EndpointEvidence(
                status="failed",
                error_message="upstream_timeout",
                finished_at=now - timedelta(days=2),
            )
        },
        now=now,
    )
    endpoint = {item.endpoint_type: item for item in status.endpoints}[
        "tikhub_tiktok_video_search"
    ]
    assert endpoint.availability == "degraded"
    assert endpoint.evidence_freshness is None


def test_provider_status_verified_without_timestamp_counts_stale() -> None:
    """没有时间戳的 verified 证据不可辩护,按 stale 处理。"""
    source = asyncio.run(get_collector_catalog())
    catalog = build_platform_package_catalog(source)
    status = build_provider_status(
        catalog,
        configured={"TIKHUB_API_KEY": True},
        evidence={
            "tikhub_tiktok_video_search": EndpointEvidence(
                status="success",
                records_count=3,
                finished_at=None,
            )
        },
    )
    endpoint = {item.endpoint_type: item for item in status.endpoints}[
        "tikhub_tiktok_video_search"
    ]
    assert endpoint.availability == "verified"
    assert endpoint.evidence_freshness == "stale"
