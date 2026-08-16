from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from data_intelligence_hub.models.workflow_plan import WorkflowPlan, WorkflowVersion
from data_intelligence_hub.schemas.capability_catalog import CapabilityCatalog
from data_intelligence_hub.schemas.project import ProjectStatus
from data_intelligence_hub.schemas.workflow_plan_persistence import WorkflowPlanStatus
from data_intelligence_hub.schemas.workflow_planner import (
    PlanningInput,
    PlanningStatus,
    RoutePlanStatus,
    WorkflowPlanPreview,
    WorkflowStepPlanningStatus,
)
from data_intelligence_hub.services.workflow_execution.eligibility import (
    WorkflowStepFixtureIdentity,
    WorkflowVersionNotFixtureRunnableError,
    build_primary_execution_contracts,
    compute_workflow_step_input_digest,
)
from data_intelligence_hub.services.workflow_execution.run_gate import (
    evaluate_workflow_fixture_run_gate,
    require_workflow_fixture_run_gate,
)
from data_intelligence_hub.services.workflow_planner.planner import (
    build_workflow_plan_preview,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "workflow_planner"
PERIODIC_FIXTURE = FIXTURE_DIR / "periodic_monitoring_request_v1.json"
SYNTHETIC_CATALOG_FIXTURE = FIXTURE_DIR / "synthetic_capability_catalog_v1.json"
PROJECT_ID = uuid.UUID("00000000-0000-0000-0000-000000000301")
VERSION_ID = uuid.UUID("00000000-0000-0000-0000-000000000302")
PROFILE_HASH = "sha256:" + "a" * 64
CASE_HASH = "sha256:" + "b" * 64
NOW = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)


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
        request_id="workflow-eligibility-test",
    )


def _replace_first_route(
    preview: WorkflowPlanPreview,
    **updates: object,
) -> WorkflowPlanPreview:
    route = preview.route_plans[0].model_copy(update=updates, deep=True)
    return preview.model_copy(
        update={"route_plans": [route, *preview.route_plans[1:]]},
        deep=True,
    )


def test_resolved_preview_builds_one_exact_primary_contract_per_future_step() -> None:
    preview = _preview()
    contracts = build_primary_execution_contracts(preview)
    future_steps = [item for item in preview.steps if item.execution_kind == "future_capability"]

    assert preview.planning_status is PlanningStatus.RESOLVED
    assert len(contracts) == len(future_steps) >= 1
    assert [item.step.sequence for item in contracts] == sorted(
        item.step.sequence for item in contracts
    )
    for contract in contracts:
        assert contract.route_plan.status is RoutePlanStatus.RESOLVED
        assert contract.route_plan.primary_implementation == contract.primary
        assert contract.primary.route_eligible is True
        assert contract.primary.evidence_refs
        assert contract.step.requirement_ref == contract.requirement.requirement_ref
        assert contract.compiled_queries
        assert all(
            query.platform == contract.requirement.platform for query in contract.compiled_queries
        )
        assert {
            scope_key for query in contract.compiled_queries for scope_key in query.scope_keys
        } == set(contract.requirement.scope_keys)


def test_active_current_resolved_version_is_fixture_runnable() -> None:
    preview = _preview()
    plan_id = uuid.uuid4()
    version_id = uuid.uuid4()
    plan = cast(
        WorkflowPlan,
        SimpleNamespace(
            id=plan_id,
            status="active",
            current_version_id=version_id,
        ),
    )
    version = cast(
        WorkflowVersion,
        SimpleNamespace(
            id=version_id,
            preview_fingerprint=preview.preview_fingerprint,
        ),
    )

    evaluation = evaluate_workflow_fixture_run_gate(
        project_status="active",
        plan=plan,
        version=version,
        preview=preview,
    )

    assert evaluation.response.runnable
    assert evaluation.response.blocker_codes == []
    assert evaluation.response.next_action_codes == ["create_fixture_run"]
    assert evaluation.response.is_current_version
    assert evaluation.response.database_write is False
    assert evaluation.response.provider_call is False
    assert evaluation.contracts == require_workflow_fixture_run_gate(
        project_status="active",
        plan=plan,
        version=version,
        preview=preview,
    )


@pytest.mark.parametrize(
    ("project_status", "plan_status", "current_version", "planning_status", "blockers"),
    [
        (
            "archived",
            "active",
            True,
            PlanningStatus.RESOLVED,
            ["project_not_active"],
        ),
        (
            "active",
            "previewed",
            True,
            PlanningStatus.RESOLVED,
            ["workflow_plan_not_active"],
        ),
        (
            "active",
            "active",
            False,
            PlanningStatus.RESOLVED,
            ["workflow_version_not_current"],
        ),
        (
            "active",
            "active",
            True,
            PlanningStatus.HELD,
            ["workflow_version_contract_not_runnable"],
        ),
    ],
)
def test_fixture_runnable_gate_reports_fixed_blockers(
    project_status: ProjectStatus,
    plan_status: WorkflowPlanStatus,
    current_version: bool,
    planning_status: PlanningStatus,
    blockers: list[str],
) -> None:
    preview = _preview().model_copy(update={"planning_status": planning_status})
    plan_id = uuid.uuid4()
    version_id = uuid.uuid4()
    plan = cast(
        WorkflowPlan,
        SimpleNamespace(
            id=plan_id,
            status=plan_status,
            current_version_id=version_id if current_version else uuid.uuid4(),
        ),
    )
    version = cast(
        WorkflowVersion,
        SimpleNamespace(
            id=version_id,
            preview_fingerprint=preview.preview_fingerprint,
        ),
    )

    evaluation = evaluate_workflow_fixture_run_gate(
        project_status=project_status,
        plan=plan,
        version=version,
        preview=preview,
    )

    assert not evaluation.response.runnable
    assert evaluation.response.blocker_codes == blockers
    assert "create_fixture_run" not in evaluation.response.next_action_codes
    if planning_status is PlanningStatus.HELD:
        assert evaluation.contracts == ()
    else:
        assert evaluation.contracts
    with pytest.raises(
        WorkflowVersionNotFixtureRunnableError,
        match=f"workflow_version_not_fixture_runnable:{blockers[0]}",
    ):
        require_workflow_fixture_run_gate(
            project_status=project_status,
            plan=plan,
            version=version,
            preview=preview,
        )


@pytest.mark.parametrize(
    "planning_status",
    [PlanningStatus.PARTIALLY_RESOLVED, PlanningStatus.HELD],
)
def test_non_resolved_preview_is_all_or_nothing(
    planning_status: PlanningStatus,
) -> None:
    preview = _preview().model_copy(update={"planning_status": planning_status})
    with pytest.raises(
        WorkflowVersionNotFixtureRunnableError,
        match="workflow_version_not_fixture_runnable:planning_status",
    ):
        build_primary_execution_contracts(preview)


@pytest.mark.parametrize(
    "mutator",
    [
        "no_future_step",
        "duplicate_requirement",
        "missing_route",
        "partial_route",
        "held_step",
        "no_primary",
        "primary_ineligible",
        "missing_query",
    ],
)
def test_incomplete_primary_contract_fails_closed(mutator: str) -> None:
    preview = _preview()
    if mutator == "no_future_step":
        preview = preview.model_copy(
            update={
                "steps": [
                    item for item in preview.steps if item.execution_kind != "future_capability"
                ]
            }
        )
    elif mutator == "duplicate_requirement":
        first = next(item for item in preview.steps if item.execution_kind == "future_capability")
        duplicate = first.model_copy(
            update={"step_ref": "step:duplicate", "sequence": first.sequence + 100}
        )
        preview = preview.model_copy(update={"steps": [*preview.steps, duplicate]})
    elif mutator == "missing_route":
        preview = preview.model_copy(update={"route_plans": preview.route_plans[1:]})
    elif mutator == "partial_route":
        preview = _replace_first_route(
            preview,
            status=RoutePlanStatus.PARTIAL,
            route_eligible=False,
        )
    elif mutator == "held_step":
        first = next(item for item in preview.steps if item.execution_kind == "future_capability")
        replaced = first.model_copy(update={"planning_status": WorkflowStepPlanningStatus.HELD})
        preview = preview.model_copy(
            update={
                "steps": [
                    replaced if item.step_ref == first.step_ref else item for item in preview.steps
                ]
            }
        )
    elif mutator == "no_primary":
        preview = _replace_first_route(preview, primary_implementation=None)
    elif mutator == "primary_ineligible":
        primary = preview.route_plans[0].primary_implementation
        assert primary is not None
        preview = _replace_first_route(
            preview,
            primary_implementation=primary.model_copy(update={"route_eligible": False}),
        )
    else:
        preview = preview.model_copy(update={"compiled_queries": []})

    with pytest.raises(
        WorkflowVersionNotFixtureRunnableError,
        match="workflow_version_not_fixture_runnable",
    ):
        build_primary_execution_contracts(preview)


def test_step_input_digest_is_stable_and_changes_only_with_semantic_identity() -> None:
    preview = _preview()
    contract = build_primary_execution_contracts(preview)[0]
    fixture = WorkflowStepFixtureIdentity(
        fixture_profile_hash=PROFILE_HASH,
        fixture_case_id="youtube-content-search-v1",
        fixture_content_hash=CASE_HASH,
    )
    digest = compute_workflow_step_input_digest(
        contract,
        workflow_version_id=VERSION_ID,
        preview_fingerprint=preview.preview_fingerprint,
        fixture=fixture,
    )

    assert digest == compute_workflow_step_input_digest(
        contract,
        workflow_version_id=VERSION_ID,
        preview_fingerprint=preview.preview_fingerprint,
        fixture=fixture,
    )
    changed = {
        compute_workflow_step_input_digest(
            contract,
            workflow_version_id=uuid.uuid4(),
            preview_fingerprint=preview.preview_fingerprint,
            fixture=fixture,
        ),
        compute_workflow_step_input_digest(
            contract,
            workflow_version_id=VERSION_ID,
            preview_fingerprint="sha256:" + "f" * 64,
            fixture=fixture,
        ),
        compute_workflow_step_input_digest(
            contract,
            workflow_version_id=VERSION_ID,
            preview_fingerprint=preview.preview_fingerprint,
            fixture=fixture.model_copy(update={"fixture_case_id": "youtube-content-search-v2"}),
        ),
        compute_workflow_step_input_digest(
            contract,
            workflow_version_id=VERSION_ID,
            preview_fingerprint=preview.preview_fingerprint,
            fixture=fixture.model_copy(update={"fixture_content_hash": "sha256:" + "c" * 64}),
        ),
    }
    assert digest not in changed
    assert len(changed) == 4
