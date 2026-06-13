from __future__ import annotations

from datetime import UTC, datetime, timedelta


class UnsupportedCronExpression(ValueError):
    pass


def is_schedule_due(
    schedule_cron: str | None,
    last_run_at: datetime | None,
    now: datetime | None = None,
) -> bool:
    if schedule_cron is None or schedule_cron.strip() == "":
        return False
    interval = cron_interval(schedule_cron)
    if last_run_at is None:
        return True

    current_time = _aware(now or datetime.now(UTC))
    last_run_time = _aware(last_run_at)
    return current_time >= last_run_time + interval


def cron_interval(schedule_cron: str) -> timedelta:
    fields = schedule_cron.split()
    if len(fields) != 5:
        raise UnsupportedCronExpression("schedule_cron must contain 5 fields")

    minute, hour, day_of_month, month, day_of_week = fields
    if day_of_month != "*" or month != "*" or day_of_week != "*":
        raise UnsupportedCronExpression("only minute and hour cron fields are supported")

    minute_step = _step_value(minute, 0, 59)
    hour_step = _step_value(hour, 0, 23)

    if minute == "*" and hour == "*":
        return timedelta(minutes=1)
    if minute_step is not None and hour == "*":
        return timedelta(minutes=minute_step)
    if _is_exact(minute, 0, 59) and hour_step is not None:
        return timedelta(hours=hour_step)
    if _is_exact(minute, 0, 59) and _is_exact(hour, 0, 23):
        return timedelta(days=1)

    raise UnsupportedCronExpression(f"unsupported schedule_cron: {schedule_cron}")


def _step_value(field: str, minimum: int, maximum: int) -> int | None:
    if not field.startswith("*/"):
        return None
    raw_step = field[2:]
    if not raw_step.isdigit():
        raise UnsupportedCronExpression(f"invalid cron step: {field}")
    step = int(raw_step)
    if step <= 0 or step > maximum - minimum + 1:
        raise UnsupportedCronExpression(f"cron step out of range: {field}")
    return step


def _is_exact(field: str, minimum: int, maximum: int) -> bool:
    if not field.isdigit():
        return False
    value = int(field)
    if value < minimum or value > maximum:
        raise UnsupportedCronExpression(f"cron value out of range: {field}")
    return True


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
