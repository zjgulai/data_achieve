from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import NamedTuple
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.report import (
    Report,
    ReportAuditEvent,
    ReportSubscription,
    ReportSubscriptionRun,
)
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
    create_report_subscription_run,
    get_report,
    get_report_subscription,
    get_report_subscription_by_scope,
    get_report_subscription_run,
    list_alert_events_for_report,
    list_intelligence_for_report,
    list_latest_report_subscription_runs,
    list_report_audit_events,
    list_report_subscription_runs,
    list_report_subscriptions,
    list_reports,
)
from data_intelligence_hub.schemas.report import (
    ReportGenerateRequest,
    ReportSendRequest,
    ReportSubscriptionRetryRequest,
    ReportSubscriptionRunRequest,
    ReportSubscriptionUpsertRequest,
)
from data_intelligence_hub.services.exceptions import (
    ProjectNotFoundError,
    ReportNotFoundError,
    ReportSendAuthorizationError,
    ReportSendConfirmationRequiredError,
    ReportSubscriptionNotFoundError,
    ReportSubscriptionRetryAuthorizationError,
    ReportSubscriptionRetryConfirmationRequiredError,
    ReportSubscriptionRunAuthorizationError,
    ReportSubscriptionRunConfirmationRequiredError,
    ReportSubscriptionRunNotFoundError,
    ReportSubscriptionRunRetryNotAllowedError,
)
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
class ReportSendResult:
    report: Report
    delivered_channels: list[str]
    skipped_channels: dict[str, str]
    idempotency_replayed: bool = False
    idempotency_key_hash: str | None = None


@dataclass(frozen=True)
class ReportSubscriptionExecutionResult:
    report: Report | None
    run: ReportSubscriptionRun
    status: str
    delivered_channels: list[str]
    skipped_channels: dict[str, str]


@dataclass(frozen=True)
class ReportSubscriptionWithLatestRun:
    subscription: ReportSubscription
    latest_run: ReportSubscriptionRun | None
    idempotency_replayed: bool = False
    idempotency_scope: str | None = None
    idempotency_key_hash: str | None = None


REPORT_SEND_IDEMPOTENCY_SCOPE = "report_send"
REPORT_SUBSCRIPTION_RUN_IDEMPOTENCY_SCOPE = "report_subscription_run"
REPORT_SUBSCRIPTION_RETRY_IDEMPOTENCY_SCOPE = "report_subscription_retry"


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
) -> list[ReportSubscriptionWithLatestRun]:
    subscriptions = await list_report_subscriptions(session, workspace.id, user.id)
    latest_runs = await list_latest_report_subscription_runs(
        session,
        workspace.id,
        [subscription.id for subscription in subscriptions],
    )
    return [
        ReportSubscriptionWithLatestRun(
            subscription=subscription,
            latest_run=latest_runs.get(subscription.id),
        )
        for subscription in subscriptions
    ]


async def upsert_report_subscription(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    payload: ReportSubscriptionUpsertRequest,
) -> ReportSubscriptionWithLatestRun:
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
    latest_runs = await list_latest_report_subscription_runs(
        session,
        workspace.id,
        [subscription.id],
    )
    return ReportSubscriptionWithLatestRun(
        subscription=subscription,
        latest_run=latest_runs.get(subscription.id),
    )


async def run_report_subscription_now(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    subscription_id: uuid.UUID,
    payload: ReportSubscriptionRunRequest,
    idempotency_key: str | None = None,
) -> ReportSubscriptionWithLatestRun:
    if not payload.authorized:
        raise ReportSubscriptionRunAuthorizationError
    if not payload.confirm_run:
        raise ReportSubscriptionRunConfirmationRequiredError

    subscription = await get_report_subscription(session, workspace.id, user.id, subscription_id)
    if subscription is None:
        raise ReportSubscriptionNotFoundError
    idempotency_key_hash = _report_subscription_execution_idempotency_key_hash(
        scope=REPORT_SUBSCRIPTION_RUN_IDEMPOTENCY_SCOPE,
        workspace=workspace,
        user=user,
        subscription=subscription,
        idempotency_key=idempotency_key,
    )
    if idempotency_key_hash is not None:
        existing_run = await _get_report_subscription_idempotency_run(
            session=session,
            workspace=workspace,
            subscription=subscription,
            scope=REPORT_SUBSCRIPTION_RUN_IDEMPOTENCY_SCOPE,
            idempotency_key_hash=idempotency_key_hash,
        )
        if existing_run is not None:
            return ReportSubscriptionWithLatestRun(
                subscription=subscription,
                latest_run=existing_run,
                idempotency_replayed=True,
                idempotency_scope=REPORT_SUBSCRIPTION_RUN_IDEMPOTENCY_SCOPE,
                idempotency_key_hash=idempotency_key_hash,
            )

    result = await execute_report_subscription(
        session=session,
        subscription=subscription,
        workspace=workspace,
        user=user,
        trigger_type="manual",
    )
    if idempotency_key_hash is not None and result.report is not None:
        await _record_report_subscription_idempotency_event(
            session=session,
            workspace=workspace,
            user=user,
            subscription=subscription,
            result=result,
            scope=REPORT_SUBSCRIPTION_RUN_IDEMPOTENCY_SCOPE,
            idempotency_key_hash=idempotency_key_hash,
        )
    return ReportSubscriptionWithLatestRun(
        subscription=subscription,
        latest_run=result.run,
        idempotency_scope=(
            REPORT_SUBSCRIPTION_RUN_IDEMPOTENCY_SCOPE
            if idempotency_key_hash is not None
            else None
        ),
        idempotency_key_hash=idempotency_key_hash,
    )


async def get_report_subscription_run_history(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    subscription_id: uuid.UUID,
    limit: int = 10,
) -> list[ReportSubscriptionRun]:
    subscription = await get_report_subscription(session, workspace.id, user.id, subscription_id)
    if subscription is None:
        raise ReportSubscriptionNotFoundError
    return await list_report_subscription_runs(
        session=session,
        workspace_id=workspace.id,
        subscription_id=subscription.id,
        limit=limit,
    )


async def retry_report_subscription_run(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    subscription_id: uuid.UUID,
    run_id: uuid.UUID,
    payload: ReportSubscriptionRetryRequest,
    idempotency_key: str | None = None,
) -> ReportSubscriptionWithLatestRun:
    if not payload.authorized:
        raise ReportSubscriptionRetryAuthorizationError
    if not payload.confirm_retry:
        raise ReportSubscriptionRetryConfirmationRequiredError

    subscription = await get_report_subscription(session, workspace.id, user.id, subscription_id)
    if subscription is None:
        raise ReportSubscriptionNotFoundError
    run = await get_report_subscription_run(session, workspace.id, subscription.id, run_id)
    if run is None:
        raise ReportSubscriptionRunNotFoundError
    idempotency_key_hash = _report_subscription_execution_idempotency_key_hash(
        scope=REPORT_SUBSCRIPTION_RETRY_IDEMPOTENCY_SCOPE,
        workspace=workspace,
        user=user,
        subscription=subscription,
        idempotency_key=idempotency_key,
        original_run_id=run.id,
    )
    if idempotency_key_hash is not None:
        existing_run = await _get_report_subscription_idempotency_run(
            session=session,
            workspace=workspace,
            subscription=subscription,
            scope=REPORT_SUBSCRIPTION_RETRY_IDEMPOTENCY_SCOPE,
            idempotency_key_hash=idempotency_key_hash,
        )
        if existing_run is not None:
            return ReportSubscriptionWithLatestRun(
                subscription=subscription,
                latest_run=existing_run,
                idempotency_replayed=True,
                idempotency_scope=REPORT_SUBSCRIPTION_RETRY_IDEMPOTENCY_SCOPE,
                idempotency_key_hash=idempotency_key_hash,
            )
    if not _can_retry_subscription_run(run.status):
        raise ReportSubscriptionRunRetryNotAllowedError
    if run.report_id is not None and run.skipped_channels:
        result = await retry_report_subscription_delivery(
            session=session,
            subscription=subscription,
            workspace=workspace,
            user=user,
            original_run=run,
        )
        if idempotency_key_hash is not None and result.report is not None:
            await _record_report_subscription_idempotency_event(
                session=session,
                workspace=workspace,
                user=user,
                subscription=subscription,
                result=result,
                scope=REPORT_SUBSCRIPTION_RETRY_IDEMPOTENCY_SCOPE,
                idempotency_key_hash=idempotency_key_hash,
                original_run_id=run.id,
            )
        return ReportSubscriptionWithLatestRun(
            subscription=subscription,
            latest_run=result.run,
            idempotency_scope=(
                REPORT_SUBSCRIPTION_RETRY_IDEMPOTENCY_SCOPE
                if idempotency_key_hash is not None
                else None
            ),
            idempotency_key_hash=idempotency_key_hash,
        )
    result = await execute_report_subscription(
        session=session,
        subscription=subscription,
        workspace=workspace,
        user=user,
        trigger_type="retry",
    )
    if idempotency_key_hash is not None and result.report is not None:
        await _record_report_subscription_idempotency_event(
            session=session,
            workspace=workspace,
            user=user,
            subscription=subscription,
            result=result,
            scope=REPORT_SUBSCRIPTION_RETRY_IDEMPOTENCY_SCOPE,
            idempotency_key_hash=idempotency_key_hash,
            original_run_id=run.id,
        )
    return ReportSubscriptionWithLatestRun(
        subscription=subscription,
        latest_run=result.run,
        idempotency_scope=(
            REPORT_SUBSCRIPTION_RETRY_IDEMPOTENCY_SCOPE
            if idempotency_key_hash is not None
            else None
        ),
        idempotency_key_hash=idempotency_key_hash,
    )


async def retry_report_subscription_delivery(
    session: AsyncSession,
    subscription: ReportSubscription,
    workspace: Workspace,
    user: User,
    original_run: ReportSubscriptionRun,
) -> ReportSubscriptionExecutionResult:
    if original_run.report_id is None:
        raise ReportNotFoundError
    report_id = original_run.report_id
    current_time = datetime.now(UTC)
    retry_channels = list(original_run.skipped_channels.keys()) or list(subscription.channels)
    run = await create_report_subscription_run(
        session,
        ReportSubscriptionRun(
            workspace_id=workspace.id,
            subscription_id=subscription.id,
            report_id=report_id,
            trigger_type="retry",
            status="running",
            delivered_channels=[],
            skipped_channels={},
            error_message=None,
            started_at=current_time,
            finished_at=None,
        ),
    )
    await session.commit()

    report: Report | None = None
    delivered_channels: list[str] = []
    skipped_channels: dict[str, str] = {}
    status = "failed"
    try:
        report_before_retry = await get_report_or_raise(session, workspace, report_id)
        previous_status = report_before_retry.status
        dispatch_result = await dispatch_report(
            session=session,
            workspace=workspace,
            user=user,
            report_id=report_id,
            channels=retry_channels,
        )
        delivered_channels = dispatch_result.delivered_channels
        skipped_channels = dispatch_result.skipped_channels
        report = dispatch_result.report
        status = _subscription_run_status(delivered_channels, skipped_channels)
        if delivered_channels:
            subscription.last_sent_at = current_time
        await _create_report_audit_event(
            session=session,
            workspace_id=workspace.id,
            report_id=report.id,
            actor_id=user.id,
            event_type="subscription_executed",
            from_status=previous_status,
            to_status=report.status,
            metadata={
                "delivered_channels": ",".join(delivered_channels),
                "retry_of_run_id": str(original_run.id),
                "skipped_channels": ",".join(skipped_channels.keys()),
                "subscription_id": str(subscription.id),
            },
        )
        run.error_message = _subscription_run_error_message(status, skipped_channels)
    except Exception as exc:
        await session.rollback()
        session.add(run)
        session.add(subscription)
        status = "failed"
        run.error_message = str(exc)[:500] or exc.__class__.__name__
    run.status = status
    run.delivered_channels = delivered_channels
    run.skipped_channels = skipped_channels
    run.finished_at = datetime.now(UTC)
    await _emit_email_delivery_failure_alert(
        session=session,
        user_id=user.id,
        run_id=run.id,
        skipped_channels=skipped_channels,
        delivered_channels=delivered_channels,
        operation="retry",
    )
    subscription.next_run_at = _compute_next_run_at(
        subscription.schedule_time,
        subscription.timezone,
        current_time,
    )
    subscription.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(subscription)
    await session.refresh(run)
    if report is not None:
        await session.refresh(report)
    return ReportSubscriptionExecutionResult(
        report=report,
        run=run,
        status=status,
        delivered_channels=delivered_channels,
        skipped_channels=skipped_channels,
    )


async def execute_report_subscription(
    session: AsyncSession,
    subscription: ReportSubscription,
    workspace: Workspace,
    user: User,
    now: datetime | None = None,
    trigger_type: str = "scheduled",
) -> ReportSubscriptionExecutionResult:
    current_time = _aware(now or datetime.now(UTC))
    run = await create_report_subscription_run(
        session,
        ReportSubscriptionRun(
            workspace_id=workspace.id,
            subscription_id=subscription.id,
            report_id=None,
            trigger_type=trigger_type,
            status="running",
            delivered_channels=[],
            skipped_channels={},
            error_message=None,
            started_at=current_time,
            finished_at=None,
        ),
    )
    await session.commit()

    period_start = _subscription_execution_period_start(subscription, current_time)
    report: Report | None = None
    delivered_channels: list[str] = []
    skipped_channels: dict[str, str] = {}
    status = "failed"
    try:
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
        delivered_channels = dispatch_result.delivered_channels
        skipped_channels = dispatch_result.skipped_channels
        report = dispatch_result.report
        status = _subscription_run_status(delivered_channels, skipped_channels)
        if delivered_channels:
            subscription.last_sent_at = current_time
        await _create_report_audit_event(
            session=session,
            workspace_id=workspace.id,
            report_id=report.id,
            actor_id=user.id,
            event_type="subscription_executed",
            from_status=generated_status,
            to_status=report.status,
            metadata={
                "delivered_channels": ",".join(delivered_channels),
                "skipped_channels": ",".join(skipped_channels.keys()),
                "subscription_id": str(subscription.id),
            },
        )
        run.report_id = report.id
        run.error_message = _subscription_run_error_message(status, skipped_channels)
    except Exception as exc:
        await session.rollback()
        session.add(run)
        session.add(subscription)
        status = "failed"
        run.error_message = str(exc)[:500] or exc.__class__.__name__
    run.status = status
    run.delivered_channels = delivered_channels
    run.skipped_channels = skipped_channels
    run.finished_at = datetime.now(UTC)
    await _emit_email_delivery_failure_alert(
        session=session,
        user_id=user.id,
        run_id=run.id,
        skipped_channels=skipped_channels,
        delivered_channels=delivered_channels,
        operation=trigger_type,
    )
    subscription.next_run_at = _compute_next_run_at(
        subscription.schedule_time,
        subscription.timezone,
        current_time,
    )
    subscription.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(subscription)
    await session.refresh(run)
    if report is not None:
        await session.refresh(report)
    return ReportSubscriptionExecutionResult(
        report=report,
        run=run,
        status=status,
        delivered_channels=delivered_channels,
        skipped_channels=skipped_channels,
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
) -> ReportSendResult:
    payload = ReportSendRequest(authorized=True, confirm_send=True, channels=["in_app"])
    return await send_report_with_payload(
        session=session,
        workspace=workspace,
        user=user,
        report_id=report_id,
        payload=payload,
        idempotency_key=None,
    )


async def send_report_with_payload(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    report_id: uuid.UUID,
    payload: ReportSendRequest,
    idempotency_key: str | None = None,
) -> ReportSendResult:
    if not payload.authorized:
        raise ReportSendAuthorizationError
    if not payload.confirm_send:
        raise ReportSendConfirmationRequiredError

    report = await get_report_or_raise(session, workspace, report_id)
    idempotency_key_hash = _report_send_idempotency_key_hash(
        workspace_id=workspace.id,
        report_id=report_id,
        channels=payload.channels,
        idempotency_key=idempotency_key,
    )
    if idempotency_key_hash is not None:
        existing_event = await _get_report_send_idempotency_event(
            session=session,
            workspace=workspace,
            report_id=report_id,
            idempotency_key_hash=idempotency_key_hash,
        )
        if existing_event is not None:
            metadata = _report_audit_event_metadata(existing_event)
            return ReportSendResult(
                report=report,
                delivered_channels=_split_metadata_list(metadata.get("delivered_channels")),
                skipped_channels=_metadata_skipped_channels(metadata),
                idempotency_replayed=True,
                idempotency_key_hash=idempotency_key_hash,
            )

    dispatch_result = await dispatch_report(
        session=session,
        workspace=workspace,
        user=user,
        report_id=report_id,
        channels=payload.channels,
    )
    if idempotency_key_hash is not None:
        await _create_report_audit_event(
            session=session,
            workspace_id=workspace.id,
            report_id=dispatch_result.report.id,
            actor_id=user.id,
            event_type="idempotency_key_recorded",
            from_status=dispatch_result.report.status,
            to_status=dispatch_result.report.status,
            metadata={
                "scope": REPORT_SEND_IDEMPOTENCY_SCOPE,
                "idempotency_key_hash": idempotency_key_hash,
                "raw_key_stored": "false",
                "delivered_channels": ",".join(dispatch_result.delivered_channels),
                "skipped_channels": ",".join(
                    f"{channel}:{reason}"
                    for channel, reason in sorted(dispatch_result.skipped_channels.items())
                ),
            },
        )
        await session.commit()
        await session.refresh(dispatch_result.report)
    return ReportSendResult(
        report=dispatch_result.report,
        delivered_channels=dispatch_result.delivered_channels,
        skipped_channels=dispatch_result.skipped_channels,
        idempotency_replayed=False,
        idempotency_key_hash=idempotency_key_hash,
    )


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


async def _record_report_subscription_idempotency_event(
    *,
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    subscription: ReportSubscription,
    result: ReportSubscriptionExecutionResult,
    scope: str,
    idempotency_key_hash: str,
    original_run_id: uuid.UUID | None = None,
) -> None:
    if result.report is None:
        return
    metadata = {
        "scope": scope,
        "idempotency_key_hash": idempotency_key_hash,
        "raw_key_stored": "false",
        "subscription_id": str(subscription.id),
        "run_id": str(result.run.id),
        "trigger_type": result.run.trigger_type,
        "delivered_channels": ",".join(result.delivered_channels),
        "skipped_channels": ",".join(
            f"{channel}:{reason}" for channel, reason in sorted(result.skipped_channels.items())
        ),
    }
    if original_run_id is not None:
        metadata["retry_of_run_id"] = str(original_run_id)
    await _create_report_audit_event(
        session=session,
        workspace_id=workspace.id,
        report_id=result.report.id,
        actor_id=user.id,
        event_type="idempotency_key_recorded",
        from_status=result.report.status,
        to_status=result.report.status,
        metadata=metadata,
    )
    await session.commit()
    await session.refresh(result.run)
    await session.refresh(result.report)


async def _get_report_subscription_idempotency_run(
    *,
    session: AsyncSession,
    workspace: Workspace,
    subscription: ReportSubscription,
    scope: str,
    idempotency_key_hash: str,
) -> ReportSubscriptionRun | None:
    runs = await list_report_subscription_runs(
        session=session,
        workspace_id=workspace.id,
        subscription_id=subscription.id,
        limit=100,
    )
    for run in runs:
        if run.report_id is None:
            continue
        events = await list_report_audit_events(session, workspace.id, run.report_id)
        for event in events:
            metadata = _report_audit_event_metadata(event)
            if event.event_type != "idempotency_key_recorded":
                continue
            if metadata.get("scope") != scope:
                continue
            if metadata.get("idempotency_key_hash") != idempotency_key_hash:
                continue
            if metadata.get("subscription_id") != str(subscription.id):
                continue
            if metadata.get("run_id") != str(run.id):
                continue
            return run
    return None


async def _get_report_send_idempotency_event(
    *,
    session: AsyncSession,
    workspace: Workspace,
    report_id: uuid.UUID,
    idempotency_key_hash: str,
) -> ReportAuditEvent | None:
    events = await list_report_audit_events(session, workspace.id, report_id)
    for event in events:
        metadata = _report_audit_event_metadata(event)
        if event.event_type != "idempotency_key_recorded":
            continue
        if metadata.get("scope") != REPORT_SEND_IDEMPOTENCY_SCOPE:
            continue
        if metadata.get("idempotency_key_hash") == idempotency_key_hash:
            return event
    return None


def _report_subscription_execution_idempotency_key_hash(
    *,
    scope: str,
    workspace: Workspace,
    user: User,
    subscription: ReportSubscription,
    idempotency_key: str | None,
    original_run_id: uuid.UUID | None = None,
) -> str | None:
    if idempotency_key is None:
        return None
    normalized_key = idempotency_key.strip()
    if not normalized_key:
        return None
    return _stable_json_hash(
        {
            "scope": scope,
            "workspace_id": str(workspace.id),
            "user_id": str(user.id),
            "subscription_id": str(subscription.id),
            "project_id": (
                str(subscription.project_id) if subscription.project_id is not None else None
            ),
            "report_type": subscription.report_type,
            "channels": list(subscription.channels),
            "original_run_id": str(original_run_id) if original_run_id is not None else None,
            "idempotency_key": normalized_key,
        }
    )


def _report_send_idempotency_key_hash(
    *,
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
    channels: Sequence[str],
    idempotency_key: str | None,
) -> str | None:
    if idempotency_key is None:
        return None
    normalized_key = idempotency_key.strip()
    if not normalized_key:
        return None
    return _stable_json_hash(
        {
            "scope": REPORT_SEND_IDEMPOTENCY_SCOPE,
            "workspace_id": str(workspace_id),
            "report_id": str(report_id),
            "channels": list(dict.fromkeys(channels)),
            "idempotency_key": normalized_key,
        }
    )


def _report_audit_event_metadata(event: ReportAuditEvent) -> dict[str, str]:
    if not event.metadata_json:
        return {}
    parsed = json.loads(event.metadata_json)
    return {str(key): str(value) for key, value in parsed.items()}


def _split_metadata_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item for item in value.split(",") if item]


def _metadata_skipped_channels(metadata: dict[str, str]) -> dict[str, str]:
    skipped: dict[str, str] = {}
    for item in _split_metadata_list(metadata.get("skipped_channels")):
        channel, _, reason = item.partition(":")
        if channel:
            skipped[channel] = reason
    return skipped


def _stable_json_hash(value: dict[str, object]) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


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


def _subscription_execution_period_start(
    subscription: ReportSubscription,
    current_time: datetime,
) -> datetime:
    if subscription.last_sent_at is not None:
        last_sent_at = _aware(subscription.last_sent_at)
        if last_sent_at < current_time:
            return last_sent_at
    return _subscription_period_start(subscription, current_time)


def _subscription_run_status(
    delivered_channels: list[str],
    skipped_channels: dict[str, str],
) -> str:
    if delivered_channels and skipped_channels:
        return "partial_success"
    if delivered_channels:
        return "success"
    return "failed"


def _subscription_run_error_message(status: str, skipped_channels: dict[str, str]) -> str | None:
    if status == "success":
        return None
    if not skipped_channels:
        return "No delivery channel completed."
    return "; ".join(
        f"{channel}: {reason}" for channel, reason in sorted(skipped_channels.items())
    )


async def _emit_email_delivery_failure_alert(
    session: AsyncSession,
    user_id: uuid.UUID,
    run_id: uuid.UUID,
    skipped_channels: dict[str, str],
    delivered_channels: list[str],
    operation: str,
) -> None:
    email_reason = skipped_channels.get("email")
    if email_reason is None:
        return

    if delivered_channels:
        title = "报告邮件发送部分失败"
        details = (
            "报告已完成部分投递，邮件通道未送达，"
            "请修复邮件配置后重试。"
        )
    else:
        title = "报告邮件发送失败"
        details = (
            "报告发送失败，未能通过邮件通道送达，"
            "请修复邮件配置后重试。"
        )

    await create_in_app_notification(
        session=session,
        user_id=user_id,
        title=title,
        body=f"[{operation}] {details}（原因：{email_reason}）",
        notification_type="task_failed",
        reference_type="task_run",
        reference_id=run_id,
    )


def _can_retry_subscription_run(status: str) -> bool:
    return status in {"failed", "partial_success"}


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
