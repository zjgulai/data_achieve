from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SocialAdapterMetadata:
    provider_id: str
    platform: str
    sdk_package: str
    sdk_import_name: str | None
    adapter_module: str
    supports_fixture_replay: bool = True
    supports_live_client: bool = False


def build_fixture_operations(
    *,
    provider_id: str,
    endpoints: list[str],
    fixture_limit: int,
    sdk_package: str | None,
) -> list[dict[str, Any]]:
    return [
        {
            "operation_id": f"fixture:{provider_id}:{endpoint}",
            "endpoint": endpoint,
            "sdk_package": sdk_package,
            "request_mode": "fixture_replay",
            "fixture_record_count": fixture_limit,
            "provider_call": False,
        }
        for endpoint in endpoints
        if endpoint.strip()
    ]
