from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowRunStatus,
    WorkflowStepRunStatus,
)


class WorkflowExecutionTransitionError(ValueError):
    """Raised when this fixture slice is asked to perform an unsupported transition."""


class WorkflowExecutionStateSnapshotError(ValueError):
    """Raised when persisted Run facts do not match the declared state semantics."""


_RUN_TRANSITIONS = frozenset(
    {
        (WorkflowRunStatus.DRAFT, WorkflowRunStatus.READY),
        (WorkflowRunStatus.READY, WorkflowRunStatus.RUNNING),
        (WorkflowRunStatus.RUNNING, WorkflowRunStatus.COMPLETED),
        (WorkflowRunStatus.RUNNING, WorkflowRunStatus.DEGRADED),
        (WorkflowRunStatus.RUNNING, WorkflowRunStatus.HELD),
        (WorkflowRunStatus.RUNNING, WorkflowRunStatus.CANCELLED),
        (WorkflowRunStatus.RUNNING, WorkflowRunStatus.EMPTY_VALID),
        (WorkflowRunStatus.HELD, WorkflowRunStatus.READY),
        (WorkflowRunStatus.HELD, WorkflowRunStatus.RUNNING),
        (WorkflowRunStatus.HELD, WorkflowRunStatus.CANCELLED),
    }
)
_STEP_TRANSITIONS = frozenset(
    {
        (WorkflowStepRunStatus.PENDING, WorkflowStepRunStatus.RUNNING),
        (WorkflowStepRunStatus.PENDING, WorkflowStepRunStatus.CANCELLED),
        (WorkflowStepRunStatus.RUNNING, WorkflowStepRunStatus.COMPLETED),
        (WorkflowStepRunStatus.RUNNING, WorkflowStepRunStatus.FAILED),
        (WorkflowStepRunStatus.RUNNING, WorkflowStepRunStatus.CANCELLED),
    }
)


def advance_workflow_run_status(
    current: WorkflowRunStatus,
    target: WorkflowRunStatus,
) -> WorkflowRunStatus:
    if (current, target) not in _RUN_TRANSITIONS:
        raise WorkflowExecutionTransitionError(
            f"workflow_run_transition_invalid:{current.value}:{target.value}"
        )
    return target


def advance_workflow_step_status(
    current: WorkflowStepRunStatus,
    target: WorkflowStepRunStatus,
) -> WorkflowStepRunStatus:
    if (current, target) not in _STEP_TRANSITIONS:
        raise WorkflowExecutionTransitionError(
            f"workflow_step_transition_invalid:{current.value}:{target.value}"
        )
    return target


def _require_state_facts(
    *,
    status: WorkflowRunStatus,
    status_reason_code: str | None,
    impact_code: str | None,
) -> None:
    if status_reason_code is None:
        raise WorkflowExecutionStateSnapshotError(
            f"workflow_run_{status.value}_reason_required"
        )
    if impact_code is None:
        raise WorkflowExecutionStateSnapshotError(
            f"workflow_run_{status.value}_impact_required"
        )


def validate_workflow_run_state_snapshot(
    status: WorkflowRunStatus,
    *,
    total_steps: int,
    completed_steps: int,
    records_count: int,
    status_reason_code: str | None,
    impact_code: str | None,
    missing_fields: Sequence[str],
    recovery_action_codes: Sequence[str],
    finished_at: datetime | None,
) -> WorkflowRunStatus:
    if total_steps < 1 or not 0 <= completed_steps <= total_steps:
        raise WorkflowExecutionStateSnapshotError("workflow_run_step_counts_invalid")
    if records_count < 0:
        raise WorkflowExecutionStateSnapshotError("workflow_run_records_count_invalid")
    if len(missing_fields) != len(set(missing_fields)) or any(
        not value for value in missing_fields
    ):
        raise WorkflowExecutionStateSnapshotError("workflow_run_missing_fields_invalid")
    if len(recovery_action_codes) != len(set(recovery_action_codes)) or any(
        not value for value in recovery_action_codes
    ):
        raise WorkflowExecutionStateSnapshotError("workflow_run_recovery_actions_invalid")

    if status is WorkflowRunStatus.COMPLETED:
        if completed_steps != total_steps:
            raise WorkflowExecutionStateSnapshotError("completed_steps_invalid")
        if records_count < 1:
            raise WorkflowExecutionStateSnapshotError("completed_records_invalid")
        if finished_at is None:
            raise WorkflowExecutionStateSnapshotError("completed_finished_at_required")
        if any(
            (
                status_reason_code is not None,
                impact_code is not None,
                bool(missing_fields),
                bool(recovery_action_codes),
            )
        ):
            raise WorkflowExecutionStateSnapshotError("completed_state_facts_invalid")
    elif status is WorkflowRunStatus.EMPTY_VALID:
        _require_state_facts(
            status=status,
            status_reason_code=status_reason_code,
            impact_code=impact_code,
        )
        if completed_steps != total_steps:
            raise WorkflowExecutionStateSnapshotError("empty_valid_steps_invalid")
        if records_count != 0:
            raise WorkflowExecutionStateSnapshotError("empty_valid_records_invalid")
        if missing_fields or recovery_action_codes:
            raise WorkflowExecutionStateSnapshotError("empty_valid_state_facts_invalid")
        if finished_at is None:
            raise WorkflowExecutionStateSnapshotError("empty_valid_finished_at_required")
    elif status is WorkflowRunStatus.DEGRADED:
        _require_state_facts(
            status=status,
            status_reason_code=status_reason_code,
            impact_code=impact_code,
        )
        if completed_steps != total_steps:
            raise WorkflowExecutionStateSnapshotError("degraded_steps_invalid")
        if not missing_fields:
            raise WorkflowExecutionStateSnapshotError("degraded_missing_fields_required")
        if not recovery_action_codes:
            raise WorkflowExecutionStateSnapshotError("degraded_recovery_action_required")
        if finished_at is None:
            raise WorkflowExecutionStateSnapshotError("degraded_finished_at_required")
    elif status is WorkflowRunStatus.HELD:
        _require_state_facts(
            status=status,
            status_reason_code=status_reason_code,
            impact_code=impact_code,
        )
        if completed_steps >= total_steps:
            raise WorkflowExecutionStateSnapshotError("held_steps_invalid")
        if not recovery_action_codes:
            raise WorkflowExecutionStateSnapshotError("held_recovery_action_required")
        if finished_at is not None:
            raise WorkflowExecutionStateSnapshotError("held_finished_at_invalid")
    elif status is WorkflowRunStatus.CANCELLED:
        _require_state_facts(
            status=status,
            status_reason_code=status_reason_code,
            impact_code=impact_code,
        )
        if recovery_action_codes:
            raise WorkflowExecutionStateSnapshotError("cancelled_recovery_actions_invalid")
        if finished_at is None:
            raise WorkflowExecutionStateSnapshotError("cancelled_finished_at_required")
    else:
        if finished_at is not None:
            raise WorkflowExecutionStateSnapshotError("active_state_finished_at_invalid")
        if any(
            (
                status_reason_code is not None,
                impact_code is not None,
                bool(missing_fields),
                bool(recovery_action_codes),
            )
        ):
            raise WorkflowExecutionStateSnapshotError("active_state_facts_invalid")
    return status


__all__ = [
    "WorkflowExecutionStateSnapshotError",
    "WorkflowExecutionTransitionError",
    "advance_workflow_run_status",
    "advance_workflow_step_status",
    "validate_workflow_run_state_snapshot",
]
