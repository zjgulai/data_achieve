"""Policy failures are terminal and quick collects never enroll themselves in schedules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.services.collector_service import _collection_failure_reason
from data_intelligence_hub.services.task_schedule_policy import is_task_due


def test_policy_failure_is_not_an_upstream_failure() -> None:
    assert (
        _collection_failure_reason("collection_policy_denied: unsupported executor")
        == "policy_denied"
    )
    assert _collection_failure_reason("outbound_domain_denied: unapproved host") == "policy_denied"
    assert (
        _collection_failure_reason("outbound_budget_exceeded: attempts exhausted")
        == "policy_denied"
    )


def test_policy_denied_task_does_not_retry_next_day() -> None:
    now = datetime.now(UTC)
    task = CollectionTask(
        collector_type="generic_web",
        name="scheduled",
        status="enabled",
        config={
            "schedule_policy": "auto_freshness",
            "freshness_target_hours": 1,
        },
        last_run_at=now - timedelta(days=1),
    )
    run = TaskRun(
        status="failed",
        finished_at=now - timedelta(days=1),
        error_message="outbound_domain_denied: unapproved host",
    )
    assert not is_task_due(task, run, now)


def test_quick_collect_marker_cannot_be_scheduled() -> None:
    now = datetime.now(UTC)
    task = CollectionTask(
        collector_type="manual_json",
        name="renamed",
        status="enabled",
        config={
            "execution_origin": "quick_collect",
            "schedule_policy": "auto_freshness",
        },
    )
    assert not is_task_due(task, None, now)


def test_policy_denial_blocks_cron_as_well_as_freshness() -> None:
    now = datetime.now(UTC)
    task = CollectionTask(
        collector_type="generic_web",
        name="cron",
        status="enabled",
        schedule_cron="30 12 * * *",
        last_run_at=now - timedelta(days=2),
        config={},
    )
    run = TaskRun(
        status="failed",
        finished_at=now - timedelta(days=2),
        error_message="collection_policy_denied: offline",
    )
    assert not is_task_due(task, run, now)


def test_one_shot_marker_blocks_even_explicit_cron() -> None:
    now = datetime.now(UTC)
    task = CollectionTask(
        collector_type="manual_json",
        name="renamed",
        status="enabled",
        schedule_cron="30 12 * * *",
        config={"execution_origin": "quick_collect"},
    )
    assert not is_task_due(task, None, now)
