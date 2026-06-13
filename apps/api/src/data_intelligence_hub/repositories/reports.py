from __future__ import annotations

import uuid
from datetime import datetime
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.alert import AlertEvent, AlertRule
from data_intelligence_hub.models.intelligence import Evidence, IntelligenceItem
from data_intelligence_hub.models.report import (
    Report,
    ReportAuditEvent,
    ReportSubscription,
    ReportSubscriptionRun,
)
from data_intelligence_hub.models.signal import Signal
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace


class ReportIntelligence(NamedTuple):
    item: IntelligenceItem
    evidence_count: int


class ReportAlertEvent(NamedTuple):
    event: AlertEvent
    rule_name: str


class DueReportSubscription(NamedTuple):
    subscription: ReportSubscription
    workspace: Workspace
    user: User


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


async def list_report_subscriptions(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[ReportSubscription]:
    result = await session.execute(
        select(ReportSubscription)
        .where(
            ReportSubscription.workspace_id == workspace_id,
            ReportSubscription.user_id == user_id,
        )
        .order_by(
            ReportSubscription.enabled.desc(),
            ReportSubscription.created_at.desc(),
            ReportSubscription.id.asc(),
        )
    )
    return list(result.scalars().all())


async def get_report_subscription_by_scope(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    project_id: uuid.UUID | None,
    report_type: str,
) -> ReportSubscription | None:
    statement = select(ReportSubscription).where(
        ReportSubscription.workspace_id == workspace_id,
        ReportSubscription.user_id == user_id,
        ReportSubscription.report_type == report_type,
    )
    if project_id is None:
        statement = statement.where(ReportSubscription.project_id.is_(None))
    else:
        statement = statement.where(ReportSubscription.project_id == project_id)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_report_subscription(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    subscription_id: uuid.UUID,
) -> ReportSubscription | None:
    result = await session.execute(
        select(ReportSubscription).where(
            ReportSubscription.workspace_id == workspace_id,
            ReportSubscription.user_id == user_id,
            ReportSubscription.id == subscription_id,
        )
    )
    return result.scalar_one_or_none()


async def create_report_subscription(
    session: AsyncSession,
    subscription: ReportSubscription,
) -> ReportSubscription:
    session.add(subscription)
    await session.flush()
    return subscription


async def create_report_subscription_run(
    session: AsyncSession,
    run: ReportSubscriptionRun,
) -> ReportSubscriptionRun:
    session.add(run)
    await session.flush()
    return run


async def list_latest_report_subscription_runs(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    subscription_ids: list[uuid.UUID],
) -> dict[uuid.UUID, ReportSubscriptionRun]:
    if not subscription_ids:
        return {}
    result = await session.execute(
        select(ReportSubscriptionRun)
        .where(
            ReportSubscriptionRun.workspace_id == workspace_id,
            ReportSubscriptionRun.subscription_id.in_(subscription_ids),
        )
        .order_by(ReportSubscriptionRun.started_at.desc(), ReportSubscriptionRun.id.desc())
    )
    latest: dict[uuid.UUID, ReportSubscriptionRun] = {}
    for run in result.scalars().all():
        latest.setdefault(run.subscription_id, run)
    return latest


async def list_due_report_subscriptions(
    session: AsyncSession,
    now: datetime,
) -> list[DueReportSubscription]:
    result = await session.execute(
        select(ReportSubscription, Workspace, User)
        .join(Workspace, ReportSubscription.workspace_id == Workspace.id)
        .join(User, ReportSubscription.user_id == User.id)
        .where(
            ReportSubscription.enabled.is_(True),
            ReportSubscription.next_run_at.is_not(None),
            ReportSubscription.next_run_at <= now,
        )
        .order_by(ReportSubscription.next_run_at.asc(), ReportSubscription.created_at.asc())
    )
    return [
        DueReportSubscription(subscription=subscription, workspace=workspace, user=user)
        for subscription, workspace, user in result.all()
    ]


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
