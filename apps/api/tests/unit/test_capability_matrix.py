from __future__ import annotations

from collections import Counter

import pytest

from data_intelligence_hub.schemas.capability_catalog import (
    AccessChannel,
    CapabilityOperation,
    CapabilityStatus,
    PlatformId,
    ResourceType,
)
from data_intelligence_hub.services import capability_matrix as capability_matrix_service
from data_intelligence_hub.services.capability_catalog import get_capability_catalog
from data_intelligence_hub.services.capability_matrix import (
    build_capability_matrix,
    get_capability_implementation_detail,
    list_capability_assertions,
    list_capability_implementations,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityImplementationNotFoundError,
)


def test_capability_matrix_has_locked_dimensions_and_summary() -> None:
    matrix = build_capability_matrix()

    assert matrix.schema_version == "capability_matrix.v1"
    assert matrix.platforms == list(PlatformId)
    assert matrix.access_channels == list(AccessChannel)
    assert len(matrix.platforms) == 7
    assert len(matrix.access_channels) == 6
    assert len(matrix.cells) == 42
    assert matrix.summary.cell_count == 42
    assert matrix.summary.populated_cell_count == 7
    assert matrix.summary.unknown_cell_count == 35
    assert matrix.summary.implementation_count == 7
    assert matrix.summary.assertion_count == 35
    assert matrix.summary.evidence_count == 14
    assert matrix.provider_call is False
    assert matrix.production_write_allowed is False


def test_official_authorized_api_cells_are_candidate_and_evidenced() -> None:
    matrix = build_capability_matrix()
    cells = [
        cell
        for cell in matrix.cells
        if cell.access_channel is AccessChannel.OFFICIAL_AUTHORIZED_API
    ]

    assert len(cells) == 7
    assert all(cell.summary_status is CapabilityStatus.CANDIDATE for cell in cells)
    assert all(cell.assertion_ids for cell in cells)
    assert all(cell.evidence_count > 0 for cell in cells)


def test_youtube_matrix_cell_aggregates_constraints_evidence_and_recency() -> None:
    catalog = get_capability_catalog()
    assertions = [
        assertion
        for assertion in catalog.assertions
        if assertion.implementation_id == "youtube.v3"
    ]
    cell = next(
        cell
        for cell in build_capability_matrix().cells
        if cell.platform is PlatformId.YOUTUBE
        and cell.access_channel is AccessChannel.OFFICIAL_AUTHORIZED_API
    )

    assert cell.constraint_codes == sorted(
        {constraint.code for assertion in assertions for constraint in assertion.constraints}
    )
    assert cell.evidence_count == len(
        {evidence_ref for assertion in assertions for evidence_ref in assertion.evidence_refs}
    )
    assert cell.last_verified_at == max(
        assertion.last_verified_at for assertion in assertions
    )


def test_summary_status_prioritizes_verified_without_losing_candidate_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = get_capability_catalog()
    source_assertion = next(
        assertion
        for assertion in catalog.assertions
        if assertion.implementation_id == "youtube.v3"
    )
    verified_assertion = source_assertion.model_copy(
        update={
            "assertion_id": f"{source_assertion.assertion_id}:verified",
            "support_status": CapabilityStatus.VERIFIED,
        }
    )
    mixed_catalog = catalog.model_copy(
        update={"assertions": [*catalog.assertions, verified_assertion]}
    )
    monkeypatch.setattr(
        capability_matrix_service,
        "get_capability_catalog",
        lambda: mixed_catalog.model_copy(deep=True),
    )

    cell = next(
        cell
        for cell in build_capability_matrix().cells
        if cell.platform is PlatformId.YOUTUBE
        and cell.access_channel is AccessChannel.OFFICIAL_AUTHORIZED_API
    )

    assert cell.summary_status is CapabilityStatus.VERIFIED
    assert cell.status_counts[CapabilityStatus.CANDIDATE] == 5
    assert cell.status_counts[CapabilityStatus.VERIFIED] == 1

    expected_priority = (
        CapabilityStatus.VERIFIED,
        CapabilityStatus.PARTIAL,
        CapabilityStatus.CANDIDATE,
        CapabilityStatus.BLOCKED,
        CapabilityStatus.UNSUPPORTED,
        CapabilityStatus.DEPRECATED,
        CapabilityStatus.UNKNOWN,
    )
    for higher_index, higher_status in enumerate(expected_priority):
        for lower_status in expected_priority[higher_index + 1 :]:
            counts = Counter({lower_status: 1, higher_status: 1})
            assert capability_matrix_service._summary_status(counts) is higher_status
    assert (
        capability_matrix_service._summary_status(Counter())
        is CapabilityStatus.UNKNOWN
    )


def test_unknown_matrix_cell_is_explicit_and_empty() -> None:
    cell = next(
        cell
        for cell in build_capability_matrix().cells
        if cell.platform is PlatformId.YOUTUBE
        and cell.access_channel is AccessChannel.AUTHORIZED_BROWSER
    )

    assert cell.summary_status is CapabilityStatus.UNKNOWN
    assert cell.status_counts == {CapabilityStatus.UNKNOWN: 1}
    assert cell.implementation_ids == []
    assert cell.assertion_ids == []
    assert cell.evidence_count == 0
    assert cell.last_verified_at is None


def test_capability_filters_are_exact_and_do_not_mutate_catalog() -> None:
    catalog_before = get_capability_catalog()

    all_implementations = list_capability_implementations()
    all_assertions = list_capability_assertions()
    assertions = list_capability_assertions(
        platform=PlatformId.YOUTUBE,
        access_channel=AccessChannel.OFFICIAL_AUTHORIZED_API,
        resource_type=ResourceType.CONVERSATION,
        operation=CapabilityOperation.LIST_ENUMERATE,
        support_status=CapabilityStatus.CANDIDATE,
    )
    implementations = list_capability_implementations(
        platform=PlatformId.YOUTUBE,
        access_channel=AccessChannel.OFFICIAL_AUTHORIZED_API,
    )

    all_implementation_ids = [
        implementation.implementation_id for implementation in all_implementations
    ]
    all_assertion_ids = [assertion.assertion_id for assertion in all_assertions]
    assert len(all_implementation_ids) > 1
    assert all_implementation_ids == sorted(all_implementation_ids)
    assert len(all_assertion_ids) > 1
    assert all_assertion_ids == sorted(all_assertion_ids)
    assert [assertion.assertion_id for assertion in assertions] == [
        "youtube.v3:conversation:list_enumerate:comment_threads"
    ]
    assert [implementation.implementation_id for implementation in implementations] == [
        "youtube.v3"
    ]
    assert get_capability_catalog() == catalog_before


def test_capability_implementation_detail_and_not_found_error() -> None:
    detail = get_capability_implementation_detail("youtube.v3")

    assert detail.schema_version == "capability_implementation_detail.v1"
    assert detail.implementation.implementation_id == "youtube.v3"
    assert len(detail.assertions) == 5
    assertion_ids = [assertion.assertion_id for assertion in detail.assertions]
    evidence_ids = [evidence.evidence_id for evidence in detail.evidence]
    evidence_refs = {
        evidence_ref
        for assertion in detail.assertions
        for evidence_ref in assertion.evidence_refs
    }
    assert assertion_ids == sorted(assertion_ids)
    assert evidence_ids == sorted(evidence_ids)
    assert set(evidence_ids) == evidence_refs

    with pytest.raises(CapabilityImplementationNotFoundError):
        get_capability_implementation_detail("missing-provider")
