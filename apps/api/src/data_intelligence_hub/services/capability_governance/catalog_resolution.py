from __future__ import annotations

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.capability_governance import CapabilityCatalogHead
from data_intelligence_hub.repositories.capability_governance import (
    get_catalog_head,
    get_catalog_snapshot,
    get_publication_revision,
)
from data_intelligence_hub.schemas.capability_catalog import CapabilityCatalog
from data_intelligence_hub.services.capability_catalog import get_capability_catalog
from data_intelligence_hub.services.workflow_planner.fingerprint import (
    compute_catalog_snapshot_id,
)


class CapabilityCatalogResolutionError(Exception):
    code = "catalog_snapshot_invalid"
    message = code


async def resolve_capability_catalog_for_head(
    session: AsyncSession,
    head: CapabilityCatalogHead,
) -> CapabilityCatalog:
    if head.current_revision_id is None:
        if head.head_version != 0:
            raise CapabilityCatalogResolutionError
        return get_capability_catalog()
    revision = await get_publication_revision(session, head.current_revision_id)
    if revision is None or revision.revision_number != head.head_version:
        raise CapabilityCatalogResolutionError
    snapshot = await get_catalog_snapshot(session, revision.catalog_snapshot_id)
    if snapshot is None:
        raise CapabilityCatalogResolutionError
    try:
        catalog = CapabilityCatalog.model_validate(snapshot.catalog_payload)
    except (TypeError, ValueError, ValidationError) as exc:
        raise CapabilityCatalogResolutionError from exc
    if compute_catalog_snapshot_id(catalog) != snapshot.catalog_snapshot_id:
        raise CapabilityCatalogResolutionError
    return catalog


async def resolve_current_capability_catalog(
    session: AsyncSession,
) -> CapabilityCatalog:
    head = await get_catalog_head(session)
    if head is None:
        raise CapabilityCatalogResolutionError
    return await resolve_capability_catalog_for_head(session, head)


__all__ = [
    "CapabilityCatalogResolutionError",
    "resolve_capability_catalog_for_head",
    "resolve_current_capability_catalog",
]
