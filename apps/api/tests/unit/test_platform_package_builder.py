from __future__ import annotations

import asyncio

from data_intelligence_hub.api.routes.collectors import get_collector_catalog
from data_intelligence_hub.platform_packages.builder import build_platform_package_catalog


def test_builder_preserves_platform_views_and_counts_unique_endpoints() -> None:
    source = asyncio.run(get_collector_catalog())

    result = build_platform_package_catalog(source)

    endpoint_ids = [
        endpoint.endpoint_type
        for package in result.packages
        for endpoint in package.endpoints
    ]
    assert len(result.packages) == 74
    assert len(endpoint_ids) == 278
    assert len(set(endpoint_ids)) == 250
    assert result.source_entry_count == 278
    assert result.unique_endpoint_count == 250
    assert result.capability_count == 278
    regulatory = next(
        package for package in result.packages if package.platform_id == "regulatory"
    )
    assert {endpoint.endpoint_type for endpoint in regulatory.endpoints} == {"public_feed"}


def test_builder_is_deterministic() -> None:
    source = asyncio.run(get_collector_catalog())

    first = build_platform_package_catalog(source)
    second = build_platform_package_catalog(source)

    assert first == second
    assert len(first.catalog_digest) == 64
    assert [package.platform_id for package in first.packages] == sorted(
        package.platform_id for package in first.packages
    )
