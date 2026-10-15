"""A past successful run must not make a policy-blocked collector look executable."""

from __future__ import annotations

import asyncio

import pytest

from data_intelligence_hub.api.routes.collectors import get_collector_catalog
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.platform_packages.builder import build_platform_package_catalog
from data_intelligence_hub.platform_packages.status import EndpointEvidence, build_provider_status


def test_policy_block_overrides_past_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    get_settings.cache_clear()
    try:
        catalog = build_platform_package_catalog(asyncio.run(get_collector_catalog()))
        result = build_provider_status(
            catalog,
            configured={},
            evidence={
                "aliens_eye_basic": EndpointEvidence(status="success", records_count=10),
            },
        )
        row = next(r for r in result.endpoints if r.endpoint_type == "aliens_eye_basic")
        assert row.availability == "config-gated"
        assert row.policy_block_reason.startswith("collection_policy_denied:")
        assert row.last_records_count == 10
    finally:
        get_settings.cache_clear()


def test_catalog_preserves_identity_but_exposes_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    get_settings.cache_clear()
    try:
        catalog = asyncio.run(get_collector_catalog())
        row = next(
            e
            for c in catalog.collectors
            for e in c.endpoints
            if e.endpoint_type == "aliens_eye_basic"
        )
        assert row.policy_block_reason.startswith("collection_policy_denied:")
        assert row.endpoint_type == "aliens_eye_basic"
        package = next(
            p
            for p in build_platform_package_catalog(catalog).packages
            if any(e.endpoint_type == "aliens_eye_basic" for e in p.endpoints)
        )
        assert package.verified_count == sum(
            e.status == "verified" and not e.policy_block_reason for e in package.endpoints
        )
    finally:
        get_settings.cache_clear()
