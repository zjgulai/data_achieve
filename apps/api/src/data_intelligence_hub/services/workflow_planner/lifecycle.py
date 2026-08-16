from __future__ import annotations

from typing import Final

from data_intelligence_hub.schemas.workflow_plan_persistence import WorkflowPlanStatus


class WorkflowPlanTransitionError(ValueError):
    """Raised when a Plan lifecycle transition is not in the approved table."""


allowed_plan_status_transitions: Final[dict[WorkflowPlanStatus, frozenset[WorkflowPlanStatus]]] = {
    "draft": frozenset({"previewed"}),
    "previewed": frozenset({"approved"}),
    "approved": frozenset({"active"}),
    "active": frozenset({"paused"}),
    "paused": frozenset({"active", "archived"}),
    "archived": frozenset(),
}


def transition_workflow_plan_status(
    current: WorkflowPlanStatus,
    target: WorkflowPlanStatus,
) -> WorkflowPlanStatus:
    if current == target:
        return current
    if target not in allowed_plan_status_transitions[current]:
        raise WorkflowPlanTransitionError(
            f"workflow_plan_invalid_transition:{current}:{target}"
        )
    return target


__all__ = [
    "WorkflowPlanTransitionError",
    "allowed_plan_status_transitions",
    "transition_workflow_plan_status",
]
