from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from data_intelligence_hub.models.workflow_plan import WorkflowPlan, WorkflowVersion
from data_intelligence_hub.schemas.project import ProjectStatus
from data_intelligence_hub.schemas.workflow_plan_persistence import WorkflowPlanStatus
from data_intelligence_hub.schemas.workflow_planner import WorkflowPlanPreview
from data_intelligence_hub.schemas.workflow_run_gate import (
    WorkflowFixtureRunGateActionCode,
    WorkflowFixtureRunGateBlockerCode,
    WorkflowFixtureRunGateResponse,
)
from data_intelligence_hub.services.workflow_execution.eligibility import (
    PrimaryExecutionContract,
    WorkflowVersionNotFixtureRunnableError,
    build_primary_execution_contracts,
)


@dataclass(frozen=True, slots=True)
class WorkflowFixtureRunGateEvaluation:
    response: WorkflowFixtureRunGateResponse
    contracts: tuple[PrimaryExecutionContract, ...]


def evaluate_workflow_fixture_run_gate(
    *,
    project_status: ProjectStatus,
    plan: WorkflowPlan,
    version: WorkflowVersion,
    preview: WorkflowPlanPreview,
) -> WorkflowFixtureRunGateEvaluation:
    blocker_codes: list[WorkflowFixtureRunGateBlockerCode] = []
    next_action_codes: list[WorkflowFixtureRunGateActionCode] = []

    if project_status != "active":
        blocker_codes.append("project_not_active")
        next_action_codes.append("activate_project")
    if plan.status != "active":
        blocker_codes.append("workflow_plan_not_active")
        next_action_codes.append("approve_and_activate_plan")
    if plan.current_version_id != version.id:
        blocker_codes.append("workflow_version_not_current")
        next_action_codes.append("select_current_version")

    try:
        contracts = build_primary_execution_contracts(preview)
    except WorkflowVersionNotFixtureRunnableError:
        contracts = ()
        blocker_codes.append("workflow_version_contract_not_runnable")
        next_action_codes.append("resolve_version_contract")

    runnable = not blocker_codes
    if runnable:
        next_action_codes.append("create_fixture_run")

    response = WorkflowFixtureRunGateResponse(
        project_status=project_status,
        workflow_plan_id=plan.id,
        workflow_version_id=version.id,
        current_version_id=plan.current_version_id,
        plan_status=cast(WorkflowPlanStatus, plan.status),
        planning_status=preview.planning_status,
        is_current_version=plan.current_version_id == version.id,
        runnable=runnable,
        blocker_codes=blocker_codes,
        next_action_codes=next_action_codes,
        evidence_refs=[
            f"workflow-plan://{plan.id}",
            f"workflow-version://{version.id}",
            f"preview-fingerprint://{version.preview_fingerprint}",
        ],
    )
    return WorkflowFixtureRunGateEvaluation(response=response, contracts=contracts)


def require_workflow_fixture_run_gate(
    *,
    project_status: ProjectStatus,
    plan: WorkflowPlan,
    version: WorkflowVersion,
    preview: WorkflowPlanPreview,
) -> tuple[PrimaryExecutionContract, ...]:
    evaluation = evaluate_workflow_fixture_run_gate(
        project_status=project_status,
        plan=plan,
        version=version,
        preview=preview,
    )
    if not evaluation.response.runnable:
        reason = evaluation.response.blocker_codes[0]
        raise WorkflowVersionNotFixtureRunnableError(
            f"workflow_version_not_fixture_runnable:{reason}"
        )
    return evaluation.contracts


__all__ = [
    "WorkflowFixtureRunGateEvaluation",
    "evaluate_workflow_fixture_run_gate",
    "require_workflow_fixture_run_gate",
]
