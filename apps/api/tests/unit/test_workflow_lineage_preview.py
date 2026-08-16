from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.capability_catalog import CapabilityCatalog
from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowRunResponse,
    WorkflowStepRunResponse,
)
from data_intelligence_hub.schemas.workflow_lineage import (
    WorkflowRunLineagePreview,
)
from data_intelligence_hub.schemas.workflow_planner import PlanningInput, WorkflowPlanPreview
from data_intelligence_hub.services.workflow_execution.lineage_preview import (
    WorkflowLineagePreviewInvalidError,
    build_workflow_lineage_preview,
)
from data_intelligence_hub.services.workflow_planner.planner import (
    build_workflow_plan_preview,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "workflow_planner"
PERIODIC_FIXTURE = FIXTURE_DIR / "periodic_monitoring_request_v1.json"
SYNTHETIC_CATALOG_FIXTURE = FIXTURE_DIR / "synthetic_capability_catalog_v1.json"
WORKSPACE_ID = UUID("00000000-0000-0000-0000-000000000101")
PROJECT_ID = UUID("00000000-0000-0000-0000-000000000102")
USER_ID = UUID("00000000-0000-0000-0000-000000000103")
PLAN_ID = UUID("00000000-0000-0000-0000-000000000104")
VERSION_ID = UUID("00000000-0000-0000-0000-000000000105")
RUN_ID = UUID("00000000-0000-0000-0000-000000000106")
STEP_ID = UUID("00000000-0000-0000-0000-000000000107")
TEMPLATE_ID = UUID("00000000-0000-0000-0000-000000000108")
REVISION_ID = UUID("00000000-0000-0000-0000-000000000109")
NOW = datetime(2026, 7, 15, 8, 0, tzinfo=UTC)
DIGEST = "sha256:" + "b" * 64


def _planning_input() -> PlanningInput:
    payload = cast(
        dict[str, object],
        json.loads(PERIODIC_FIXTURE.read_text(encoding="utf-8")),
    )
    payload["required_fields"] = ["id", "url", "text"]
    return PlanningInput.model_validate(payload)


def _preview() -> WorkflowPlanPreview:
    return build_workflow_plan_preview(
        project_id=PROJECT_ID,
        planning_input=_planning_input(),
        catalog=CapabilityCatalog.model_validate_json(
            SYNTHETIC_CATALOG_FIXTURE.read_text(encoding="utf-8")
        ),
        generated_at=NOW,
        request_id="workflow-lineage-preview-test",
    )


def _run(
    fixture_profile_id: str = "fixture-primary-v1",
    *,
    records_count: int = 2,
) -> WorkflowRunResponse:
    preview = _preview()
    return WorkflowRunResponse(
        id=RUN_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_plan_id=PLAN_ID,
        workflow_version_id=VERSION_ID,
        workflow_template_id=TEMPLATE_ID,
        workflow_template_revision_id=REVISION_ID,
        created_by_user_id=USER_ID,
        execution_contract_version="workflow_execution_fixture.v1",
        execution_mode="fixture",
        status="completed",
        planner_contract_version=preview.planner_contract_version,
        preview_fingerprint=preview.preview_fingerprint,
        catalog_snapshot_id=preview.catalog_snapshot_id,
        policy_version=preview.policy_version,
        mode_template_version=preview.mode_template_version,
        query_versions=preview.query_versions,
        fixture_profile_id=fixture_profile_id,
        fixture_profile_hash=DIGEST,
        total_steps=1,
        completed_steps=1,
        records_count=records_count,
        started_at=NOW,
        finished_at=NOW,
        created_at=NOW,
    )


def _step(*, records_count: int = 2) -> WorkflowStepRunResponse:
    preview = _preview()
    step = next(item for item in preview.steps if item.execution_kind == "future_capability")
    route = next(
        item for item in preview.route_plans if item.requirement_ref == step.requirement_ref
    )
    candidate = route.primary_implementation
    assert candidate is not None
    assert step.platform is not None
    assert step.resource_type is not None
    assert step.operation is not None
    assert step.requirement_ref is not None
    return WorkflowStepRunResponse(
        id=STEP_ID,
        workflow_run_id=RUN_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        step_ref=step.step_ref,
        requirement_ref=step.requirement_ref,
        sequence=step.sequence,
        platform=step.platform,
        resource_type=step.resource_type,
        operation=step.operation,
        assertion_id=candidate.assertion_id,
        implementation_id=candidate.implementation_id,
        route_plan_snapshot=route,
        evidence_refs=candidate.evidence_refs,
        fixture_case_id="youtube-content-list-v1",
        fixture_content_hash=DIGEST,
        input_digest=DIGEST,
        output_digest="sha256:" + "c" * 64,
        idempotency_scope="workflow_fixture_step:v1",
        idempotency_key_hash="sha256:" + "d" * 64,
        status="completed",
        records_count=records_count,
        started_at=NOW,
        finished_at=NOW,
        created_at=NOW,
    )


def test_preview_is_deterministic_and_preserves_provider_step_evidence() -> None:
    run = _run()
    step = _step()

    first = build_workflow_lineage_preview(run, [step], payload_bound=True)
    second = build_workflow_lineage_preview(run, [step], payload_bound=True)

    assert first == second
    assert first.schema_version == "workflow_lineage_preview.v2"
    assert first.materialization_eligible is True
    assert first.lineage_digest.startswith("sha256:")
    assert first.blocked_reasons == []
    assert first.workflow_run_id == RUN_ID
    assert first.provider_evidence[0].step_run_id == STEP_ID
    assert first.provider_evidence[0].implementation_id == step.implementation_id
    assert first.provider_evidence[0].evidence_refs == step.evidence_refs
    assert first.raw_record.expected_record_count == 2
    assert first.dataset.expected_record_count == 2


def test_preview_is_explicitly_non_materialized_and_does_not_expose_payloads() -> None:
    preview = build_workflow_lineage_preview(_run(), [_step()], payload_bound=False)
    payload = preview.model_dump(mode="json")

    assert payload["provider_call"] is False
    assert payload["database_write"] is False
    assert payload["raw_record_write"] is False
    assert payload["dataset_write"] is False
    assert payload["raw_record"]["materialized"] is False
    assert payload["dataset"]["materialized"] is False
    assert payload["raw_record"]["materialized_raw_record_ids"] == []
    assert payload["dataset"]["dataset_id"] is None
    assert payload["dataset"]["dataset_version_id"] is None
    assert "raw_payload" not in payload
    assert "fixture_body" not in payload
    assert "content" not in payload
    assert preview.materialization_eligible is False
    assert preview.blocked_reasons == ["workflow_payload_unbound"]


@pytest.mark.parametrize(
    "mutated_step",
    [
        lambda step: step.model_copy(update={"project_id": uuid4()}),
        lambda step: step.model_copy(update={"workspace_id": uuid4()}),
        lambda step: step.model_copy(update={"workflow_run_id": uuid4()}),
        lambda step: step.model_copy(update={"evidence_refs": []}),
    ],
)
def test_preview_fails_closed_on_scope_or_evidence_mismatch(
    mutated_step: Callable[[WorkflowStepRunResponse], WorkflowStepRunResponse],
) -> None:
    with pytest.raises(WorkflowLineagePreviewInvalidError):
        build_workflow_lineage_preview(
            _run(),
            [mutated_step(_step())],
            payload_bound=True,
        )


def test_preview_rejects_duplicate_or_empty_step_sets() -> None:
    with pytest.raises(WorkflowLineagePreviewInvalidError, match="steps_required"):
        build_workflow_lineage_preview(_run(), [], payload_bound=True)
    with pytest.raises(WorkflowLineagePreviewInvalidError, match="step_duplicate"):
        build_workflow_lineage_preview(_run(), [_step(), _step()], payload_bound=True)


def test_preview_contract_rejects_partial_materialized_dataset_identity() -> None:
    with pytest.raises(ValidationError):
        WorkflowRunLineagePreview.model_validate(
            {
                **build_workflow_lineage_preview(
                    _run(),
                    [_step()],
                    payload_bound=True,
                ).model_dump(mode="json"),
                "dataset": {
                    **build_workflow_lineage_preview(
                        _run(),
                        [_step()],
                        payload_bound=True,
                    ).dataset.model_dump(mode="json"),
                    "dataset_id": str(uuid4()),
                },
            }
        )


def test_preview_reports_complete_materialized_asset_identity() -> None:
    raw_record_ids = [uuid4(), uuid4()]
    dataset_id = uuid4()
    dataset_version_id = uuid4()
    preview = build_workflow_lineage_preview(
        _run("fixture-primary-payload-v1"),
        [_step()],
        payload_bound=True,
        materialized_raw_record_ids=raw_record_ids,
        dataset_id=dataset_id,
        dataset_version_id=dataset_version_id,
    )

    assert preview.raw_record.materialized is True
    assert preview.raw_record.materialized_raw_record_ids == raw_record_ids
    assert preview.dataset.materialized is True
    assert preview.dataset.dataset_id == dataset_id
    assert preview.dataset.dataset_version_id == dataset_version_id
    assert preview.dataset.source_raw_record_ids == raw_record_ids
    assert preview.materialization_eligible is False
    assert preview.blocked_reasons == ["workflow_run_already_materialized"]


def test_preview_accepts_full_materialization_batch() -> None:
    raw_record_ids = [uuid4() for _ in range(1000)]
    preview = build_workflow_lineage_preview(
        _run("fixture-primary-payload-v1", records_count=1000),
        [_step(records_count=1000)],
        payload_bound=True,
        materialized_raw_record_ids=raw_record_ids,
        dataset_id=uuid4(),
        dataset_version_id=uuid4(),
    )

    assert preview.raw_record.materialized_raw_record_ids == raw_record_ids
    assert preview.dataset.source_raw_record_ids == raw_record_ids
