"""Task freshness check with notifications.

Run inside the API container:

    python -m data_intelligence_hub.maintenance.freshness_check

Scans enabled collection tasks for staleness: a task whose last_run_at is
older than its freshness target (config["freshness_target_hours"], default
24h) plus a fixed grace window (STALE_GRACE_HOURS) counts as stale. Stale
tasks produce one in-app notification per affected workspace owner and are
reported as compact JSON on stdout.

Design mirrors prod_health_check: pure functions (evaluate_stale_tasks,
build_report_text) do no I/O and are unit-tested; main() wires the session
and notification service. Scheduler-independent — schedule it via cron or
run manually. Exit codes: 0 healthy, 1 stale found.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.models.task import CollectionTask
from data_intelligence_hub.services.dashboard_service import _freshness_target_hours

STALE_GRACE_HOURS = 48  # 72h stale 阈值 = 24h 目标 + 48h 宽限


@dataclass(frozen=True)
class StaleTaskItem:
    task_id: str
    task_name: str
    workspace_id: str
    collector_type: str
    last_run_at: str | None
    freshness_target_hours: int
    stale_hours: float | None


def evaluate_stale_tasks(
    rows: Sequence[tuple[CollectionTask, float | None]],
    grace_hours: int = STALE_GRACE_HOURS,
) -> tuple[StaleTaskItem, ...]:
    """Pure: pick stale tasks from (task, last_run_age_hours) rows.

    rows 的第二个元素是 last_run_at 距当前时基的小时数,None 表示从未运行。
    """
    stale: list[StaleTaskItem] = []
    for task, last_run_age in rows:
        target = _freshness_target_hours(task.config)
        is_stale = last_run_age is None or last_run_age > target + grace_hours
        if not is_stale:
            continue
        stale_hours = (
            None
            if last_run_age is None
            else round(max(last_run_age - target - grace_hours, 0.0), 2)
        )
        stale.append(
            StaleTaskItem(
                task_id=str(task.id),
                task_name=task.name,
                workspace_id=str(task.workspace_id),
                collector_type=task.collector_type,
                last_run_at=task.last_run_at.isoformat() if task.last_run_at else None,
                freshness_target_hours=target,
                stale_hours=stale_hours,
            )
        )
    return tuple(stale)


def build_report_text(items: Sequence[StaleTaskItem]) -> str:
    if not items:
        return "任务新鲜度巡检:全部正常,无超期任务。"
    lines = [f"任务新鲜度巡检:发现 {len(items)} 个超期任务(阈值 72h):"]
    for item in items[:10]:
        age = "从未运行" if item.last_run_at is None else f"超期 {item.stale_hours}h"
        lines.append(f"- {item.task_name}({item.collector_type}):{age}")
    if len(items) > 10:
        lines.append(f"…另有 {len(items) - 10} 个,详见 JSON 输出。")
    return "\n".join(lines)


async def run() -> int:
    from datetime import UTC, datetime

    async with async_session_factory() as session:
        result = await session.execute(
            select(CollectionTask).where(CollectionTask.status == "active")
        )
        tasks = result.scalars().all()
        now = datetime.now(UTC)
        rows = [
            (
                task,
                None
                if task.last_run_at is None
                else (now - task.last_run_at).total_seconds() / 3600,
            )
            for task in tasks
        ]
    stale = evaluate_stale_tasks(rows)
    report = {
        "checked_at": now.isoformat(),
        "scanned": len(rows),
        "stale_count": len(stale),
        "stale": [item.__dict__ for item in stale],
    }
    import json

    print(json.dumps(report, ensure_ascii=False))
    # 站内通知:按工作区聚合,给每个受影响工作区发一条。
    # 通知通道走 Notification 模型(in-app);邮件与飞书文本由运维按需扩展。
    if stale:
        await _notify_workspace_owners(stale)
    return 1 if stale else 0


async def _notify_workspace_owners(items: Sequence[StaleTaskItem]) -> None:
    from collections import defaultdict

    from data_intelligence_hub.core.database import async_session_factory
    from data_intelligence_hub.models.notification import Notification
    from data_intelligence_hub.models.workspace import WorkspaceMember

    by_workspace: dict[str, list[StaleTaskItem]] = defaultdict(list)
    for item in items:
        by_workspace[item.workspace_id].append(item)

    async with async_session_factory() as session:
        for workspace_id, ws_items in by_workspace.items():
            members = await session.execute(
                select(WorkspaceMember.user_id).where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.role.in_(("owner", "admin")),
                )
            )
            text = build_report_text(ws_items)
            for (user_id,) in members.all():
                session.add(
                    Notification(
                        user_id=user_id,
                        title=f"采集任务超期 {len(ws_items)} 个",
                        body=text,
                        notification_type="task_freshness",
                        reference_type="collection_task",
                        reference_id=uuid.UUID(ws_items[0].task_id),
                    )
                )
        await session.commit()


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
