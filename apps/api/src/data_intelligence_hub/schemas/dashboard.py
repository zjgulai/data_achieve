from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class DashboardTypeBreakdownItem(BaseModel):
    type: str
    count: int
    percent: float


class DashboardDomainBreakdownItem(BaseModel):
    domain: str
    intelligence_count: int
    signal_count: int
    project_count: int


class DashboardTopIntelligenceItem(BaseModel):
    id: uuid.UUID
    title: str
    summary: str
    domain: str
    type: str
    evidence_count: int
    final_score: float
    status: str
    created_at: datetime
    updated_at: datetime


class DashboardRecentFailureItem(BaseModel):
    task_id: uuid.UUID
    task_name: str
    status: str
    error_message: str | None
    created_at: datetime


class DashboardTaskHealth(BaseModel):
    total_tasks: int
    enabled_tasks: int
    failed_tasks: int
    recent_runs: int
    recent_failures: list[DashboardRecentFailureItem]


class DashboardStaleTaskItem(BaseModel):
    task_id: uuid.UUID
    task_name: str
    collector_type: str
    status: str
    last_run_at: datetime | None
    freshness_target_hours: int
    stale_hours: float | None


class DashboardFreshness(BaseModel):
    generated_at: datetime
    latest_collection_at: datetime | None
    stale_enabled_tasks: int
    stale_tasks: list[DashboardStaleTaskItem]


class DashboardOverviewResponse(BaseModel):
    intelligence_count: int
    task_success_rate: float
    field_completeness: float
    active_alerts: int
    failed_tasks: int
    recent_runs: int
    source_count: int
    type_breakdown: list[DashboardTypeBreakdownItem]
    domain_breakdown: list[DashboardDomainBreakdownItem]
    top_intelligence: list[DashboardTopIntelligenceItem]
    task_health: DashboardTaskHealth
    freshness: DashboardFreshness
