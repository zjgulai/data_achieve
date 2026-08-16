from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.capability_catalog import CapabilityCatalog
from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowFixtureRunCreateRequest,
    WorkflowFixtureRunCreateResponse,
    WorkflowRunDetailResponse,
    WorkflowRunListResponse,
    WorkflowRunResponse,
    WorkflowStepRunResponse,
    normalize_workflow_execution_idempotency_key,
)
from data_intelligence_hub.schemas.workflow_planner import (
    PlanningInput,
    WorkflowPlanPreview,
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
FINGERPRINT = "sha256:" + "a" * 64
DIGEST = "sha256:" + "b" * 64


def _planning_input() -> PlanningInput:
    payload = cast(
        dict[str, object],
        json.loads(PERIODIC_FIXTURE.read_text(encoding="utf-8")),
    )
    payload["required_fields"] = ["id", "url", "text"]
    return PlanningInput.model_validate(payload)


def _catalog() -> CapabilityCatalog:
    return CapabilityCatalog.model_validate_json(
        SYNTHETIC_CATALOG_FIXTURE.read_text(encoding="utf-8")
    )


def _preview() -> WorkflowPlanPreview:
    return build_workflow_plan_preview(
        project_id=PROJECT_ID,
        planning_input=_planning_input(),
        catalog=_catalog(),
        generated_at=NOW,
        request_id="workflow-execution-schema-test",
    )


def _run() -> WorkflowRunResponse:
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
        fixture_profile_id="fixture-primary-v1",
        fixture_profile_hash=DIGEST,
        total_steps=1,
        completed_steps=1,
        records_count=2,
        started_at=NOW,
        finished_at=NOW,
        created_at=NOW,
    )


def _step() -> WorkflowStepRunResponse:
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
        records_count=2,
        started_at=NOW,
        finished_at=NOW,
        created_at=NOW,
    )


def test_create_request_is_strict_and_accepts_only_registered_profile_shape() -> None:
    request = WorkflowFixtureRunCreateRequest(
        expected_preview_fingerprint=FINGERPRINT,
        fixture_profile_id="fixture-primary-v1",
    )
    assert request.fixture_profile_id == "fixture-primary-v1"

    invalid_payloads = [
        {**request.model_dump(), "expected_preview_fingerprint": "sha256:ABC"},
        {**request.model_dump(), "fixture_profile_id": "../secret"},
        {**request.model_dump(), "fixture_profile_id": "/tmp/profile.json"},
        {**request.model_dump(), "fixture_profile_id": "A Fixture"},
        {**request.model_dump(), "fixture_path": "fixture-primary-v1.json"},
        {**request.model_dump(), "fixture_body": {}},
    ]
    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            WorkflowFixtureRunCreateRequest.model_validate(payload)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  workflow-run-key-0001  ", "workflow-run-key-0001"),
        ("x" * 12, "x" * 12),
        ("x" * 200, "x" * 200),
    ],
)
def test_idempotency_key_is_trimmed_and_bounded(raw: str, expected: str) -> None:
    assert normalize_workflow_execution_idempotency_key(raw) == expected


@pytest.mark.parametrize("raw", ["", " " * 20, "x" * 11, "x" * 201])
def test_idempotency_key_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(ValueError, match="idempotency_key_invalid"):
        normalize_workflow_execution_idempotency_key(raw)


def test_run_and_step_contracts_keep_frozen_facts_and_false_attempt_flags() -> None:
    run = _run()
    step = _step()

    assert run.status.value == "completed"
    assert run.workflow_template_id == TEMPLATE_ID
    assert run.workflow_template_revision_id == REVISION_ID
    assert run.provider_call_attempted is False
    assert run.credential_read_attempted is False
    assert run.production_write_allowed is False
    assert step.route_plan_snapshot.requirement_ref == step.requirement_ref
    assert step.evidence_refs
    assert step.provider_call_attempted is False
    assert step.records_count == 2


def test_create_attempt_truth_and_boundary_flags_are_consistent() -> None:
    run = _run()
    step = _step()
    created = WorkflowFixtureRunCreateResponse(
        database_write=True,
        idempotent_replay=False,
        run=run,
        steps=[step],
    )
    replay = WorkflowFixtureRunCreateResponse(
        database_write=False,
        idempotent_replay=True,
        run=run,
        steps=[step],
    )

    for response in (created, replay):
        assert response.execution_mode == "fixture"
        assert response.live_execution_authorized is False
        assert response.provider_call is False
        assert response.provider_call_attempted is False
        assert response.credential_read_attempted is False
        assert response.actor_run is False
        assert response.browser_run is False
        assert response.llm_call is False
        assert response.raw_record_write is False
        assert response.dataset_write is False
        assert response.production_write_allowed is False

    with pytest.raises(ValidationError, match="fixture_run_attempt_flags_invalid"):
        WorkflowFixtureRunCreateResponse(
            database_write=False,
            idempotent_replay=False,
            run=run,
            steps=[step],
        )


def test_steps_must_be_unique_and_stably_sorted() -> None:
    run = _run()
    first = _step()
    second = first.model_copy(
        update={
            "id": UUID("00000000-0000-0000-0000-000000000108"),
            "step_ref": "step-z",
            "sequence": first.sequence + 1,
        }
    )

    response = WorkflowFixtureRunCreateResponse(
        database_write=True,
        idempotent_replay=False,
        run=run.model_copy(update={"total_steps": 2, "completed_steps": 2}),
        steps=[first, second],
    )
    assert [item.sequence for item in response.steps] == sorted(
        item.sequence for item in response.steps
    )

    for invalid_steps in ([second, first], [first, first]):
        with pytest.raises(ValidationError, match="workflow_step_order_invalid"):
            WorkflowFixtureRunCreateResponse(
                database_write=True,
                idempotent_replay=False,
                run=run.model_copy(update={"total_steps": 2, "completed_steps": 2}),
                steps=invalid_steps,
            )


def test_list_and_detail_reads_are_write_free_and_shape_separated() -> None:
    run = _run()
    step = _step()
    listed = WorkflowRunListResponse(
        project_status="archived",
        items=[run],
        total=1,
    )
    detailed = WorkflowRunDetailResponse(
        project_status="archived",
        run=run,
        steps=[step],
    )

    assert listed.database_write is False
    assert listed.limit == 50
    assert listed.offset == 0
    assert "steps" not in listed.model_dump()
    assert detailed.database_write is False
    assert detailed.steps[0].route_plan_snapshot.requirement_ref == step.requirement_ref


def test_contracts_do_not_expose_raw_key_or_fixture_body_fields() -> None:
    forbidden = {"idempotency_key", "fixture_raw_body", "fixture_body", "raw_payload"}
    models = (
        WorkflowFixtureRunCreateRequest,
        WorkflowFixtureRunCreateResponse,
        WorkflowRunResponse,
        WorkflowStepRunResponse,
        WorkflowRunListResponse,
        WorkflowRunDetailResponse,
    )
    for model in models:
        assert forbidden.isdisjoint(model.model_fields)
