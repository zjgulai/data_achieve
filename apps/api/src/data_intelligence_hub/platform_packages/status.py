from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from data_intelligence_hub.platform_packages.models import PlatformPackageCatalog

Availability = Literal[
    "verified", "config-gated", "degraded", "empty", "untested", "disabled"
]


class EndpointEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: str
    finished_at: datetime | None = None
    records_count: int | None = None
    error_message: str | None = None


class EndpointAvailability(BaseModel):
    model_config = ConfigDict(frozen=True)
    endpoint_type: str
    availability: Availability
    missing_configuration: tuple[str, ...]
    last_test_status: str | None
    last_test_at: datetime | None
    last_records_count: int | None
    last_error_message: str | None


class ProviderStatusResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    catalog_digest: str
    endpoints: tuple[EndpointAvailability, ...]


GROUP_REQUIREMENTS: dict[str, tuple[tuple[str, ...], ...]] = {
    "tikhub_social": (("TIKHUB_API_KEY",),),
    "apify_actor": (("APIFY_API_TOKEN",),),
    "anysearch": (("ANYSEARCH_API_KEY",),),
    "exa": (("EXA_API_KEY",),),
    "jina_reader": (("JINA_API_KEY",),),
    "firecrawl": (("FIRECRAWL_API_KEY",),),
    "bestblogs": (("BESTBLOGS_API_KEY",),),
    "blackbird": (("BLACKBIRD_BASE_URL",),),
    "twscrape": (("TWITTER_ACCOUNTS_JSON", "TWITTER_ACCOUNTS_FILE"),),
    "browser_use": (("ANTHROPIC_API_KEY", "OPENAI_API_KEY"),),
}


def build_provider_status(
    catalog: PlatformPackageCatalog,
    configured: Mapping[str, bool],
    evidence: Mapping[str, EndpointEvidence],
) -> ProviderStatusResponse:
    endpoint_map: dict[str, EndpointAvailability] = {}
    for package in catalog.packages:
        for endpoint in package.endpoints:
            if endpoint.endpoint_type in endpoint_map:
                continue
            required_groups = GROUP_REQUIREMENTS.get(endpoint.provider_group, ())
            missing = tuple(
                "/".join(group)
                for group in required_groups
                if not any(configured.get(name, False) for name in group)
            )
            latest = evidence.get(endpoint.endpoint_type)
            if endpoint.status == "disabled":
                availability: Availability = "disabled"
            elif missing:
                availability = "config-gated"
            elif latest is None:
                # 没有任何实测证据：不得谎报 verified，标记为 untested。
                availability = "untested"
            elif latest.status not in {"success", "ok"}:
                availability = "degraded"
            elif not (latest.records_count or 0):
                # 运行成功但 0 条记录：不能算验证通过（演示参数或上游返回空）。
                availability = "empty"
            else:
                availability = "verified"
            endpoint_map[endpoint.endpoint_type] = EndpointAvailability(
                endpoint_type=endpoint.endpoint_type,
                availability=availability,
                missing_configuration=missing,
                last_test_status=latest.status if latest else None,
                last_test_at=latest.finished_at if latest else None,
                last_records_count=latest.records_count if latest else None,
                last_error_message=latest.error_message if latest else None,
            )
    return ProviderStatusResponse(
        catalog_digest=catalog.catalog_digest,
        endpoints=tuple(endpoint_map[key] for key in sorted(endpoint_map)),
    )
