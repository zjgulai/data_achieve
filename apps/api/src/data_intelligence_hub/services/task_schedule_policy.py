from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.scheduler.cron import UnsupportedCronExpression, cron_interval

AUTO_FRESHNESS_POLICY = "auto_freshness"
MANUAL_REFRESH_POLICY = "manual_refresh_only"
DEFAULT_FRESHNESS_TARGET_HOURS = 24
DEFAULT_RETRY_DELAY_MINUTES = 15


def task_schedule_policy(config: dict[str, Any] | None) -> str:
    if config is None:
        return MANUAL_REFRESH_POLICY
    value = config.get("schedule_policy")
    if value == AUTO_FRESHNESS_POLICY:
        return AUTO_FRESHNESS_POLICY
    return MANUAL_REFRESH_POLICY


def freshness_target_hours(config: dict[str, Any] | None) -> int:
    if config is None:
        return DEFAULT_FRESHNESS_TARGET_HOURS
    value = config.get("freshness_target_hours")
    if isinstance(value, int | float) and value > 0:
        return int(value)
    return DEFAULT_FRESHNESS_TARGET_HOURS


def retry_delay_minutes(config: dict[str, Any] | None) -> int:
    if config is None:
        return DEFAULT_RETRY_DELAY_MINUTES
    value = config.get("retry_delay_minutes")
    if isinstance(value, int | float) and value > 0:
        return int(value)
    return DEFAULT_RETRY_DELAY_MINUTES


def next_run_at(
    task: CollectionTask,
    latest_run: TaskRun | None,
    now: datetime,
) -> datetime | None:
    current_time = _as_utc(now)
    if task.status in {"paused", "disabled"}:
        return None
    if task.schedule_cron:
        try:
            return _next_cron_run_at(task, current_time)
        except UnsupportedCronExpression:
            return None
    if task_schedule_policy(task.config) != AUTO_FRESHNESS_POLICY:
        return None
    if latest_run is not None and latest_run.status == "failed":
        return retry_after_at(task, latest_run)
    if task.last_run_at is None:
        return current_time
    return _as_utc(task.last_run_at) + timedelta(hours=freshness_target_hours(task.config))


def retry_after_at(task: CollectionTask, latest_run: TaskRun | None) -> datetime | None:
    if latest_run is None or latest_run.status != "failed":
        return None
    base_time = latest_run.finished_at or latest_run.started_at or latest_run.created_at
    return _as_utc(base_time) + timedelta(minutes=retry_delay_minutes(task.config))


def is_task_due(
    task: CollectionTask,
    latest_run: TaskRun | None,
    now: datetime,
) -> bool:
    due_at = next_run_at(task, latest_run, now)
    return due_at is not None and _as_utc(due_at) <= _as_utc(now)


def _next_cron_run_at(task: CollectionTask, now: datetime) -> datetime:
    if task.schedule_cron is None:
        return now
    interval = cron_interval(task.schedule_cron)
    if task.last_run_at is None:
        return now
    next_time = _as_utc(task.last_run_at) + interval
    if next_time <= now:
        return now
    return next_time


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
