from __future__ import annotations

import pytest

from data_intelligence_hub.schemas.workflow_plan_persistence import (
    WorkflowPlanStatus,
    WorkflowPlanTransitionRequest,
)
from data_intelligence_hub.services.workflow_planner.lifecycle import (
    WorkflowPlanTransitionError,
    allowed_plan_status_transitions,
    transition_workflow_plan_status,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("draft", "previewed"),
        ("previewed", "approved"),
        ("approved", "active"),
        ("active", "paused"),
        ("paused", "active"),
        ("paused", "archived"),
    ],
)
def test_plan_lifecycle_allows_documented_edges(
    current: WorkflowPlanStatus,
    target: WorkflowPlanStatus,
) -> None:
    assert transition_workflow_plan_status(current, target) == target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("draft", "approved"),
        ("previewed", "active"),
        ("approved", "paused"),
        ("active", "archived"),
        ("archived", "active"),
    ],
)
def test_plan_lifecycle_rejects_undocumented_edges(
    current: WorkflowPlanStatus,
    target: WorkflowPlanStatus,
) -> None:
    with pytest.raises(
        WorkflowPlanTransitionError,
        match=f"workflow_plan_invalid_transition:{current}:{target}",
    ):
        transition_workflow_plan_status(current, target)


def test_same_state_is_an_explicit_noop() -> None:
    assert transition_workflow_plan_status("previewed", "previewed") == "previewed"


def test_transition_table_is_closed_over_six_states() -> None:
    assert set(allowed_plan_status_transitions) == {
        "draft",
        "previewed",
        "approved",
        "active",
        "paused",
        "archived",
    }
    assert allowed_plan_status_transitions["archived"] == frozenset()


def test_transition_request_rejects_extra_and_invalid_status() -> None:
    request = WorkflowPlanTransitionRequest(
        expected_status="previewed",
        to_status="approved",
        reason="owner reviewed the frozen plan",
    )
    assert request.to_status == "approved"
    with pytest.raises(ValueError):
        WorkflowPlanTransitionRequest.model_validate(
            {
                "expected_status": "previewed",
                "to_status": "approved",
                "unexpected": True,
            }
        )
    with pytest.raises(ValueError):
        WorkflowPlanTransitionRequest(
            expected_status="unknown",
            to_status="approved",
        )
