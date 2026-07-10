from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityCatalog,
    PlatformId,
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
