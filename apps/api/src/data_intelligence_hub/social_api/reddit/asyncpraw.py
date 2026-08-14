from __future__ import annotations

from typing import Any

from data_intelligence_hub.social_api.contracts import (
    SocialAdapterMetadata,
    build_fixture_operations,
)

_METADATA = SocialAdapterMetadata(
    provider_id="reddit.praw",
    platform="reddit",
    sdk_package="asyncpraw",
    sdk_import_name="asyncpraw",
    adapter_module="data_intelligence_hub.social_api.reddit.asyncpraw",
)


def adapter_metadata() -> SocialAdapterMetadata:
    return _METADATA


def plan_fixture_operations(
    *,
    endpoints: list[str],
    fixture_limit: int,
) -> list[dict[str, Any]]:
    return build_fixture_operations(
        provider_id=_METADATA.provider_id,
        endpoints=endpoints,
        fixture_limit=fixture_limit,
        sdk_package=_METADATA.sdk_package,
    )
