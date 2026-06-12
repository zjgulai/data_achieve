from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.dashboard import (
    count_active_alerts,
    count_intelligence,
    count_intelligence_by_domain,
    count_intelligence_by_type,
    count_latest_failed_tasks,
    count_projects_by_domain,
    count_signals_by_domain,
    count_sources,
    count_tasks,
    list_recent_failures,
    list_snapshot_metrics,
    list_top_intelligence,
    task_run_status_counts,
)
from data_intelligence_hub.schemas.dashboard import (
    DashboardDomainBreakdownItem,
    DashboardOverviewResponse,
    DashboardRecentFailureItem,
    DashboardTaskHealth,
    DashboardTopIntelligenceItem,
    DashboardTypeBreakdownItem,
)


async def get_dashboard_overview(
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID | None,
    domain: str | None,
    from_time: datetime | None,
    to_time: datetime | None,
    limit: int,
) -> DashboardOverviewResponse:
    intelligence_count = await count_intelligence(
        session,
        workspace.id,
        project_id=project_id,
        domain=domain,
        from_time=from_time,
        to_time=to_time,
    )
    type_counts = await count_intelligence_by_type(
        session,
        workspace.id,
        project_id=project_id,
        domain=domain,
        from_time=from_time,
        to_time=to_time,
    )
    top_items = await list_top_intelligence(
        session,
        workspace.id,
        project_id=project_id,
        domain=domain,
        from_time=from_time,
        to_time=to_time,
        limit=limit,
    )
    run_counts = await task_run_status_counts(
        session,
        workspace.id,
        project_id=project_id,
        domain=domain,
        from_time=from_time,
        to_time=to_time,
    )
    total_tasks, enabled_tasks = await count_tasks(
        session,
        workspace.id,
        project_id=project_id,
        domain=domain,
    )
    failed_tasks = await count_latest_failed_tasks(
        session,
        workspace.id,
        project_id=project_id,
        domain=domain,
    )
    active_alerts = await count_active_alerts(
        session,
        workspace.id,
        project_id=project_id,
        domain=domain,
        from_time=from_time,
        to_time=to_time,
    )
    recent_failures = await list_recent_failures(
        session,
        workspace.id,
        project_id=project_id,
        domain=domain,
        limit=min(limit, 10),
    )
    source_count = await count_sources(session, workspace.id, project_id=project_id, domain=domain)
    snapshot_metrics = await list_snapshot_metrics(
        session,
        workspace.id,
        project_id=project_id,
        domain=domain,
        limit=200,
    )

    return DashboardOverviewResponse(
        intelligence_count=intelligence_count,
        task_success_rate=_success_rate(run_counts),
        field_completeness=_field_completeness(snapshot_metrics),
        active_alerts=active_alerts,
        failed_tasks=failed_tasks,
        recent_runs=sum(run_counts.values()),
        source_count=source_count,
        type_breakdown=_type_breakdown(type_counts, intelligence_count),
        domain_breakdown=await _domain_breakdown(
            session,
            workspace,
            domain=domain,
            from_time=from_time,
            to_time=to_time,
        ),
        top_intelligence=[
            DashboardTopIntelligenceItem(
                id=row.item.id,
                title=row.item.title,
                summary=row.item.summary,
                domain=row.item.domain,
                type=row.item.intelligence_type,
                evidence_count=row.evidence_count,
                final_score=row.item.final_score,
                status=row.item.status,
                created_at=row.item.created_at,
            )
            for row in top_items
        ],
        task_health=DashboardTaskHealth(
            total_tasks=total_tasks,
            enabled_tasks=enabled_tasks,
            failed_tasks=failed_tasks,
            recent_runs=sum(run_counts.values()),
            recent_failures=[
                DashboardRecentFailureItem(
                    task_id=row.task_id,
                    task_name=row.task_name,
                    status=row.status,
                    error_message=row.error_message,
                    created_at=row.created_at,
                )
                for row in recent_failures
            ],
        ),
    )


async def _domain_breakdown(
    session: AsyncSession,
    workspace: Workspace,
    domain: str | None,
    from_time: datetime | None,
    to_time: datetime | None,
) -> list[DashboardDomainBreakdownItem]:
    project_counts = await count_projects_by_domain(session, workspace.id, domain=domain)
    intelligence_counts = await count_intelligence_by_domain(
        session,
        workspace.id,
        domain=domain,
        from_time=from_time,
        to_time=to_time,
    )
    signal_counts = await count_signals_by_domain(
        session,
        workspace.id,
        domain=domain,
        from_time=from_time,
        to_time=to_time,
    )
    domains = sorted(set(project_counts) | set(intelligence_counts) | set(signal_counts))
    return [
        DashboardDomainBreakdownItem(
            domain=item,
            intelligence_count=intelligence_counts.get(item, 0),
            signal_count=signal_counts.get(item, 0),
            project_count=project_counts.get(item, 0),
        )
        for item in domains
    ]


def _type_breakdown(
    type_counts: dict[str, int],
    total: int,
) -> list[DashboardTypeBreakdownItem]:
    return [
        DashboardTypeBreakdownItem(
            type=item,
            count=count,
            percent=round((count / total) * 100, 2) if total > 0 else 0.0,
        )
        for item, count in sorted(type_counts.items(), key=lambda entry: (-entry[1], entry[0]))
    ]


def _success_rate(run_counts: dict[str, int]) -> float:
    total = sum(run_counts.values())
    if total == 0:
        return 0.0
    successful = run_counts.get("success", 0) + run_counts.get("partial_success", 0)
    return round((successful / total) * 100, 2)


def _field_completeness(metrics_items: list[dict[str, object]]) -> float:
    total_fields = 0
    filled_fields = 0
    for metrics in metrics_items:
        for value in metrics.values():
            total_fields += 1
            if value is not None and value != "":
                filled_fields += 1
    if total_fields == 0:
        return 0.0
    return round((filled_fields / total_fields) * 100, 2)
