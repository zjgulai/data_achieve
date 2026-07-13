from __future__ import annotations

import inspect
import json
from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityOperation,
    PlatformId,
    ResourceType,
)
from data_intelligence_hub.schemas.workflow_planner import (
    PlanningInput,
    RouteRequirement,
    WorkflowStepPlanningStatus,
    WorkflowStepPreview,
)
from data_intelligence_hub.services.exceptions import WorkflowPlannerTopologyError
from data_intelligence_hub.services.workflow_planner.candidate_expansion import (
    FixtureCandidateExpansionAdapter,
)
from data_intelligence_hub.services.workflow_planner.normalization import (
    NormalizationResult,
    normalize_planning_input,
)
from data_intelligence_hub.services.workflow_planner.query_compiler import (
    QueryCompilationResult,
    build_query_terms,
    compile_platform_queries,
    default_platform_query_compilers,
)
from data_intelligence_hub.services.workflow_planner.templates import (
    TemplateBuildResult,
    build_workflow_template,
    stable_ref,
    validate_step_graph,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "workflow_planner"
PERIODIC_FIXTURE = FIXTURE_DIR / "periodic_monitoring_request_v1.json"
BATCH_FIXTURE = FIXTURE_DIR / "batch_research_request_v1.json"

ContractFieldSignature = tuple[str, str, str, bool, str | None]
STEP_DATA_CONTRACTS: dict[
    str,
    tuple[tuple[ContractFieldSignature, ...], tuple[ContractFieldSignature, ...]],
] = {
    "compile_scope_queries": (
        (("normalized_scope_contract", "object", "many", True, None),),
        (("compiled_query_refs", "string", "many", False, "compile_scope_queries"),),
    ),
    "classify_seed_urls": (
        (("seed_urls", "url", "many", True, None),),
        (
            (
                "classified_seed_contract",
                "object",
                "many",
                False,
                "classify_seed_urls",
            ),
        ),
    ),
    "discover_content": (
        (("compiled_query_refs", "string", "many", True, "compile_scope_queries"),),
        (("future_content_refs", "string", "many", True, "discover_content"),),
    ),
    "resolve_seed_content": (
        (
            (
                "classified_seed_contract",
                "object",
                "many",
                True,
                "classify_seed_urls",
            ),
        ),
        (
            (
                "future_content_details",
                "object",
                "many",
                True,
                "resolve_seed_content",
            ),
        ),
    ),
    "monitor_incremental": (
        (
            (
                "discover_content_output",
                "object",
                "many",
                True,
                "discover_content",
            ),
            (
                "resolve_seed_content_output",
                "object",
                "many",
                True,
                "resolve_seed_content",
            ),
        ),
        (
            (
                "future_change_cursor",
                "string",
                "one",
                True,
                "monitor_incremental",
            ),
            (
                "future_content_refs",
                "string",
                "many",
                True,
                "monitor_incremental",
            ),
        ),
    ),
    "summarize_delivery_intent": (
        (("delivery_intent", "object", "one", True, None),),
        (
            (
                "delivery_contract",
                "object",
                "one",
                True,
                "summarize_delivery_intent",
            ),
        ),
    ),
    "batch_parse_content": (
        (
            (
                "classified_seed_contract",
                "object",
                "many",
                True,
                "classify_seed_urls",
            ),
            (
                "future_content_refs",
                "string",
                "many",
                False,
                "discover_content",
            ),
        ),
        (
            (
                "future_raw_record_contract",
                "object",
                "many",
                True,
                "batch_parse_content",
            ),
        ),
    ),
    "validate_field_contract": (
        (
            (
                "future_raw_record_contract_reddit",
                "object",
                "many",
                False,
                "batch_parse_content",
            ),
        ),
        (
            (
                "optional_field_coverage",
                "object",
                "many",
                False,
                "validate_field_contract",
            ),
            (
                "required_field_coverage",
                "object",
                "many",
                True,
                "validate_field_contract",
            ),
        ),
    ),
}


def load_payload(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def normalize_payload(payload: dict[str, object]) -> NormalizationResult:
    return normalize_planning_input(PlanningInput.model_validate(payload))


def compile_queries(
    normalization: NormalizationResult,
    *,
    missing_platforms: set[PlatformId] | None = None,
) -> QueryCompilationResult:
    adapter = FixtureCandidateExpansionAdapter.from_default_fixture()
    terms = build_query_terms(normalization, candidate_adapter=adapter)
    compilers = default_platform_query_compilers()
    for platform in missing_platforms or set():
        del compilers[platform]
    return compile_platform_queries(
        normalization,
        terms,
        compilers=compilers,
    )


@pytest.fixture()
def periodic_normalization() -> NormalizationResult:
    return normalize_payload(load_payload(PERIODIC_FIXTURE))


@pytest.fixture()
def batch_normalization() -> NormalizationResult:
    return normalize_payload(load_payload(BATCH_FIXTURE))


@pytest.fixture()
def periodic_queries(
    periodic_normalization: NormalizationResult,
) -> QueryCompilationResult:
    return compile_queries(periodic_normalization)


@pytest.fixture()
def batch_queries(
    batch_normalization: NormalizationResult,
) -> QueryCompilationResult:
    return compile_queries(batch_normalization)


def step_by_key(
    result: TemplateBuildResult,
    template_key: str,
) -> WorkflowStepPreview:
    return next(step for step in result.steps if step.template_key == template_key)


def requirements_for(
    result: TemplateBuildResult,
    operation: CapabilityOperation,
) -> list[RouteRequirement]:
    return [
        requirement
        for requirement in result.requirements
        if requirement.operation is operation
    ]


def test_periodic_template_has_locked_steps(
    periodic_normalization: NormalizationResult,
    periodic_queries: QueryCompilationResult,
) -> None:
    result = build_workflow_template(
        periodic_normalization.normalized_input,
        periodic_queries,
    )

    assert result.mode_template_version == "periodic_monitoring.v1"
    assert [step.template_key for step in result.steps] == [
        "compile_scope_queries",
        "classify_seed_urls",
        "discover_content",
        "resolve_seed_content",
        "monitor_incremental",
        "summarize_delivery_intent",
    ]
    assert [step.sequence for step in result.steps] == list(
        range(1, len(result.steps) + 1)
    )
    validate_step_graph(result.steps)


def test_batch_template_maps_to_search_and_batch_parse(
    batch_normalization: NormalizationResult,
    batch_queries: QueryCompilationResult,
) -> None:
    result = build_workflow_template(
        batch_normalization.normalized_input,
        batch_queries,
    )

    assert result.mode_template_version == "batch_research.v1"
    assert [step.template_key for step in result.steps] == [
        "compile_scope_queries",
        "classify_seed_urls",
        "discover_content",
        "batch_parse_content",
        "validate_field_contract",
    ]
    requirements = {
        (requirement.resource_type, requirement.operation)
        for requirement in result.requirements
    }
    assert (ResourceType.CONTENT, CapabilityOperation.SEARCH_DISCOVER) in requirements
    assert (ResourceType.CONTENT, CapabilityOperation.BATCH_PARSE) in requirements
    assert all(
        step.execution_kind in {"planner_internal", "future_capability"}
        for step in result.steps
    )


def test_internal_steps_have_no_capability_identity(
    periodic_normalization: NormalizationResult,
    periodic_queries: QueryCompilationResult,
) -> None:
    result = build_workflow_template(
        periodic_normalization.normalized_input,
        periodic_queries,
    )

    internal_steps = [
        step for step in result.steps if step.execution_kind == "planner_internal"
    ]
    assert internal_steps
    for step in internal_steps:
        assert step.platform is None
        assert step.resource_type is None
        assert step.operation is None
        assert step.requirement_ref is None
    assert all(
        contract.fields == sorted(contract.fields, key=lambda field: field.name)
        for step in result.steps
        for contract in (step.input_contract, step.output_contract)
    )


@pytest.mark.parametrize(
    ("fixture_path", "expected_template_keys"),
    [
        (
            PERIODIC_FIXTURE,
            (
                "compile_scope_queries",
                "classify_seed_urls",
                "discover_content",
                "resolve_seed_content",
                "monitor_incremental",
                "summarize_delivery_intent",
            ),
        ),
        (
            BATCH_FIXTURE,
            (
                "compile_scope_queries",
                "classify_seed_urls",
                "discover_content",
                "batch_parse_content",
                "validate_field_contract",
            ),
        ),
    ],
)
def test_each_template_key_has_locked_step_data_contracts(
    fixture_path: Path,
    expected_template_keys: tuple[str, ...],
) -> None:
    normalization = normalize_payload(load_payload(fixture_path))
    result = build_workflow_template(
        normalization.normalized_input,
        compile_queries(normalization),
    )
    source_key_by_ref = {step.step_ref: step.template_key for step in result.steps}

    def source_template_key(source_step_ref: str | None) -> str | None:
        if source_step_ref is None:
            return None
        return source_key_by_ref.get(source_step_ref, source_step_ref)

    assert tuple(step.template_key for step in result.steps) == expected_template_keys
    for step in result.steps:
        actual_contracts = tuple(
            tuple(
                (
                    field.name,
                    field.data_type,
                    field.cardinality,
                    field.required,
                    source_template_key(field.source_step_ref),
                )
                for field in contract.fields
            )
            for contract in (step.input_contract, step.output_contract)
        )
        assert actual_contracts == STEP_DATA_CONTRACTS[step.template_key]


def test_no_seed_url_omits_optional_steps_and_records_not_applicable() -> None:
    payload = load_payload(PERIODIC_FIXTURE)
    scopes = payload["scopes"]
    assert isinstance(scopes, list)
    for scope in scopes:
        assert isinstance(scope, dict)
        scope["seed_urls"] = []
    normalization = normalize_payload(payload)

    result = build_workflow_template(
        normalization.normalized_input,
        compile_queries(normalization),
    )

    keys = [step.template_key for step in result.steps]
    assert "classify_seed_urls" not in keys
    assert "resolve_seed_content" not in keys
    not_applicable = {
        entry.details.get("template_key")
        for entry in result.semantic_entries
        if entry.code == "template_step_not_applicable"
    }
    assert {"classify_seed_urls", "resolve_seed_content"} <= not_applicable


def test_mixed_seed_urls_make_classification_partial_without_fake_route() -> None:
    payload = load_payload(PERIODIC_FIXTURE)
    scopes = payload["scopes"]
    assert isinstance(scopes, list)
    first = scopes[0]
    assert isinstance(first, dict)
    first["seed_urls"] = [
        "https://youtu.be/demo",
        "https://example.com/unclassified",
    ]
    payload["scopes"] = [first]
    normalization = normalize_payload(payload)

    result = build_workflow_template(
        normalization.normalized_input,
        compile_queries(normalization),
    )

    classify = step_by_key(result, "classify_seed_urls")
    assert classify.planning_status is WorkflowStepPlanningStatus.PARTIAL
    assert any(
        entry.code == "seed_url_unclassified"
        for entry in result.semantic_entries
    )
    resolve_requirements = requirements_for(
        result,
        CapabilityOperation.RESOLVE_DETAIL,
    )
    assert len(resolve_requirements) == 1
    assert resolve_requirements[0].platform is PlatformId.YOUTUBE


def test_platform_mismatched_url_stays_in_classification_only() -> None:
    payload = load_payload(PERIODIC_FIXTURE)
    scopes = payload["scopes"]
    assert isinstance(scopes, list)
    first = scopes[0]
    assert isinstance(first, dict)
    first["platforms"] = ["reddit"]
    first["seed_urls"] = ["https://youtu.be/demo"]
    payload["default_platforms"] = []
    payload["scopes"] = [first]
    normalization = normalize_payload(payload)

    result = build_workflow_template(
        normalization.normalized_input,
        compile_queries(normalization),
    )

    classify = step_by_key(result, "classify_seed_urls")
    assert classify.planning_status is WorkflowStepPlanningStatus.HELD
    assert any(
        entry.code == "platform_not_selected"
        for entry in result.semantic_entries
    )
    assert requirements_for(result, CapabilityOperation.RESOLVE_DETAIL) == []


def test_seed_url_only_batch_does_not_create_search_requirement() -> None:
    payload = load_payload(BATCH_FIXTURE)
    scopes = payload["scopes"]
    assert isinstance(scopes, list)
    scope = scopes[0]
    assert isinstance(scope, dict)
    scope["canonical_term"] = None
    scope["aliases"] = []
    scope["include_terms"] = []
    scope["official_accounts"] = []
    scope["seed_urls"] = ["https://www.reddit.com/r/demo"]
    scope["platforms"] = []
    payload["default_platforms"] = []
    normalization = normalize_payload(payload)

    result = build_workflow_template(
        normalization.normalized_input,
        compile_queries(normalization),
    )

    assert "discover_content" not in [step.template_key for step in result.steps]
    assert requirements_for(result, CapabilityOperation.SEARCH_DISCOVER) == []
    batch_requirements = requirements_for(result, CapabilityOperation.BATCH_PARSE)
    assert len(batch_requirements) == 1
    assert batch_requirements[0].precondition_failures == []


def test_unclassified_seed_url_only_batch_creates_no_future_requirement() -> None:
    payload = load_payload(BATCH_FIXTURE)
    scopes = payload["scopes"]
    assert isinstance(scopes, list)
    scope = scopes[0]
    assert isinstance(scope, dict)
    scope["canonical_term"] = None
    scope["aliases"] = []
    scope["include_terms"] = []
    scope["official_accounts"] = []
    scope["seed_urls"] = ["https://example.com/unclassified"]
    scope["platforms"] = []
    payload["default_platforms"] = []
    normalization = normalize_payload(payload)

    result = build_workflow_template(
        normalization.normalized_input,
        compile_queries(normalization),
    )

    assert step_by_key(result, "classify_seed_urls").planning_status == "held"
    assert result.requirements == ()
    assert all(step.execution_kind == "planner_internal" for step in result.steps)


def test_same_platform_requirements_merge_all_scope_context(
    periodic_normalization: NormalizationResult,
    periodic_queries: QueryCompilationResult,
) -> None:
    result = build_workflow_template(
        periodic_normalization.normalized_input,
        periodic_queries,
    )

    search_requirements = requirements_for(
        result,
        CapabilityOperation.SEARCH_DISCOVER,
    )
    assert len(search_requirements) == 1
    requirement = search_requirements[0]
    assert requirement.scope_keys == sorted(
        scope.scope_key for scope in periodic_normalization.normalized_input.scopes
    )
    assert requirement.step_refs == sorted(set(requirement.step_refs))
    assert requirement.regions == sorted(set(requirement.regions))


def test_missing_compiler_is_a_held_query_precondition_but_direct_url_survives() -> None:
    normalization = normalize_payload(load_payload(PERIODIC_FIXTURE))
    queries = compile_queries(
        normalization,
        missing_platforms={PlatformId.YOUTUBE},
    )
    assert queries.compiled_queries == ()

    result = build_workflow_template(normalization.normalized_input, queries)

    discover = step_by_key(result, "discover_content")
    assert discover.planning_status is WorkflowStepPlanningStatus.HELD
    search_requirement = requirements_for(
        result,
        CapabilityOperation.SEARCH_DISCOVER,
    )[0]
    assert [reason.code for reason in search_requirement.precondition_failures] == [
        "compiler_missing"
    ]
    resolve = step_by_key(result, "resolve_seed_content")
    assert resolve.planning_status is WorkflowStepPlanningStatus.PLANNED
    resolve_requirement = requirements_for(
        result,
        CapabilityOperation.RESOLVE_DETAIL,
    )[0]
    assert resolve_requirement.precondition_failures == []
    monitor_requirement = requirements_for(
        result,
        CapabilityOperation.MONITOR_INCREMENTAL,
    )[0]
    assert monitor_requirement.precondition_failures == []


def test_batch_direct_url_survives_unrelated_compiler_failure() -> None:
    payload = load_payload(BATCH_FIXTURE)
    scopes = payload["scopes"]
    assert isinstance(scopes, list)
    query_scope = scopes[0]
    assert isinstance(query_scope, dict)
    query_scope["seed_urls"] = []
    direct_scope = deepcopy(query_scope)
    direct_scope["scope_ref"] = "scope-direct-url"
    direct_scope["canonical_term"] = None
    direct_scope["aliases"] = []
    direct_scope["include_terms"] = []
    direct_scope["official_accounts"] = []
    direct_scope["seed_urls"] = ["https://www.reddit.com/r/demo"]
    payload["scopes"] = [query_scope, direct_scope]
    normalization = normalize_payload(payload)
    queries = compile_queries(
        normalization,
        missing_platforms={PlatformId.REDDIT},
    )

    result = build_workflow_template(normalization.normalized_input, queries)

    assert step_by_key(result, "discover_content").planning_status == "held"
    batch_step = step_by_key(result, "batch_parse_content")
    assert batch_step.planning_status == "planned"
    batch_requirement = requirements_for(
        result,
        CapabilityOperation.BATCH_PARSE,
    )[0]
    assert batch_requirement.precondition_failures == []
    direct_scope_key = next(
        scope.scope_key
        for scope in normalization.normalized_input.scopes
        if scope.canonical_term is None
    )
    query_scope_key = next(
        scope.scope_key
        for scope in normalization.normalized_input.scopes
        if scope.canonical_term is not None
    )
    assert batch_requirement.scope_keys == [direct_scope_key]
    assert requirements_for(
        result,
        CapabilityOperation.SEARCH_DISCOVER,
    )[0].scope_keys == [query_scope_key]


def test_query_only_compiler_failure_propagates_to_downstream_requirement() -> None:
    payload = load_payload(PERIODIC_FIXTURE)
    scopes = payload["scopes"]
    assert isinstance(scopes, list)
    for scope in scopes:
        assert isinstance(scope, dict)
        scope["seed_urls"] = []
    normalization = normalize_payload(payload)

    result = build_workflow_template(
        normalization.normalized_input,
        compile_queries(
            normalization,
            missing_platforms={PlatformId.YOUTUBE},
        ),
    )

    for operation in (
        CapabilityOperation.SEARCH_DISCOVER,
        CapabilityOperation.MONITOR_INCREMENTAL,
    ):
        requirement = requirements_for(result, operation)[0]
        assert [reason.code for reason in requirement.precondition_failures] == [
            "compiler_missing"
        ]


def test_refs_and_sorted_outputs_ignore_scope_ref_and_input_order() -> None:
    first_payload = load_payload(PERIODIC_FIXTURE)
    second_payload = deepcopy(first_payload)
    second_scopes = second_payload["scopes"]
    assert isinstance(second_scopes, list)
    reordered_scopes = list(reversed(second_scopes))
    second_payload["scopes"] = reordered_scopes
    for index, scope in enumerate(reordered_scopes):
        assert isinstance(scope, dict)
        scope["scope_ref"] = f"renamed-{index}"

    first_normalization = normalize_payload(first_payload)
    second_normalization = normalize_payload(second_payload)
    first = build_workflow_template(
        first_normalization.normalized_input,
        compile_queries(first_normalization),
    )
    second = build_workflow_template(
        second_normalization.normalized_input,
        compile_queries(second_normalization),
    )

    assert [step.step_ref for step in first.steps] == [
        step.step_ref for step in second.steps
    ]
    assert [requirement.requirement_ref for requirement in first.requirements] == [
        requirement.requirement_ref for requirement in second.requirements
    ]
    assert [
        requirement.model_dump(mode="json")
        for requirement in first.requirements
    ] == [
        requirement.model_dump(mode="json")
        for requirement in second.requirements
    ]
    assert "project_id" not in inspect.signature(build_workflow_template).parameters


def test_step_refs_ignore_scope_semantics_when_template_topology_is_unchanged() -> None:
    first_payload = load_payload(PERIODIC_FIXTURE)
    second_payload = deepcopy(first_payload)
    second_scopes = second_payload["scopes"]
    assert isinstance(second_scopes, list)
    for index, scope in enumerate(second_scopes):
        assert isinstance(scope, dict)
        scope["canonical_term"] = f"semantic variant {index}"
        scope["aliases"] = [f"variant alias {index}"]
        scope["include_terms"] = [f"variant include {index}"]
        scope["languages"] = ["fr"]
        scope["regions"] = ["CA"]

    first_normalization = normalize_payload(first_payload)
    second_normalization = normalize_payload(second_payload)
    first = build_workflow_template(
        first_normalization.normalized_input,
        compile_queries(first_normalization),
    )
    second = build_workflow_template(
        second_normalization.normalized_input,
        compile_queries(second_normalization),
    )

    assert [
        (step.template_key, step.platform, step.resource_type, step.operation)
        for step in first.steps
    ] == [
        (step.template_key, step.platform, step.resource_type, step.operation)
        for step in second.steps
    ]
    assert [step.step_ref for step in first.steps] == [
        step.step_ref for step in second.steps
    ]
    assert any(
        first_step.scope_keys != second_step.scope_keys
        for first_step, second_step in zip(first.steps, second.steps, strict=True)
    )
    assert [requirement.requirement_ref for requirement in first.requirements] != [
        requirement.requirement_ref for requirement in second.requirements
    ]


def test_template_result_is_frozen_and_stable_ref_is_deterministic(
    periodic_normalization: NormalizationResult,
    periodic_queries: QueryCompilationResult,
) -> None:
    result = build_workflow_template(
        periodic_normalization.normalized_input,
        periodic_queries,
    )

    assert stable_ref("step", {"b": 2, "a": 1}) == stable_ref(
        "step", {"a": 1, "b": 2}
    )
    with pytest.raises(FrozenInstanceError):
        result.mode_template_version = "changed"  # type: ignore[misc]


def test_topology_missing_forward_and_cycle_fail_fast(
    periodic_normalization: NormalizationResult,
    periodic_queries: QueryCompilationResult,
) -> None:
    result = build_workflow_template(
        periodic_normalization.normalized_input,
        periodic_queries,
    )
    first = result.steps[0]
    last = result.steps[-1]

    missing = [
        *result.steps[:-1],
        last.model_copy(update={"depends_on": ["step:missing"]}),
    ]
    with pytest.raises(WorkflowPlannerTopologyError):
        validate_step_graph(missing)

    forward = [
        first.model_copy(update={"depends_on": [last.step_ref]}),
        *result.steps[1:],
    ]
    with pytest.raises(WorkflowPlannerTopologyError):
        validate_step_graph(forward)

    cycle = [
        first.model_copy(update={"depends_on": [last.step_ref]}),
        *result.steps[1:-1],
        last.model_copy(update={"depends_on": [first.step_ref]}),
    ]
    with pytest.raises(WorkflowPlannerTopologyError):
        validate_step_graph(cycle)
