from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.models import (
    AlertEvent,
    AlertRule,
    CleaningPlan,
    CollectionTask,
    Dataset,
    DatasetDriftEvent,
    DatasetExportJob,
    DatasetVersion,
    Entity,
    EntitySnapshot,
    Evidence,
    ExtractionPlan,
    IntelligenceFeedback,
    IntelligenceItem,
    Notification,
    Project,
    RawRecord,
    Report,
    ReportAuditEvent,
    ReportSubscription,
    ReportSubscriptionRun,
    Signal,
    SiteAnalysis,
    Source,
    TaskRun,
    User,
    Workspace,
    WorkspaceMember,
)

SAFE_EMAIL_PREFIX = "e2e-"
SAFE_EMAIL_DOMAIN = "example.com"
DEFAULT_OLDER_THAN_HOURS = 24 * 7


@dataclass(frozen=True)
class E2ECleanupReport:
    dry_run: bool
    cutoff: datetime
    counts: dict[str, int]
    samples: dict[str, list[str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "cutoff": self.cutoff.isoformat(),
            "counts": self.counts,
            "samples": self.samples,
        }


async def cleanup_e2e_fixtures(
    session: AsyncSession,
    *,
    dry_run: bool = True,
    older_than_hours: int = DEFAULT_OLDER_THAN_HOURS,
) -> E2ECleanupReport:
    cutoff = datetime.now(UTC) - timedelta(hours=older_than_hours)
    user_ids = await _fetch_ids(
        session,
        select(User.id).where(
            User.email.like(f"{SAFE_EMAIL_PREFIX}%@{SAFE_EMAIL_DOMAIN}"),
            User.created_at <= cutoff,
        ),
    )
    workspace_ids = await _fetch_ids(
        session,
        select(Workspace.id).where(Workspace.owner_id.in_(user_ids)),
    )
    project_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Project.id).where(
                or_(Project.workspace_id.in_(workspace_ids), Project.owner_id.in_(user_ids)),
            ),
        )
    )
    source_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Source.id).where(
                or_(Source.workspace_id.in_(workspace_ids), Source.project_id.in_(project_ids)),
            ),
        )
    )
    task_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(CollectionTask.id).where(
                or_(
                    CollectionTask.workspace_id.in_(workspace_ids),
                    CollectionTask.project_id.in_(project_ids),
                    CollectionTask.source_id.in_(source_ids),
                ),
            ),
        )
    )
    run_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(TaskRun.id).where(
                or_(TaskRun.workspace_id.in_(workspace_ids), TaskRun.task_id.in_(task_ids)),
            ),
        )
    )
    raw_record_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(RawRecord.id).where(
                or_(
                    RawRecord.workspace_id.in_(workspace_ids),
                    RawRecord.project_id.in_(project_ids),
                    RawRecord.source_id.in_(source_ids),
                    RawRecord.task_run_id.in_(run_ids),
                ),
            ),
        )
    )
    entity_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Entity.id).where(
                or_(Entity.workspace_id.in_(workspace_ids), Entity.project_id.in_(project_ids)),
            ),
        )
    )
    snapshot_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(EntitySnapshot.id)
            .join(Entity, EntitySnapshot.entity_id == Entity.id)
            .where(
                or_(
                    Entity.workspace_id.in_(workspace_ids),
                    EntitySnapshot.entity_id.in_(entity_ids),
                    EntitySnapshot.raw_record_id.in_(raw_record_ids),
                ),
            ),
        )
    )
    signal_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Signal.id).where(
                or_(
                    Signal.workspace_id.in_(workspace_ids),
                    Signal.project_id.in_(project_ids),
                    Signal.entity_id.in_(entity_ids),
                    Signal.previous_snapshot_id.in_(snapshot_ids),
                    Signal.current_snapshot_id.in_(snapshot_ids),
                ),
            ),
        )
    )
    intelligence_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(IntelligenceItem.id).where(
                or_(
                    IntelligenceItem.workspace_id.in_(workspace_ids),
                    IntelligenceItem.project_id.in_(project_ids),
                ),
            ),
        )
    )
    feedback_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(IntelligenceFeedback.id).where(
                or_(
                    IntelligenceFeedback.intelligence_id.in_(intelligence_ids),
                    IntelligenceFeedback.user_id.in_(user_ids),
                ),
            ),
        )
    )
    evidence_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Evidence.id).where(
                or_(
                    Evidence.intelligence_id.in_(intelligence_ids),
                    Evidence.signal_id.in_(signal_ids),
                    Evidence.entity_id.in_(entity_ids),
                    Evidence.raw_record_id.in_(raw_record_ids),
                ),
            ),
        )
    )
    report_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Report.id).where(
                or_(Report.workspace_id.in_(workspace_ids), Report.project_id.in_(project_ids)),
            ),
        )
    )
    report_subscription_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(ReportSubscription.id).where(
                or_(
                    ReportSubscription.workspace_id.in_(workspace_ids),
                    ReportSubscription.user_id.in_(user_ids),
                    ReportSubscription.project_id.in_(project_ids),
                ),
            ),
        )
    )
    report_subscription_run_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(ReportSubscriptionRun.id).where(
                or_(
                    ReportSubscriptionRun.workspace_id.in_(workspace_ids),
                    ReportSubscriptionRun.subscription_id.in_(report_subscription_ids),
                    ReportSubscriptionRun.report_id.in_(report_ids),
                ),
            ),
        )
    )
    report_audit_event_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(ReportAuditEvent.id).where(
                or_(
                    ReportAuditEvent.workspace_id.in_(workspace_ids),
                    ReportAuditEvent.report_id.in_(report_ids),
                    ReportAuditEvent.actor_id.in_(user_ids),
                ),
            ),
        )
    )
    dataset_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Dataset.id).where(
                or_(Dataset.workspace_id.in_(workspace_ids), Dataset.project_id.in_(project_ids)),
            ),
        )
    )
    dataset_version_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(DatasetVersion.id).where(
                or_(
                    DatasetVersion.workspace_id.in_(workspace_ids),
                    DatasetVersion.project_id.in_(project_ids),
                    DatasetVersion.dataset_id.in_(dataset_ids),
                    DatasetVersion.created_by_user_id.in_(user_ids),
                ),
            ),
        )
    )
    dataset_version_cleaning_plan_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(DatasetVersion.cleaning_plan_id).where(
                DatasetVersion.id.in_(dataset_version_ids),
                DatasetVersion.cleaning_plan_id.is_not(None),
            ),
        )
    )
    owned_cleaning_plan_ids = await _fetch_ids(
        session,
        select(CleaningPlan.id).where(
            or_(
                CleaningPlan.workspace_id.in_(workspace_ids),
                CleaningPlan.project_id.in_(project_ids),
                CleaningPlan.created_by_user_id.in_(user_ids),
            ),
        ),
    )
    cleaning_plan_ids = _unique_ids(
        [*dataset_version_cleaning_plan_ids, *owned_cleaning_plan_ids]
    )
    dataset_drift_event_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(DatasetDriftEvent.id).where(
                or_(
                    DatasetDriftEvent.workspace_id.in_(workspace_ids),
                    DatasetDriftEvent.project_id.in_(project_ids),
                    DatasetDriftEvent.dataset_id.in_(dataset_ids),
                    DatasetDriftEvent.dataset_version_id.in_(dataset_version_ids),
                ),
            ),
        )
    )
    dataset_export_job_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(DatasetExportJob.id).where(
                or_(
                    DatasetExportJob.workspace_id.in_(workspace_ids),
                    DatasetExportJob.project_id.in_(project_ids),
                    DatasetExportJob.dataset_id.in_(dataset_ids),
                    DatasetExportJob.dataset_version_id.in_(dataset_version_ids),
                    DatasetExportJob.created_by_user_id.in_(user_ids),
                ),
            ),
        )
    )
    site_analysis_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(SiteAnalysis.id).where(
                or_(
                    SiteAnalysis.workspace_id.in_(workspace_ids),
                    SiteAnalysis.project_id.in_(project_ids),
                    SiteAnalysis.created_by_user_id.in_(user_ids),
                ),
            ),
        )
    )
    extraction_plan_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(ExtractionPlan.id).where(
                or_(
                    ExtractionPlan.workspace_id.in_(workspace_ids),
                    ExtractionPlan.project_id.in_(project_ids),
                    ExtractionPlan.site_analysis_id.in_(site_analysis_ids),
                    ExtractionPlan.created_by_user_id.in_(user_ids),
                ),
            ),
        )
    )
    alert_rule_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(AlertRule.id).where(
                or_(
                    AlertRule.workspace_id.in_(workspace_ids),
                    AlertRule.project_id.in_(project_ids),
                ),
            ),
        )
    )
    alert_event_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(AlertEvent.id).where(
                or_(AlertEvent.rule_id.in_(alert_rule_ids), AlertEvent.signal_id.in_(signal_ids)),
            ),
        )
    )
    notification_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Notification.id).where(Notification.user_id.in_(user_ids)),
        )
    )
    workspace_member_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(WorkspaceMember.id).where(
                or_(
                    WorkspaceMember.workspace_id.in_(workspace_ids),
                    WorkspaceMember.user_id.in_(user_ids),
                ),
            ),
        )
    )

    counts = {
        "users": len(user_ids),
        "workspaces": len(workspace_ids),
        "workspace_members": len(workspace_member_ids),
        "projects": len(project_ids),
        "sources": len(source_ids),
        "collection_tasks": len(task_ids),
        "task_runs": len(run_ids),
        "raw_records": len(raw_record_ids),
        "entities": len(entity_ids),
        "entity_snapshots": len(snapshot_ids),
        "signals": len(signal_ids),
        "intelligence_items": len(intelligence_ids),
        "intelligence_feedback": len(feedback_ids),
        "evidences": len(evidence_ids),
        "reports": len(report_ids),
        "report_subscriptions": len(report_subscription_ids),
        "report_subscription_runs": len(report_subscription_run_ids),
        "report_audit_events": len(report_audit_event_ids),
        "datasets": len(dataset_ids),
        "dataset_versions": len(dataset_version_ids),
        "cleaning_plans": len(cleaning_plan_ids),
        "dataset_drift_events": len(dataset_drift_event_ids),
        "dataset_export_jobs": len(dataset_export_job_ids),
        "site_analyses": len(site_analysis_ids),
        "extraction_plans": len(extraction_plan_ids),
        "alert_rules": len(alert_rule_ids),
        "alert_events": len(alert_event_ids),
        "notifications": len(notification_ids),
    }
    samples = {
        "users": await _fetch_strings(
            session,
            select(User.email).where(User.id.in_(user_ids)).order_by(User.created_at).limit(10),
        ),
        "workspaces": await _fetch_strings(
            session,
            select(Workspace.slug)
            .where(Workspace.id.in_(workspace_ids))
            .order_by(Workspace.created_at)
            .limit(10),
        ),
    }
    report = E2ECleanupReport(dry_run=dry_run, cutoff=cutoff, counts=counts, samples=samples)
    if dry_run:
        return report

    await _apply_cleanup(
        session=session,
        user_ids=user_ids,
        workspace_ids=workspace_ids,
        workspace_member_ids=workspace_member_ids,
        project_ids=project_ids,
        source_ids=source_ids,
        task_ids=task_ids,
        run_ids=run_ids,
        raw_record_ids=raw_record_ids,
        entity_ids=entity_ids,
        snapshot_ids=snapshot_ids,
        signal_ids=signal_ids,
        intelligence_ids=intelligence_ids,
        feedback_ids=feedback_ids,
        evidence_ids=evidence_ids,
        report_ids=report_ids,
        report_subscription_ids=report_subscription_ids,
        report_subscription_run_ids=report_subscription_run_ids,
        report_audit_event_ids=report_audit_event_ids,
        dataset_ids=dataset_ids,
        dataset_version_ids=dataset_version_ids,
        cleaning_plan_ids=cleaning_plan_ids,
        dataset_drift_event_ids=dataset_drift_event_ids,
        dataset_export_job_ids=dataset_export_job_ids,
        site_analysis_ids=site_analysis_ids,
        extraction_plan_ids=extraction_plan_ids,
        alert_rule_ids=alert_rule_ids,
        alert_event_ids=alert_event_ids,
        notification_ids=notification_ids,
    )
    return report


async def _apply_cleanup(
    *,
    session: AsyncSession,
    user_ids: list[uuid.UUID],
    workspace_ids: list[uuid.UUID],
    workspace_member_ids: list[uuid.UUID],
    project_ids: list[uuid.UUID],
    source_ids: list[uuid.UUID],
    task_ids: list[uuid.UUID],
    run_ids: list[uuid.UUID],
    raw_record_ids: list[uuid.UUID],
    entity_ids: list[uuid.UUID],
    snapshot_ids: list[uuid.UUID],
    signal_ids: list[uuid.UUID],
    intelligence_ids: list[uuid.UUID],
    feedback_ids: list[uuid.UUID],
    evidence_ids: list[uuid.UUID],
    report_ids: list[uuid.UUID],
    report_subscription_ids: list[uuid.UUID],
    report_subscription_run_ids: list[uuid.UUID],
    report_audit_event_ids: list[uuid.UUID],
    dataset_ids: list[uuid.UUID],
    dataset_version_ids: list[uuid.UUID],
    cleaning_plan_ids: list[uuid.UUID],
    dataset_drift_event_ids: list[uuid.UUID],
    dataset_export_job_ids: list[uuid.UUID],
    site_analysis_ids: list[uuid.UUID],
    extraction_plan_ids: list[uuid.UUID],
    alert_rule_ids: list[uuid.UUID],
    alert_event_ids: list[uuid.UUID],
    notification_ids: list[uuid.UUID],
) -> None:
    if snapshot_ids:
        await session.execute(
            update(Entity)
            .where(Entity.latest_snapshot_id.in_(snapshot_ids))
            .values(latest_snapshot_id=None)
        )
    await session.flush()

    await _delete_ids(session, Notification, notification_ids)
    await _delete_ids(session, ReportSubscriptionRun, report_subscription_run_ids)
    await _delete_ids(session, ReportAuditEvent, report_audit_event_ids)
    await _delete_ids(session, AlertEvent, alert_event_ids)
    await _delete_ids(session, IntelligenceFeedback, feedback_ids)
    await _delete_ids(session, Evidence, evidence_ids)
    await _delete_ids(session, ReportSubscription, report_subscription_ids)
    await _delete_ids(session, Report, report_ids)
    await _delete_ids(session, IntelligenceItem, intelligence_ids)
    await _delete_ids(session, Signal, signal_ids)
    await _delete_ids(session, DatasetDriftEvent, dataset_drift_event_ids)
    await _delete_ids(session, DatasetExportJob, dataset_export_job_ids)
    await _delete_ids(session, DatasetVersion, dataset_version_ids)
    await _delete_ids(session, CleaningPlan, cleaning_plan_ids)
    await _delete_ids(session, Dataset, dataset_ids)
    await _delete_ids(session, ExtractionPlan, extraction_plan_ids)
    await _delete_ids(session, SiteAnalysis, site_analysis_ids)
    await _delete_ids(session, EntitySnapshot, snapshot_ids)
    await _delete_ids(session, RawRecord, raw_record_ids)
    await _delete_ids(session, Entity, entity_ids)
    await _delete_ids(session, TaskRun, run_ids)
    await _delete_ids(session, CollectionTask, task_ids)
    await _delete_ids(session, Source, source_ids)
    await _delete_ids(session, AlertRule, alert_rule_ids)
    await _delete_ids(session, Project, project_ids)
    await _delete_ids(session, WorkspaceMember, workspace_member_ids)
    await _delete_ids(session, Workspace, workspace_ids)
    await _delete_ids(session, User, user_ids)
    await session.flush()


async def _fetch_ids(session: AsyncSession, statement: Any) -> list[uuid.UUID]:
    result = await session.execute(statement)
    return list(result.scalars().all())


async def _fetch_strings(session: AsyncSession, statement: Any) -> list[str]:
    result = await session.execute(statement)
    return [str(value) for value in result.scalars().all()]


async def _delete_ids(session: AsyncSession, model: type[Any], ids: list[uuid.UUID]) -> None:
    if ids:
        await session.execute(delete(model).where(model.id.in_(ids)))


def _unique_ids(ids: list[uuid.UUID]) -> list[uuid.UUID]:
    return list(dict.fromkeys(ids))


async def _run_cleanup_command(*, dry_run: bool, older_than_hours: int) -> None:
    async with async_session_factory() as session:
        report = await cleanup_e2e_fixtures(
            session,
            dry_run=dry_run,
            older_than_hours=older_than_hours,
        )
        if not dry_run:
            await session.commit()
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit or remove isolated real E2E fixtures.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute cleanup. Without this flag cleanup runs in dry-run mode.",
    )
    parser.add_argument(
        "--older-than-hours",
        type=int,
        default=DEFAULT_OLDER_THAN_HOURS,
        help="Only clean e2e users older than this threshold. Defaults to 168 hours.",
    )
    args = parser.parse_args()
    if args.older_than_hours < 0:
        raise SystemExit("--older-than-hours must be greater than or equal to 0")
    asyncio.run(
        _run_cleanup_command(
            dry_run=not args.execute,
            older_than_hours=args.older_than_hours,
        )
    )


if __name__ == "__main__":
    main()
