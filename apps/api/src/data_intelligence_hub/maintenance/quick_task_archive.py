from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.models import CollectionTask, TaskRun
from data_intelligence_hub.repositories.workspaces import (
    DEMO_WORKSPACE_SLUG,
    get_demo_workspace,
)

QUICK_NAME_PATTERN = "[quick]%"
TEST_NAME_PREFIX = "[quick] [test]"
LEGACY_TEST_NAME_PREFIX = "[quick] [quick] [test]"
PROBE_NAME_PREFIX = "[quick] [probe]"
ENABLED_STATUS = "enabled"
PAUSED_STATUS = "paused"
SAMPLE_LIMIT = 10
TEST_BUCKET = "[quick] [test]"
PROBE_BUCKET = "[quick] [probe]"
OTHER_BUCKET = "other"
BREAKDOWN_BUCKETS = (TEST_BUCKET, PROBE_BUCKET, OTHER_BUCKET)


@dataclass(frozen=True)
class QuickTaskArchiveSample:
    id: uuid.UUID
    name: str
    latest_run_status: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "name": self.name,
            "latest_run_status": self.latest_run_status,
        }


@dataclass(frozen=True)
class QuickTaskArchiveReport:
    dry_run: bool
    workspace_id: uuid.UUID
    workspace_slug: str
    total: int
    breakdown: dict[str, int]
    samples: list[QuickTaskArchiveSample]
    updated: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "workspace": {
                "id": str(self.workspace_id),
                "slug": self.workspace_slug,
            },
            "total": self.total,
            "breakdown": dict(self.breakdown),
            "samples": [sample.to_dict() for sample in self.samples],
            "updated": self.updated,
        }


async def archive_quick_test_tasks(
    session: AsyncSession,
    *,
    dry_run: bool = True,
) -> QuickTaskArchiveReport:
    """Pause quick test tasks in the demo workspace.

    Selection only reads enabled tasks whose name starts with ``[quick]``.
    Dry-run reports the selection. Execute updates the selection by id in one
    statement. The caller owns the transaction commit.
    """
    workspace = await get_demo_workspace(session)
    if workspace is None:
        raise RuntimeError(f"demo workspace not found: {DEMO_WORKSPACE_SLUG}")

    result = await session.execute(
        select(CollectionTask)
        .where(
            CollectionTask.workspace_id == workspace.id,
            CollectionTask.name.like(QUICK_NAME_PATTERN),
            CollectionTask.status == ENABLED_STATUS,
        )
        .order_by(CollectionTask.created_at.asc(), CollectionTask.id.asc())
    )
    tasks = list(result.scalars().all())

    counts: Counter[str] = Counter(_classify_task_name(task.name) for task in tasks)
    breakdown = {bucket: counts.get(bucket, 0) for bucket in BREAKDOWN_BUCKETS}

    samples = tasks[:SAMPLE_LIMIT]
    latest_statuses = await _latest_run_statuses(session, [task.id for task in samples])
    sample_rows = [
        QuickTaskArchiveSample(
            id=task.id,
            name=task.name,
            latest_run_status=latest_statuses.get(task.id),
        )
        for task in samples
    ]

    updated = 0
    if not dry_run and tasks:
        update_result = await session.execute(
            update(CollectionTask)
            .where(
                CollectionTask.id.in_([task.id for task in tasks]),
                CollectionTask.status == ENABLED_STATUS,
            )
            .values(status=PAUSED_STATUS)
        )
        updated = update_result.rowcount or 0
        await session.flush()

    return QuickTaskArchiveReport(
        dry_run=dry_run,
        workspace_id=workspace.id,
        workspace_slug=workspace.slug,
        total=len(tasks),
        breakdown=breakdown,
        samples=sample_rows,
        updated=updated,
    )


def _classify_task_name(name: str) -> str:
    if name.startswith(TEST_NAME_PREFIX) or name.startswith(LEGACY_TEST_NAME_PREFIX):
        return TEST_BUCKET
    if name.startswith(PROBE_NAME_PREFIX):
        return PROBE_BUCKET
    return OTHER_BUCKET


async def _latest_run_statuses(
    session: AsyncSession,
    task_ids: list[uuid.UUID],
) -> dict[uuid.UUID, str]:
    if not task_ids:
        return {}
    run_completed_at = func.coalesce(TaskRun.finished_at, TaskRun.created_at)
    latest_runs = (
        select(
            TaskRun.task_id,
            func.max(run_completed_at).label("latest_completed_at"),
        )
        .where(TaskRun.task_id.in_(task_ids))
        .group_by(TaskRun.task_id)
        .subquery()
    )
    result = await session.execute(
        select(TaskRun.task_id, TaskRun.status)
        .join(
            latest_runs,
            (TaskRun.task_id == latest_runs.c.task_id)
            & (run_completed_at == latest_runs.c.latest_completed_at),
        )
        .order_by(TaskRun.created_at.asc())
    )
    return {task_id: status for task_id, status in result.all()}


async def _run_archive_command(*, dry_run: bool) -> None:
    async with async_session_factory() as session:
        report = await archive_quick_test_tasks(session, dry_run=dry_run)
        if not dry_run:
            await session.commit()
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="归档 demo workspace 内的 [quick] 测试任务。默认只报告，不写库。",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="写库执行。把选中任务的 status 批量置为 paused。",
    )
    args = parser.parse_args()
    asyncio.run(_run_archive_command(dry_run=not args.execute))


if __name__ == "__main__":
    main()
