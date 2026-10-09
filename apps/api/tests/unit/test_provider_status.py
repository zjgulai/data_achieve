from __future__ import annotations

import asyncio

from data_intelligence_hub.api.routes.collectors import get_collector_catalog
from data_intelligence_hub.platform_packages.builder import build_platform_package_catalog
from data_intelligence_hub.platform_packages.status import (
    EndpointEvidence,
    build_provider_status,
)


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
