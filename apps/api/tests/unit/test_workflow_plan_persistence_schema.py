from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.capability_catalog import CapabilityCatalog
from data_intelligence_hub.schemas.workflow_plan_persistence import (
    MonitoringScopeListResponse,
    MonitoringScopeResponse,
    WorkflowPlanCreateRequest,
    WorkflowPlanListResponse,
    WorkflowPlanResponse,
    WorkflowPlanSaveResponse,
    WorkflowPlanVersionCompareResponse,
    WorkflowVersionCreateRequest,
    WorkflowVersionResponse,
    WorkflowVersionSummaryResponse,
    normalize_idempotency_key,
    serialize_preview_snapshot,
)
from data_intelligence_hub.schemas.workflow_planner import (
    PlanningInput,
    WorkflowPlanPreview,
)
from data_intelligence_hub.services.capability_catalog import get_capability_catalog
from data_intelligence_hub.services.workflow_planner.planner import (
    build_workflow_plan_preview,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "workflow_planner"
PERIODIC_FIXTURE = FIXTURE_DIR / "periodic_monitoring_request_v1.json"
PROJECT_ID = UUID("00000000-0000-0000-0000-000000000001")
WORKSPACE_ID = UUID("00000000-0000-0000-0000-000000000002")
USER_ID = UUID("00000000-0000-0000-0000-000000000003")
PLAN_ID = UUID("00000000-0000-0000-0000-000000000004")
VERSION_ID = UUID("00000000-0000-0000-0000-000000000005")
NOW = datetime(2026, 7, 13, tzinfo=UTC)
FINGERPRINT = "sha256:" + "a" * 64


def _planning_input() -> PlanningInput:
    payload = cast(
        dict[str, object],
        json.loads(PERIODIC_FIXTURE.read_text(encoding="utf-8")),
    )
    return PlanningInput.model_validate(payload)


def _catalog() -> CapabilityCatalog:
    return get_capability_catalog()


def _preview() -> WorkflowPlanPreview:
    return build_workflow_plan_preview(
        project_id=PROJECT_ID,
        planning_input=_planning_input(),
        catalog=_catalog(),
        generated_at=NOW,
        request_id="schema-test",
    )


def _plan() -> WorkflowPlanResponse:
    return WorkflowPlanResponse(
        id=PLAN_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        created_by_user_id=USER_ID,
        name="Competitor monitoring",
        flow_mode="periodic_monitoring",
        status="previewed",
        current_version_id=VERSION_ID,
        current_version_number=1,
        planning_status="held",
        scope_count=1,
        query_term_count=2,
        created_at=NOW,
        updated_at=NOW,
    )


def _version() -> WorkflowVersionResponse:
    preview = _preview()
    return WorkflowVersionResponse(
        id=VERSION_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_plan_id=PLAN_ID,
        created_by_user_id=USER_ID,
        version_number=1,
        planning_status=preview.planning_status,
        planner_contract_version=preview.planner_contract_version,
        catalog_snapshot_id=preview.catalog_snapshot_id,
        policy_version=preview.policy_version,
        mode_template_version=preview.mode_template_version,
        query_versions=preview.query_versions,
        preview_fingerprint=preview.preview_fingerprint,
        editable_input=_planning_input(),
        preview=preview,
        created_at=NOW,
    )


def test_create_request_trims_name_and_accepts_only_lowercase_sha256() -> None:
    request = WorkflowPlanCreateRequest(
        name="  Competitor monitoring  ",
        preview_input=_planning_input(),
        expected_preview_fingerprint=FINGERPRINT,
    )

    assert request.name == "Competitor monitoring"

    for invalid in ("sha256:" + "A" * 64, "sha256:abc", "md5:" + "a" * 64):
        with pytest.raises(ValidationError):
            WorkflowPlanCreateRequest(
                name="Plan",
                preview_input=_planning_input(),
                expected_preview_fingerprint=invalid,
            )


@pytest.mark.parametrize("name", ["", "   ", "x" * 201])
def test_create_request_rejects_invalid_trimmed_name(name: str) -> None:
    with pytest.raises(ValidationError):
        WorkflowPlanCreateRequest(
            name=name,
            preview_input=_planning_input(),
            expected_preview_fingerprint=FINGERPRINT,
        )


def test_version_request_requires_current_version_and_forbids_name() -> None:
    request = WorkflowVersionCreateRequest(
        preview_input=_planning_input(),
        expected_preview_fingerprint=FINGERPRINT,
        expected_current_version_id=VERSION_ID,
    )
    assert request.expected_current_version_id == VERSION_ID

    with pytest.raises(ValidationError):
        WorkflowVersionCreateRequest.model_validate(
            {
                **request.model_dump(mode="python"),
                "name": "must not be accepted",
            }
        )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  logical-save-key-0001  ", "logical-save-key-0001"),
        ("x" * 12, "x" * 12),
        ("x" * 200, "x" * 200),
    ],
)
def test_idempotency_key_is_trimmed_and_bounded(raw: str, expected: str) -> None:
    assert normalize_idempotency_key(raw) == expected


@pytest.mark.parametrize("raw", ["", " " * 20, "x" * 11, "x" * 201])
def test_idempotency_key_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(ValueError, match="idempotency_key_invalid"):
        normalize_idempotency_key(raw)


def test_save_response_models_created_no_op_and_replay_attempt_truth() -> None:
    plan = _plan()
    version = _version()

    created = WorkflowPlanSaveResponse(
        database_write=True,
        plan_changed=True,
        outcome="created",
        idempotent_replay=False,
        plan=plan,
        version=version,
    )
    no_op = WorkflowPlanSaveResponse(
        database_write=True,
        plan_changed=False,
        outcome="semantic_no_op",
        idempotent_replay=False,
        plan=plan,
        version=version,
    )
    replay = WorkflowPlanSaveResponse(
        database_write=False,
        plan_changed=False,
        outcome="created",
        idempotent_replay=True,
        plan=plan,
        version=version,
    )

    assert created.model_dump()["provider_call"] is False
    assert no_op.plan_changed is False
    assert replay.database_write is False
    assert replay.execution_authorized is False
    assert replay.workflow_run_created is False

    with pytest.raises(ValidationError, match="save_attempt_flags_invalid"):
        WorkflowPlanSaveResponse(
            database_write=False,
            plan_changed=True,
            outcome="created",
            idempotent_replay=True,
            plan=plan,
            version=version,
        )


def test_preview_snapshot_uses_json_mode() -> None:
    snapshot = serialize_preview_snapshot(_preview())

    assert snapshot["generated_at"] == NOW.isoformat().replace("+00:00", "Z")
    assert snapshot["flow_mode"] == "periodic_monitoring"
    json.dumps(snapshot, allow_nan=False)


def test_read_contracts_allow_archived_project_and_fixed_false_boundaries() -> None:
    plan = _plan()
    plan_list = WorkflowPlanListResponse(
        project_status="archived",
        items=[plan],
        total=1,
    )

    assert plan_list.limit == 50
    assert plan_list.offset == 0
    assert plan_list.database_write is False
    assert plan_list.plan_changed is False
    assert plan_list.provider_call is False


def test_version_history_summary_omits_full_preview_snapshot() -> None:
    version = _version()
    summary = WorkflowVersionSummaryResponse.model_validate(
        version.model_dump(mode="python", exclude={"editable_input", "preview"})
    )

    assert "preview" not in summary.model_dump()
    assert "editable_input" not in summary.model_dump()
    assert summary.preview_fingerprint == version.preview_fingerprint


def test_full_version_requires_editable_input_without_exposing_fingerprint_payload() -> None:
    version = _version()
    serialized = version.model_dump(mode="json")

    assert serialized["editable_input"] == _planning_input().model_dump(mode="json")
    assert "fingerprint_payload" not in serialized
    assert "fingerprint_input" not in serialized

    with pytest.raises(ValidationError):
        WorkflowVersionResponse.model_validate(
            version.model_dump(mode="python", exclude={"editable_input"})
        )


def test_list_pagination_bounds() -> None:
    plan = _plan()
    with pytest.raises(ValidationError):
        WorkflowPlanListResponse(
            project_status="active",
            items=[plan],
            total=1,
            limit=101,
        )
    with pytest.raises(ValidationError):
        MonitoringScopeListResponse(
            project_status="active",
            items=[],
            total=0,
            offset=-1,
        )


def test_scope_and_same_version_compare_contracts_are_structured() -> None:
    scope = MonitoringScopeResponse(
        id=UUID("00000000-0000-0000-0000-000000000006"),
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        created_by_user_id=USER_ID,
        scope_key="sha256:" + "b" * 64,
        scope_type="brand",
        canonical_term="Example",
        aliases=[],
        include_terms=[],
        exclude_terms=[],
        official_accounts=[],
        seed_urls=[],
        effective_languages=["en"],
        effective_regions=["US"],
        effective_platforms=["youtube"],
        match_mode="phrase",
        created_at=NOW,
    )
    scope_list = MonitoringScopeListResponse(
        project_status="archived",
        items=[scope],
        total=1,
    )
    compare = WorkflowPlanVersionCompareResponse(
        project_status="archived",
        plan=_plan(),
        base_version=_version(),
        target_version=_version(),
        same_version=True,
        sections=[],
    )

    assert scope_list.items[0].scope_type.value == "brand"
    assert compare.same_version is True
    assert compare.sections == []
