from __future__ import annotations

import pytest

from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowRunStatus,
    WorkflowStepRunStatus,
)
from data_intelligence_hub.services.workflow_execution.state_machine import (
    WorkflowExecutionTransitionError,
    advance_workflow_run_status,
    advance_workflow_step_status,
)


def test_workflow_run_allows_only_ready_running_completed_path() -> None:
    assert (
        advance_workflow_run_status(WorkflowRunStatus.DRAFT, WorkflowRunStatus.READY)
        is WorkflowRunStatus.READY
    )
    assert (
        advance_workflow_run_status(WorkflowRunStatus.READY, WorkflowRunStatus.RUNNING)
        is WorkflowRunStatus.RUNNING
    )
    assert (
        advance_workflow_run_status(
            WorkflowRunStatus.RUNNING,
            WorkflowRunStatus.COMPLETED,
        )
        is WorkflowRunStatus.COMPLETED
    )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (WorkflowRunStatus.RUNNING, WorkflowRunStatus.DEGRADED),
        (WorkflowRunStatus.RUNNING, WorkflowRunStatus.HELD),
        (WorkflowRunStatus.RUNNING, WorkflowRunStatus.CANCELLED),
        (WorkflowRunStatus.RUNNING, WorkflowRunStatus.EMPTY_VALID),
        (WorkflowRunStatus.HELD, WorkflowRunStatus.READY),
        (WorkflowRunStatus.HELD, WorkflowRunStatus.RUNNING),
        (WorkflowRunStatus.HELD, WorkflowRunStatus.CANCELLED),
    ],
)
def test_workflow_run_allows_declared_terminal_and_recovery_paths(
    current: WorkflowRunStatus,
    target: WorkflowRunStatus,
) -> None:
    assert advance_workflow_run_status(current, target) is target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (WorkflowRunStatus.READY, WorkflowRunStatus.COMPLETED),
        (WorkflowRunStatus.READY, WorkflowRunStatus.HELD),
        (WorkflowRunStatus.COMPLETED, WorkflowRunStatus.RUNNING),
        (WorkflowRunStatus.COMPLETED, WorkflowRunStatus.COMPLETED),
        (WorkflowRunStatus.DEGRADED, WorkflowRunStatus.RUNNING),
        (WorkflowRunStatus.EMPTY_VALID, WorkflowRunStatus.RUNNING),
        (WorkflowRunStatus.CANCELLED, WorkflowRunStatus.READY),
    ],
)
def test_workflow_run_rejects_unapproved_transitions(
    current: WorkflowRunStatus,
    target: WorkflowRunStatus,
) -> None:
    with pytest.raises(
        WorkflowExecutionTransitionError,
        match=f"workflow_run_transition_invalid:{current.value}:{target.value}",
    ):
        advance_workflow_run_status(current, target)


def test_workflow_step_allows_only_pending_running_completed_path() -> None:
    assert (
        advance_workflow_step_status(
            WorkflowStepRunStatus.PENDING,
            WorkflowStepRunStatus.RUNNING,
        )
        is WorkflowStepRunStatus.RUNNING
    )
    assert (
        advance_workflow_step_status(
            WorkflowStepRunStatus.RUNNING,
            WorkflowStepRunStatus.COMPLETED,
        )
        is WorkflowStepRunStatus.COMPLETED
    )
    assert (
        advance_workflow_step_status(
            WorkflowStepRunStatus.RUNNING,
            WorkflowStepRunStatus.FAILED,
        )
        is WorkflowStepRunStatus.FAILED
    )
    assert (
        advance_workflow_step_status(
            WorkflowStepRunStatus.PENDING,
            WorkflowStepRunStatus.CANCELLED,
        )
        is WorkflowStepRunStatus.CANCELLED
    )
    assert (
        advance_workflow_step_status(
            WorkflowStepRunStatus.RUNNING,
            WorkflowStepRunStatus.CANCELLED,
        )
        is WorkflowStepRunStatus.CANCELLED
    )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (WorkflowStepRunStatus.PENDING, WorkflowStepRunStatus.COMPLETED),
        (WorkflowStepRunStatus.RUNNING, WorkflowStepRunStatus.PENDING),
        (WorkflowStepRunStatus.COMPLETED, WorkflowStepRunStatus.RUNNING),
        (WorkflowStepRunStatus.COMPLETED, WorkflowStepRunStatus.COMPLETED),
        (WorkflowStepRunStatus.FAILED, WorkflowStepRunStatus.RUNNING),
        (WorkflowStepRunStatus.CANCELLED, WorkflowStepRunStatus.PENDING),
    ],
)
def test_workflow_step_rejects_unapproved_transitions(
    current: WorkflowStepRunStatus,
    target: WorkflowStepRunStatus,
) -> None:
    with pytest.raises(
        WorkflowExecutionTransitionError,
        match=f"workflow_step_transition_invalid:{current.value}:{target.value}",
    ):
        advance_workflow_step_status(current, target)
