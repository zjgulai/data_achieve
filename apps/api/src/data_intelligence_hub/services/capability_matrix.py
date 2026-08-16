from __future__ import annotations

from collections import Counter

from data_intelligence_hub.schemas.capability_catalog import (
    AccessChannel,
    CapabilityAssertion,
    CapabilityCatalog,
    CapabilityImplementation,
    CapabilityOperation,
    CapabilityStatus,
    PlatformId,
    ResourceType,
)
from data_intelligence_hub.schemas.capability_matrix import (
    CapabilityImplementationDetail,
    CapabilityMatrixCell,
    CapabilityMatrixResponse,
    CapabilityMatrixSummary,
)
from data_intelligence_hub.services.capability_catalog import get_capability_catalog
from data_intelligence_hub.services.exceptions import (
    CapabilityImplementationNotFoundError,
)

STATUS_PRIORITY = (
    CapabilityStatus.VERIFIED,
    CapabilityStatus.PARTIAL,
    CapabilityStatus.CANDIDATE,
    CapabilityStatus.BLOCKED,
    CapabilityStatus.UNSUPPORTED,
    CapabilityStatus.DEPRECATED,
    CapabilityStatus.UNKNOWN,
)


def _summary_status(
    counts: Counter[CapabilityStatus],
) -> CapabilityStatus:
    for status in STATUS_PRIORITY:
        if counts[status] > 0:
            return status
    return CapabilityStatus.UNKNOWN


def build_capability_matrix(
    *,
    catalog: CapabilityCatalog | None = None,
) -> CapabilityMatrixResponse:
    catalog = catalog or get_capability_catalog()
    cells: list[CapabilityMatrixCell] = []

    for platform in PlatformId:
        for access_channel in AccessChannel:
            implementations = [
                implementation
                for implementation in catalog.implementations
                if implementation.platform is platform
                and implementation.access_channel is access_channel
            ]
            implementation_ids = {
                implementation.implementation_id for implementation in implementations
            }
            assertions = [
                assertion
                for assertion in catalog.assertions
                if assertion.implementation_id in implementation_ids
            ]
            status_counts = Counter(assertion.support_status for assertion in assertions)
            if not assertions:
                status_counts[CapabilityStatus.UNKNOWN] = 1
            evidence_refs = {
                evidence_ref for assertion in assertions for evidence_ref in assertion.evidence_refs
            }
            cells.append(
                CapabilityMatrixCell(
                    platform=platform,
                    access_channel=access_channel,
                    summary_status=_summary_status(status_counts),
                    status_counts=dict(status_counts),
                    implementation_ids=sorted(implementation_ids),
                    assertion_ids=sorted(assertion.assertion_id for assertion in assertions),
                    resource_types=sorted(
                        {assertion.resource_type for assertion in assertions},
                        key=lambda resource_type: resource_type.value,
                    ),
                    operations=sorted(
                        {assertion.operation for assertion in assertions},
                        key=lambda operation: operation.value,
                    ),
                    constraint_codes=sorted(
                        {
                            constraint.code
                            for assertion in assertions
                            for constraint in assertion.constraints
                        }
                    ),
                    evidence_count=len(evidence_refs),
                    last_verified_at=max(
                        (assertion.last_verified_at for assertion in assertions),
                        default=None,
                    ),
                )
            )

    populated_cell_count = sum(1 for cell in cells if cell.assertion_ids)
    return CapabilityMatrixResponse(
        schema_version="capability_matrix.v1",
        generated_at=catalog.generated_at,
        evidence_level=catalog.evidence_level,
        provider_call=False,
        production_write_allowed=False,
        platforms=list(PlatformId),
        access_channels=list(AccessChannel),
        cells=cells,
        summary=CapabilityMatrixSummary(
            cell_count=42,
            populated_cell_count=populated_cell_count,
            unknown_cell_count=42 - populated_cell_count,
            implementation_count=len(catalog.implementations),
            assertion_count=len(catalog.assertions),
            evidence_count=len(catalog.evidence),
        ),
    )


def list_capability_implementations(
    *,
    platform: PlatformId | None = None,
    access_channel: AccessChannel | None = None,
    catalog: CapabilityCatalog | None = None,
) -> list[CapabilityImplementation]:
    catalog = catalog or get_capability_catalog()
    implementations = [
        implementation
        for implementation in catalog.implementations
        if (platform is None or implementation.platform is platform)
        and (access_channel is None or implementation.access_channel is access_channel)
    ]
    return sorted(
        implementations,
        key=lambda implementation: implementation.implementation_id,
    )


def list_capability_assertions(
    *,
    platform: PlatformId | None = None,
    access_channel: AccessChannel | None = None,
    resource_type: ResourceType | None = None,
    operation: CapabilityOperation | None = None,
    support_status: CapabilityStatus | None = None,
    catalog: CapabilityCatalog | None = None,
) -> list[CapabilityAssertion]:
    catalog = catalog or get_capability_catalog()
    implementation_ids = {
        implementation.implementation_id
        for implementation in catalog.implementations
        if (platform is None or implementation.platform is platform)
        and (access_channel is None or implementation.access_channel is access_channel)
    }
    assertions = [
        assertion
        for assertion in catalog.assertions
        if assertion.implementation_id in implementation_ids
        and (resource_type is None or assertion.resource_type is resource_type)
        and (operation is None or assertion.operation is operation)
        and (support_status is None or assertion.support_status is support_status)
    ]
    return sorted(assertions, key=lambda assertion: assertion.assertion_id)


def get_capability_implementation_detail(
    implementation_id: str,
    *,
    catalog: CapabilityCatalog | None = None,
) -> CapabilityImplementationDetail:
    catalog = catalog or get_capability_catalog()
    implementation = next(
        (item for item in catalog.implementations if item.implementation_id == implementation_id),
        None,
    )
    if implementation is None:
        raise CapabilityImplementationNotFoundError

    assertions = sorted(
        (
            assertion
            for assertion in catalog.assertions
            if assertion.implementation_id == implementation_id
        ),
        key=lambda assertion: assertion.assertion_id,
    )
    evidence_refs = {
        evidence_ref for assertion in assertions for evidence_ref in assertion.evidence_refs
    }
    evidence = sorted(
        (item for item in catalog.evidence if item.evidence_id in evidence_refs),
        key=lambda item: item.evidence_id,
    )
    return CapabilityImplementationDetail(
        schema_version="capability_implementation_detail.v1",
        implementation=implementation,
        assertions=assertions,
        evidence=evidence,
    )
