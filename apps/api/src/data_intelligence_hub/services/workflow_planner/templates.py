from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from pydantic import JsonValue

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityOperation,
    PlatformId,
    ResourceType,
)
from data_intelligence_hub.schemas.workflow_planner import (
    DecisionReason,
    DecisionTraceEntry,
    FlowMode,
    NormalizedMonitoringScope,
    NormalizedPlanningInput,
    RouteRequirement,
    StepDataContract,
    StepDataContractField,
    WorkflowStepPlanningStatus,
    WorkflowStepPreview,
)
from data_intelligence_hub.services.exceptions import WorkflowPlannerTopologyError
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id
from data_intelligence_hub.services.workflow_planner.normalization import (
    classify_seed_url,
)
from data_intelligence_hub.services.workflow_planner.query_compiler import (
    QueryCompilationResult,
)

_PLATFORM_ORDER = {platform: index for index, platform in enumerate(PlatformId)}
_OPERATION_ORDER = {
    CapabilityOperation.SEARCH_DISCOVER: 0,
    CapabilityOperation.RESOLVE_DETAIL: 1,
    CapabilityOperation.MONITOR_INCREMENTAL: 2,
    CapabilityOperation.BATCH_PARSE: 3,
}
_TEMPLATE_ORDINALS = {
    "compile_scope_queries": 1,
    "classify_seed_urls": 2,
    "discover_content": 3,
    "resolve_seed_content": 4,
    "batch_parse_content": 4,
    "monitor_incremental": 5,
    "validate_field_contract": 5,
    "summarize_delivery_intent": 6,
}


@dataclass(frozen=True)
class TemplateBuildResult:
    mode_template_version: str
    steps: tuple[WorkflowStepPreview, ...]
    requirements: tuple[RouteRequirement, ...]
    semantic_entries: tuple[DecisionTraceEntry, ...]


@dataclass(frozen=True)
class _SeedInventory:
    total_count: int
    eligible_count: int
    eligible_urls: dict[PlatformId, tuple[str, ...]]
    eligible_scope_keys: dict[PlatformId, tuple[str, ...]]
    semantic_entries: tuple[DecisionTraceEntry, ...]


def stable_ref(prefix: str, value: dict[str, JsonValue]) -> str:
    digest = sha256_id(value).removeprefix("sha256:")
    return f"{prefix}:{digest[:16]}"


def _platform_sort_key(platform: PlatformId) -> int:
    return _PLATFORM_ORDER[platform]


def _field(
    name: str,
    *,
    data_type: str,
    cardinality: str,
    required: bool,
    source_step_ref: str | None,
    description: str,
) -> StepDataContractField:
    return StepDataContractField(
        name=name,
        data_type=data_type,
        cardinality=cardinality,
        required=required,
        source_step_ref=source_step_ref,
        description=description,
    )


def _contract(fields: Sequence[StepDataContractField]) -> StepDataContract:
    return StepDataContract(
        schema_version="step_data_contract.v1",
        fields=sorted(fields, key=lambda field: field.name),
    )


def _output_contract(
    step_ref: str,
    fields: Sequence[tuple[str, str, str, bool, str]],
) -> StepDataContract:
    return _contract(
        [
            _field(
                name,
                data_type=data_type,
                cardinality=cardinality,
                required=required,
                source_step_ref=step_ref,
                description=description,
            )
            for name, data_type, cardinality, required, description in fields
        ]
    )


def _step_ref(
    *,
    mode_template_version: str,
    template_key: str,
    platform: PlatformId | None,
    resource_type: ResourceType | None,
    operation: CapabilityOperation | None,
) -> str:
    return stable_ref(
        "step",
        cast(
            dict[str, JsonValue],
            {
                "mode_template_version": mode_template_version,
                "template_key": template_key,
                "template_ordinal": _TEMPLATE_ORDINALS[template_key],
                "platform": platform.value if platform is not None else None,
                "resource_type": (
                    resource_type.value if resource_type is not None else None
                ),
                "operation": operation.value if operation is not None else None,
            },
        ),
    )


def _requirement_ref(
    *,
    mode_template_version: str,
    platform: PlatformId,
    scope_keys: Sequence[str],
    resource_type: ResourceType,
    operation: CapabilityOperation,
) -> str:
    return stable_ref(
        "requirement",
        cast(
            dict[str, JsonValue],
            {
                "mode_template_version": mode_template_version,
                "platform": platform.value,
                "resource_type": resource_type.value,
                "operation": operation.value,
                "scope_keys": sorted(set(scope_keys)),
            },
        ),
    )


def _internal_step(
    *,
    mode_template_version: str,
    template_key: str,
    label: str,
    scope_keys: Sequence[str],
    depends_on: Sequence[str] = (),
    planning_status: WorkflowStepPlanningStatus = WorkflowStepPlanningStatus.PLANNED,
    limitations: Sequence[str] = (),
    input_fields: Sequence[StepDataContractField] = (),
    output_fields: Sequence[tuple[str, str, str, bool, str]],
) -> WorkflowStepPreview:
    step_ref = _step_ref(
        mode_template_version=mode_template_version,
        template_key=template_key,
        platform=None,
        resource_type=None,
        operation=None,
    )
    return WorkflowStepPreview(
        step_ref=step_ref,
        template_key=template_key,
        sequence=1,
        label=label,
        execution_kind="planner_internal",
        depends_on=list(dict.fromkeys(depends_on)),
        platform=None,
        scope_keys=sorted(set(scope_keys)),
        resource_type=None,
        operation=None,
        requirement_ref=None,
        input_contract=_contract(input_fields),
        output_contract=_output_contract(step_ref, output_fields),
        planning_status=planning_status,
        limitations=sorted(set(limitations)),
    )


def _future_step_and_requirement(
    *,
    mode_template_version: str,
    normalized_input: NormalizedPlanningInput,
    scopes_by_key: dict[str, NormalizedMonitoringScope],
    template_key: str,
    label: str,
    platform: PlatformId,
    scope_keys: Sequence[str],
    operation: CapabilityOperation,
    depends_on: Sequence[str],
    planning_status: WorkflowStepPlanningStatus,
    precondition_failures: Sequence[DecisionReason] = (),
    limitations: Sequence[str] = (),
    input_fields: Sequence[StepDataContractField] = (),
    output_fields: Sequence[tuple[str, str, str, bool, str]],
) -> tuple[WorkflowStepPreview, RouteRequirement]:
    normalized_scope_keys = sorted(set(scope_keys))
    resource_type = ResourceType.CONTENT
    requirement_ref = _requirement_ref(
        mode_template_version=mode_template_version,
        platform=platform,
        scope_keys=normalized_scope_keys,
        resource_type=resource_type,
        operation=operation,
    )
    step_ref = _step_ref(
        mode_template_version=mode_template_version,
        template_key=template_key,
        platform=platform,
        resource_type=resource_type,
        operation=operation,
    )
    step = WorkflowStepPreview(
        step_ref=step_ref,
        template_key=template_key,
        sequence=1,
        label=label,
        execution_kind="future_capability",
        depends_on=list(dict.fromkeys(depends_on)),
        platform=platform,
        scope_keys=normalized_scope_keys,
        resource_type=resource_type,
        operation=operation,
        requirement_ref=requirement_ref,
        input_contract=_contract(input_fields),
        output_contract=_output_contract(step_ref, output_fields),
        planning_status=planning_status,
        limitations=sorted({"future_capability_preview_only", *limitations}),
    )
    regions = sorted(
        {
            region
            for scope_key in normalized_scope_keys
            for region in scopes_by_key[scope_key].effective_regions
        }
    )
    failures = sorted(
        {
            (failure.code, failure.reason)
            for failure in precondition_failures
        }
    )
    requirement = RouteRequirement(
        requirement_ref=requirement_ref,
        scope_keys=normalized_scope_keys,
        step_refs=[step_ref],
        platform=platform,
        resource_type=resource_type,
        operation=operation,
        purpose=normalized_input.purpose,
        regions=regions,
        required_fields=sorted(set(normalized_input.required_fields)),
        optional_fields=sorted(set(normalized_input.optional_fields)),
        budget_ceiling=normalized_input.budget_ceiling,
        freshness_requirement=(
            normalized_input.schedule_intent.cadence
            if operation is CapabilityOperation.MONITOR_INCREMENTAL
            and normalized_input.schedule_intent is not None
            else None
        ),
        rate_limit_requirement=normalized_input.rate_limit_intent,
        retention_requirement=normalized_input.retention_intent,
        allow_partial_degradation=normalized_input.allow_partial_degradation,
        precondition_failures=[
            DecisionReason(code=code, reason=reason) for code, reason in failures
        ],
    )
    return step, requirement


def _not_applicable_entry(
    *,
    mode_template_version: str,
    template_key: str,
    scope_keys: Sequence[str],
) -> DecisionTraceEntry:
    return DecisionTraceEntry(
        code="template_step_not_applicable",
        reason="Template condition not satisfied",
        scope_keys=sorted(set(scope_keys)),
        requirement_ref=None,
        details={
            "mode_template_version": mode_template_version,
            "template_key": template_key,
        },
    )


def _build_seed_inventory(
    scopes: Sequence[NormalizedMonitoringScope],
) -> _SeedInventory:
    eligible_urls: dict[PlatformId, set[str]] = {}
    eligible_scope_keys: dict[PlatformId, set[str]] = {}
    semantic_entries: list[DecisionTraceEntry] = []
    total_count = 0
    eligible_count = 0
    for scope in sorted(scopes, key=lambda item: item.scope_key):
        selected_platforms = set(scope.effective_platforms)
        for seed_url in sorted(set(scope.seed_urls)):
            total_count += 1
            platform = classify_seed_url(seed_url)
            if platform is None:
                semantic_entries.append(
                    DecisionTraceEntry(
                        code="seed_url_unclassified",
                        reason="Seed URL does not match a supported platform host",
                        scope_keys=[scope.scope_key],
                        requirement_ref=None,
                        details={"seed_url": seed_url},
                    )
                )
                continue
            if platform not in selected_platforms:
                semantic_entries.append(
                    DecisionTraceEntry(
                        code="platform_not_selected",
                        reason="Seed URL platform is outside the selected platform scope",
                        scope_keys=[scope.scope_key],
                        requirement_ref=None,
                        details={
                            "classified_platform": platform.value,
                            "effective_platforms": [
                                selected.value
                                for selected in sorted(
                                    selected_platforms,
                                    key=_platform_sort_key,
                                )
                            ],
                            "seed_url": seed_url,
                        },
                    )
                )
                continue
            eligible_count += 1
            eligible_urls.setdefault(platform, set()).add(seed_url)
            eligible_scope_keys.setdefault(platform, set()).add(scope.scope_key)
    return _SeedInventory(
        total_count=total_count,
        eligible_count=eligible_count,
        eligible_urls={
            platform: tuple(sorted(urls))
            for platform, urls in eligible_urls.items()
        },
        eligible_scope_keys={
            platform: tuple(sorted(scope_keys))
            for platform, scope_keys in eligible_scope_keys.items()
        },
        semantic_entries=tuple(semantic_entries),
    )


def _query_scope_keys_by_platform(
    normalized_input: NormalizedPlanningInput,
    query_result: QueryCompilationResult,
) -> dict[PlatformId, tuple[str, ...]]:
    scopes_by_key = {scope.scope_key: scope for scope in normalized_input.scopes}
    queryable_scope_keys = {
        term.scope_key
        for term in query_result.query_terms
        if term.status == "active" and term.origin != "seed_url"
    }
    by_platform: dict[PlatformId, set[str]] = {}
    for scope_key in sorted(queryable_scope_keys):
        scope = scopes_by_key.get(scope_key)
        if scope is None:
            continue
        for platform in scope.effective_platforms:
            by_platform.setdefault(platform, set()).add(scope_key)
    return {
        platform: tuple(sorted(scope_keys))
        for platform, scope_keys in by_platform.items()
    }


def _compiler_preconditions(
    query_result: QueryCompilationResult,
) -> dict[PlatformId, tuple[DecisionReason, ...]]:
    return {
        failure.platform: (
            DecisionReason(code="compiler_missing", reason=failure.reason),
        )
        for failure in query_result.compiler_failures
    }


def _sequence_steps(
    steps: Sequence[WorkflowStepPreview],
) -> tuple[WorkflowStepPreview, ...]:
    return tuple(
        step.model_copy(update={"sequence": index})
        for index, step in enumerate(steps, start=1)
    )


def _sorted_semantic_entries(
    entries: Sequence[DecisionTraceEntry],
) -> tuple[DecisionTraceEntry, ...]:
    return tuple(
        sorted(
            entries,
            key=lambda entry: (
                entry.scope_keys,
                entry.code,
                entry.reason,
                json.dumps(entry.details, ensure_ascii=False, sort_keys=True),
            ),
        )
    )


def validate_step_graph(steps: Sequence[WorkflowStepPreview]) -> None:
    step_by_ref = {step.step_ref: step for step in steps}
    if len(step_by_ref) != len(steps):
        raise WorkflowPlannerTopologyError("duplicate_step_ref")

    for step in steps:
        if any(dependency not in step_by_ref for dependency in step.depends_on):
            raise WorkflowPlannerTopologyError("missing_step_dependency")

    visit_state: dict[str, int] = {}

    def visit(step_ref: str) -> None:
        state = visit_state.get(step_ref, 0)
        if state == 1:
            raise WorkflowPlannerTopologyError("cyclic_step_dependency")
        if state == 2:
            return
        visit_state[step_ref] = 1
        for dependency in step_by_ref[step_ref].depends_on:
            visit(dependency)
        visit_state[step_ref] = 2

    for step in steps:
        visit(step.step_ref)

    position_by_ref = {step.step_ref: index for index, step in enumerate(steps)}
    for step in steps:
        if any(
            position_by_ref[dependency] >= position_by_ref[step.step_ref]
            for dependency in step.depends_on
        ):
            raise WorkflowPlannerTopologyError("forward_step_dependency")


def build_workflow_template(
    normalized_input: NormalizedPlanningInput,
    query_result: QueryCompilationResult,
) -> TemplateBuildResult:
    mode_template_version = f"{normalized_input.flow_mode.value}.v1"
    scopes = sorted(normalized_input.scopes, key=lambda scope: scope.scope_key)
    scopes_by_key = {scope.scope_key: scope for scope in scopes}
    all_scope_keys = sorted(scopes_by_key)
    seed_inventory = _build_seed_inventory(scopes)
    query_scope_keys = _query_scope_keys_by_platform(normalized_input, query_result)
    compiler_preconditions = _compiler_preconditions(query_result)
    semantic_entries: list[DecisionTraceEntry] = list(seed_inventory.semantic_entries)
    steps: list[WorkflowStepPreview] = []
    requirements: list[RouteRequirement] = []

    if query_result.compiler_failures:
        compile_status = (
            WorkflowStepPlanningStatus.PARTIAL
            if query_result.compiled_queries
            else WorkflowStepPlanningStatus.HELD
        )
    else:
        compile_status = WorkflowStepPlanningStatus.PLANNED
    compile_step = _internal_step(
        mode_template_version=mode_template_version,
        template_key="compile_scope_queries",
        label="Compile scope queries",
        scope_keys=all_scope_keys,
        planning_status=compile_status,
        limitations=query_result.limitations,
        input_fields=[
            _field(
                "normalized_scope_contract",
                data_type="object",
                cardinality="many",
                required=True,
                source_step_ref=None,
                description="Normalized semantic Scope inputs",
            )
        ],
        output_fields=[
            (
                "compiled_query_refs",
                "string",
                "many",
                False,
                "References to declarative compiled queries",
            )
        ],
    )
    steps.append(compile_step)

    classification_step: WorkflowStepPreview | None = None
    seed_scope_keys = sorted(
        {scope.scope_key for scope in scopes if scope.seed_urls}
    )
    if seed_inventory.total_count:
        if seed_inventory.eligible_count == seed_inventory.total_count:
            classification_status = WorkflowStepPlanningStatus.PLANNED
        elif seed_inventory.eligible_count:
            classification_status = WorkflowStepPlanningStatus.PARTIAL
        else:
            classification_status = WorkflowStepPlanningStatus.HELD
        classification_step = _internal_step(
            mode_template_version=mode_template_version,
            template_key="classify_seed_urls",
            label="Classify Seed URLs",
            scope_keys=seed_scope_keys,
            planning_status=classification_status,
            limitations=[entry.code for entry in seed_inventory.semantic_entries],
            input_fields=[
                _field(
                    "seed_urls",
                    data_type="url",
                    cardinality="many",
                    required=True,
                    source_step_ref=None,
                    description="Normalized user-provided Seed URLs",
                )
            ],
            output_fields=[
                (
                    "classified_seed_contract",
                    "object",
                    "many",
                    False,
                    "String-only Seed URL platform classifications",
                )
            ],
        )
        steps.append(classification_step)
    else:
        semantic_entries.append(
            _not_applicable_entry(
                mode_template_version=mode_template_version,
                template_key="classify_seed_urls",
                scope_keys=all_scope_keys,
            )
        )

    discover_steps: dict[PlatformId, WorkflowStepPreview] = {}
    for platform in sorted(query_scope_keys, key=_platform_sort_key):
        discover_scope_keys = query_scope_keys[platform]
        discover_preconditions = compiler_preconditions.get(platform, ())
        status = (
            WorkflowStepPlanningStatus.HELD
            if discover_preconditions
            else WorkflowStepPlanningStatus.PLANNED
        )
        step, requirement = _future_step_and_requirement(
            mode_template_version=mode_template_version,
            normalized_input=normalized_input,
            scopes_by_key=scopes_by_key,
            template_key="discover_content",
            label=f"Discover {platform.value} content",
            platform=platform,
            scope_keys=discover_scope_keys,
            operation=CapabilityOperation.SEARCH_DISCOVER,
            depends_on=[compile_step.step_ref],
            planning_status=status,
            precondition_failures=discover_preconditions,
            limitations=[reason.code for reason in discover_preconditions],
            input_fields=[
                _field(
                    "compiled_query_refs",
                    data_type="string",
                    cardinality="many",
                    required=True,
                    source_step_ref=compile_step.step_ref,
                    description="Same-platform declarative query references",
                )
            ],
            output_fields=[
                (
                    "future_content_refs",
                    "string",
                    "many",
                    True,
                    "Future content references; no content is collected in Preview",
                )
            ],
        )
        steps.append(step)
        requirements.append(requirement)
        discover_steps[platform] = step
    if not discover_steps:
        semantic_entries.append(
            _not_applicable_entry(
                mode_template_version=mode_template_version,
                template_key="discover_content",
                scope_keys=all_scope_keys,
            )
        )

    if normalized_input.flow_mode is FlowMode.PERIODIC_MONITORING:
        resolve_steps: dict[PlatformId, WorkflowStepPreview] = {}
        if classification_step is not None:
            for platform in sorted(
                seed_inventory.eligible_scope_keys,
                key=_platform_sort_key,
            ):
                step, requirement = _future_step_and_requirement(
                    mode_template_version=mode_template_version,
                    normalized_input=normalized_input,
                    scopes_by_key=scopes_by_key,
                    template_key="resolve_seed_content",
                    label=f"Resolve {platform.value} Seed content",
                    platform=platform,
                    scope_keys=seed_inventory.eligible_scope_keys[platform],
                    operation=CapabilityOperation.RESOLVE_DETAIL,
                    depends_on=[classification_step.step_ref],
                    planning_status=WorkflowStepPlanningStatus.PLANNED,
                    input_fields=[
                        _field(
                            "classified_seed_contract",
                            data_type="object",
                            cardinality="many",
                            required=True,
                            source_step_ref=classification_step.step_ref,
                            description="Selected same-platform Seed URL inputs",
                        )
                    ],
                    output_fields=[
                        (
                            "future_content_details",
                            "object",
                            "many",
                            True,
                            "Future resolved content details",
                        )
                    ],
                )
                steps.append(step)
                requirements.append(requirement)
                resolve_steps[platform] = step
        if not resolve_steps:
            semantic_entries.append(
                _not_applicable_entry(
                    mode_template_version=mode_template_version,
                    template_key="resolve_seed_content",
                    scope_keys=seed_scope_keys or all_scope_keys,
                )
            )

        upstream_platforms = set(discover_steps) | set(resolve_steps)
        monitor_steps: list[WorkflowStepPreview] = []
        for platform in sorted(upstream_platforms, key=_platform_sort_key):
            upstream = [
                step
                for step in (
                    discover_steps.get(platform),
                    resolve_steps.get(platform),
                )
                if step is not None
            ]
            usable_upstream = [
                step
                for step in upstream
                if step.planning_status is not WorkflowStepPlanningStatus.HELD
            ]
            selected_upstream = usable_upstream or upstream
            monitor_scope_keys = sorted(
                {
                    scope_key
                    for step in selected_upstream
                    for scope_key in step.scope_keys
                }
            )
            monitor_preconditions: Sequence[DecisionReason] = ()
            status = WorkflowStepPlanningStatus.PLANNED
            if not usable_upstream:
                status = WorkflowStepPlanningStatus.HELD
                monitor_preconditions = compiler_preconditions.get(platform, ())
            monitor_input_fields = [
                _field(
                    f"{upstream_step.template_key}_output",
                    data_type="object",
                    cardinality="many",
                    required=True,
                    source_step_ref=upstream_step.step_ref,
                    description="Same-platform upstream collection contract",
                )
                for upstream_step in selected_upstream
            ]
            step, requirement = _future_step_and_requirement(
                mode_template_version=mode_template_version,
                normalized_input=normalized_input,
                scopes_by_key=scopes_by_key,
                template_key="monitor_incremental",
                label=f"Monitor incremental {platform.value} content",
                platform=platform,
                scope_keys=monitor_scope_keys,
                operation=CapabilityOperation.MONITOR_INCREMENTAL,
                depends_on=[step.step_ref for step in selected_upstream],
                planning_status=status,
                precondition_failures=monitor_preconditions,
                limitations=[reason.code for reason in monitor_preconditions],
                input_fields=monitor_input_fields,
                output_fields=[
                    (
                        "future_change_cursor",
                        "string",
                        "one",
                        True,
                        "Future incremental change cursor",
                    ),
                    (
                        "future_content_refs",
                        "string",
                        "many",
                        True,
                        "Future changed content references",
                    ),
                ],
            )
            steps.append(step)
            requirements.append(requirement)
            monitor_steps.append(step)
        if not monitor_steps:
            semantic_entries.append(
                _not_applicable_entry(
                    mode_template_version=mode_template_version,
                    template_key="monitor_incremental",
                    scope_keys=all_scope_keys,
                )
            )

        summary_step = _internal_step(
            mode_template_version=mode_template_version,
            template_key="summarize_delivery_intent",
            label="Summarize delivery intent",
            scope_keys=all_scope_keys,
            input_fields=[
                _field(
                    "delivery_intent",
                    data_type="object",
                    cardinality="one",
                    required=normalized_input.delivery_intent is not None,
                    source_step_ref=None,
                    description="Declarative delivery intent only",
                )
            ],
            output_fields=[
                (
                    "delivery_contract",
                    "object",
                    "one",
                    True,
                    "Future delivery data-shape contract",
                )
            ],
        )
        steps.append(summary_step)
    else:
        parse_steps: list[WorkflowStepPreview] = []
        parse_platforms = set(discover_steps) | set(seed_inventory.eligible_scope_keys)
        for platform in sorted(parse_platforms, key=_platform_sort_key):
            discover_step = discover_steps.get(platform)
            has_direct_seed = platform in seed_inventory.eligible_scope_keys
            usable_discover = (
                discover_step is not None
                and discover_step.planning_status is not WorkflowStepPlanningStatus.HELD
            )
            dependencies: list[str] = []
            parse_input_fields: list[StepDataContractField] = []
            if has_direct_seed and classification_step is not None:
                dependencies.append(classification_step.step_ref)
                parse_input_fields.append(
                    _field(
                        "classified_seed_contract",
                        data_type="object",
                        cardinality="many",
                        required=True,
                        source_step_ref=classification_step.step_ref,
                        description="Direct same-platform Seed URL contract",
                    )
                )
            if usable_discover and discover_step is not None:
                dependencies.append(discover_step.step_ref)
                parse_input_fields.append(
                    _field(
                        "future_content_refs",
                        data_type="string",
                        cardinality="many",
                        required=not has_direct_seed,
                        source_step_ref=discover_step.step_ref,
                        description="Future content references from discovery",
                    )
                )
            elif not has_direct_seed and discover_step is not None:
                dependencies.append(discover_step.step_ref)
                parse_input_fields.append(
                    _field(
                        "future_content_refs",
                        data_type="string",
                        cardinality="many",
                        required=True,
                        source_step_ref=discover_step.step_ref,
                        description="Held discovery output contract",
                    )
                )
            parse_scope_keys = sorted(
                {
                    *(
                        seed_inventory.eligible_scope_keys.get(platform, ())
                        if has_direct_seed
                        else ()
                    ),
                    *(
                        discover_step.scope_keys
                        if discover_step is not None
                        and (usable_discover or not has_direct_seed)
                        else []
                    ),
                }
            )
            parse_preconditions: Sequence[DecisionReason] = ()
            status = WorkflowStepPlanningStatus.PLANNED
            if not has_direct_seed and not usable_discover:
                status = WorkflowStepPlanningStatus.HELD
                parse_preconditions = compiler_preconditions.get(platform, ())
            step, requirement = _future_step_and_requirement(
                mode_template_version=mode_template_version,
                normalized_input=normalized_input,
                scopes_by_key=scopes_by_key,
                template_key="batch_parse_content",
                label=f"Batch parse {platform.value} content",
                platform=platform,
                scope_keys=parse_scope_keys,
                operation=CapabilityOperation.BATCH_PARSE,
                depends_on=dependencies,
                planning_status=status,
                precondition_failures=parse_preconditions,
                limitations=[reason.code for reason in parse_preconditions],
                input_fields=parse_input_fields,
                output_fields=[
                    (
                        "future_raw_record_contract",
                        "object",
                        "many",
                        True,
                        "Future RawRecord data-shape contract",
                    )
                ],
            )
            steps.append(step)
            requirements.append(requirement)
            parse_steps.append(step)
        if not parse_steps:
            semantic_entries.append(
                _not_applicable_entry(
                    mode_template_version=mode_template_version,
                    template_key="batch_parse_content",
                    scope_keys=all_scope_keys,
                )
            )

        validation_inputs = [
            _field(
                f"future_raw_record_contract_{step.platform.value}",
                data_type="object",
                cardinality="many",
                required=False,
                source_step_ref=step.step_ref,
                description="Future RawRecord contract for field validation",
            )
            for step in parse_steps
            if step.platform is not None
        ]
        validate_fields_step = _internal_step(
            mode_template_version=mode_template_version,
            template_key="validate_field_contract",
            label="Validate field contract",
            scope_keys=all_scope_keys,
            depends_on=[step.step_ref for step in parse_steps],
            input_fields=validation_inputs,
            output_fields=[
                (
                    "optional_field_coverage",
                    "object",
                    "many",
                    False,
                    "Optional field coverage contract",
                ),
                (
                    "required_field_coverage",
                    "object",
                    "many",
                    True,
                    "Required field coverage contract",
                ),
            ],
        )
        steps.append(validate_fields_step)

    sequenced_steps = _sequence_steps(steps)
    validate_step_graph(sequenced_steps)
    step_position = {
        step.step_ref: step.sequence for step in sequenced_steps
    }
    requirements.sort(
        key=lambda requirement: (
            min(step_position[step_ref] for step_ref in requirement.step_refs),
            _PLATFORM_ORDER[requirement.platform],
            _OPERATION_ORDER[requirement.operation],
            requirement.requirement_ref,
        )
    )
    return TemplateBuildResult(
        mode_template_version=mode_template_version,
        steps=sequenced_steps,
        requirements=tuple(requirements),
        semantic_entries=_sorted_semantic_entries(semantic_entries),
    )
