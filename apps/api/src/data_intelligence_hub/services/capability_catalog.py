from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityCatalog,
    PlatformId,
)
from data_intelligence_hub.schemas.social_provider import (
    SocialProviderCatalogItem,
    SocialProviderCatalogResponse,
    SocialProviderEndpointItem,
    SocialProviderSdkSelection,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityCatalogLoadError,
    CapabilityCatalogUnknownPlatformError,
)

CATALOG_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "capability_catalog_overseas_v2.json"
)


@lru_cache(maxsize=1)
def _load_capability_catalog() -> CapabilityCatalog:
    try:
        return CapabilityCatalog.model_validate_json(
            CATALOG_PATH.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, ValidationError) as exc:
        raise CapabilityCatalogLoadError from exc


def clear_capability_catalog_cache() -> None:
    _load_capability_catalog.cache_clear()


def get_capability_catalog(platform: str | None = None) -> CapabilityCatalog:
    catalog = _load_capability_catalog().model_copy(deep=True)
    if platform is None:
        return catalog

    try:
        platform_id = PlatformId(platform.strip().lower())
    except ValueError as exc:
        raise CapabilityCatalogUnknownPlatformError from exc

    implementations = [
        item for item in catalog.implementations if item.platform == platform_id
    ]
    if not implementations:
        raise CapabilityCatalogUnknownPlatformError

    implementation_ids = {item.implementation_id for item in implementations}
    assertions = [
        item
        for item in catalog.assertions
        if item.implementation_id in implementation_ids
    ]
    evidence_refs = {
        evidence_ref
        for assertion in assertions
        for evidence_ref in assertion.evidence_refs
    }
    evidence = [
        item for item in catalog.evidence if item.evidence_id in evidence_refs
    ]
    return catalog.model_copy(
        update={
            "implementations": implementations,
            "assertions": assertions,
            "evidence": evidence,
        }
    )


def project_external_provider_catalog_v1() -> SocialProviderCatalogResponse:
    catalog = get_capability_catalog()
    providers: list[SocialProviderCatalogItem] = []
    for item in catalog.implementations:
        sdk_selection = None
        if item.sdk_selection is not None:
            sdk_selection = SocialProviderSdkSelection(
                package=item.sdk_selection.package,
                import_name=item.sdk_selection.import_name,
                source_url=item.sdk_selection.source_url,
                status=item.sdk_selection.status,
                reason=item.sdk_selection.reason,
            )
        providers.append(
            SocialProviderCatalogItem(
                provider_id=item.provider_id,
                platform=item.platform.value,
                data_domain=item.data_domains,
                resource_groups=item.resource_groups,
                official_docs=item.official_docs,
                sdk_selection=sdk_selection,
                live_adapter_strategy=item.live_adapter_strategy,
                auth_mode=item.auth_mode,
                quota_hint=item.quota_hint,
                policy_flags=item.policy_flags,
                blocked_actions=item.blocked_actions,
                stability=item.stability,
                self_host_priority=item.self_host_priority,
                api_version=item.api_version,
                required_credentials=item.required_credentials,
                supported_endpoints=item.supported_endpoints,
                endpoint_contracts=[
                    SocialProviderEndpointItem(endpoint_id=endpoint)
                    for endpoint in item.supported_endpoints
                ],
            )
        )
    return SocialProviderCatalogResponse(
        schema_version="external_provider_catalog.v1",
        evidence_level=catalog.evidence_level,
        provider_call=False,
        generated_at=catalog.generated_at.date().isoformat(),
        providers=providers,
    )
