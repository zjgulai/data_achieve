from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import NamedTuple
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.report import Report, ReportAuditEvent, ReportSubscription
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.intelligence import (
    EvidenceWithTrace,
    list_evidences_with_trace,
)
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.repositories.reports import (
    ReportAlertEvent,
    ReportIntelligence,
    create_report,
    create_report_audit_event,
    create_report_subscription,
    get_report,
    get_report_subscription_by_scope,
    list_alert_events_for_report,
    list_intelligence_for_report,
    list_report_audit_events,
    list_report_subscriptions,
    list_reports,
)
from data_intelligence_hub.schemas.report import (
    ReportGenerateRequest,
    ReportSubscriptionUpsertRequest,
)
from data_intelligence_hub.services.exceptions import ProjectNotFoundError, ReportNotFoundError
from data_intelligence_hub.services.notification_service import (
    create_in_app_notification,
    send_email_notification,
)


class ReportEvidenceReference(NamedTuple):
    intelligence: ReportIntelligence
    evidences: list[EvidenceWithTrace]


@dataclass(frozen=True)
class ReportDispatchResult:
    report: Report
    delivered_channels: list[str]
    skipped_channels: dict[str, str]


@dataclass(frozen=True)
class ReportSubscriptionExecutionResult:
    report: Report
    delivered_channels: list[str]
    skipped_channels: dict[str, str]


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


async def get_report_evidence_references(
    session: AsyncSession,
    workspace: Workspace,
    report_id: uuid.UUID,
) -> list[ReportEvidenceReference]:
    report = await get_report_or_raise(session, workspace, report_id)
    intelligence_items = await list_intelligence_for_report(
        session=session,
        workspace_id=workspace.id,
        project_id=report.project_id,
        period_start=report.period_start,
        period_end=report.period_end,
    )
    references: list[ReportEvidenceReference] = []
    for intelligence in intelligence_items:
        evidences = await list_evidences_with_trace(session, intelligence.item.id)
        references.append(ReportEvidenceReference(intelligence=intelligence, evidences=evidences))
    return references


async def get_report_audit_events(
    session: AsyncSession,
    workspace: Workspace,
    report_id: uuid.UUID,
) -> list[ReportAuditEvent]:
    await get_report_or_raise(session, workspace, report_id)
    return await list_report_audit_events(session, workspace.id, report_id)


async def get_report_subscriptions(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
) -> list[ReportSubscription]:
    return await list_report_subscriptions(session, workspace.id, user.id)


async def upsert_report_subscription(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    payload: ReportSubscriptionUpsertRequest,
) -> ReportSubscription:
    if payload.project_id is not None:
        project = await get_project(session, workspace.id, payload.project_id)
        if project is None:
            raise ProjectNotFoundError

    now = datetime.now(UTC)
    next_run_at = _compute_next_run_at(payload.schedule_time, payload.timezone, now)
    subscription = await get_report_subscription_by_scope(
        session=session,
        workspace_id=workspace.id,
        user_id=user.id,
        project_id=payload.project_id,
        report_type=payload.report_type,
    )
    if subscription is None:
        subscription = await create_report_subscription(
            session,
            ReportSubscription(
                workspace_id=workspace.id,
                user_id=user.id,
                project_id=payload.project_id,
                report_type=payload.report_type,
                schedule_time=payload.schedule_time,
                timezone=payload.timezone,
                channels=list(payload.channels),
                enabled=payload.enabled,
                next_run_at=next_run_at if payload.enabled else None,
                updated_at=now,
            ),
        )
    else:
        subscription.schedule_time = payload.schedule_time
        subscription.timezone = payload.timezone
        subscription.channels = list(payload.channels)
        subscription.enabled = payload.enabled
        subscription.next_run_at = next_run_at if payload.enabled else None
        subscription.updated_at = now

    await session.commit()
    await session.refresh(subscription)
    return subscription


async def execute_report_subscription(
    session: AsyncSession,
    subscription: ReportSubscription,
    workspace: Workspace,
    user: User,
    now: datetime | None = None,
) -> ReportSubscriptionExecutionResult:
    current_time = _aware(now or datetime.now(UTC))
    period_start = subscription.last_sent_at or _subscription_period_start(
        subscription,
        current_time,
    )
    report = await generate_report(
        session=session,
        workspace=workspace,
        user=user,
        payload=ReportGenerateRequest(
            project_id=subscription.project_id,
            report_type="daily",
            period_start=period_start,
            period_end=current_time,
        ),
    )
    generated_status = report.status
    dispatch_result = await dispatch_report(
        session=session,
        workspace=workspace,
        user=user,
        report_id=report.id,
        channels=subscription.channels,
    )
    if dispatch_result.delivered_channels:
        subscription.last_sent_at = current_time
    subscription.next_run_at = _compute_next_run_at(
        subscription.schedule_time,
        subscription.timezone,
        current_time,
    )
    subscription.updated_at = current_time
    await _create_report_audit_event(
        session=session,
        workspace_id=workspace.id,
        report_id=report.id,
        actor_id=user.id,
        event_type="subscription_executed",
        from_status=generated_status,
        to_status=dispatch_result.report.status,
        metadata={
            "delivered_channels": ",".join(dispatch_result.delivered_channels),
            "skipped_channels": ",".join(dispatch_result.skipped_channels.keys()),
            "subscription_id": str(subscription.id),
        },
    )
    await session.commit()
    await session.refresh(subscription)
    await session.refresh(dispatch_result.report)
    return ReportSubscriptionExecutionResult(
        report=dispatch_result.report,
        delivered_channels=dispatch_result.delivered_channels,
        skipped_channels=dispatch_result.skipped_channels,
    )


async def generate_report(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
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
    await _create_report_audit_event(
        session=session,
        workspace_id=workspace.id,
        report_id=report.id,
        actor_id=user.id,
        event_type="generated",
        from_status=None,
        to_status=report.status,
        metadata={
            "project_id": str(payload.project_id) if payload.project_id is not None else "global",
            "period_end": period_end.isoformat(),
            "period_start": period_start.isoformat(),
        },
    )
    await session.commit()
    await session.refresh(report)
    return report


async def send_report(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    report_id: uuid.UUID,
) -> Report:
    dispatch_result = await dispatch_report(
        session=session,
        workspace=workspace,
        user=user,
        report_id=report_id,
        channels=["in_app"],
    )
    return dispatch_result.report


async def dispatch_report(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    report_id: uuid.UUID,
    channels: Sequence[str],
) -> ReportDispatchResult:
    report = await get_report_or_raise(session, workspace, report_id)
    previous_status = report.status
    delivered_channels: list[str] = []
    skipped_channels: dict[str, str] = {}
    unique_channels = list(dict.fromkeys(channels))

    if "in_app" in unique_channels:
        await create_in_app_notification(
            session=session,
            user_id=user.id,
            title=f"日报已生成：{report.title}",
            body="报告已进入站内通知中心，可从报告中心查看完整内容。",
            notification_type="report_ready",
            reference_type="report",
            reference_id=report.id,
        )
        delivered_channels.append("in_app")

    if "email" in unique_channels:
        email_result = await send_email_notification(
            recipient_email=user.email,
            subject=f"日报已生成：{report.title}",
            body=report.content,
        )
        if email_result.delivered:
            delivered_channels.append("email")
        else:
            skipped_channels["email"] = email_result.reason or "unknown"

    if delivered_channels:
        report.status = "sent"
        for channel in delivered_channels:
            await _create_report_audit_event(
                session=session,
                workspace_id=workspace.id,
                report_id=report.id,
                actor_id=user.id,
                event_type="sent",
                from_status=previous_status,
                to_status=report.status,
                metadata={"channel": channel},
            )

    for channel, reason in skipped_channels.items():
        await _create_report_audit_event(
            session=session,
            workspace_id=workspace.id,
            report_id=report.id,
            actor_id=user.id,
            event_type="send_skipped",
            from_status=previous_status,
            to_status=report.status,
            metadata={"channel": channel, "reason": reason},
        )

    await session.commit()
    await session.refresh(report)
    return ReportDispatchResult(
        report=report,
        delivered_channels=delivered_channels,
        skipped_channels=skipped_channels,
    )


async def record_report_share_event(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    report_id: uuid.UUID,
    event_type: str,
    metadata: dict[str, str],
) -> ReportAuditEvent:
    report = await get_report_or_raise(session, workspace, report_id)
    event = await _create_report_audit_event(
        session=session,
        workspace_id=workspace.id,
        report_id=report.id,
        actor_id=user.id,
        event_type=event_type,
        from_status=report.status,
        to_status=report.status,
        metadata=metadata,
    )
    await session.commit()
    await session.refresh(event)
    return event


async def _create_report_audit_event(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    event_type: str,
    from_status: str | None,
    to_status: str | None,
    metadata: dict[str, str],
) -> ReportAuditEvent:
    event = ReportAuditEvent(
        workspace_id=workspace_id,
        report_id=report_id,
        actor_id=actor_id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        metadata_json=json.dumps(metadata, ensure_ascii=False),
        created_at=datetime.now(UTC),
    )
    return await create_report_audit_event(session, event)


def _compute_next_run_at(schedule_time: str, timezone_name: str, now: datetime) -> datetime:
    timezone = ZoneInfo(timezone_name)
    hour_text, minute_text = schedule_time.split(":")
    local_now = _aware(now).astimezone(timezone)
    candidate = local_now.replace(
        hour=int(hour_text),
        minute=int(minute_text),
        second=0,
        microsecond=0,
    )
    if candidate <= local_now:
        candidate += timedelta(days=1)
    return candidate.astimezone(UTC)


def _subscription_period_start(subscription: ReportSubscription, now: datetime) -> datetime:
    timezone = ZoneInfo(subscription.timezone)
    local_now = _aware(now).astimezone(timezone)
    local_start = datetime.combine(local_now.date(), time.min, tzinfo=timezone)
    return local_start.astimezone(UTC)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


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
