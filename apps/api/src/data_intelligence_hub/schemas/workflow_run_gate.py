from __future__ import annotations

from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from data_intelligence_hub.schemas.project import ProjectStatus
from data_intelligence_hub.schemas.workflow_execution import WorkflowFixtureReadBoundary
from data_intelligence_hub.schemas.workflow_plan_persistence import WorkflowPlanStatus
from data_intelligence_hub.schemas.workflow_planner import PlanningStatus

WorkflowFixtureRunGateBlockerCode = Literal[
    "project_not_active",
    "workflow_plan_not_active",
    "workflow_version_not_current",
    "workflow_version_contract_not_runnable",
]
WorkflowFixtureRunGateActionCode = Literal[
    "activate_project",
    "approve_and_activate_plan",
    "select_current_version",
    "resolve_version_contract",
    "create_fixture_run",
]


class WorkflowFixtureRunGateResponse(WorkflowFixtureReadBoundary):
    gate_contract_version: Literal["workflow_fixture_run_gate.v1"] = "workflow_fixture_run_gate.v1"
    project_status: ProjectStatus
    workflow_plan_id: UUID
    workflow_version_id: UUID
    current_version_id: UUID | None
    plan_status: WorkflowPlanStatus
    planning_status: PlanningStatus
    is_current_version: bool
    runnable: bool
    blocker_codes: list[WorkflowFixtureRunGateBlockerCode] = Field(max_length=4)
    next_action_codes: list[WorkflowFixtureRunGateActionCode] = Field(
        min_length=1,
        max_length=4,
    )
    evidence_refs: list[str] = Field(min_length=2, max_length=8)

    @model_validator(mode="after")
    def validate_gate(self) -> Self:
        if len(self.blocker_codes) != len(set(self.blocker_codes)):
            raise ValueError("workflow_fixture_run_gate_blockers_duplicate")
        if len(self.next_action_codes) != len(set(self.next_action_codes)):
            raise ValueError("workflow_fixture_run_gate_actions_duplicate")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("workflow_fixture_run_gate_evidence_duplicate")
        if self.is_current_version != (self.current_version_id == self.workflow_version_id):
            raise ValueError("workflow_fixture_run_gate_current_version_invalid")
        if self.runnable != (not self.blocker_codes):
            raise ValueError("workflow_fixture_run_gate_outcome_invalid")
        if self.runnable:
            if self.next_action_codes != ["create_fixture_run"]:
                raise ValueError("workflow_fixture_run_gate_runnable_action_invalid")
        elif "create_fixture_run" in self.next_action_codes:
            raise ValueError("workflow_fixture_run_gate_blocked_action_invalid")
        return self


__all__ = [
    "WorkflowFixtureRunGateActionCode",
    "WorkflowFixtureRunGateBlockerCode",
    "WorkflowFixtureRunGateResponse",
]
