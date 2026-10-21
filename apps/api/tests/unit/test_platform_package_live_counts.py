"""Live verified counts for platform packages."""

from __future__ import annotations

from data_intelligence_hub.api.routes.platform_packages import (
    _apply_live_verified_counts,
)
from data_intelligence_hub.platform_packages.models import (
    PackageEndpoint,
    PlatformPackage,
)
from data_intelligence_hub.platform_packages.status import (
    EndpointAvailability,
    ProviderStatusResponse,
)


def _endpoint(endpoint_type: str, status: str) -> PackageEndpoint:
    return PackageEndpoint(
        capability_id=endpoint_type,
        canonical_capability_id=endpoint_type,
        is_alias_view=False,
        endpoint_type=endpoint_type,
        label=endpoint_type,
        platform="tiktok",
        description="test",
        status=status,
        required_params=(),
        optional_params=(),
        cost_hint=None,
        provider="test",
        provider_group="test",
        provider_label="test",
        content_type="post",
        method="GET",
        param_fields={},
    )


def _package() -> PlatformPackage:
    return PlatformPackage(
        platform_id="tiktok",
        display_name="TikTok",
        description="test",
        endpoint_count=3,
        verified_count=3,
        disabled_count=0,
        provider_groups=("test",),
        methods=("GET",),
        content_types=("post",),
        endpoints=(
            _endpoint("a", "verified"),
            _endpoint("b", "verified"),
            _endpoint("c", "pending"),
        ),
        skill_path="generated/tiktok",
        playbook_path="docs/tiktok.md",
        detail_path="/tools/tiktok",
    )


def _status(endpoint_type: str, availability: str) -> EndpointAvailability:
    return EndpointAvailability(
        endpoint_type=endpoint_type,
        availability=availability,  # type: ignore[arg-type]
        missing_configuration=(),
        last_test_status="success",
        last_test_at=None,
        last_records_count=1,
        last_error_message=None,
    )


def test_static_verified_count_is_replaced_by_live_evidence() -> None:
    statuses = ProviderStatusResponse(
        catalog_digest="test",
        endpoints=(
            _status("a", "verified"),
            _status("b", "empty"),
            _status("c", "untested"),
        ),
    )
    package = _apply_live_verified_counts((_package(),), statuses)[0]
    assert package.verified_count == 1


def test_missing_evidence_counts_as_not_verified() -> None:
    statuses = ProviderStatusResponse(catalog_digest="test", endpoints=())
    package = _apply_live_verified_counts((_package(),), statuses)[0]
    assert package.verified_count == 0
