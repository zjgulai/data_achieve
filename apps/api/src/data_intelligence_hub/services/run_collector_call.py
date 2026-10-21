"""RunExecutor 的 collector 调用适配器。

本模块把一行 ``runs`` 转成一次 collector 调用。
采集逻辑全部来自 ``collector_service.execute_collector_call``。
本模块只做三件事：

1. 解析工作区与采集任务；
2. 建一行 ``task_runs``，供原始记录与日志关联；
3. 把调用结果写回 ``task_runs``。

成本字段从调用结果读取。结果没有该字段时返回 ``None``。
本模块不提交事务。事务边界由 worker 负责。
"""

from __future__ import annotations

import traceback
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from data_intelligence_hub.collectors.base import collector_log
from data_intelligence_hub.models.run import RunStep
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services.collector_service import (
    CollectionCallResult,
    _collection_timeout_seconds,
    _lock_task_for_run_or_raise,
    execute_collector_call,
)
from data_intelligence_hub.services.run_executor import RunRecord
from data_intelligence_hub.services.task_schedule_policy import (
    update_retry_state_after_run,
)

RUN_QUEUE_TRIGGER = "run_queue"


class RunCollectorCall:
    """把 ``runs`` 行兑现为一次 collector 调用。

    ``RunRecord`` 只声明执行字段。本适配器还要读 ``workspace_id`` 与
    ``task_id``。生产记录 ``OrmRunRecord`` 提供这两个字段。
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        trigger: str = RUN_QUEUE_TRIGGER,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._trigger = trigger
        self._clock = clock or (lambda: datetime.now(UTC))
        self._task_run_ids: dict[uuid.UUID, uuid.UUID] = {}
        self._previous_task_status: dict[uuid.UUID, str] = {}

    async def __call__(self, run: RunRecord) -> CollectionCallResult:
        workspace_id = _required_uuid(run, "workspace_id")
        task_id = _required_uuid(run, "task_id")
        workspace = await self._session.get(Workspace, workspace_id)
        if workspace is None:
            raise RuntimeError(f"工作区不存在：{workspace_id}")
        task = await self._session.scalar(
            select(CollectionTask).where(
                CollectionTask.id == task_id,
                CollectionTask.workspace_id == workspace_id,
            )
        )
        if task is None:
            raise RuntimeError(f"采集任务不存在：{task_id}")

        # 与调度器共用同一套任务护栏：
        # 锁定任务行；已暂停任务拒绝执行；同一任务不得并发执行。
        task = await _lock_task_for_run_or_raise(self._session, workspace, task)
        self._previous_task_status[task.id] = task.status
        task.status = "running"

        started_at = self._clock()
        timeout_seconds = _collection_timeout_seconds(task.config)
        logs: list[dict[str, Any]] = [
            collector_log(
                "task_run_created",
                f"Collection requested by {self._trigger}.",
            ),
            collector_log(
                "collector_execution_started",
                f"Starting collector {task.collector_type}.",
            ),
            collector_log(
                "collector_timeout_configured",
                f"Collector run timeout set to {timeout_seconds:g}s.",
            ),
        ]
        task_run = TaskRun(
            task_id=task.id,
            workspace_id=workspace.id,
            status="running",
            started_at=started_at,
            finished_at=None,
            records_count=0,
            entities_count=0,
            error_message=None,
            error_traceback=None,
            logs=logs,
            created_at=started_at,
            project_id=task.project_id,
            run_id=run.id,
        )
        self._session.add(task_run)
        await self._session.flush()
        self._task_run_ids[run.id] = task_run.id

        try:
            # 采集失败时回滚本次调用的部分写入。
            # 保存点不覆盖上面已 flush 的 task_runs 行。
            async with self._session.begin_nested():
                result = await execute_collector_call(
                    session=self._session,
                    workspace=workspace,
                    task=task,
                    task_run=task_run,
                    trigger=self._trigger,
                    timeout_seconds=timeout_seconds,
                    logs=logs,
                )
        except Exception as exc:
            await self._mark_failed(task_run, task, exc, logs)
            raise

        await self._mark_finished(task_run, task, result, logs)
        return result

    async def mirror_evidence_grade(
        self,
        run_id: uuid.UUID,
        grade: str | None,
    ) -> None:
        """把运行等级镜像到 ``task_runs.evidence_grade``。

        本方法只 flush。找不到对应的 ``task_runs`` 行时静默返回。
        """
        if grade is None:
            return
        task_run_id = self._task_run_ids.get(run_id)
        if task_run_id is None:
            task_run_id = await self._session.scalar(
                select(RunStep.task_run_id)
                .where(
                    RunStep.run_id == run_id,
                    RunStep.task_run_id.is_not(None),
                )
                .order_by(RunStep.step_index.desc())
                .limit(1)
            )
        if task_run_id is None:
            return
        await self._session.execute(
            update(TaskRun).where(TaskRun.id == task_run_id).values(evidence_grade=grade)
        )
        await self._session.flush()

    async def _mark_finished(
        self,
        task_run: TaskRun,
        task: CollectionTask,
        result: CollectionCallResult,
        logs: list[dict[str, Any]],
    ) -> None:
        """把调用结果写回 ``task_runs``。"""
        task_run.status = result.status
        task_run.finished_at = self._clock()
        task_run.records_count = result.records_count
        task_run.entities_count = result.entities_count
        task_run.error_message = result.error_message
        task_run.endpoint_type = result.endpoint_type or _endpoint_type(task.config)
        task_run.provider = result.provider
        task_run.unit = result.unit
        task_run.quantity = _as_decimal_or_none(result.quantity)
        task_run.unit_price = _as_decimal_or_none(result.unit_price)
        task_run.total_cost_usd = _as_decimal_or_none(result.total_cost_usd)
        task_run.logs = [dict(log) for log in logs]
        flag_modified(task_run, "logs")
        self._restore_task(task, status=result.status)
        await self._session.flush()

    async def _mark_failed(
        self,
        task_run: TaskRun,
        task: CollectionTask,
        exc: Exception,
        logs: list[dict[str, Any]],
    ) -> None:
        """采集抛异常时把 ``task_runs`` 置为 failed，再原样抛出。"""
        error_message = str(exc) or exc.__class__.__name__
        task_run.status = "failed"
        task_run.finished_at = self._clock()
        task_run.error_message = error_message
        task_run.error_traceback = traceback.format_exc()
        logs.append(collector_log("collector_failed", error_message, level="error"))
        task_run.logs = [dict(log) for log in logs]
        flag_modified(task_run, "logs")
        self._restore_task(task, status="failed")
        await self._session.flush()

    def _restore_task(self, task: CollectionTask, *, status: str) -> None:
        """恢复任务状态，并推进最近运行时间、计数与重试状态。"""
        task.status = self._previous_task_status.pop(task.id, "enabled")
        task.last_run_at = self._clock()
        if status in {"success", "ok", "empty"}:
            task.success_count += 1
        else:
            task.failure_count += 1
        next_config = update_retry_state_after_run(task.config, status)
        if next_config != task.config:
            task.config = next_config
            flag_modified(task, "config")


def _required_uuid(run: RunRecord, name: str) -> uuid.UUID:
    """读取运行记录上的必填 UUID 字段。"""
    value = getattr(run, name, None)
    if not isinstance(value, uuid.UUID):
        raise RuntimeError(f"运行记录缺少字段 {name}")
    return value


def _endpoint_type(config: dict[str, Any] | None) -> str | None:
    value = (config or {}).get("endpoint_type")
    return value if isinstance(value, str) else None


def _as_decimal_or_none(value: object) -> Decimal | None:
    """把金额转成 Decimal。空值返回 None。"""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool | float):
        return Decimal(str(value))
    if isinstance(value, int | str):
        return Decimal(value)
    return None


__all__ = ["RUN_QUEUE_TRIGGER", "RunCollectorCall"]
