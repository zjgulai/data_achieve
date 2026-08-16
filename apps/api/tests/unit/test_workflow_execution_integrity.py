from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from data_intelligence_hub.models.workflow_plan import WorkflowVersion
from data_intelligence_hub.schemas.capability_catalog import CapabilityCatalog
from data_intelligence_hub.schemas.workflow_plan_persistence import serialize_preview_snapshot
from data_intelligence_hub.schemas.workflow_planner import PlanningInput
from data_intelligence_hub.services.workflow_execution.integrity import (
    WorkflowVersionExpectedFingerprintConflictError,
    WorkflowVersionOwnerMismatchError,
    WorkflowVersionSnapshotInvalidError,
    validate_workflow_version_snapshot,
)
from data_intelligence_hub.services.workflow_planner.planner import (
    build_workflow_plan_result,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "workflow_planner"
PERIODIC_FIXTURE = FIXTURE_DIR / "periodic_monitoring_request_v1.json"
SYNTHETIC_CATALOG_FIXTURE = FIXTURE_DIR / "synthetic_capability_catalog_v1.json"
WORKSPACE_ID = uuid.UUID("00000000-0000-0000-0000-000000000201")
PROJECT_ID = uuid.UUID("00000000-0000-0000-0000-000000000202")
PLAN_ID = uuid.UUID("00000000-0000-0000-0000-000000000203")
VERSION_ID = uuid.UUID("00000000-0000-0000-0000-000000000204")
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000205")
NOW = datetime(2026, 7, 15, 9, 0, tzinfo=UTC)


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


def _version() -> WorkflowVersion:
    result = build_workflow_plan_result(
        project_id=PROJECT_ID,
        planning_input=_planning_input(),
        catalog=_catalog(),
        generated_at=NOW,
        request_id="workflow-integrity-test",
    )
    preview = result.preview
    return WorkflowVersion(
        id=VERSION_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_plan_id=PLAN_ID,
        created_by_user_id=USER_ID,
        version_number=1,
        planning_status=preview.planning_status.value,
        planner_contract_version=preview.planner_contract_version,
        catalog_snapshot_id=preview.catalog_snapshot_id,
        policy_version=preview.policy_version,
        mode_template_version=preview.mode_template_version,
        query_versions={key.value: value for key, value in preview.query_versions.items()},
        fingerprint_payload=result.fingerprint_payload.model_dump(mode="json"),
        normalized_input=preview.normalized_input.model_dump(mode="json"),
        plan_payload=serialize_preview_snapshot(preview),
        preview_fingerprint=preview.preview_fingerprint,
        created_at=NOW,
    )


def test_validates_frozen_snapshot_and_returns_typed_execution_inputs() -> None:
    version = _version()
    validated = validate_workflow_version_snapshot(
        version,
        expected_workspace_id=WORKSPACE_ID,
        expected_project_id=PROJECT_ID,
        expected_workflow_plan_id=PLAN_ID,
        expected_workflow_version_id=VERSION_ID,
        expected_preview_fingerprint=version.preview_fingerprint,
    )

    assert validated.preview.preview_fingerprint == version.preview_fingerprint
    assert validated.preview.project_id == PROJECT_ID
    assert validated.fingerprint_payload.catalog_snapshot_id == version.catalog_snapshot_id
    assert validated.editable_input.flow_mode == validated.preview.flow_mode


def test_client_expected_fingerprint_conflict_is_not_snapshot_corruption() -> None:
    version = _version()
    with pytest.raises(
        WorkflowVersionExpectedFingerprintConflictError,
        match="workflow_version_fingerprint_conflict",
    ):
        validate_workflow_version_snapshot(
            version,
            expected_preview_fingerprint="sha256:" + "f" * 64,
        )


@pytest.mark.parametrize(
    ("argument", "value"),
    [
        ("expected_workspace_id", uuid.UUID("00000000-0000-0000-0000-000000000211")),
        ("expected_project_id", uuid.UUID("00000000-0000-0000-0000-000000000212")),
        (
            "expected_workflow_plan_id",
            uuid.UUID("00000000-0000-0000-0000-000000000213"),
        ),
        (
            "expected_workflow_version_id",
            uuid.UUID("00000000-0000-0000-0000-000000000214"),
        ),
    ],
)
def test_requested_owner_mismatch_is_distinct_and_fail_closed(
    argument: str,
    value: uuid.UUID,
) -> None:
    with pytest.raises(
        WorkflowVersionOwnerMismatchError,
        match="workflow_version_owner_mismatch",
    ):
        version = _version()
        if argument == "expected_workspace_id":
            validate_workflow_version_snapshot(version, expected_workspace_id=value)
        elif argument == "expected_project_id":
            validate_workflow_version_snapshot(version, expected_project_id=value)
        elif argument == "expected_workflow_plan_id":
            validate_workflow_version_snapshot(version, expected_workflow_plan_id=value)
        else:
            validate_workflow_version_snapshot(version, expected_workflow_version_id=value)


@pytest.mark.parametrize(
    "tamper_target",
    [
        "plan_payload",
        "fingerprint_payload",
        "planning_status",
        "planner_contract_version",
        "catalog_snapshot_id",
        "policy_version",
        "mode_template_version",
        "query_versions",
        "normalized_input",
        "project_id",
    ],
)
def test_persisted_snapshot_tamper_has_one_sanitized_error(tamper_target: str) -> None:
    version = _version()
    if tamper_target == "plan_payload":
        payload = deepcopy(version.plan_payload)
        query_terms = cast(list[dict[str, Any]], payload["query_terms"])
        query_terms[0]["status"] = "rejected"
        version.plan_payload = payload
    elif tamper_target == "fingerprint_payload":
        payload = deepcopy(version.fingerprint_payload)
        fingerprint_input = cast(dict[str, Any], payload["fingerprint_input"])
        fingerprint_input["required_fields"] = ["id", "tampered"]
        version.fingerprint_payload = payload
    elif tamper_target == "query_versions":
        version.query_versions = {**version.query_versions, "youtube": "tampered"}
    elif tamper_target == "normalized_input":
        version.normalized_input = {**version.normalized_input, "purpose": "tampered"}
    elif tamper_target == "project_id":
        version.project_id = uuid.UUID("00000000-0000-0000-0000-000000000299")
    elif tamper_target == "planning_status":
        version.planning_status = f"{version.planning_status}-tampered"
    elif tamper_target == "planner_contract_version":
        version.planner_contract_version = f"{version.planner_contract_version}-tampered"
    elif tamper_target == "catalog_snapshot_id":
        version.catalog_snapshot_id = f"{version.catalog_snapshot_id}-tampered"
    elif tamper_target == "policy_version":
        version.policy_version = f"{version.policy_version}-tampered"
    else:
        version.mode_template_version = f"{version.mode_template_version}-tampered"

    with pytest.raises(
        WorkflowVersionSnapshotInvalidError,
        match="workflow_plan_version_fingerprint_mismatch",
    ):
        validate_workflow_version_snapshot(version)


def test_invalid_plan_payload_is_sanitized_as_snapshot_corruption() -> None:
    version = _version()
    version.plan_payload = {"unexpected": "payload"}

    with pytest.raises(
        WorkflowVersionSnapshotInvalidError,
        match="workflow_plan_version_fingerprint_mismatch",
    ):
        validate_workflow_version_snapshot(version)
