"""Regression checks for policy classification and trusted approval input."""

from __future__ import annotations

import pytest

from data_intelligence_hub.collectors.outbound_policy import (
    GUARDED_HTTP_COLLECTORS,
    OFFLINE_COLLECTORS,
    PROVIDER_API_COLLECTORS,
    UNSUPPORTED_COLLECTORS,
    canonical_host,
)
from data_intelligence_hub.collectors.registry import COLLECTOR_REGISTRY


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
