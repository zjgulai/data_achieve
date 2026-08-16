from __future__ import annotations

from collections.abc import Sequence
from typing import cast
from uuid import UUID

from pydantic import JsonValue

from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowRunResponse,
    WorkflowStepRunResponse,
)
from data_intelligence_hub.schemas.workflow_lineage import (
    WorkflowDatasetLineagePreview,
    WorkflowProviderLineagePreview,
    WorkflowRawRecordLineagePreview,
    WorkflowRunLineagePreview,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id

PAYLOAD_UNBOUND_BLOCKER = "workflow_payload_unbound"
ALREADY_MATERIALIZED_BLOCKER = "workflow_run_already_materialized"


class WorkflowLineagePreviewInvalidError(ValueError):
    """The immutable fixture evidence cannot form a safe lineage preview."""


def _invalid(reason: str) -> WorkflowLineagePreviewInvalidError:
    return WorkflowLineagePreviewInvalidError(f"workflow_lineage_preview_invalid:{reason}")


def _validate_inputs(
    run: WorkflowRunResponse,
    steps: Sequence[WorkflowStepRunResponse],
) -> tuple[WorkflowStepRunResponse, ...]:
    if run.execution_mode != "fixture":
        raise _invalid("execution_mode")
    if run.status != "completed":
        raise _invalid("run_status")
    if run.provider_call_attempted or run.credential_read_attempted:
        raise _invalid("provider_boundary")
    if run.actor_run or run.browser_run or run.llm_call or run.production_write_allowed:
        raise _invalid("execution_boundary")
    frozen_steps = tuple(steps)
    if not frozen_steps:
        raise _invalid("steps_required")
    step_ids = [item.id for item in frozen_steps]
    if len(step_ids) != len(set(step_ids)):
        raise _invalid("step_duplicate")
    if len(frozen_steps) != run.total_steps:
        raise _invalid("step_count")
    sequences = [item.sequence for item in frozen_steps]
    if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
        raise _invalid("step_order")
    if run.records_count != sum(item.records_count for item in frozen_steps):
        raise _invalid("record_count")
    for step in frozen_steps:
        if (
            step.workflow_run_id != run.id
            or step.workspace_id != run.workspace_id
            or step.project_id != run.project_id
        ):
            raise _invalid("scope_mismatch")
        if step.status != "completed":
            raise _invalid("step_status")
        if not step.evidence_refs:
            raise _invalid("evidence_required")
        if len(step.evidence_refs) != len(set(step.evidence_refs)):
            raise _invalid("evidence_duplicate")
        if step.provider_call_attempted or step.credential_read_attempted:
            raise _invalid("step_provider_boundary")
        if step.actor_run or step.browser_run or step.llm_call or step.production_write_allowed:
            raise _invalid("step_execution_boundary")
    return frozen_steps


def build_workflow_lineage_preview(
    run: WorkflowRunResponse,
    steps: Sequence[WorkflowStepRunResponse],
    *,
    payload_bound: bool = False,
    materialized_raw_record_ids: Sequence[UUID] = (),
    dataset_id: UUID | None = None,
    dataset_version_id: UUID | None = None,
) -> WorkflowRunLineagePreview:
    """Map frozen fixture evidence without creating downstream data objects."""

    frozen_steps = _validate_inputs(run, steps)
    provider_evidence = [
        WorkflowProviderLineagePreview(
            step_run_id=step.id,
            implementation_id=step.implementation_id,
            platform=step.platform,
            resource_type=step.resource_type,
            operation=step.operation,
            fixture_case_id=step.fixture_case_id,
            fixture_content_hash=step.fixture_content_hash,
            output_digest=step.output_digest,
            records_count=step.records_count,
            evidence_refs=list(step.evidence_refs),
        )
        for step in frozen_steps
    ]
    source_step_run_ids = [item.id for item in frozen_steps]
    expected_record_count = sum(item.records_count for item in frozen_steps)
    raw_record_ids = list(materialized_raw_record_ids)
    materialized = bool(raw_record_ids)
    lineage_payload = cast(
        JsonValue,
        [
            {
                "step_run_id": str(step.id),
                "fixture_case_id": step.fixture_case_id,
                "output_digest": step.output_digest,
                "records_count": step.records_count,
                "evidence_refs": list(step.evidence_refs),
            }
            for step in frozen_steps
        ],
    )
    blocked_reasons: list[str] = []
    if not payload_bound:
        blocked_reasons.append(PAYLOAD_UNBOUND_BLOCKER)
    if materialized:
        blocked_reasons.append(ALREADY_MATERIALIZED_BLOCKER)
    return WorkflowRunLineagePreview(
        schema_version="workflow_lineage_preview.v2",
        workflow_run_id=run.id,
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        lineage_digest=sha256_id(lineage_payload),
        materialization_eligible=payload_bound and not materialized,
        provider_evidence=provider_evidence,
        raw_record=WorkflowRawRecordLineagePreview(
            source_task_run_id=None,
            source_step_run_ids=source_step_run_ids,
            materialized_raw_record_ids=raw_record_ids,
            expected_record_count=expected_record_count,
            raw_record_write=False,
            materialized=materialized,
            blocked_reasons=blocked_reasons,
        ),
        dataset=WorkflowDatasetLineagePreview(
            dataset_id=dataset_id,
            dataset_version_id=dataset_version_id,
            source_step_run_ids=source_step_run_ids,
            source_raw_record_ids=raw_record_ids,
            expected_record_count=expected_record_count,
            dataset_write=False,
            materialized=materialized,
            blocked_reasons=blocked_reasons,
        ),
        blocked_reasons=blocked_reasons,
        provider_call=False,
        database_write=False,
        raw_record_write=False,
        dataset_write=False,
    )


__all__ = [
    "ALREADY_MATERIALIZED_BLOCKER",
    "PAYLOAD_UNBOUND_BLOCKER",
    "WorkflowLineagePreviewInvalidError",
    "build_workflow_lineage_preview",
]
