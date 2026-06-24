from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.models import (
    CollectionTask,
    Dataset,
    DatasetDriftEvent,
    DatasetExportJob,
    DatasetVersion,
    Entity,
    EntitySnapshot,
    Notification,
    Project,
    RawRecord,
    Report,
    ReportAuditEvent,
    Source,
    TaskRun,
    User,
    Workspace,
    WorkspaceMember,
)

SAFE_EMAIL_PREFIX = "retained-public-content-"
SAFE_EMAIL_DOMAIN = "example.com"
DEFAULT_RETENTION_HOURS = 24 * 7
PUBLIC_CONTENT_SOURCE_TYPES = ("public_feed", "generic_web")
PUBLIC_CONTENT_DATASET_TYPE = "public_content_update"
PUBLIC_CONTENT_REPORT_TYPE = "public_content"


@dataclass(frozen=True)
class RetainedPublicContentCleanupReport:
    dry_run: bool
    cutoff: datetime
    retention_hours: int
    counts: dict[str, int]
    samples: dict[str, list[str]]
    policy: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "cutoff": self.cutoff.isoformat(),
            "retention_hours": self.retention_hours,
            "counts": self.counts,
            "samples": self.samples,
            "policy": self.policy,
        }


async def cleanup_retained_public_content_assets(
    session: AsyncSession,
    *,
    dry_run: bool = True,
    older_than_hours: int = DEFAULT_RETENTION_HOURS,
    export_root: Path | None = None,
) -> RetainedPublicContentCleanupReport:
    if older_than_hours < 0:
        raise ValueError("older_than_hours must be greater than or equal to 0")

    cutoff = datetime.now(UTC) - timedelta(hours=older_than_hours)
    ids = await _collect_retained_public_content_ids(session, cutoff=cutoff)
    export_artifacts = _classify_export_artifacts(
        await _fetch_strings(
            session,
            select(DatasetExportJob.artifact_path).where(
                DatasetExportJob.id.in_(ids["dataset_export_jobs"])
            ),
        ),
        export_root=export_root,
    )
    counts = {
        key: len(value)
        for key, value in ids.items()
        if key != "dataset_export_artifact_paths"
    }
    counts["export_artifact_files"] = len(export_artifacts["existing"])
    counts["export_artifact_missing_files"] = len(export_artifacts["missing"])
    counts["export_artifact_path_violations"] = len(export_artifacts["violations"])
    samples = {
        "users": await _fetch_strings(
            session,
            select(User.email)
            .where(User.id.in_(ids["users"]))
            .order_by(User.created_at)
            .limit(10),
        ),
        "workspaces": await _fetch_strings(
            session,
            select(Workspace.slug)
            .where(Workspace.id.in_(ids["workspaces"]))
            .order_by(Workspace.created_at)
            .limit(10),
        ),
        "export_artifact_files": [str(path) for path in export_artifacts["existing"][:10]],
        "export_artifact_path_violations": export_artifacts["violations"][:10],
    }
    report = RetainedPublicContentCleanupReport(
        dry_run=dry_run,
        cutoff=cutoff,
        retention_hours=older_than_hours,
        counts=counts,
        samples=samples,
        policy={
            "name": "retained_public_content_ttl",
            "safe_email_prefix": SAFE_EMAIL_PREFIX,
            "safe_email_domain": SAFE_EMAIL_DOMAIN,
            "dataset_type": PUBLIC_CONTENT_DATASET_TYPE,
            "source_types": list(PUBLIC_CONTENT_SOURCE_TYPES),
            "cleanup_ready": counts["export_artifact_path_violations"] == 0,
            "artifact_delete_before_db_delete": True,
            "scheduler_tick_started": False,
            "provider_call": False,
            "email_sent": False,
        },
    )
    if dry_run:
        return report
    if export_artifacts["violations"]:
        raise RuntimeError("retained_public_content_export_artifact_outside_root")

    for artifact_path in export_artifacts["existing"]:
        artifact_path.unlink()
    await _apply_retained_public_content_cleanup(session, ids)
    return report


async def _collect_retained_public_content_ids(
    session: AsyncSession,
    *,
    cutoff: datetime,
) -> dict[str, list[uuid.UUID]]:
    user_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(User.id).where(
                User.email.like(f"{SAFE_EMAIL_PREFIX}%@{SAFE_EMAIL_DOMAIN}"),
                User.created_at <= cutoff,
            ),
        )
    )
    # Only user-owned workspaces/projects are deleted. Assets in shared workspaces are
    # reached through DatasetVersion/ReportAuditEvent lineage, not broad workspace scope.
    workspace_ids = _unique_ids(
        await _fetch_ids(session, select(Workspace.id).where(Workspace.owner_id.in_(user_ids)))
    )
    project_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Project.id).where(
                or_(Project.workspace_id.in_(workspace_ids), Project.owner_id.in_(user_ids))
            ),
        )
    )
    initial_source_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Source.id).where(
                Source.type.in_(PUBLIC_CONTENT_SOURCE_TYPES),
                or_(Source.workspace_id.in_(workspace_ids), Source.project_id.in_(project_ids)),
            ),
        )
    )
    initial_task_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(CollectionTask.id).where(
                CollectionTask.collector_type.in_(PUBLIC_CONTENT_SOURCE_TYPES),
                or_(
                    CollectionTask.workspace_id.in_(workspace_ids),
                    CollectionTask.project_id.in_(project_ids),
                    CollectionTask.source_id.in_(initial_source_ids),
                ),
            ),
        )
    )
    initial_run_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(TaskRun.id).where(
                or_(TaskRun.workspace_id.in_(workspace_ids), TaskRun.task_id.in_(initial_task_ids))
            ),
        )
    )
    initial_dataset_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Dataset.id).where(
                Dataset.dataset_type == PUBLIC_CONTENT_DATASET_TYPE,
                or_(Dataset.workspace_id.in_(workspace_ids), Dataset.project_id.in_(project_ids)),
            ),
        )
    )
    dataset_version_rows = (
        await session.execute(
            select(
                DatasetVersion.id,
                DatasetVersion.dataset_id,
                DatasetVersion.source_task_run_ids,
            ).where(
                or_(
                    DatasetVersion.workspace_id.in_(workspace_ids),
                    DatasetVersion.project_id.in_(project_ids),
                    DatasetVersion.dataset_id.in_(initial_dataset_ids),
                    DatasetVersion.created_by_user_id.in_(user_ids),
                ),
            )
        )
    ).all()
    dataset_ids = _unique_ids(
        initial_dataset_ids + [row.dataset_id for row in dataset_version_rows]
    )
    dataset_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Dataset.id).where(
                Dataset.id.in_(dataset_ids),
                Dataset.dataset_type == PUBLIC_CONTENT_DATASET_TYPE,
            ),
        )
    )
    dataset_id_set = set(dataset_ids)
    dataset_version_rows = [row for row in dataset_version_rows if row.dataset_id in dataset_id_set]
    dataset_version_ids = _unique_ids([row.id for row in dataset_version_rows])
    lineage_run_ids = _uuid_values_from_strings(
        source_task_run_id
        for row in dataset_version_rows
        for source_task_run_id in (row.source_task_run_ids or [])
    )
    run_ids = _unique_ids(initial_run_ids + lineage_run_ids)
    task_ids = _unique_ids(
        initial_task_ids
        + await _fetch_ids(
            session,
            select(TaskRun.task_id).where(
                TaskRun.id.in_(run_ids),
                TaskRun.task_id.is_not(None),
            ),
        )
    )
    source_ids = _unique_ids(
        initial_source_ids
        + await _fetch_ids(
            session,
            select(CollectionTask.source_id).where(
                CollectionTask.id.in_(task_ids),
                CollectionTask.source_id.is_not(None),
            ),
        )
    )
    raw_record_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(RawRecord.id).where(
                RawRecord.record_type.in_(PUBLIC_CONTENT_SOURCE_TYPES),
                or_(
                    RawRecord.workspace_id.in_(workspace_ids),
                    RawRecord.project_id.in_(project_ids),
                    RawRecord.source_id.in_(source_ids),
                    RawRecord.task_run_id.in_(run_ids),
                ),
            ),
        )
    )
    initial_entity_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Entity.id).where(
                or_(Entity.workspace_id.in_(workspace_ids), Entity.project_id.in_(project_ids))
            ),
        )
    )
    snapshot_rows = (
        await session.execute(
            select(EntitySnapshot.id, EntitySnapshot.entity_id)
            .join(Entity, EntitySnapshot.entity_id == Entity.id)
            .where(
                or_(
                    Entity.workspace_id.in_(workspace_ids),
                    EntitySnapshot.entity_id.in_(initial_entity_ids),
                    EntitySnapshot.raw_record_id.in_(raw_record_ids),
                ),
            )
        )
    ).all()
    snapshot_ids = _unique_ids([row.id for row in snapshot_rows])
    entity_ids = _unique_ids(initial_entity_ids + [row.entity_id for row in snapshot_rows])
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
    actor_report_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(ReportAuditEvent.report_id).where(
                ReportAuditEvent.actor_id.in_(user_ids),
                ReportAuditEvent.report_id.is_not(None),
            ),
        )
    )
    owned_report_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Report.id).where(
                Report.report_type == PUBLIC_CONTENT_REPORT_TYPE,
                or_(Report.workspace_id.in_(workspace_ids), Report.project_id.in_(project_ids)),
            ),
        )
    )
    report_ids = _unique_ids(actor_report_ids + owned_report_ids)
    report_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(Report.id).where(
                Report.id.in_(report_ids),
                Report.report_type == PUBLIC_CONTENT_REPORT_TYPE,
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
    notification_ids = _unique_ids(
        await _fetch_ids(session, select(Notification.id).where(Notification.user_id.in_(user_ids)))
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
    return {
        "users": user_ids,
        "workspaces": workspace_ids,
        "workspace_members": workspace_member_ids,
        "projects": project_ids,
        "sources": source_ids,
        "collection_tasks": task_ids,
        "task_runs": run_ids,
        "raw_records": raw_record_ids,
        "entities": entity_ids,
        "entity_snapshots": snapshot_ids,
        "datasets": dataset_ids,
        "dataset_versions": dataset_version_ids,
        "dataset_drift_events": dataset_drift_event_ids,
        "dataset_export_jobs": dataset_export_job_ids,
        "reports": report_ids,
        "report_audit_events": report_audit_event_ids,
        "notifications": notification_ids,
    }


async def _apply_retained_public_content_cleanup(
    session: AsyncSession,
    ids: dict[str, list[uuid.UUID]],
) -> None:
    if ids["entity_snapshots"]:
        await session.execute(
            update(Entity)
            .where(Entity.latest_snapshot_id.in_(ids["entity_snapshots"]))
            .values(latest_snapshot_id=None)
        )
    await session.flush()

    await _delete_ids(session, Notification, ids["notifications"])
    await _delete_ids(session, ReportAuditEvent, ids["report_audit_events"])
    await _delete_ids(session, Report, ids["reports"])
    await _delete_ids(session, DatasetDriftEvent, ids["dataset_drift_events"])
    await _delete_ids(session, DatasetExportJob, ids["dataset_export_jobs"])
    await _delete_ids(session, DatasetVersion, ids["dataset_versions"])
    await _delete_ids(session, Dataset, ids["datasets"])
    await _delete_ids(session, EntitySnapshot, ids["entity_snapshots"])
    await _delete_ids(session, RawRecord, ids["raw_records"])
    await _delete_ids(session, Entity, ids["entities"])
    await _delete_ids(session, TaskRun, ids["task_runs"])
    await _delete_ids(session, CollectionTask, ids["collection_tasks"])
    await _delete_ids(session, Source, ids["sources"])
    await _delete_ids(session, Project, ids["projects"])
    await _delete_ids(session, WorkspaceMember, ids["workspace_members"])
    await _delete_ids(session, Workspace, ids["workspaces"])
    await _delete_ids(session, User, ids["users"])
    await session.flush()


def _classify_export_artifacts(
    artifact_paths: list[str],
    *,
    export_root: Path | None = None,
) -> dict[str, list[Any]]:
    root = (
        export_root.expanduser().resolve()
        if export_root is not None
        else Path(get_settings().dataset_export_dir).expanduser().resolve()
    )
    existing: list[Path] = []
    missing: list[Path] = []
    violations: list[str] = []
    for raw_path in artifact_paths:
        candidate = Path(raw_path).expanduser().resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            violations.append(str(candidate))
            continue
        if candidate.is_file():
            existing.append(candidate)
        else:
            missing.append(candidate)
    return {"existing": existing, "missing": missing, "violations": violations}


def _uuid_values_from_strings(values: Any) -> list[uuid.UUID]:
    parsed: list[uuid.UUID] = []
    for value in values:
        try:
            parsed.append(uuid.UUID(str(value)))
        except (TypeError, ValueError):
            continue
    return _unique_ids(parsed)


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
        report = await cleanup_retained_public_content_assets(
            session,
            dry_run=dry_run,
            older_than_hours=older_than_hours,
        )
        if not dry_run:
            await session.commit()
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit or remove expired retained public-content canary assets."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute cleanup. Without this flag cleanup runs in dry-run mode.",
    )
    parser.add_argument(
        "--older-than-hours",
        type=int,
        default=DEFAULT_RETENTION_HOURS,
        help="Only clean retained public-content users older than this threshold.",
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
