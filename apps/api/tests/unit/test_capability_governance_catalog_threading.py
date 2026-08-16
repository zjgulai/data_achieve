from __future__ import annotations

from data_intelligence_hub.schemas.capability_catalog import CapabilityCatalog
from data_intelligence_hub.services.capability_catalog import (
    get_capability_catalog,
    project_external_provider_catalog_v1,
)
from data_intelligence_hub.services.capability_matrix import (
    build_capability_matrix,
    get_capability_implementation_detail,
    list_capability_assertions,
    list_capability_implementations,
)
from data_intelligence_hub.services.social_provider import get_social_provider_catalog


def _overlay_catalog() -> CapabilityCatalog:
    base = get_capability_catalog()
    source_implementation = base.implementations[0]
    source_assertion = next(
        item
        for item in base.assertions
        if item.implementation_id == source_implementation.implementation_id
    )
    implementation = source_implementation.model_copy(
        update={
            "implementation_id": "governance.synthetic.v1",
            "provider_id": "governance.synthetic",
        },
        deep=True,
    )
    assertion = source_assertion.model_copy(
        update={
            "assertion_id": "governance.synthetic.assertion.v1",
            "implementation_id": implementation.implementation_id,
        },
        deep=True,
    )
    return CapabilityCatalog.model_validate(
        base.model_copy(
            update={
                "implementations": [*base.implementations, implementation],
                "assertions": [*base.assertions, assertion],
            },
            deep=True,
        ).model_dump(mode="json")
    )


def test_matrix_list_detail_and_provider_projection_share_explicit_catalog() -> None:
    base = get_capability_catalog()
    overlay = _overlay_catalog()

    matrix = build_capability_matrix(catalog=overlay)
    implementations = list_capability_implementations(catalog=overlay)
    assertions = list_capability_assertions(catalog=overlay)
    detail = get_capability_implementation_detail(
        "governance.synthetic.v1",
        catalog=overlay,
    )
    projected = project_external_provider_catalog_v1(catalog=overlay)
    social = get_social_provider_catalog(catalog=overlay)

    assert matrix.summary.cell_count == 42
    assert matrix.summary.implementation_count == len(base.implementations) + 1
    assert matrix.summary.assertion_count == len(base.assertions) + 1
    assert implementations[-1].implementation_id == "youtube.v3"
    assert {item.implementation_id for item in implementations} >= {"governance.synthetic.v1"}
    assert {item.assertion_id for item in assertions} >= {"governance.synthetic.assertion.v1"}
    assert detail.implementation.implementation_id == "governance.synthetic.v1"
    assert {item.provider_id for item in projected.providers} >= {"governance.synthetic"}
    assert {item.provider_id for item in social.providers} >= {"governance.synthetic"}
    assert get_capability_catalog() == base
