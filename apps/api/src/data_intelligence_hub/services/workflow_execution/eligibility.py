from __future__ import annotations

import re
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from pydantic import Field, JsonValue

from data_intelligence_hub.schemas.workflow_execution import (
    Sha256Digest,
    WorkflowExecutionContract,
)
from data_intelligence_hub.schemas.workflow_planner import (
    CompiledPlatformQuery,
    PlanningStatus,
    RouteCandidateDecision,
    RoutePlanPreview,
    RoutePlanStatus,
    RouteRequirement,
    WorkflowPlanPreview,
    WorkflowStepPlanningStatus,
    WorkflowStepPreview,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id

_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


class WorkflowVersionNotFixtureRunnableError(ValueError):
    """The frozen Version cannot execute as one complete Primary fixture run."""


class WorkflowStepFixtureIdentity(WorkflowExecutionContract):
    fixture_profile_hash: Sha256Digest
    fixture_case_id: str = Field(min_length=1, max_length=200)
    fixture_content_hash: Sha256Digest


@dataclass(frozen=True, slots=True)
class PrimaryExecutionContract:
    step: WorkflowStepPreview
    requirement: RouteRequirement
    route_plan: RoutePlanPreview
    primary: RouteCandidateDecision
    compiled_queries: tuple[CompiledPlatformQuery, ...]


def _not_runnable(reason: str) -> WorkflowVersionNotFixtureRunnableError:
    return WorkflowVersionNotFixtureRunnableError(
        f"workflow_version_not_fixture_runnable:{reason}"
    )


def _compiled_queries_for(
    preview: WorkflowPlanPreview,
    requirement: RouteRequirement,
) -> tuple[CompiledPlatformQuery, ...]:
    requirement_scopes = set(requirement.scope_keys)
    matches = [
        query
        for query in preview.compiled_queries
        if query.platform is requirement.platform
        and query.resource_type is requirement.resource_type
        and set(query.scope_keys).issubset(requirement_scopes)
    ]
    covered_scopes = {scope_key for query in matches for scope_key in query.scope_keys}
    if not matches or covered_scopes != requirement_scopes:
        raise _not_runnable("compiled_query")
    if any(
        preview.query_versions.get(requirement.platform) != query.query_version
        for query in matches
    ):
        raise _not_runnable("query_version")
    return tuple(
        query.model_copy(deep=True)
        for query in sorted(
            matches,
            key=lambda item: (
                item.scope_keys,
                item.operation.value,
                item.normalized_expression,
            ),
        )
    )


def build_primary_execution_contracts(
    preview: WorkflowPlanPreview,
) -> tuple[PrimaryExecutionContract, ...]:
    if preview.planning_status is not PlanningStatus.RESOLVED:
        raise _not_runnable("planning_status")

    future_steps = [
        step for step in preview.steps if step.execution_kind == "future_capability"
    ]
    if not future_steps:
        raise _not_runnable("future_steps")
    if any(
        step.planning_status is not WorkflowStepPlanningStatus.PLANNED
        for step in future_steps
    ):
        raise _not_runnable("step_status")

    requirement_refs = [step.requirement_ref for step in future_steps]
    if any(item is None for item in requirement_refs) or len(set(requirement_refs)) != len(
        requirement_refs
    ):
        raise _not_runnable("step_requirement")

    requirements: dict[str, RouteRequirement] = {
        item.requirement_ref: item for item in preview.route_requirements
    }
    if len(requirements) != len(preview.route_requirements):
        raise _not_runnable("duplicate_requirement")
    routes: dict[str, RoutePlanPreview] = {
        item.requirement_ref: item for item in preview.route_plans
    }
    if len(routes) != len(preview.route_plans):
        raise _not_runnable("duplicate_route")
    contracts: list[PrimaryExecutionContract] = []
    for step in sorted(future_steps, key=lambda item: (item.sequence, item.step_ref)):
        requirement_ref = step.requirement_ref
        if requirement_ref is None:
            raise _not_runnable("step_requirement")
        requirement = requirements.get(requirement_ref)
        route = routes.get(requirement_ref)
        if requirement is None or route is None:
            raise _not_runnable("requirement_route")
        if (
            step.step_ref not in requirement.step_refs
            or step.platform is not requirement.platform
            or step.resource_type is not requirement.resource_type
            or step.operation is not requirement.operation
            or sorted(step.scope_keys) != sorted(requirement.scope_keys)
        ):
            raise _not_runnable("step_requirement_alignment")
        if (
            route.status is not RoutePlanStatus.RESOLVED
            or not route.route_eligible
            or route.requirement_ref != requirement_ref
            or route.required_fields != requirement.required_fields
            or route.optional_fields != requirement.optional_fields
        ):
            raise _not_runnable("route")
        primary = route.primary_implementation
        if primary is None or not primary.route_eligible or not primary.evidence_refs:
            raise _not_runnable("primary")
        contracts.append(
            PrimaryExecutionContract(
                step=step.model_copy(deep=True),
                requirement=requirement.model_copy(deep=True),
                route_plan=route.model_copy(deep=True),
                primary=primary.model_copy(deep=True),
                compiled_queries=_compiled_queries_for(preview, requirement),
            )
        )
    return tuple(contracts)


def _require_sha256(value: str, *, field: str) -> None:
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field}_invalid")


def compute_workflow_step_input_digest(
    contract: PrimaryExecutionContract,
    *,
    workflow_version_id: UUID,
    preview_fingerprint: str,
    fixture: WorkflowStepFixtureIdentity,
) -> str:
    _require_sha256(preview_fingerprint, field="preview_fingerprint")
    payload = cast(
        JsonValue,
        {
            "execution_contract_version": "workflow_execution_fixture.v1",
            "workflow_version_id": str(workflow_version_id),
            "preview_fingerprint": preview_fingerprint,
            "step_ref": contract.step.step_ref,
            "requirement_ref": contract.requirement.requirement_ref,
            "platform": contract.requirement.platform.value,
            "resource_type": contract.requirement.resource_type.value,
            "operation": contract.requirement.operation.value,
            "assertion_id": contract.primary.assertion_id,
            "implementation_id": contract.primary.implementation_id,
            "compiled_queries": [
                {
                    "query_version": query.query_version,
                    "normalized_expression": query.normalized_expression,
                    "scope_keys": sorted(set(query.scope_keys)),
                    "include_terms": sorted(set(query.include_terms)),
                    "exclude_terms": sorted(set(query.exclude_terms)),
                    "account_filters": sorted(set(query.account_filters)),
                    "url_inputs": sorted(set(query.url_inputs)),
                }
                for query in contract.compiled_queries
            ],
            "required_fields": sorted(set(contract.requirement.required_fields)),
            "optional_fields": sorted(set(contract.requirement.optional_fields)),
            "fixture_profile_hash": fixture.fixture_profile_hash,
            "fixture_case_id": fixture.fixture_case_id,
            "fixture_content_hash": fixture.fixture_content_hash,
        },
    )
    return sha256_id(payload)


__all__ = [
    "PrimaryExecutionContract",
    "WorkflowStepFixtureIdentity",
    "WorkflowVersionNotFixtureRunnableError",
    "build_primary_execution_contracts",
    "compute_workflow_step_input_digest",
]
