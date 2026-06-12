from __future__ import annotations

import uuid
from datetime import UTC, datetime, time

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.report import Report
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.repositories.reports import (
    ReportAlertEvent,
    ReportIntelligence,
    create_report,
    get_report,
    list_alert_events_for_report,
    list_intelligence_for_report,
    list_reports,
)
from data_intelligence_hub.schemas.report import ReportGenerateRequest
from data_intelligence_hub.services.exceptions import ProjectNotFoundError, ReportNotFoundError
from data_intelligence_hub.services.notification_service import create_in_app_notification


async def get_reports(
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID | None,
) -> list[Report]:
    return await list_reports(session, workspace.id, project_id=project_id)


async def get_report_or_raise(
    session: AsyncSession,
    workspace: Workspace,
    report_id: uuid.UUID,
) -> Report:
    report = await get_report(session, workspace.id, report_id)
    if report is None:
        raise ReportNotFoundError
    return report


async def generate_report(
    session: AsyncSession,
    workspace: Workspace,
    payload: ReportGenerateRequest,
) -> Report:
    project = None
    if payload.project_id is not None:
        project = await get_project(session, workspace.id, payload.project_id)
        if project is None:
            raise ProjectNotFoundError

    now = datetime.now(UTC)
    period_start = payload.period_start or datetime.combine(now.date(), time.min, tzinfo=UTC)
    period_end = payload.period_end or now
    intelligence_items = await list_intelligence_for_report(
        session=session,
        workspace_id=workspace.id,
        project_id=payload.project_id,
        period_start=period_start,
        period_end=period_end,
    )
    alert_events = await list_alert_events_for_report(
        session=session,
        workspace_id=workspace.id,
        project_id=payload.project_id,
        period_start=period_start,
        period_end=period_end,
    )
    title_prefix = project.name if project is not None else "全局"
    title = f"{title_prefix} 日报 — {now.date().isoformat()}"
    report = Report(
        workspace_id=workspace.id,
        project_id=payload.project_id,
        report_type=payload.report_type,
        title=title,
        content=_render_daily_report(
            title=title,
            intelligence_items=intelligence_items,
            alert_events=alert_events,
        ),
        status="generated",
        period_start=period_start,
        period_end=period_end,
    )
    await create_report(session, report)
    await session.commit()
    await session.refresh(report)
    return report


async def send_report(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    report_id: uuid.UUID,
) -> Report:
    report = await get_report_or_raise(session, workspace, report_id)
    report.status = "sent"
    await create_in_app_notification(
        session=session,
        user_id=user.id,
        title=f"日报已生成：{report.title}",
        body="报告已进入站内通知中心，可从报告中心查看完整内容。",
        notification_type="report_ready",
        reference_type="report",
        reference_id=report.id,
    )
    await session.commit()
    await session.refresh(report)
    return report


def _render_daily_report(
    title: str,
    intelligence_items: list[ReportIntelligence],
    alert_events: list[ReportAlertEvent],
) -> str:
    lines = [
        f"# {title}",
        "",
        "## 监控概览",
        f"- 新增情报数：{len(intelligence_items)}",
        f"- 活跃预警：{len(alert_events)}",
        "",
        "## 核心发现",
    ]
    if not intelligence_items:
        lines.append("- 当前周期没有新增情报。")
    by_domain: dict[str, list[ReportIntelligence]] = {}
    for intelligence_row in intelligence_items:
        intelligence = intelligence_row.item
        by_domain.setdefault(intelligence.domain, []).append(intelligence_row)

    for domain, domain_items in by_domain.items():
        lines.extend(["", f"### {domain}"])
        for index, intelligence_row in enumerate(domain_items, start=1):
            intelligence = intelligence_row.item
            lines.extend(
                [
                    f"{index}. **{intelligence.title}** — Score: {intelligence.final_score}",
                    f"   {intelligence.summary}",
                    f"   情报 ID：{intelligence.id}",
                    f"   证据数：{intelligence_row.evidence_count}",
                ]
            )

    lines.extend(["", "## 预警区"])
    if not alert_events:
        lines.append("- 当前周期没有预警事件。")
    for index, alert_row in enumerate(alert_events, start=1):
        payload = alert_row.event.payload
        signal_type = payload.get("signal_type", "unknown")
        severity = payload.get("severity", "unknown")
        intelligence_id = payload.get("intelligence_id")
        lines.append(
            f"{index}. {alert_row.rule_name} — {signal_type}, severity={severity}, "
            f"status={alert_row.event.status}, intelligence_id={intelligence_id}"
        )
    return "\n".join(lines)
