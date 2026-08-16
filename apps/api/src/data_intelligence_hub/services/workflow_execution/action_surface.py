from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import cast

from pydantic import JsonValue

from data_intelligence_hub.schemas.workflow_action_command import (
    WORKFLOW_ACTION_APPROVAL_KIND_BY_ACTION,
    WorkflowActionAvailabilityBlockerCode,
    WorkflowRunActionGatesV2Response,
    WorkflowRunActionGateV2Evidence,
)
from data_intelligence_hub.schemas.workflow_attempt_fallback import (
    WorkflowAttemptFallbackEvidenceResponse,
)
from data_intelligence_hub.schemas.workflow_checkpoint_budget import (
    WorkflowCheckpointBudgetEvidenceResponse,
)
from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowRunDetailResponse,
    WorkflowRunStatus,
)
from data_intelligence_hub.schemas.workflow_provider_health import (
    WorkflowProviderHealthEvidenceResponse,
)
from data_intelligence_hub.services.workflow_execution.action_command import (
    WorkflowActionCommandEvidence,
)
from data_intelligence_hub.services.workflow_execution.action_gate import (
    build_workflow_run_action_gates,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id


@dataclass(frozen=True, slots=True)
class WorkflowRunActionSurface:
    response: WorkflowRunActionGatesV2Response
    evidence: WorkflowActionCommandEvidence


def _availability_blockers(
    *,
    action: str,
    run_status: WorkflowRunStatus,
    precondition_status: str,
) -> list[WorkflowActionAvailabilityBlockerCode]:
    if precondition_status != "ready_for_review":
        return []
    if action != "cancel":
        return ["workflow_action_persistence_unavailable"]
    if run_status is WorkflowRunStatus.RUNNING:
        return ["workflow_action_executor_ack_unavailable"]
    return []


def build_workflow_run_action_surface(
    *,
    detail: WorkflowRunDetailResponse,
    attempt_fallback: WorkflowAttemptFallbackEvidenceResponse,
    checkpoint_budget: WorkflowCheckpointBudgetEvidenceResponse,
    provider_health: WorkflowProviderHealthEvidenceResponse,
    action_context_version: int,
    evaluated_at: datetime,
) -> WorkflowRunActionSurface:
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("workflow_action_surface_time_invalid")
    if action_context_version < 1:
        raise ValueError("workflow_action_context_version_invalid")

    v1 = build_workflow_run_action_gates(
        detail=detail,
        attempt_fallback=attempt_fallback,
        checkpoint_budget=checkpoint_budget,
        provider_health=provider_health,
    )
    expires_at = evaluated_at + timedelta(minutes=15)
    gates = [
        WorkflowRunActionGateV2Evidence(
            action=gate.action,
            precondition_status=gate.precondition_status,
            precondition_blocker_codes=gate.precondition_blocker_codes,
            submission_available=(
                gate.precondition_status == "ready_for_review"
                and not _availability_blockers(
                    action=gate.action,
                    run_status=v1.run_status,
                    precondition_status=gate.precondition_status,
                )
            ),
            availability_blocker_codes=_availability_blockers(
                action=gate.action,
                run_status=v1.run_status,
                precondition_status=gate.precondition_status,
            ),
            approval_kind=WORKFLOW_ACTION_APPROVAL_KIND_BY_ACTION[gate.action],
            evidence_refs=gate.evidence_refs,
            expires_at=expires_at,
        )
        for gate in v1.gates
    ]
    digest_payload = {
        "schema_version": "workflow_run_action_gates.v2",
        "workspace_id": str(v1.workspace_id),
        "project_id": str(v1.project_id),
        "workflow_plan_id": str(v1.workflow_plan_id),
        "workflow_version_id": str(v1.workflow_version_id),
        "workflow_run_id": str(v1.workflow_run_id),
        "run_status": v1.run_status.value,
        "action_context_version": action_context_version,
        "gates": [gate.model_dump(mode="json", exclude={"expires_at"}) for gate in gates],
    }
    action_gate_digest = sha256_id(cast(JsonValue, digest_payload))
    response = WorkflowRunActionGatesV2Response(
        workspace_id=v1.workspace_id,
        project_id=v1.project_id,
        workflow_plan_id=v1.workflow_plan_id,
        workflow_version_id=v1.workflow_version_id,
        workflow_run_id=v1.workflow_run_id,
        run_status=v1.run_status,
        action_gate_digest=action_gate_digest,
        action_context_version=action_context_version,
        gates=gates,
        ready_for_review_total=sum(
            gate.precondition_status == "ready_for_review" for gate in gates
        ),
        blocked_total=sum(gate.precondition_status == "blocked" for gate in gates),
        not_applicable_total=sum(gate.precondition_status == "not_applicable" for gate in gates),
        available_action_total=sum(gate.submission_available for gate in gates),
    )

    usage = checkpoint_budget.usage
    evidence = WorkflowActionCommandEvidence(
        action_gate_digest=action_gate_digest,
        evidence_digests=(action_gate_digest,),
        checkpoint_available=any(
            not step.terminal and step.next_cursor is not None
            for step in checkpoint_budget.checkpoint_steps
        ),
        checkpoint_terminal=bool(checkpoint_budget.checkpoint_steps)
        and all(step.terminal for step in checkpoint_budget.checkpoint_steps),
        budget_within_limit=checkpoint_budget.budget_status in {"configured", "within_limit"},
        failed_step_requires_retry=any(step.status.value == "failed" for step in detail.steps),
        budget_held=checkpoint_budget.budget_status == "held",
        budget_current_request_count=usage.request_count if usage else 0,
        budget_current_item_count=usage.item_count if usage else 0,
        budget_current_quota_units=(sum(usage.quota_units.values()) if usage else 0),
        budget_current_cost_usd=usage.cost_usd if usage else Decimal("0"),
        budget_current_elapsed_ms=usage.time_ms if usage else 0,
    )
    return WorkflowRunActionSurface(response=response, evidence=evidence)


__all__ = ["WorkflowRunActionSurface", "build_workflow_run_action_surface"]
