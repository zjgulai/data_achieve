from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from data_intelligence_hub.models.scheduler import SchedulerTick


class SchedulerTickResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lease_name: str
    owner_id: str
    status: str
    lock_acquired: bool
    started_at: datetime
    finished_at: datetime
    scanned: int
    due: int
    started: int
    skipped_running: int
    skipped_invalid_schedule: int
    task_errors: int
    report_subscriptions_scanned: int
    report_subscriptions_due: int
    report_subscriptions_started: int
    report_subscriptions_skipped_running: int
    report_subscription_errors: int
    error_message: str | None


class SchedulerOverviewResponse(BaseModel):
    enabled: bool
    latest_tick: SchedulerTickResponse | None

    @classmethod
    def from_tick(
        cls,
        *,
        enabled: bool,
        latest_tick: SchedulerTick | None,
    ) -> SchedulerOverviewResponse:
        return cls(
            enabled=enabled,
            latest_tick=(
                SchedulerTickResponse.model_validate(latest_tick)
                if latest_tick is not None
                else None
            ),
        )
