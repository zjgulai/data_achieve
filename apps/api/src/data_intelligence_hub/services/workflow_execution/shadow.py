from __future__ import annotations

import math
from dataclasses import dataclass
from typing import cast

from pydantic import JsonValue

from data_intelligence_hub.schemas.workflow_lineage import WorkflowProviderPayloadRecord
from data_intelligence_hub.schemas.workflow_shadow import WorkflowShadowDifferenceEvidence
from data_intelligence_hub.services.workflow_execution.eligibility import (
    PrimaryExecutionContract,
)
from data_intelligence_hub.services.workflow_execution.fixtures import (
    LoadedWorkflowFixtureProfile,
    WorkflowFixtureContractInvalidError,
    WorkflowFixtureStepReceipt,
    execute_workflow_fixture_candidate,
    get_workflow_fixture_candidate_case,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id


@dataclass(frozen=True, slots=True)
class WorkflowShadowComparisonDraft:
    contract_version: str
    comparison_digest: str
    primary_implementation_id: str
    shadow_implementation_id: str
    fixture_profile_id: str
    fixture_profile_hash: str
    primary_fixture_case_id: str
    primary_fixture_content_hash: str
    shadow_fixture_case_id: str
    shadow_fixture_content_hash: str
    sample_rate: float
    max_items: int
    sampled_items: int
    matched_items: int
    mismatched_items: int
    primary_only_items: int
    shadow_only_items: int
    equivalence_status: str
    difference_evidence: WorkflowShadowDifferenceEvidence
    routing_recommendation: str
    evidence_refs: tuple[str, ...]


def _record_key(record: WorkflowProviderPayloadRecord) -> str:
    record_id = record.content.get("id")
    if isinstance(record_id, str) and record_id:
        return f"id:{record_id}"
    if record.source_url:
        return f"url:{record.source_url}"
    return f"content:{sha256_id(cast(JsonValue, record.content))}"


def _records_by_key(
    records: list[WorkflowProviderPayloadRecord],
) -> dict[str, WorkflowProviderPayloadRecord]:
    indexed = {_record_key(record): record for record in records}
    if len(indexed) != len(records):
        raise WorkflowFixtureContractInvalidError(
            "workflow_fixture_contract_invalid:shadow_record_key_duplicate"
        )
    return indexed


def _required_projection(
    record: WorkflowProviderPayloadRecord,
    required_fields: list[str],
) -> dict[str, JsonValue | None]:
    return {field: record.content.get(field) for field in required_fields}


def compile_workflow_fixture_shadow_comparison(
    loaded: LoadedWorkflowFixtureProfile,
    contract: PrimaryExecutionContract,
    primary_receipt: WorkflowFixtureStepReceipt,
) -> WorkflowShadowComparisonDraft | None:
    rule = contract.route_plan.shadow_rule
    shadow_implementation_id = rule.fallback_implementation_id
    if (
        not rule.enabled
        or shadow_implementation_id is None
        or rule.sample_rate is None
        or rule.max_items is None
        or shadow_implementation_id not in loaded.allowed_implementation_ids
    ):
        return None

    shadow_candidate = next(
        (
            item
            for item in contract.route_plan.fallback_implementations
            if item.implementation_id == shadow_implementation_id
        ),
        None,
    )
    if shadow_candidate is None or not shadow_candidate.route_eligible:
        raise WorkflowFixtureContractInvalidError(
            "workflow_fixture_contract_invalid:shadow_candidate_unbound"
        )

    primary_case = get_workflow_fixture_candidate_case(
        loaded,
        implementation_id=contract.primary.implementation_id,
        platform=contract.requirement.platform,
        resource_type=contract.requirement.resource_type,
        operation=contract.requirement.operation,
        evidence_refs=list(contract.primary.evidence_refs),
    )
    checked_primary_receipt = execute_workflow_fixture_candidate(
        loaded,
        implementation_id=contract.primary.implementation_id,
        platform=contract.requirement.platform,
        resource_type=contract.requirement.resource_type,
        operation=contract.requirement.operation,
        evidence_refs=list(contract.primary.evidence_refs),
    )
    if checked_primary_receipt != primary_receipt:
        raise WorkflowFixtureContractInvalidError(
            "workflow_fixture_contract_invalid:shadow_primary_receipt_mismatch"
        )

    shadow_case = get_workflow_fixture_candidate_case(
        loaded,
        implementation_id=shadow_candidate.implementation_id,
        platform=contract.requirement.platform,
        resource_type=contract.requirement.resource_type,
        operation=contract.requirement.operation,
        evidence_refs=list(shadow_candidate.evidence_refs),
    )
    shadow_receipt = execute_workflow_fixture_candidate(
        loaded,
        implementation_id=shadow_candidate.implementation_id,
        platform=contract.requirement.platform,
        resource_type=contract.requirement.resource_type,
        operation=contract.requirement.operation,
        evidence_refs=list(shadow_candidate.evidence_refs),
    )
    if primary_case.records is None or shadow_case.records is None:
        return None

    primary_records = _records_by_key(primary_case.records)
    shadow_records = _records_by_key(shadow_case.records)
    available_items = max(len(primary_records), len(shadow_records))
    if available_items == 0:
        return None
    sample_limit = min(
        rule.max_items,
        max(1, math.ceil(available_items * rule.sample_rate)),
        available_items,
    )
    sampled_keys = sorted(set(primary_records) | set(shadow_records))[:sample_limit]

    matched: list[str] = []
    mismatched: list[str] = []
    primary_only: list[str] = []
    shadow_only: list[str] = []
    missing_required_fields: set[str] = set()
    required_fields = sorted(set(contract.requirement.required_fields))
    for key in sampled_keys:
        primary_record = primary_records.get(key)
        shadow_record = shadow_records.get(key)
        if primary_record is None:
            shadow_only.append(key)
            continue
        if shadow_record is None:
            primary_only.append(key)
            continue
        primary_projection = _required_projection(primary_record, required_fields)
        shadow_projection = _required_projection(shadow_record, required_fields)
        record_missing_required_fields = {
            field
            for field in required_fields
            if primary_projection[field] is None or shadow_projection[field] is None
        }
        missing_required_fields.update(record_missing_required_fields)
        if primary_projection == shadow_projection and not record_missing_required_fields:
            matched.append(key)
        else:
            mismatched.append(key)

    primary_fields = set(primary_case.summary.fields)
    shadow_fields = set(shadow_case.summary.fields)
    evidence = WorkflowShadowDifferenceEvidence(
        sampled_record_keys=sampled_keys,
        matched_record_keys=matched,
        mismatched_record_keys=mismatched,
        primary_only_record_keys=primary_only,
        shadow_only_record_keys=shadow_only,
        missing_required_fields=sorted(missing_required_fields),
        primary_only_fields=sorted(primary_fields - shadow_fields),
        shadow_only_fields=sorted(shadow_fields - primary_fields),
    )
    equivalent = len(matched) == len(sampled_keys)
    equivalence_status = "equivalent" if equivalent else "different"
    routing_recommendation = (
        "eligible_for_governance_review"
        if equivalent
        else "keep_primary_investigate_shadow"
    )
    evidence_refs = tuple(
        sorted(set(primary_receipt.evidence_refs + shadow_receipt.evidence_refs))
    )
    digest_payload = cast(
        JsonValue,
        {
            "contract_version": "workflow_shadow_comparison.v1",
            "requirement_ref": contract.requirement.requirement_ref,
            "primary_implementation_id": contract.primary.implementation_id,
            "shadow_implementation_id": shadow_candidate.implementation_id,
            "fixture_profile_id": loaded.profile.profile_id,
            "fixture_profile_hash": loaded.profile_hash,
            "primary_fixture_case_id": primary_receipt.fixture_case_id,
            "primary_fixture_content_hash": primary_receipt.fixture_content_hash,
            "shadow_fixture_case_id": shadow_receipt.fixture_case_id,
            "shadow_fixture_content_hash": shadow_receipt.fixture_content_hash,
            "sample_rate": rule.sample_rate,
            "max_items": rule.max_items,
            "sampled_items": len(sampled_keys),
            "equivalence_status": equivalence_status,
            "difference_evidence": evidence.model_dump(mode="json"),
            "routing_recommendation": routing_recommendation,
            "evidence_refs": list(evidence_refs),
            "catalog_mutation_applied": False,
            "route_ranking_mutation_applied": False,
        },
    )
    return WorkflowShadowComparisonDraft(
        contract_version="workflow_shadow_comparison.v1",
        comparison_digest=sha256_id(digest_payload),
        primary_implementation_id=contract.primary.implementation_id,
        shadow_implementation_id=shadow_candidate.implementation_id,
        fixture_profile_id=loaded.profile.profile_id,
        fixture_profile_hash=loaded.profile_hash,
        primary_fixture_case_id=primary_receipt.fixture_case_id,
        primary_fixture_content_hash=primary_receipt.fixture_content_hash,
        shadow_fixture_case_id=shadow_receipt.fixture_case_id,
        shadow_fixture_content_hash=shadow_receipt.fixture_content_hash,
        sample_rate=rule.sample_rate,
        max_items=rule.max_items,
        sampled_items=len(sampled_keys),
        matched_items=len(matched),
        mismatched_items=len(mismatched),
        primary_only_items=len(primary_only),
        shadow_only_items=len(shadow_only),
        equivalence_status=equivalence_status,
        difference_evidence=evidence,
        routing_recommendation=routing_recommendation,
        evidence_refs=evidence_refs,
    )


__all__ = [
    "WorkflowShadowComparisonDraft",
    "compile_workflow_fixture_shadow_comparison",
]
