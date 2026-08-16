from __future__ import annotations

from datetime import UTC, datetime

import pytest

from data_intelligence_hub.schemas.workflow_execution import WorkflowRunStatus
from data_intelligence_hub.services.workflow_execution.state_machine import (
    WorkflowExecutionStateSnapshotError,
    validate_workflow_run_state_snapshot,
)

NOW = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    (
        "status",
        "records_count",
        "reason_code",
        "impact_code",
        "missing_fields",
        "actions",
        "finished_at",
    ),
    [
        (WorkflowRunStatus.COMPLETED, 3, None, None, (), (), NOW),
        (
            WorkflowRunStatus.EMPTY_VALID,
            0,
            "verified_zero_result",
            "no_records_in_scope",
            (),
            (),
            NOW,
        ),
        (
            WorkflowRunStatus.DEGRADED,
            2,
            "fallback_missing_optional_fields",
            "delivery_missing_fields",
            ("author.avatar_url",),
            ("review_missing_fields",),
            NOW,
        ),
        (
            WorkflowRunStatus.HELD,
            0,
            "fallback_blocked",
            "step_not_completed_following_steps_not_started",
            (),
            ("inspect_fallback_gate_evidence", "resolve_primary_failure"),
            None,
        ),
        (
            WorkflowRunStatus.CANCELLED,
            0,
            "cancelled_by_owner",
            "remaining_steps_not_started",
            (),
            (),
            NOW,
        ),
    ],
)
def test_terminal_and_held_snapshots_have_explicit_semantics(
    status: WorkflowRunStatus,
    records_count: int,
    reason_code: str | None,
    impact_code: str | None,
    missing_fields: tuple[str, ...],
    actions: tuple[str, ...],
    finished_at: datetime | None,
) -> None:
    completed_steps = 1 if status is not WorkflowRunStatus.HELD else 0
    assert (
        validate_workflow_run_state_snapshot(
            status,
            total_steps=1,
            completed_steps=completed_steps,
            records_count=records_count,
            status_reason_code=reason_code,
            impact_code=impact_code,
            missing_fields=missing_fields,
            recovery_action_codes=actions,
            finished_at=finished_at,
        )
        is status
    )


@pytest.mark.parametrize(
    (
        "status",
        "records_count",
        "reason_code",
        "impact_code",
        "missing_fields",
        "actions",
        "finished_at",
        "error",
    ),
    [
        (WorkflowRunStatus.COMPLETED, 0, None, None, (), (), NOW, "completed_records_invalid"),
        (
            WorkflowRunStatus.EMPTY_VALID,
            1,
            "verified_zero_result",
            "no_records_in_scope",
            (),
            (),
            NOW,
            "empty_valid_records_invalid",
        ),
        (
            WorkflowRunStatus.DEGRADED,
            1,
            "fallback_missing_optional_fields",
            "delivery_missing_fields",
            (),
            ("review_missing_fields",),
            NOW,
            "degraded_missing_fields_required",
        ),
        (
            WorkflowRunStatus.HELD,
            0,
            "fallback_blocked",
            "step_not_completed_following_steps_not_started",
            (),
            (),
            None,
            "held_recovery_action_required",
        ),
        (
            WorkflowRunStatus.HELD,
            0,
            "fallback_blocked",
            "step_not_completed_following_steps_not_started",
            (),
            ("inspect_fallback_gate_evidence",),
            NOW,
            "held_finished_at_invalid",
        ),
    ],
)
def test_invalid_state_snapshots_fail_closed(
    status: WorkflowRunStatus,
    records_count: int,
    reason_code: str | None,
    impact_code: str | None,
    missing_fields: tuple[str, ...],
    actions: tuple[str, ...],
    finished_at: datetime | None,
    error: str,
) -> None:
    with pytest.raises(WorkflowExecutionStateSnapshotError, match=error):
        validate_workflow_run_state_snapshot(
            status,
            total_steps=1,
            completed_steps=1 if status is not WorkflowRunStatus.HELD else 0,
            records_count=records_count,
            status_reason_code=reason_code,
            impact_code=impact_code,
            missing_fields=missing_fields,
            recovery_action_codes=actions,
            finished_at=finished_at,
        )
