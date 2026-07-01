from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.scheduler.cron import UnsupportedCronExpression, cron_interval

AUTO_FRESHNESS_POLICY = "auto_freshness"
MANUAL_REFRESH_POLICY = "manual_refresh_only"
DEFAULT_FRESHNESS_TARGET_HOURS = 24
DEFAULT_RETRY_DELAY_MINUTES = 15
DEFAULT_MAX_RETRY_ATTEMPTS = 3
RETRY_ATTEMPTS_USED_CONFIG_KEY = "retry_attempts_used"


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


def max_retry_attempts(config: dict[str, Any] | None) -> int:
    if config is None:
        return DEFAULT_MAX_RETRY_ATTEMPTS
    value = config.get("max_retry_attempts")
    if isinstance(value, int | float) and value >= 0:
        return int(value)
    return DEFAULT_MAX_RETRY_ATTEMPTS


def retry_attempts_used(config: dict[str, Any] | None) -> int:
    if config is None:
        return 0
    value = config.get(RETRY_ATTEMPTS_USED_CONFIG_KEY)
    if isinstance(value, int | float) and value > 0:
        return int(value)
    return 0


def retry_budget_exhausted(task: CollectionTask, latest_run: TaskRun | None) -> bool:
    if latest_run is None or latest_run.status != "failed":
        return False
    return retry_attempts_used(task.config) >= max_retry_attempts(task.config)


def update_retry_state_after_run(
    config: dict[str, Any] | None,
    status: str,
) -> dict[str, Any] | None:
    if status == "failed":
        next_config = dict(config or {})
        next_config[RETRY_ATTEMPTS_USED_CONFIG_KEY] = min(
            retry_attempts_used(next_config) + 1,
            max_retry_attempts(next_config),
        )
        return next_config

    if config is None or retry_attempts_used(config) == 0:
        return config

    next_config = dict(config)
    next_config[RETRY_ATTEMPTS_USED_CONFIG_KEY] = 0
    return next_config


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
        if retry_budget_exhausted(task, latest_run):
            return None
        return retry_after_at(task, latest_run)
    if task.last_run_at is None:
        return current_time
    return _as_utc(task.last_run_at) + timedelta(hours=freshness_target_hours(task.config))


def retry_after_at(task: CollectionTask, latest_run: TaskRun | None) -> datetime | None:
    if latest_run is None or latest_run.status != "failed":
        return None
    if retry_budget_exhausted(task, latest_run):
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
