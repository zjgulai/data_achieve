"""搜索监控的创建、状态与运行后处理。

调度复用 CollectionTask：监控创建时同步建一条启用任务，cron 由
interval_hours 决定。任务执行完成后调用 ``process_monitor_run``：
1. 用 source_url 对比历史运行，找出本次新增结果；
2. 有新结果时写合成实体快照与 ``new_search_result`` 信号；
3. 调用告警规则匹配，并给工作区所有者发站内通知。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.collectors.endpoint_catalog import _ENDPOINT_TO_COLLECTOR
from data_intelligence_hub.models.entity import Entity, EntitySnapshot
from data_intelligence_hub.models.monitor import Monitor
from data_intelligence_hub.models.notification import Notification
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.signal import Signal
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services.alert_service import match_alert_rules_for_signal
from data_intelligence_hub.services.collector_catalog import validate_collector_config
from data_intelligence_hub.services.quick_collect_service import (
    build_collector_config,
)

_INTERVAL_CRON = {1: "0 * * * *", 6: "0 */6 * * *", 24: "0 3 * * *"}


class MonitorError(ValueError):
    """监控操作的业务错误。错误码直接回给调用方。"""


async def create_monitor(
    session: AsyncSession,
    *,
    workspace: Workspace,
    project_id: uuid.UUID,
    name: str,
    endpoint_type: str,
    params: dict[str, Any],
    interval_hours: int,
) -> Monitor:
    normalized_name = name.strip()
    if not normalized_name:
        raise MonitorError("monitor_name_required")
    cron = _INTERVAL_CRON.get(interval_hours)
    if cron is None:
        raise MonitorError("monitor_interval_invalid")
    collector_type = _ENDPOINT_TO_COLLECTOR.get(endpoint_type)
    if collector_type is None:
        raise MonitorError("monitor_endpoint_unknown")
    # 与 quick-collect 同一套装配：预设端点的缺省参数也会注入。
    config = build_collector_config(endpoint_type, collector_type, params)
    try:
        validate_collector_config(collector_type, config)
    except Exception as exc:  # noqa: BLE001 - 统一翻译成业务错误码
        raise MonitorError(f"monitor_params_invalid: {exc}") from exc

    monitor = Monitor(
        workspace_id=workspace.id,
        project_id=project_id,
        name=normalized_name,
        endpoint_type=endpoint_type,
        params=params,
        interval_hours=interval_hours,
        status="enabled",
    )
    session.add(monitor)
    await session.flush()

    source = Source(
        workspace_id=workspace.id,
        project_id=project_id,
        name=f"[monitor] {normalized_name}",
        type=collector_type,
        url=None,
        config=config,
        schedule_cron=cron,
        enabled=True,
    )
    session.add(source)
    await session.flush()

    task_config = {**config, "monitor_id": str(monitor.id)}
    task = CollectionTask(
        workspace_id=workspace.id,
        project_id=project_id,
        source_id=source.id,
        collector_type=collector_type,
        name=f"[monitor] {normalized_name}",
        schedule_cron=cron,
        status="enabled",
        config=task_config,
    )
    session.add(task)
    await session.flush()
    monitor.task_id = task.id
    await session.commit()
    await session.refresh(monitor)
    return monitor


async def list_monitors(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
) -> list[Monitor]:
    statement = select(Monitor).where(Monitor.workspace_id == workspace_id)
    if project_id is not None:
        statement = statement.where(Monitor.project_id == project_id)
    statement = statement.order_by(Monitor.created_at.desc())
    return list((await session.execute(statement)).scalars().all())


async def get_monitor(
    session: AsyncSession, workspace_id: uuid.UUID, monitor_id: uuid.UUID
) -> Monitor | None:
    result = await session.execute(
        select(Monitor).where(
            Monitor.id == monitor_id, Monitor.workspace_id == workspace_id
        )
    )
    return result.scalar_one_or_none()


async def set_monitor_status(
    session: AsyncSession,
    monitor: Monitor,
    status: str,
) -> Monitor:
    monitor.status = status
    if monitor.task_id is not None:
        task = await session.get(CollectionTask, monitor.task_id)
        if task is not None:
            task.status = "enabled" if status == "enabled" else "paused"
    await session.commit()
    await session.refresh(monitor)
    return monitor


async def process_monitor_run(
    session: AsyncSession,
    task: CollectionTask,
    run: TaskRun,
) -> int | None:
    """运行完成后判定新结果。返回新增条数；非监控任务返回 None。"""
    monitor_id_raw = (task.config or {}).get("monitor_id")
    if not monitor_id_raw:
        return None
    try:
        monitor_id = uuid.UUID(str(monitor_id_raw))
    except ValueError:
        return None
    monitor = await session.get(Monitor, monitor_id)
    if monitor is None:
        return None

    current = (
        await session.execute(
            select(RawRecord.id, RawRecord.source_url).where(
                RawRecord.task_run_id == run.id
            )
        )
    ).all()
    if not current:
        monitor.last_checked_at = datetime.now(UTC)
        monitor.last_new_count = 0
        await session.commit()
        return 0

    previous_urls = {
        url
        for (url,) in (
            await session.execute(
                select(RawRecord.source_url).where(
                    RawRecord.source_id == task.source_id,
                    RawRecord.task_run_id.is_not(None),
                    RawRecord.task_run_id != run.id,
                )
            )
        ).all()
        if url
    }
    new_rows = [(rid, url) for rid, url in current if url and url not in previous_urls]
    monitor.last_checked_at = datetime.now(UTC)
    monitor.last_new_count = len(new_rows)

    if new_rows:
        await _emit_new_results(
            session,
            monitor=monitor,
            task=task,
            run=run,
            new_rows=new_rows,
        )
    await session.commit()

    if new_rows:
        from data_intelligence_hub.services.webhook_service import dispatch_event

        try:
            await dispatch_event(
                session,
                workspace_id=monitor.workspace_id,
                event_type="monitor.new_results",
                payload={
                    "monitor_id": str(monitor.id),
                    "monitor_name": monitor.name,
                    "endpoint_type": monitor.endpoint_type,
                    "new_count": len(new_rows),
                    "new_urls": [url for _, url in new_rows[:20]],
                    "run_id": str(run.id),
                },
            )
        except Exception:  # noqa: BLE001 - 投递失败不改变监控结果
            await session.rollback()
    return len(new_rows)


async def _emit_new_results(
    session: AsyncSession,
    *,
    monitor: Monitor,
    task: CollectionTask,
    run: TaskRun,
    new_rows: list[tuple[uuid.UUID, str | None]],
) -> None:
    now = datetime.now(UTC)
    entity = (
        await session.execute(
            select(Entity).where(
                Entity.workspace_id == monitor.workspace_id,
                Entity.entity_type == "monitor",
                Entity.external_id == str(monitor.id),
            )
        )
    ).scalar_one_or_none()
    if entity is None:
        entity = Entity(
            workspace_id=monitor.workspace_id,
            project_id=monitor.project_id,
            entity_type="monitor",
            external_id=str(monitor.id),
            canonical_url=None,
            name=monitor.name,
            domain="monitor",
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(entity)
        await session.flush()

    previous_snapshot = (
        await session.execute(
            select(EntitySnapshot)
            .where(EntitySnapshot.entity_id == entity.id)
            .order_by(EntitySnapshot.captured_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    previous_value = 0
    if previous_snapshot is not None:
        raw_previous = (previous_snapshot.metrics or {}).get("new_results")
        if isinstance(raw_previous, int):
            previous_value = raw_previous

    snapshot = EntitySnapshot(
        entity_id=entity.id,
        raw_record_id=new_rows[0][0],
        snapshot_data={
            "monitor_id": str(monitor.id),
            "endpoint_type": monitor.endpoint_type,
            "run_id": str(run.id),
            "new_urls": [url for _, url in new_rows[:20]],
        },
        metrics={"new_results": len(new_rows)},
        captured_at=now,
        created_at=now,
    )
    session.add(snapshot)
    await session.flush()
    entity.latest_snapshot_id = snapshot.id
    entity.last_seen_at = now

    current_value = len(new_rows)
    signal = Signal(
        workspace_id=monitor.workspace_id,
        project_id=monitor.project_id,
        entity_id=entity.id,
        signal_type="new_search_result",
        previous_snapshot_id=(
            previous_snapshot.id if previous_snapshot is not None else snapshot.id
        ),
        current_snapshot_id=snapshot.id,
        current_value=float(current_value),
        previous_value=float(previous_value),
        delta=float(current_value - previous_value),
        delta_ratio=None,
        confidence=0.9,
        severity="high" if current_value >= 10 else "medium",
        metadata_json={
            "monitor_id": str(monitor.id),
            "endpoint_type": monitor.endpoint_type,
            "new_urls": [url for _, url in new_rows[:10]],
        },
        detected_at=now,
    )
    session.add(signal)
    await session.flush()

    workspace = await session.get(Workspace, monitor.workspace_id)
    if workspace is not None:
        await match_alert_rules_for_signal(session, workspace, signal, None)
        session.add(
            Notification(
                user_id=workspace.owner_id,
                title=f"监控「{monitor.name}」发现 {current_value} 条新结果",
                body=", ".join(url for _, url in new_rows[:3] if url),
                notification_type="monitor_new_results",
                reference_type="monitor",
                reference_id=monitor.id,
                is_read=False,
            )
        )
        await session.flush()