from __future__ import annotations

import uuid
from datetime import datetime
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.alert import AlertEvent, AlertRule
from data_intelligence_hub.models.intelligence import Evidence, IntelligenceItem
from data_intelligence_hub.models.report import Report, ReportAuditEvent
from data_intelligence_hub.models.signal import Signal


class ReportIntelligence(NamedTuple):
    item: IntelligenceItem
    evidence_count: int


class ReportAlertEvent(NamedTuple):
    event: AlertEvent
    rule_name: str


async def list_reports(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
) -> list[Report]:
    statement = select(Report).where(Report.workspace_id == workspace_id)
    if project_id is not None:
        statement = statement.where(Report.project_id == project_id)
    statement = statement.order_by(Report.created_at.desc())
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_report(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
) -> Report | None:
    result = await session.execute(
        select(Report).where(Report.workspace_id == workspace_id, Report.id == report_id)
    )
    return result.scalar_one_or_none()


async def create_report(session: AsyncSession, report: Report) -> Report:
    session.add(report)
    await session.flush()
    return report


async def create_report_audit_event(
    session: AsyncSession,
    event: ReportAuditEvent,
) -> ReportAuditEvent:
    session.add(event)
    await session.flush()
    return event


async def list_report_audit_events(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
) -> list[ReportAuditEvent]:
    result = await session.execute(
        select(ReportAuditEvent)
        .where(
            ReportAuditEvent.workspace_id == workspace_id,
            ReportAuditEvent.report_id == report_id,
        )
        .order_by(ReportAuditEvent.created_at.asc(), ReportAuditEvent.id.asc())
    )
    return list(result.scalars().all())


async def list_intelligence_for_report(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    period_start: datetime,
    period_end: datetime,
) -> list[ReportIntelligence]:
    statement = (
        select(IntelligenceItem, func.count(Evidence.id))
        .outerjoin(Evidence, Evidence.intelligence_id == IntelligenceItem.id)
        .where(
            IntelligenceItem.workspace_id == workspace_id,
            IntelligenceItem.created_at >= period_start,
            IntelligenceItem.created_at <= period_end,
        )
        .group_by(IntelligenceItem.id)
        .order_by(IntelligenceItem.final_score.desc(), IntelligenceItem.created_at.desc())
    )
    if project_id is not None:
        statement = statement.where(IntelligenceItem.project_id == project_id)

    result = await session.execute(statement)
    return [
        ReportIntelligence(item=item, evidence_count=int(evidence_count))
        for item, evidence_count in result.all()
    ]


async def list_alert_events_for_report(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    period_start: datetime,
    period_end: datetime,
) -> list[ReportAlertEvent]:
    statement = (
        select(AlertEvent, AlertRule.name)
        .join(AlertRule, AlertEvent.rule_id == AlertRule.id)
        .join(Signal, AlertEvent.signal_id == Signal.id)
        .where(
            AlertRule.workspace_id == workspace_id,
            AlertEvent.triggered_at >= period_start,
            AlertEvent.triggered_at <= period_end,
        )
        .order_by(AlertEvent.triggered_at.desc())
    )
    if project_id is not None:
        statement = statement.where(Signal.project_id == project_id)

    result = await session.execute(statement)
    return [
        ReportAlertEvent(event=event, rule_name=rule_name)
        for event, rule_name in result.all()
    ]
