from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.core.security import hash_password
from data_intelligence_hub.models.alert import AlertEvent, AlertRule
from data_intelligence_hub.models.entity import Entity, EntitySnapshot
from data_intelligence_hub.models.intelligence import (
    Evidence,
    IntelligenceFeedback,
    IntelligenceItem,
)
from data_intelligence_hub.models.notification import Notification
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.report import (
    Report,
    ReportAuditEvent,
    ReportSubscription,
    ReportSubscriptionRun,
)
from data_intelligence_hub.models.signal import Signal
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember

NAMESPACE = uuid.UUID("2df8a496-5ea6-49c3-8aef-9604ac8e6238")
DEFAULT_EMAIL = "owner@example.com"
DEMO_SEED_VERSION = "2026-06-14-curated-v2"

DOMAIN_FRESHNESS_TARGETS: dict[str, dict[str, Any]] = {
    "osint": {
        "label": "开源雷达",
        "collector_type": "github_repo",
        "target_hours": 6,
        "platforms": ["GitHub"],
    },
    "ecommerce": {
        "label": "电商风向",
        "collector_type": "manual_json",
        "target_hours": 12,
        "platforms": ["Amazon", "Keepa", "Shopify Storefront"],
    },
    "social": {
        "label": "社媒脉搏",
        "collector_type": "manual_json",
        "target_hours": 6,
        "platforms": ["TikTok Creative Center", "Reddit", "YouTube"],
    },
    "competitor": {
        "label": "竞品守望",
        "collector_type": "generic_web",
        "target_hours": 24,
        "platforms": ["Public competitor sites"],
    },
}


@dataclass(frozen=True)
class DemoContext:
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    project_ids: dict[str, uuid.UUID]
    source_ids: dict[str, uuid.UUID]
    task_ids: dict[str, uuid.UUID]
    run_ids: dict[str, uuid.UUID]
    raw_record_ids: dict[str, uuid.UUID]
    entity_ids: dict[str, uuid.UUID]
    snapshot_ids: dict[str, uuid.UUID]
    signal_ids: dict[str, uuid.UUID]
    intelligence_ids: dict[str, uuid.UUID]
    alert_rule_ids: dict[str, uuid.UUID]


@dataclass(frozen=True)
class DemoCleanupReport:
    dry_run: bool
    workspace_id: uuid.UUID | None
    counts: dict[str, int]
    samples: dict[str, list[str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "workspace_id": str(self.workspace_id) if self.workspace_id is not None else None,
            "counts": self.counts,
            "samples": self.samples,
        }


def _id(key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"data-achieve-demo:{key}")


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _provenance(layer: str, domain: str | None = None) -> dict[str, str]:
    value = {
        "data_layer": layer,
        "dataset": "curated_demo",
        "seed_version": DEMO_SEED_VERSION,
        "source": "data_intelligence_hub.seed.demo_data",
    }
    if domain is not None:
        value["domain"] = domain
    return value


async def _merge_all(session: AsyncSession, items: list[Any]) -> None:
    for item in items:
        await session.merge(item)
    await session.flush()


def _demo_password() -> str:
    password = os.getenv("SCRAPY_DEMO_PASSWORD")
    if password is None or len(password) < 8:
        raise RuntimeError("SCRAPY_DEMO_PASSWORD must be set to at least 8 characters")
    return password


def _build_context() -> DemoContext:
    return DemoContext(
        user_id=_id("user-owner"),
        workspace_id=_id("workspace-main"),
        project_ids={
            "osint": _id("project-osint"),
            "ecommerce": _id("project-ecommerce"),
            "social": _id("project-social"),
            "competitor": _id("project-competitor"),
        },
        source_ids={
            "osint": _id("source-osint"),
            "amazon": _id("source-amazon"),
            "social": _id("source-social"),
            "competitor": _id("source-competitor"),
        },
        task_ids={
            "osint": _id("task-osint"),
            "amazon": _id("task-amazon"),
            "social": _id("task-social"),
            "competitor": _id("task-competitor"),
        },
        run_ids={
            "osint-success": _id("run-osint-success"),
            "amazon-success": _id("run-amazon-success"),
            "social-success": _id("run-social-success"),
            "competitor-success": _id("run-competitor-success"),
            "competitor-failed": _id("run-competitor-failed"),
        },
        raw_record_ids={
            "osint-prev": _id("raw-osint-prev"),
            "osint-current": _id("raw-osint-current"),
            "amazon-prev": _id("raw-amazon-prev"),
            "amazon-current": _id("raw-amazon-current"),
            "social-prev": _id("raw-social-prev"),
            "social-current": _id("raw-social-current"),
            "competitor-prev": _id("raw-competitor-prev"),
            "competitor-current": _id("raw-competitor-current"),
        },
        entity_ids={
            "osint-repo": _id("entity-osint-repo"),
            "amazon-product": _id("entity-amazon-product"),
            "social-topic": _id("entity-social-topic"),
            "competitor-page": _id("entity-competitor-page"),
        },
        snapshot_ids={
            "osint-prev": _id("snapshot-osint-prev"),
            "osint-current": _id("snapshot-osint-current"),
            "amazon-prev": _id("snapshot-amazon-prev"),
            "amazon-current": _id("snapshot-amazon-current"),
            "social-prev": _id("snapshot-social-prev"),
            "social-current": _id("snapshot-social-current"),
            "competitor-prev": _id("snapshot-competitor-prev"),
            "competitor-current": _id("snapshot-competitor-current"),
        },
        signal_ids={
            "osint-stars-surge": _id("signal-osint-stars-surge"),
            "amazon-price-drop": _id("signal-amazon-price-drop"),
            "social-mentions-spike": _id("signal-social-mentions-spike"),
            "competitor-page-change": _id("signal-competitor-page-change"),
        },
        intelligence_ids={
            "osint-scrapy-momentum": _id("intel-osint-scrapy-momentum"),
            "amazon-margin-risk": _id("intel-amazon-margin-risk"),
            "social-method-window": _id("intel-social-method-window"),
            "competitor-landing-shift": _id("intel-competitor-landing-shift"),
        },
        alert_rule_ids={
            "price": _id("alert-rule-price"),
            "traffic": _id("alert-rule-traffic"),
            "competitor": _id("alert-rule-competitor"),
        },
    )


async def seed_demo_data() -> None:
    password = _demo_password()
    email = os.getenv("SCRAPY_DEMO_EMAIL", DEFAULT_EMAIL)
    name = os.getenv("SCRAPY_DEMO_NAME", "Data Achieve Owner")
    context = _build_context()
    now = _now()

    async with async_session_factory() as session:
        await _delete_legacy_demo_records(session)
        await cleanup_demo_noise(session, dry_run=False)
        await _merge_identity(session, context, email, password, name, now)
        await _merge_projects(session, context, now)
        await _merge_collection_layer(session, context, now)
        await _merge_entity_layer(session, context, now)
        await _merge_intelligence_layer(session, context, now)
        await _merge_reports_alerts_notifications(session, context, now)
        await session.commit()

    print(f"Seeded demo workspace for {email}")


async def _delete_legacy_demo_records(session: AsyncSession) -> None:
    legacy_project_ids = [_id("project-content"), _id("project-technology")]
    legacy_source_ids = _unique_ids(
        [_id("source-tiktok"), _id("source-github")]
        + await _fetch_ids(
            session, select(Source.id).where(Source.project_id.in_(legacy_project_ids))
        )
    )
    legacy_task_ids = _unique_ids(
        [_id("task-tiktok"), _id("task-github")]
        + await _fetch_ids(
            session,
            select(CollectionTask.id).where(
                or_(
                    CollectionTask.project_id.in_(legacy_project_ids),
                    CollectionTask.source_id.in_(legacy_source_ids),
                )
            ),
        )
    )
    legacy_run_ids = [
        _id("run-tiktok-success"),
        _id("run-github-failed"),
    ] + await _fetch_ids(session, select(TaskRun.id).where(TaskRun.task_id.in_(legacy_task_ids)))
    legacy_raw_record_ids = [
        _id("raw-tiktok-prev"),
        _id("raw-tiktok-current"),
        _id("raw-github-prev"),
        _id("raw-github-current"),
    ] + await _fetch_ids(
        session,
        select(RawRecord.id).where(
            or_(
                RawRecord.project_id.in_(legacy_project_ids),
                RawRecord.source_id.in_(legacy_source_ids),
                RawRecord.task_run_id.in_(legacy_run_ids),
            )
        ),
    )
    legacy_entity_ids = [
        _id("entity-tiktok-creator"),
        _id("entity-github-repo"),
    ] + await _fetch_ids(
        session, select(Entity.id).where(Entity.project_id.in_(legacy_project_ids))
    )
    legacy_snapshot_ids = [
        _id("snapshot-tiktok-prev"),
        _id("snapshot-tiktok-current"),
        _id("snapshot-github-prev"),
        _id("snapshot-github-current"),
    ] + await _fetch_ids(
        session,
        select(EntitySnapshot.id).where(
            or_(
                EntitySnapshot.entity_id.in_(legacy_entity_ids),
                EntitySnapshot.raw_record_id.in_(legacy_raw_record_ids),
            )
        ),
    )
    legacy_signal_ids = [
        _id("signal-tiktok-views-spike"),
        _id("signal-github-stars-surge"),
    ] + await _fetch_ids(
        session,
        select(Signal.id).where(
            or_(
                Signal.project_id.in_(legacy_project_ids),
                Signal.entity_id.in_(legacy_entity_ids),
                Signal.previous_snapshot_id.in_(legacy_snapshot_ids),
                Signal.current_snapshot_id.in_(legacy_snapshot_ids),
            )
        ),
    )
    legacy_intelligence_ids = [
        _id("intel-tiktok-demand-window"),
        _id("intel-github-open-source-momentum"),
    ] + await _fetch_ids(
        session,
        select(IntelligenceItem.id).where(IntelligenceItem.project_id.in_(legacy_project_ids)),
    )

    legacy_run_ids = _unique_ids(legacy_run_ids)
    legacy_raw_record_ids = _unique_ids(legacy_raw_record_ids)
    legacy_entity_ids = _unique_ids(legacy_entity_ids)
    legacy_snapshot_ids = _unique_ids(legacy_snapshot_ids)
    legacy_signal_ids = _unique_ids(legacy_signal_ids)
    legacy_intelligence_ids = _unique_ids(legacy_intelligence_ids)

    await session.execute(
        update(Entity)
        .where(Entity.latest_snapshot_id.in_(legacy_snapshot_ids))
        .values(latest_snapshot_id=None)
    )
    await session.execute(
        update(AlertRule)
        .where(AlertRule.project_id.in_(legacy_project_ids))
        .values(project_id=None)
    )
    await session.execute(
        update(Report).where(Report.project_id.in_(legacy_project_ids)).values(project_id=None)
    )
    await session.execute(
        update(ReportSubscription)
        .where(ReportSubscription.project_id.in_(legacy_project_ids))
        .values(project_id=None)
    )
    await session.flush()

    await session.execute(
        delete(Notification).where(Notification.id.in_([_id("notification-task-failed")]))
    )
    await session.execute(
        delete(AlertEvent).where(
            or_(
                AlertEvent.id.in_([_id("alert-event-traffic")]),
                AlertEvent.signal_id.in_(legacy_signal_ids),
            )
        )
    )
    await session.execute(
        delete(IntelligenceFeedback).where(
            IntelligenceFeedback.intelligence_id.in_(legacy_intelligence_ids)
        )
    )
    await session.execute(
        delete(Evidence).where(
            or_(
                Evidence.id.in_([_id("evidence-tiktok-views"), _id("evidence-github-stars")]),
                Evidence.intelligence_id.in_(legacy_intelligence_ids),
                Evidence.signal_id.in_(legacy_signal_ids),
                Evidence.entity_id.in_(legacy_entity_ids),
                Evidence.raw_record_id.in_(legacy_raw_record_ids),
            )
        )
    )
    await session.execute(
        delete(IntelligenceItem).where(IntelligenceItem.id.in_(legacy_intelligence_ids))
    )
    await session.execute(delete(Signal).where(Signal.id.in_(legacy_signal_ids)))
    await session.execute(delete(EntitySnapshot).where(EntitySnapshot.id.in_(legacy_snapshot_ids)))
    await session.execute(delete(RawRecord).where(RawRecord.id.in_(legacy_raw_record_ids)))
    await session.execute(delete(Entity).where(Entity.id.in_(legacy_entity_ids)))
    await session.execute(delete(TaskRun).where(TaskRun.id.in_(legacy_run_ids)))
    await session.execute(delete(CollectionTask).where(CollectionTask.id.in_(legacy_task_ids)))
    await session.execute(delete(Source).where(Source.id.in_(legacy_source_ids)))
    await session.execute(delete(Project).where(Project.id.in_(legacy_project_ids)))
    await session.flush()


async def cleanup_demo_noise(session: AsyncSession, dry_run: bool = True) -> DemoCleanupReport:
    context = _build_context()
    workspace = await session.get(Workspace, context.workspace_id)
    if workspace is None:
        return DemoCleanupReport(dry_run=dry_run, workspace_id=None, counts={}, samples={})

    curated = _curated_demo_ids(context)
    workspace_id = context.workspace_id

    noise_project_ids = await _fetch_ids(
        session,
        select(Project.id).where(
            Project.workspace_id == workspace_id,
            ~Project.id.in_(curated["projects"]),
        ),
    )
    noise_source_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Source.id).where(
                Source.workspace_id == workspace_id,
                or_(
                    ~Source.id.in_(curated["sources"]),
                    Source.project_id.in_(noise_project_ids),
                ),
            ),
        )
    )
    noise_task_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(CollectionTask.id).where(
                CollectionTask.workspace_id == workspace_id,
                or_(
                    ~CollectionTask.id.in_(curated["tasks"]),
                    CollectionTask.project_id.in_(noise_project_ids),
                    CollectionTask.source_id.in_(noise_source_ids),
                ),
            ),
        )
    )
    noise_run_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(TaskRun.id).where(
                TaskRun.workspace_id == workspace_id,
                or_(
                    ~TaskRun.id.in_(curated["task_runs"]),
                    TaskRun.task_id.in_(noise_task_ids),
                ),
            ),
        )
    )
    noise_raw_record_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(RawRecord.id).where(
                RawRecord.workspace_id == workspace_id,
                or_(
                    ~RawRecord.id.in_(curated["raw_records"]),
                    RawRecord.project_id.in_(noise_project_ids),
                    RawRecord.source_id.in_(noise_source_ids),
                    RawRecord.task_run_id.in_(noise_run_ids),
                ),
            ),
        )
    )
    noise_entity_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Entity.id).where(
                Entity.workspace_id == workspace_id,
                or_(
                    ~Entity.id.in_(curated["entities"]),
                    Entity.project_id.in_(noise_project_ids),
                ),
            ),
        )
    )
    noise_snapshot_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(EntitySnapshot.id)
            .join(Entity, EntitySnapshot.entity_id == Entity.id)
            .where(
                Entity.workspace_id == workspace_id,
                or_(
                    ~EntitySnapshot.id.in_(curated["snapshots"]),
                    EntitySnapshot.entity_id.in_(noise_entity_ids),
                    EntitySnapshot.raw_record_id.in_(noise_raw_record_ids),
                ),
            ),
        )
    )
    noise_signal_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Signal.id).where(
                Signal.workspace_id == workspace_id,
                or_(
                    ~Signal.id.in_(curated["signals"]),
                    Signal.project_id.in_(noise_project_ids),
                    Signal.entity_id.in_(noise_entity_ids),
                    Signal.previous_snapshot_id.in_(noise_snapshot_ids),
                    Signal.current_snapshot_id.in_(noise_snapshot_ids),
                ),
            ),
        )
    )
    noise_intelligence_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(IntelligenceItem.id).where(
                IntelligenceItem.workspace_id == workspace_id,
                or_(
                    ~IntelligenceItem.id.in_(curated["intelligence"]),
                    IntelligenceItem.project_id.in_(noise_project_ids),
                ),
            ),
        )
    )
    noise_evidence_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Evidence.id)
            .join(IntelligenceItem, Evidence.intelligence_id == IntelligenceItem.id)
            .where(
                IntelligenceItem.workspace_id == workspace_id,
                or_(
                    ~Evidence.id.in_(curated["evidence"]),
                    Evidence.intelligence_id.in_(noise_intelligence_ids),
                    Evidence.signal_id.in_(noise_signal_ids),
                    Evidence.entity_id.in_(noise_entity_ids),
                    Evidence.raw_record_id.in_(noise_raw_record_ids),
                ),
            ),
        )
    )
    noise_report_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Report.id).where(
                Report.workspace_id == workspace_id,
                or_(
                    ~Report.id.in_(curated["reports"]),
                    Report.project_id.in_(noise_project_ids),
                ),
            ),
        )
    )
    noise_report_subscription_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(ReportSubscription.id).where(ReportSubscription.workspace_id == workspace_id),
        )
    )
    noise_report_subscription_run_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(ReportSubscriptionRun.id).where(
                ReportSubscriptionRun.workspace_id == workspace_id,
            ),
        )
    )
    noise_report_audit_event_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(ReportAuditEvent.id).where(
                ReportAuditEvent.workspace_id == workspace_id,
                ReportAuditEvent.report_id.in_(noise_report_ids),
            ),
        )
    )
    noise_alert_rule_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(AlertRule.id).where(
                AlertRule.workspace_id == workspace_id,
                or_(
                    ~AlertRule.id.in_(curated["alert_rules"]),
                    AlertRule.project_id.in_(noise_project_ids),
                ),
            ),
        )
    )
    noise_alert_event_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(AlertEvent.id)
            .join(AlertRule, AlertEvent.rule_id == AlertRule.id)
            .where(
                AlertRule.workspace_id == workspace_id,
                or_(
                    ~AlertEvent.id.in_(curated["alert_events"]),
                    AlertEvent.rule_id.in_(noise_alert_rule_ids),
                    AlertEvent.signal_id.in_(noise_signal_ids),
                ),
            ),
        )
    )
    noise_notification_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Notification.id).where(
                Notification.user_id == context.user_id,
                ~Notification.id.in_(curated["notifications"]),
            ),
        )
    )

    counts = {
        "projects": len(noise_project_ids),
        "sources": len(noise_source_ids),
        "collection_tasks": len(noise_task_ids),
        "task_runs": len(noise_run_ids),
        "raw_records": len(noise_raw_record_ids),
        "entities": len(noise_entity_ids),
        "entity_snapshots": len(noise_snapshot_ids),
        "signals": len(noise_signal_ids),
        "intelligence_items": len(noise_intelligence_ids),
        "evidences": len(noise_evidence_ids),
        "reports": len(noise_report_ids),
        "report_subscriptions": len(noise_report_subscription_ids),
        "report_subscription_runs": len(noise_report_subscription_run_ids),
        "report_audit_events": len(noise_report_audit_event_ids),
        "alert_rules": len(noise_alert_rule_ids),
        "alert_events": len(noise_alert_event_ids),
        "notifications": len(noise_notification_ids),
    }
    samples = {
        "intelligence_items": await _fetch_strings(
            session,
            select(IntelligenceItem.title)
            .where(IntelligenceItem.id.in_(noise_intelligence_ids))
            .order_by(IntelligenceItem.final_score.desc(), IntelligenceItem.created_at.desc())
            .limit(10),
        ),
        "reports": await _fetch_strings(
            session,
            select(Report.title)
            .where(Report.id.in_(noise_report_ids))
            .order_by(Report.created_at.desc())
            .limit(10),
        ),
    }
    report = DemoCleanupReport(
        dry_run=dry_run,
        workspace_id=workspace_id,
        counts=counts,
        samples=samples,
    )
    if dry_run:
        return report

    await _apply_demo_noise_cleanup(
        session=session,
        context=context,
        noise_project_ids=noise_project_ids,
        noise_source_ids=noise_source_ids,
        noise_task_ids=noise_task_ids,
        noise_run_ids=noise_run_ids,
        noise_raw_record_ids=noise_raw_record_ids,
        noise_entity_ids=noise_entity_ids,
        noise_snapshot_ids=noise_snapshot_ids,
        noise_signal_ids=noise_signal_ids,
        noise_intelligence_ids=noise_intelligence_ids,
        noise_evidence_ids=noise_evidence_ids,
        noise_report_ids=noise_report_ids,
        noise_report_subscription_ids=noise_report_subscription_ids,
        noise_report_subscription_run_ids=noise_report_subscription_run_ids,
        noise_report_audit_event_ids=noise_report_audit_event_ids,
        noise_alert_rule_ids=noise_alert_rule_ids,
        noise_alert_event_ids=noise_alert_event_ids,
        noise_notification_ids=noise_notification_ids,
    )
    return report


async def _apply_demo_noise_cleanup(
    *,
    session: AsyncSession,
    context: DemoContext,
    noise_project_ids: list[uuid.UUID],
    noise_source_ids: list[uuid.UUID],
    noise_task_ids: list[uuid.UUID],
    noise_run_ids: list[uuid.UUID],
    noise_raw_record_ids: list[uuid.UUID],
    noise_entity_ids: list[uuid.UUID],
    noise_snapshot_ids: list[uuid.UUID],
    noise_signal_ids: list[uuid.UUID],
    noise_intelligence_ids: list[uuid.UUID],
    noise_evidence_ids: list[uuid.UUID],
    noise_report_ids: list[uuid.UUID],
    noise_report_subscription_ids: list[uuid.UUID],
    noise_report_subscription_run_ids: list[uuid.UUID],
    noise_report_audit_event_ids: list[uuid.UUID],
    noise_alert_rule_ids: list[uuid.UUID],
    noise_alert_event_ids: list[uuid.UUID],
    noise_notification_ids: list[uuid.UUID],
) -> None:
    if noise_snapshot_ids:
        await session.execute(
            update(Entity)
            .where(Entity.latest_snapshot_id.in_(noise_snapshot_ids))
            .values(latest_snapshot_id=None)
        )
    for entity_key, snapshot_key in {
        "osint-repo": "osint-current",
        "amazon-product": "amazon-current",
        "social-topic": "social-current",
        "competitor-page": "competitor-current",
    }.items():
        snapshot_id = context.snapshot_ids[snapshot_key]
        if await session.get(EntitySnapshot, snapshot_id) is not None:
            await session.execute(
                update(Entity)
                .where(Entity.id == context.entity_ids[entity_key])
                .values(latest_snapshot_id=snapshot_id)
            )
    await session.flush()

    await _delete_ids(session, Notification, noise_notification_ids)
    await _delete_ids(session, ReportSubscriptionRun, noise_report_subscription_run_ids)
    await _delete_ids(session, ReportAuditEvent, noise_report_audit_event_ids)
    await _delete_ids(session, AlertEvent, noise_alert_event_ids)
    if noise_intelligence_ids:
        await session.execute(
            delete(IntelligenceFeedback).where(
                IntelligenceFeedback.intelligence_id.in_(noise_intelligence_ids)
            )
        )
    await _delete_ids(session, Evidence, noise_evidence_ids)
    await _delete_ids(session, ReportSubscription, noise_report_subscription_ids)
    await _delete_ids(session, Report, noise_report_ids)
    await _delete_ids(session, IntelligenceItem, noise_intelligence_ids)
    await _delete_ids(session, Signal, noise_signal_ids)
    await _delete_ids(session, EntitySnapshot, noise_snapshot_ids)
    await _delete_ids(session, RawRecord, noise_raw_record_ids)
    await _delete_ids(session, Entity, noise_entity_ids)
    await _delete_ids(session, TaskRun, noise_run_ids)
    await _delete_ids(session, CollectionTask, noise_task_ids)
    await _delete_ids(session, Source, noise_source_ids)
    await _delete_ids(session, AlertRule, noise_alert_rule_ids)
    await _delete_ids(session, Project, noise_project_ids)
    await session.flush()


async def _delete_ids(session: AsyncSession, model: type[Any], ids: list[uuid.UUID]) -> None:
    if ids:
        await session.execute(delete(model).where(model.id.in_(ids)))


def _curated_demo_ids(context: DemoContext) -> dict[str, list[uuid.UUID]]:
    return {
        "projects": list(context.project_ids.values()),
        "sources": list(context.source_ids.values()),
        "tasks": list(context.task_ids.values()),
        "task_runs": list(context.run_ids.values()),
        "raw_records": list(context.raw_record_ids.values()),
        "entities": list(context.entity_ids.values()),
        "snapshots": list(context.snapshot_ids.values()),
        "signals": list(context.signal_ids.values()),
        "intelligence": list(context.intelligence_ids.values()),
        "evidence": [
            _id("evidence-osint-stars"),
            _id("evidence-amazon-price"),
            _id("evidence-social-mentions"),
            _id("evidence-competitor-page"),
        ],
        "reports": [_id("report-daily")],
        "alert_rules": list(context.alert_rule_ids.values()),
        "alert_events": [
            _id("alert-event-price"),
            _id("alert-event-traffic"),
            _id("alert-event-competitor"),
        ],
        "notifications": [
            _id("notification-report"),
            _id("notification-alert"),
            _id("notification-task-failed"),
            _id("notification-competitor-alert"),
        ],
    }


async def _fetch_ids(session: AsyncSession, statement: Any) -> list[uuid.UUID]:
    return list((await session.execute(statement)).scalars())


async def _fetch_strings(session: AsyncSession, statement: Any) -> list[str]:
    return [str(item) for item in (await session.execute(statement)).scalars()]


def _unique_ids(ids: list[uuid.UUID]) -> list[uuid.UUID]:
    return list(dict.fromkeys(ids))


async def _merge_identity(
    session: AsyncSession,
    context: DemoContext,
    email: str,
    password: str,
    name: str,
    now: datetime,
) -> None:
    await _merge_all(
        session,
        [
            User(
                id=context.user_id,
                email=email,
                password_hash=hash_password(password),
                name=name,
                status="active",
                created_at=now - timedelta(days=30),
                updated_at=now,
            ),
            Workspace(
                id=context.workspace_id,
                name="Data Achieve Intelligence Hub",
                slug="data-achieve-demo",
                owner_id=context.user_id,
                created_at=now - timedelta(days=30),
                updated_at=now,
            ),
            WorkspaceMember(
                id=_id("workspace-member-owner"),
                workspace_id=context.workspace_id,
                user_id=context.user_id,
                role="owner",
                created_at=now - timedelta(days=30),
                updated_at=now,
            ),
        ],
    )


async def _merge_projects(session: AsyncSession, context: DemoContext, now: datetime) -> None:
    await _merge_all(
        session,
        [
            Project(
                id=context.project_ids["osint"],
                workspace_id=context.workspace_id,
                name="开源采集工具雷达",
                description="追踪 GitHub 采集框架、自动化工具和社区增长信号。",
                domain="osint",
                status="active",
                owner_id=context.user_id,
                created_at=now - timedelta(days=21),
                updated_at=now,
            ),
            Project(
                id=context.project_ids["ecommerce"],
                workspace_id=context.workspace_id,
                name="电商采集方法库",
                description="跟踪 Amazon、Keepa 与独立站商品价格、排名、评论采集方法。",
                domain="ecommerce",
                status="active",
                owner_id=context.user_id,
                created_at=now - timedelta(days=20),
                updated_at=now,
            ),
            Project(
                id=context.project_ids["social"],
                workspace_id=context.workspace_id,
                name="社媒热点采集方法库",
                description="监控 TikTok Creative Center、Reddit 和 YouTube 趋势采集窗口。",
                domain="social",
                status="active",
                owner_id=context.user_id,
                created_at=now - timedelta(days=18),
                updated_at=now,
            ),
            Project(
                id=context.project_ids["competitor"],
                workspace_id=context.workspace_id,
                name="竞品网站采集哨兵",
                description="跟踪公开竞品页面、定价页和反爬说明的页面变化。",
                domain="competitor",
                status="active",
                owner_id=context.user_id,
                created_at=now - timedelta(days=16),
                updated_at=now,
            ),
        ],
    )


async def _merge_collection_layer(
    session: AsyncSession,
    context: DemoContext,
    now: datetime,
) -> None:
    source_items = [
        Source(
            id=context.source_ids["osint"],
            workspace_id=context.workspace_id,
            project_id=context.project_ids["osint"],
            name="GitHub Scrapy 仓库采集",
            type="github_repo",
            url="https://github.com/scrapy/scrapy",
            config={
                "owner": "scrapy",
                "repo": "scrapy",
                "freshness_target_hours": DOMAIN_FRESHNESS_TARGETS["osint"]["target_hours"],
                "provenance": _provenance("source", "osint"),
                "schedule_policy": "auto_freshness",
                "method": {
                    "platform": "GitHub REST API",
                    "fields": ["stargazers_count", "forks_count", "open_issues_count", "pushed_at"],
                    "use_case": "开源采集框架社区动量监控",
                },
            },
            schedule_cron=None,
            enabled=True,
            created_at=now - timedelta(days=14),
            updated_at=now,
        ),
        Source(
            id=context.source_ids["amazon"],
            workspace_id=context.workspace_id,
            project_id=context.project_ids["ecommerce"],
            name="Amazon BSR 与 Keepa 价格雷达",
            type="manual_json",
            url="https://www.amazon.com/Best-Sellers/zgbs",
            config={
                "entity_type": "product_method",
                "provenance": _provenance("source", "ecommerce"),
                "schedule_policy": "auto_freshness",
                "json_data": {
                    "id": "amazon-bsr-keepa-air-filter",
                    "title": "Amazon BSR + Keepa 价格排名雷达",
                    "url": "https://www.amazon.com/Best-Sellers/zgbs",
                    "price": 39.9,
                    "rank": 6,
                    "review_count": 1840,
                    "method_quality": 91,
                    "freshness_target_hours": DOMAIN_FRESHNESS_TARGETS["ecommerce"]["target_hours"],
                    "collection_methods": [
                        "Amazon Best Sellers public page",
                        "Keepa price history API",
                    ],
                },
            },
            schedule_cron=None,
            enabled=True,
            created_at=now - timedelta(days=13),
            updated_at=now,
        ),
        Source(
            id=context.source_ids["social"],
            workspace_id=context.workspace_id,
            project_id=context.project_ids["social"],
            name="TikTok / Reddit 热点方法雷达",
            type="manual_json",
            url=None,
            config={
                "entity_type": "social_topic",
                "provenance": _provenance("source", "social"),
                "schedule_policy": "auto_freshness",
                "json_data": {
                    "id": "ai-scraping-methods-social",
                    "name": "AI 数据采集方法",
                    "url": "https://www.tiktok.com/business/creativecenter/",
                    "mentions_24h": 690000,
                    "engagement_rate": 0.093,
                    "method_quality": 86,
                    "freshness_target_hours": DOMAIN_FRESHNESS_TARGETS["social"]["target_hours"],
                    "collection_methods": [
                        "TikTok Creative Center trend discovery",
                        "Reddit API keyword monitoring",
                        "YouTube RSS topic watch",
                    ],
                },
            },
            schedule_cron=None,
            enabled=True,
            created_at=now - timedelta(days=12),
            updated_at=now,
        ),
        Source(
            id=context.source_ids["competitor"],
            workspace_id=context.workspace_id,
            project_id=context.project_ids["competitor"],
            name="ScrapingBee 公开页面快照",
            type="generic_web",
            url="https://www.scrapingbee.com/",
            config={
                "url": "https://www.scrapingbee.com/",
                "extract_mode": "main_content",
                "freshness_target_hours": DOMAIN_FRESHNESS_TARGETS["competitor"]["target_hours"],
                "provenance": _provenance("source", "competitor"),
                "schedule_policy": "auto_freshness",
                "method": {
                    "platform": "public web",
                    "fields": ["title", "text_content", "html_content"],
                    "use_case": "竞品定位、定价和反爬能力页面变化监控",
                },
            },
            schedule_cron=None,
            enabled=True,
            created_at=now - timedelta(days=11),
            updated_at=now,
        ),
    ]
    await _merge_all(session, source_items)

    task_items = [
        CollectionTask(
            id=context.task_ids["osint"],
            workspace_id=context.workspace_id,
            project_id=context.project_ids["osint"],
            source_id=context.source_ids["osint"],
            collector_type="github_repo",
            name="Scrapy GitHub 指标采集",
            schedule_cron=None,
            status="enabled",
            config={
                "owner": "scrapy",
                "repo": "scrapy",
                "freshness_target_hours": 6,
                "provenance": _provenance("collection_task", "osint"),
                "schedule_policy": "auto_freshness",
            },
            success_count=96,
            failure_count=1,
            last_run_at=now - timedelta(minutes=28),
            created_at=now - timedelta(days=14),
            updated_at=now,
        ),
        CollectionTask(
            id=context.task_ids["amazon"],
            workspace_id=context.workspace_id,
            project_id=context.project_ids["ecommerce"],
            source_id=context.source_ids["amazon"],
            collector_type="manual_json",
            name="Amazon BSR / Keepa 指标导入",
            schedule_cron=None,
            status="enabled",
            config={
                "schema": "product_method_snapshot",
                "freshness_target_hours": 12,
                "provenance": _provenance("collection_task", "ecommerce"),
                "schedule_policy": "auto_freshness",
            },
            success_count=128,
            failure_count=2,
            last_run_at=now - timedelta(minutes=18),
            created_at=now - timedelta(days=13),
            updated_at=now,
        ),
        CollectionTask(
            id=context.task_ids["social"],
            workspace_id=context.workspace_id,
            project_id=context.project_ids["social"],
            source_id=context.source_ids["social"],
            collector_type="manual_json",
            name="社媒热点方法雷达导入",
            schedule_cron=None,
            status="enabled",
            config={
                "schema": "social_method_snapshot",
                "freshness_target_hours": 6,
                "provenance": _provenance("collection_task", "social"),
                "schedule_policy": "auto_freshness",
            },
            success_count=64,
            failure_count=0,
            last_run_at=now - timedelta(hours=1),
            created_at=now - timedelta(days=12),
            updated_at=now,
        ),
        CollectionTask(
            id=context.task_ids["competitor"],
            workspace_id=context.workspace_id,
            project_id=context.project_ids["competitor"],
            source_id=context.source_ids["competitor"],
            collector_type="generic_web",
            name="竞品公开页面快照采集",
            schedule_cron=None,
            status="enabled",
            config={
                "url": "https://www.scrapingbee.com/",
                "freshness_target_hours": 24,
                "provenance": _provenance("collection_task", "competitor"),
                "schedule_policy": "auto_freshness",
            },
            success_count=44,
            failure_count=1,
            last_run_at=now - timedelta(minutes=42),
            created_at=now - timedelta(days=11),
            updated_at=now,
        ),
    ]
    await _merge_all(session, task_items)

    run_items = [
        TaskRun(
            id=context.run_ids["osint-success"],
            task_id=context.task_ids["osint"],
            workspace_id=context.workspace_id,
            status="success",
            started_at=now - timedelta(minutes=30),
            finished_at=now - timedelta(minutes=28),
            records_count=1,
            entities_count=1,
            error_message=None,
            error_traceback=None,
            logs=[{"step": "github_repo_collected", "repo": "scrapy/scrapy"}],
            created_at=now - timedelta(minutes=28),
        ),
        TaskRun(
            id=context.run_ids["amazon-success"],
            task_id=context.task_ids["amazon"],
            workspace_id=context.workspace_id,
            status="success",
            started_at=now - timedelta(minutes=20),
            finished_at=now - timedelta(minutes=18),
            records_count=42,
            entities_count=12,
            error_message=None,
            error_traceback=None,
            logs=[{"step": "collector_finished", "records": 42}],
            created_at=now - timedelta(minutes=18),
        ),
        TaskRun(
            id=context.run_ids["social-success"],
            task_id=context.task_ids["social"],
            workspace_id=context.workspace_id,
            status="success",
            started_at=now - timedelta(hours=1, minutes=6),
            finished_at=now - timedelta(hours=1),
            records_count=1,
            entities_count=1,
            error_message=None,
            error_traceback=None,
            logs=[{"step": "manual_json_imported", "records": 1}],
            created_at=now - timedelta(hours=1),
        ),
        TaskRun(
            id=context.run_ids["competitor-success"],
            task_id=context.task_ids["competitor"],
            workspace_id=context.workspace_id,
            status="success",
            started_at=now - timedelta(minutes=44),
            finished_at=now - timedelta(minutes=42),
            records_count=1,
            entities_count=1,
            error_message=None,
            error_traceback=None,
            logs=[{"step": "generic_web_collected", "url": "https://www.scrapingbee.com/"}],
            created_at=now - timedelta(minutes=42),
        ),
        TaskRun(
            id=context.run_ids["competitor-failed"],
            task_id=context.task_ids["competitor"],
            workspace_id=context.workspace_id,
            status="failed",
            started_at=now - timedelta(minutes=12),
            finished_at=now - timedelta(minutes=10),
            records_count=0,
            entities_count=0,
            error_message="Target page returned bot protection challenge, retry scheduled",
            error_traceback=None,
            logs=[{"step": "collector_failed", "reason": "bot_protection_challenge"}],
            created_at=now - timedelta(minutes=10),
        ),
    ]
    await _merge_all(session, run_items)

    await _merge_all(
        session,
        [
            _raw_record(
                context,
                "osint-prev",
                context.project_ids["osint"],
                context.source_ids["osint"],
                context.run_ids["osint-success"],
                "https://github.com/scrapy/scrapy",
                {
                    "full_name": "scrapy/scrapy",
                    "stars": 53500,
                    "forks": 10900,
                    "open_issues": 640,
                    "collection_method": "GitHub REST API repo metrics",
                },
                now - timedelta(days=3),
            ),
            _raw_record(
                context,
                "osint-current",
                context.project_ids["osint"],
                context.source_ids["osint"],
                context.run_ids["osint-success"],
                "https://github.com/scrapy/scrapy",
                {
                    "full_name": "scrapy/scrapy",
                    "stars": 54280,
                    "forks": 11020,
                    "open_issues": 618,
                    "collection_method": "GitHub REST API repo metrics",
                    "freshness_target_hours": 6,
                },
                now - timedelta(minutes=28),
            ),
            _raw_record(
                context,
                "amazon-prev",
                context.project_ids["ecommerce"],
                context.source_ids["amazon"],
                context.run_ids["amazon-success"],
                "https://www.amazon.com/Best-Sellers/zgbs/home-garden",
                {
                    "id": "amazon-bsr-keepa-air-filter",
                    "title": "Amazon BSR + Keepa 价格排名雷达",
                    "price": 49.9,
                    "rank": 18,
                    "review_count": 1760,
                    "method_quality": 84,
                    "collection_methods": [
                        "Amazon Best Sellers public page",
                        "Keepa price history API",
                    ],
                },
                now - timedelta(days=2),
            ),
            _raw_record(
                context,
                "amazon-current",
                context.project_ids["ecommerce"],
                context.source_ids["amazon"],
                context.run_ids["amazon-success"],
                "https://www.amazon.com/Best-Sellers/zgbs/home-garden",
                {
                    "id": "amazon-bsr-keepa-air-filter",
                    "title": "Amazon BSR + Keepa 价格排名雷达",
                    "price": 39.9,
                    "rank": 6,
                    "review_count": 1840,
                    "method_quality": 91,
                    "collection_methods": [
                        "Amazon Best Sellers public page",
                        "Keepa price history API",
                    ],
                    "freshness_target_hours": 12,
                },
                now - timedelta(minutes=19),
            ),
            _raw_record(
                context,
                "social-prev",
                context.project_ids["social"],
                context.source_ids["social"],
                context.run_ids["social-success"],
                "https://www.tiktok.com/business/creativecenter/",
                {
                    "id": "ai-scraping-methods-social",
                    "name": "AI 数据采集方法",
                    "mentions_24h": 210000,
                    "engagement_rate": 0.061,
                    "method_quality": 78,
                    "collection_methods": ["TikTok Creative Center", "Reddit API"],
                },
                now - timedelta(days=1),
            ),
            _raw_record(
                context,
                "social-current",
                context.project_ids["social"],
                context.source_ids["social"],
                context.run_ids["social-success"],
                "https://www.tiktok.com/business/creativecenter/",
                {
                    "id": "ai-scraping-methods-social",
                    "name": "AI 数据采集方法",
                    "mentions_24h": 690000,
                    "engagement_rate": 0.093,
                    "method_quality": 86,
                    "collection_methods": [
                        "TikTok Creative Center",
                        "Reddit API",
                        "YouTube RSS",
                    ],
                    "freshness_target_hours": 6,
                },
                now - timedelta(hours=1),
            ),
            _raw_record(
                context,
                "competitor-prev",
                context.project_ids["competitor"],
                context.source_ids["competitor"],
                context.run_ids["competitor-success"],
                "https://www.scrapingbee.com/",
                {
                    "url": "https://www.scrapingbee.com/",
                    "title": "ScrapingBee - Web Scraping API",
                    "text_length": 18200,
                    "html_length": 89200,
                    "content_hash": "competitor-prev-public-page",
                    "collection_method": "Generic web page HTML snapshot",
                },
                now - timedelta(days=2),
            ),
            _raw_record(
                context,
                "competitor-current",
                context.project_ids["competitor"],
                context.source_ids["competitor"],
                context.run_ids["competitor-success"],
                "https://www.scrapingbee.com/",
                {
                    "url": "https://www.scrapingbee.com/",
                    "title": "ScrapingBee - Web Scraping API",
                    "text_length": 21400,
                    "html_length": 96700,
                    "content_hash": "competitor-current-public-page",
                    "collection_method": "Generic web page HTML snapshot",
                    "freshness_target_hours": 24,
                },
                now - timedelta(minutes=45),
            ),
        ],
    )


def _raw_record(
    context: DemoContext,
    key: str,
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    task_run_id: uuid.UUID,
    source_url: str,
    content: dict[str, Any],
    collected_at: datetime,
) -> RawRecord:
    domain = _domain_for_demo_key(key)
    return RawRecord(
        id=context.raw_record_ids[key],
        workspace_id=context.workspace_id,
        project_id=project_id,
        source_id=source_id,
        task_run_id=task_run_id,
        record_type="metric_snapshot",
        source_url=source_url,
        content={**content, "provenance": _provenance("raw_record", domain)},
        content_hash=str(context.raw_record_ids[key]).replace("-", ""),
        screenshot_url=None,
        collected_at=collected_at,
        created_at=collected_at,
    )


def _domain_for_demo_key(key: str) -> str:
    if key.startswith("amazon"):
        return "ecommerce"
    if key.startswith("osint"):
        return "osint"
    if key.startswith("social"):
        return "social"
    if key.startswith("competitor"):
        return "competitor"
    return "mixed"


async def _merge_entity_layer(
    session: AsyncSession,
    context: DemoContext,
    now: datetime,
) -> None:
    await _merge_all(
        session,
        [
            Entity(
                id=context.entity_ids["osint-repo"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["osint"],
                entity_type="github_repo",
                external_id="scrapy/scrapy",
                canonical_url="https://github.com/scrapy/scrapy",
                name="scrapy/scrapy",
                domain="osint",
                latest_snapshot_id=None,
                first_seen_at=now - timedelta(days=3),
                last_seen_at=now - timedelta(minutes=28),
                created_at=now - timedelta(days=3),
                updated_at=now,
            ),
            Entity(
                id=context.entity_ids["amazon-product"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["ecommerce"],
                entity_type="product_method",
                external_id="amazon-bsr-keepa-air-filter",
                canonical_url="https://www.amazon.com/Best-Sellers/zgbs",
                name="Amazon BSR + Keepa 价格排名雷达",
                domain="ecommerce",
                latest_snapshot_id=None,
                first_seen_at=now - timedelta(days=2),
                last_seen_at=now - timedelta(minutes=19),
                created_at=now - timedelta(days=2),
                updated_at=now,
            ),
            Entity(
                id=context.entity_ids["social-topic"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["social"],
                entity_type="social_topic",
                external_id="ai-scraping-methods-social",
                canonical_url="https://www.tiktok.com/business/creativecenter/",
                name="AI 数据采集方法",
                domain="social",
                latest_snapshot_id=None,
                first_seen_at=now - timedelta(days=1),
                last_seen_at=now - timedelta(hours=1),
                created_at=now - timedelta(days=1),
                updated_at=now,
            ),
            Entity(
                id=context.entity_ids["competitor-page"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["competitor"],
                entity_type="web_page",
                external_id="https://www.scrapingbee.com/",
                canonical_url="https://www.scrapingbee.com/",
                name="ScrapingBee public homepage",
                domain="competitor",
                latest_snapshot_id=None,
                first_seen_at=now - timedelta(days=2),
                last_seen_at=now - timedelta(minutes=45),
                created_at=now - timedelta(days=2),
                updated_at=now,
            ),
        ],
    )

    snapshot_items = [
        _snapshot(
            context,
            "osint-prev",
            "osint-repo",
            {"stars": 53500, "forks": 10900, "open_issues": 640},
            now - timedelta(days=3),
        ),
        _snapshot(
            context,
            "osint-current",
            "osint-repo",
            {"stars": 54280, "forks": 11020, "open_issues": 618, "freshness_target_hours": 6},
            now - timedelta(minutes=28),
        ),
        _snapshot(
            context,
            "amazon-prev",
            "amazon-product",
            {"price": 49.9, "rank": 18, "review_count": 1760, "method_quality": 84},
            now - timedelta(days=2),
        ),
        _snapshot(
            context,
            "amazon-current",
            "amazon-product",
            {
                "price": 39.9,
                "rank": 6,
                "review_count": 1840,
                "method_quality": 91,
                "freshness_target_hours": 12,
            },
            now - timedelta(minutes=19),
        ),
        _snapshot(
            context,
            "social-prev",
            "social-topic",
            {"mentions_24h": 210000, "engagement_rate": 0.061, "method_quality": 78},
            now - timedelta(days=1),
        ),
        _snapshot(
            context,
            "social-current",
            "social-topic",
            {
                "mentions_24h": 690000,
                "engagement_rate": 0.093,
                "method_quality": 86,
                "freshness_target_hours": 6,
            },
            now - timedelta(hours=1),
        ),
        _snapshot(
            context,
            "competitor-prev",
            "competitor-page",
            {
                "text_length": 18200,
                "html_length": 89200,
                "content_hash": "competitor-prev-public-page",
            },
            now - timedelta(days=2),
        ),
        _snapshot(
            context,
            "competitor-current",
            "competitor-page",
            {
                "text_length": 21400,
                "html_length": 96700,
                "content_hash": "competitor-current-public-page",
                "freshness_target_hours": 24,
            },
            now - timedelta(minutes=45),
        ),
    ]
    await _merge_all(session, snapshot_items)

    latest_map = {
        "osint-repo": context.snapshot_ids["osint-current"],
        "amazon-product": context.snapshot_ids["amazon-current"],
        "social-topic": context.snapshot_ids["social-current"],
        "competitor-page": context.snapshot_ids["competitor-current"],
    }
    for entity_key, snapshot_id in latest_map.items():
        entity = await session.get(Entity, context.entity_ids[entity_key])
        if entity is not None:
            entity.latest_snapshot_id = snapshot_id
    await session.flush()

    await _merge_all(
        session,
        [
            Signal(
                id=context.signal_ids["osint-stars-surge"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["osint"],
                entity_id=context.entity_ids["osint-repo"],
                signal_type="star_growth",
                previous_snapshot_id=context.snapshot_ids["osint-prev"],
                current_snapshot_id=context.snapshot_ids["osint-current"],
                current_value=54280,
                previous_value=53500,
                delta=780,
                delta_ratio=0.0146,
                confidence=0.9,
                severity="high",
                metadata_json={
                    "metric": "stars",
                    "window": "72h",
                    "freshness_target_hours": 6,
                    "provenance": _provenance("signal", "osint"),
                },
                detected_at=now - timedelta(minutes=27),
            ),
            Signal(
                id=context.signal_ids["amazon-price-drop"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["ecommerce"],
                entity_id=context.entity_ids["amazon-product"],
                signal_type="price_drop",
                previous_snapshot_id=context.snapshot_ids["amazon-prev"],
                current_snapshot_id=context.snapshot_ids["amazon-current"],
                current_value=39.9,
                previous_value=49.9,
                delta=-10.0,
                delta_ratio=-0.2004,
                confidence=0.91,
                severity="high",
                metadata_json={
                    "metric": "price",
                    "threshold": 0.15,
                    "currency": "USD",
                    "freshness_target_hours": 12,
                    "provenance": _provenance("signal", "ecommerce"),
                },
                detected_at=now - timedelta(minutes=18),
            ),
            Signal(
                id=context.signal_ids["social-mentions-spike"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["social"],
                entity_id=context.entity_ids["social-topic"],
                signal_type="traffic_spike",
                previous_snapshot_id=context.snapshot_ids["social-prev"],
                current_snapshot_id=context.snapshot_ids["social-current"],
                current_value=690000,
                previous_value=210000,
                delta=480000,
                delta_ratio=2.2857,
                confidence=0.88,
                severity="medium",
                metadata_json={
                    "metric": "mentions_24h",
                    "threshold": 1.5,
                    "freshness_target_hours": 6,
                    "provenance": _provenance("signal", "social"),
                },
                detected_at=now - timedelta(hours=1),
            ),
            Signal(
                id=context.signal_ids["competitor-page-change"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["competitor"],
                entity_id=context.entity_ids["competitor-page"],
                signal_type="page_changed",
                previous_snapshot_id=context.snapshot_ids["competitor-prev"],
                current_snapshot_id=context.snapshot_ids["competitor-current"],
                current_value=0.21,
                previous_value=None,
                delta=None,
                delta_ratio=0.21,
                confidence=0.85,
                severity="medium",
                metadata_json={
                    "metric": "content_hash",
                    "change_ratio": 0.21,
                    "freshness_target_hours": 24,
                    "provenance": _provenance("signal", "competitor"),
                },
                detected_at=now - timedelta(minutes=44),
            ),
        ],
    )


def _snapshot(
    context: DemoContext,
    snapshot_key: str,
    entity_key: str,
    metrics: dict[str, Any],
    captured_at: datetime,
) -> EntitySnapshot:
    domain = _domain_for_demo_key(snapshot_key)
    return EntitySnapshot(
        id=context.snapshot_ids[snapshot_key],
        entity_id=context.entity_ids[entity_key],
        raw_record_id=context.raw_record_ids[snapshot_key],
        snapshot_data={
            "metrics": metrics,
            "source": "demo_seed",
            "provenance": _provenance("entity_snapshot", domain),
        },
        metrics=metrics,
        captured_at=captured_at,
        created_at=captured_at,
    )


async def _merge_intelligence_layer(
    session: AsyncSession,
    context: DemoContext,
    now: datetime,
) -> None:
    await _merge_all(
        session,
        [
            IntelligenceItem(
                id=context.intelligence_ids["osint-scrapy-momentum"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["osint"],
                title="Scrapy 仓库 72h Star 净增 780，开源采集框架热度回升",
                summary=(
                    "GitHub REST API 指标显示 scrapy/scrapy 在 72 小时窗口内 Star 从 "
                    "53,500 增至 54,280，同时 open issues 下降；适合作为 Python 采集栈"
                    "基准框架持续跟踪。"
                ),
                intelligence_type="trend",
                status="reviewed",
                impact_score=82.0,
                confidence_score=90.0,
                novelty_score=78.0,
                urgency_score=76.0,
                final_score=82.4,
                generated_by="rule",
                domain="osint",
                created_at=now - timedelta(minutes=26),
                updated_at=now,
            ),
            IntelligenceItem(
                id=context.intelligence_ids["amazon-margin-risk"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["ecommerce"],
                title="Amazon BSR + Keepa 雷达显示价格下探 20%，排名同步抬升",
                summary=(
                    "电商价格雷达显示目标商品价格从 49.9 降至 39.9，BSR 排名从 18 升至 6；"
                    "Keepa 价格历史与公开榜单组合适合承载价格/排名双指标监控。"
                ),
                intelligence_type="risk",
                status="new",
                impact_score=88.0,
                confidence_score=91.0,
                novelty_score=76.0,
                urgency_score=92.0,
                final_score=87.0,
                generated_by="rule",
                domain="ecommerce",
                created_at=now - timedelta(minutes=16),
                updated_at=now,
            ),
            IntelligenceItem(
                id=context.intelligence_ids["social-method-window"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["social"],
                title="TikTok / Reddit 方法雷达 24h 提及量放大 3.3 倍",
                summary=(
                    "社媒热点雷达显示 AI 数据采集方法主题提及量从 21 万提升至 69 万，"
                    "互动率同步升至 9.3%；Creative Center + Reddit API 可形成早期趋势雷达。"
                ),
                intelligence_type="opportunity",
                status="following",
                impact_score=81.0,
                confidence_score=88.0,
                novelty_score=83.0,
                urgency_score=79.0,
                final_score=83.0,
                generated_by="rule",
                domain="social",
                created_at=now - timedelta(hours=1),
                updated_at=now,
            ),
            IntelligenceItem(
                id=context.intelligence_ids["competitor-landing-shift"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["competitor"],
                title="ScrapingBee 公开页面内容变化约 21%，竞品定位需复核",
                summary=(
                    "通用网页快照显示竞品公开主页文本/HTML 指纹发生中等变化，"
                    "适合检查定价、反爬能力描述和落地页 CTA 是否更新。"
                ),
                intelligence_type="competitor",
                status="new",
                impact_score=72.0,
                confidence_score=85.0,
                novelty_score=80.0,
                urgency_score=68.0,
                final_score=76.0,
                generated_by="rule",
                domain="competitor",
                created_at=now - timedelta(minutes=43),
                updated_at=now,
            ),
        ],
    )

    await _merge_all(
        session,
        [
            Evidence(
                id=_id("evidence-osint-stars"),
                intelligence_id=context.intelligence_ids["osint-scrapy-momentum"],
                signal_id=context.signal_ids["osint-stars-surge"],
                entity_id=context.entity_ids["osint-repo"],
                raw_record_id=context.raw_record_ids["osint-current"],
                evidence_type="signal",
                title="scrapy/scrapy 72h Star 净增 780",
                url="https://github.com/scrapy/scrapy",
                excerpt="stars: 54280, forks: 11020, open_issues: 618",
                highlighted_text="GitHub REST API repo metrics, freshness target 6h",
                reference_metadata=_provenance("evidence", "osint"),
                created_at=now - timedelta(minutes=26),
            ),
            Evidence(
                id=_id("evidence-amazon-price"),
                intelligence_id=context.intelligence_ids["amazon-margin-risk"],
                signal_id=context.signal_ids["amazon-price-drop"],
                entity_id=context.entity_ids["amazon-product"],
                raw_record_id=context.raw_record_ids["amazon-current"],
                evidence_type="signal",
                title="Amazon / Keepa 价格指标从 49.9 降至 39.9",
                url="https://www.amazon.com/Best-Sellers/zgbs",
                excerpt="price: 39.9, rank: 6, review_count: 1840",
                highlighted_text="price drop -20.0%, BSR rank improved to 6",
                reference_metadata=_provenance("evidence", "ecommerce"),
                created_at=now - timedelta(minutes=16),
            ),
            Evidence(
                id=_id("evidence-social-mentions"),
                intelligence_id=context.intelligence_ids["social-method-window"],
                signal_id=context.signal_ids["social-mentions-spike"],
                entity_id=context.entity_ids["social-topic"],
                raw_record_id=context.raw_record_ids["social-current"],
                evidence_type="signal",
                title="AI 数据采集方法主题提及量 24h 提升至 69 万",
                url="https://www.tiktok.com/business/creativecenter/",
                excerpt="mentions_24h: 690000, engagement_rate: 0.093",
                highlighted_text="Creative Center + Reddit API trend watch, traffic spike +228.6%",
                reference_metadata=_provenance("evidence", "social"),
                created_at=now - timedelta(hours=1),
            ),
            Evidence(
                id=_id("evidence-competitor-page"),
                intelligence_id=context.intelligence_ids["competitor-landing-shift"],
                signal_id=context.signal_ids["competitor-page-change"],
                entity_id=context.entity_ids["competitor-page"],
                raw_record_id=context.raw_record_ids["competitor-current"],
                evidence_type="signal",
                title="公开主页 HTML 指纹发生中等变化",
                url="https://www.scrapingbee.com/",
                excerpt="text_length: 21400, html_length: 96700",
                highlighted_text="page_changed change_ratio=0.21",
                reference_metadata=_provenance("evidence", "competitor"),
                created_at=now - timedelta(minutes=43),
            ),
        ],
    )


async def _merge_reports_alerts_notifications(
    session: AsyncSession,
    context: DemoContext,
    now: datetime,
) -> None:
    report_id = _id("report-daily")
    await _merge_all(
        session,
        [
            Report(
                id=report_id,
                workspace_id=context.workspace_id,
                project_id=None,
                report_type="daily",
                title="Data Achieve 每日情报摘要",
                content=(
                    "今日共识别 4 条高价值情报：Scrapy 开源仓库热度回升、Amazon/Keepa "
                    "价格排名信号变化、社媒采集主题热度放大、竞品公开页面发生中等变化。"
                    "建议优先复核电商价格风险和竞品页面更新，同时把社媒方法雷达纳入日采集。"
                ),
                status="generated",
                period_start=now - timedelta(days=1),
                period_end=now,
                created_at=now - timedelta(minutes=8),
            ),
            AlertRule(
                id=context.alert_rule_ids["price"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["ecommerce"],
                name="价格跌幅超过 15%",
                signal_type="price_drop",
                condition={"field": "delta_ratio", "op": "lte", "value": -0.15},
                channel="both",
                enabled=True,
                created_at=now - timedelta(days=7),
            ),
            AlertRule(
                id=context.alert_rule_ids["traffic"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["social"],
                name="流量增长超过 150%",
                signal_type="traffic_spike",
                condition={"field": "delta_ratio", "op": "gte", "value": 1.5},
                channel="in_app",
                enabled=True,
                created_at=now - timedelta(days=6),
            ),
            AlertRule(
                id=context.alert_rule_ids["competitor"],
                workspace_id=context.workspace_id,
                project_id=context.project_ids["competitor"],
                name="竞品页面发生中等以上变化",
                signal_type="page_changed",
                condition={"field": "delta_ratio", "op": "gte", "value": 0.1},
                channel="in_app",
                enabled=True,
                created_at=now - timedelta(days=5),
            ),
        ],
    )

    await _merge_all(
        session,
        [
            AlertEvent(
                id=_id("alert-event-price"),
                rule_id=context.alert_rule_ids["price"],
                signal_id=context.signal_ids["amazon-price-drop"],
                status="sent",
                payload={
                    "title": "价格跌幅超过 15%",
                    "delta_ratio": -0.2004,
                    "provenance": _provenance("alert_event", "ecommerce"),
                },
                triggered_at=now - timedelta(minutes=15),
                sent_at=now - timedelta(minutes=14),
            ),
            AlertEvent(
                id=_id("alert-event-traffic"),
                rule_id=context.alert_rule_ids["traffic"],
                signal_id=context.signal_ids["social-mentions-spike"],
                status="triggered",
                payload={
                    "title": "流量增长超过 150%",
                    "delta_ratio": 2.2857,
                    "provenance": _provenance("alert_event", "social"),
                },
                triggered_at=now - timedelta(hours=1),
                sent_at=None,
            ),
            AlertEvent(
                id=_id("alert-event-competitor"),
                rule_id=context.alert_rule_ids["competitor"],
                signal_id=context.signal_ids["competitor-page-change"],
                status="sent",
                payload={
                    "title": "竞品页面发生中等以上变化",
                    "delta_ratio": 0.21,
                    "provenance": _provenance("alert_event", "competitor"),
                },
                triggered_at=now - timedelta(minutes=43),
                sent_at=now - timedelta(minutes=42),
            ),
            Notification(
                id=_id("notification-report"),
                user_id=context.user_id,
                title="日报已生成",
                body="Data Achieve 每日情报摘要已准备好，可进入报告页查看。",
                notification_type="report_ready",
                reference_type="report",
                reference_id=report_id,
                is_read=False,
                created_at=now - timedelta(minutes=8),
            ),
            Notification(
                id=_id("notification-alert"),
                user_id=context.user_id,
                title="价格告警已触发",
                body="Portable Air Quality Filter 价格下探 20%，已生成风险情报。",
                notification_type="alert",
                reference_type="alert_event",
                reference_id=_id("alert-event-price"),
                is_read=False,
                created_at=now - timedelta(minutes=14),
            ),
            Notification(
                id=_id("notification-task-failed"),
                user_id=context.user_id,
                title="竞品页面采集任务失败",
                body="ScrapingBee 公开页面快照遇到 bot protection challenge，系统已等待下次调度。",
                notification_type="task_failed",
                reference_type="task_run",
                reference_id=context.run_ids["competitor-failed"],
                is_read=True,
                created_at=now - timedelta(minutes=10),
            ),
            Notification(
                id=_id("notification-competitor-alert"),
                user_id=context.user_id,
                title="竞品页面变化已触发",
                body="ScrapingBee 公开页面内容变化约 21%，已生成竞品情报。",
                notification_type="alert",
                reference_type="alert_event",
                reference_id=_id("alert-event-competitor"),
                is_read=False,
                created_at=now - timedelta(minutes=42),
            ),
        ],
    )


async def _run_cleanup_command(dry_run: bool) -> None:
    async with async_session_factory() as session:
        report = await cleanup_demo_noise(session, dry_run=dry_run)
        if not dry_run:
            await session.commit()
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed and maintain curated demo data.")
    parser.add_argument(
        "--cleanup-demo-noise",
        action="store_true",
        help="Audit or remove non-curated runtime data from the demo workspace.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute cleanup. Without this flag cleanup runs in dry-run mode.",
    )
    args = parser.parse_args()
    if args.cleanup_demo_noise:
        asyncio.run(_run_cleanup_command(dry_run=not args.execute))
        return
    asyncio.run(seed_demo_data())


if __name__ == "__main__":
    main()
