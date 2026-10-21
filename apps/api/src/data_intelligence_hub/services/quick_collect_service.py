"""一键采集的执行服务。

职责：把一次 quick-collect 请求兑现为 Source + Task + TaskRun。

不依赖 FastAPI：
抛领域异常，由 api/routes/quick_collect.py 映射为 HTTP 状态码。
这样 MCP 与 agent 可以在进程内直接调用，不必回环打自己的 HTTP 接口。

workspace 由调用方传入：
- HTTP 路由传已鉴权的 AuthContext.workspace（fail-closed）。
- MCP / agent 未传时回退 demo workspace（保持既有行为）。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.collectors.apify_actor import DEFAULT_MAX_TOTAL_CHARGE_USD
from data_intelligence_hub.collectors.endpoint_catalog import (
    _APIFY_ENDPOINT_DEFAULTS,
    _APIFY_INPUT_BUILDERS,
    _COLLECTOR_TEST_DEFAULTS,
    _ENDPOINT_TO_COLLECTOR,
    build_apify_actor_input,
)
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.collectors import get_collector_by_type
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.repositories.raw_records import list_raw_records
from data_intelligence_hub.repositories.workspaces import get_demo_workspace
from data_intelligence_hub.services.collector_catalog import (
    ensure_collectors_seeded,
    validate_collector_config,
)
from data_intelligence_hub.services.collector_service import execute_collection_task
from data_intelligence_hub.services.exceptions import (
    CollectorConfigError,
    CollectorNotFoundError,
    QuickCollectCollectorUnavailableError,
    QuickCollectDemoWorkspaceUnavailableError,
    QuickCollectExecutionError,
    QuickCollectUnknownEndpointError,
    QuickCollectUnknownProjectError,
)
from data_intelligence_hub.services.raw_record_service import build_record_preview
from data_intelligence_hub.services.run_queue import enqueue_run

# 执行元数据由服务端拥有，绝不能变成 Actor input。
RESERVED_PARAM_KEYS = frozenset(
    {
        "execution_origin",
        "tool_call",
        "schedule_policy",
        "schedule_cron",
        "freshness_target_hours",
        "max_retry_attempts",
        "retry_delay_minutes",
        "retry_attempts_used",
    }
)


class QuickCollectRequest(BaseModel):
    project_id: uuid.UUID
    endpoint_type: str = Field(min_length=1, max_length=100)
    params: dict[str, Any] = Field(default_factory=dict)
    label: str | None = Field(default=None, max_length=200)
    # Server-owned tool metadata. Never merged into collector params.
    tool_call: dict[str, Any] | None = None


# 回执里最多返回多少条原始记录。完整记录仍可按 task_run_id 分页查询。
QUICK_COLLECT_RECORDS_PREVIEW_LIMIT = 20


class QuickCollectResponse(BaseModel):
    task_run_id: uuid.UUID
    task_id: uuid.UUID
    source_id: uuid.UUID
    status: str
    records_count: int
    error_message: str | None
    # 一次回执即可判断结果、看到样本、读到用量与耗时。
    records: list[dict[str, Any]] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)
    timing: dict[str, Any] = Field(default_factory=dict)


class QuickCollectQueuedResponse(BaseModel):
    """异步提交的返回体。状态固定为 queued。"""

    run_id: uuid.UUID
    task_id: uuid.UUID
    source_id: uuid.UUID
    status: str


@dataclass(frozen=True)
class QuickCollectOutcome:
    """服务返回值。与响应模型分开，便于调用方按需取字段。"""

    run: TaskRun
    task_id: uuid.UUID
    source_id: uuid.UUID
    records: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class QuickCollectQueuedOutcome:
    """异步提交的返回值。对应 ``runs`` 里的一行 queued。"""

    run_id: uuid.UUID
    task_id: uuid.UUID
    source_id: uuid.UUID


@dataclass(frozen=True)
class PreparedQuickCollect:
    """一次 quick-collect 的落库结果。

    Source 与 CollectionTask 已 flush。事务尚未提交。
    """

    workspace: Workspace
    task: CollectionTask
    source_id: uuid.UUID
    task_id: uuid.UUID
    collector_type: str


def build_collector_config(
    endpoint_type: str,
    collector_type: str,
    raw_params: dict[str, Any],
) -> dict[str, Any]:
    """组装 collector config。

    三个来源的优先级由原实现固定，逐行照搬：

    1. 基础：endpoint_type + 过滤后的 params。
    2. collector 级默认值（按 collector_type 索引）覆盖基础。
    3. Apify 端点（按 endpoint_type 索引）整体重建 config。

    两个键空间不同，混用会静默取到错误默认值。
    """
    params = {key: value for key, value in raw_params.items() if key not in RESERVED_PARAM_KEYS}
    config: dict[str, Any] = {"endpoint_type": endpoint_type, **params}

    collector_defaults = _COLLECTOR_TEST_DEFAULTS.get(collector_type)
    if collector_defaults is not None:
        config = {"endpoint_type": endpoint_type, **collector_defaults, **params}

    apify_defaults = _APIFY_ENDPOINT_DEFAULTS.get(endpoint_type)
    if apify_defaults is not None:
        actor_id, base_input = apify_defaults
        input_builder = _APIFY_INPUT_BUILDERS.get(endpoint_type)
        actor_input = (
            input_builder(params)
            if input_builder is not None
            else build_apify_actor_input(base_input, params)
        )
        config = {
            "actor_id": actor_id,
            "actor_input": actor_input,
            "max_items": raw_params.get("maxItems") or raw_params.get("max_items") or 10,
            "max_total_charge_usd": raw_params.get(
                "max_total_charge_usd", DEFAULT_MAX_TOTAL_CHARGE_USD
            ),
            "run_timeout_seconds": raw_params.get("run_timeout_seconds", 600),
        }
    return config


async def run_quick_collect(
    session: AsyncSession,
    body: QuickCollectRequest,
    *,
    workspace: Workspace | None = None,
) -> QuickCollectOutcome:
    """同步执行一次 quick-collect。

    workspace 为 None 时回退 demo workspace。HTTP 路由必须显式传入，
    否则 fail-closed 鉴权形同虚设。

    同步路径的行为保持不变：先落 Source 与 Task，再同步执行，最后返回 TaskRun。
    """
    prepared = await _prepare_quick_collect(session, body, workspace)
    await session.commit()

    try:
        run: TaskRun = await execute_collection_task(
            session,
            prepared.workspace,
            prepared.task,
            trigger="quick_collect",
        )
    except Exception as exc:
        raise QuickCollectExecutionError(str(exc)) from exc

    preview = await list_raw_records(
        session,
        workspace_id=prepared.workspace.id,
        task_run_id=run.id,
        limit=QUICK_COLLECT_RECORDS_PREVIEW_LIMIT,
    )
    return QuickCollectOutcome(
        run=run,
        task_id=prepared.task_id,
        source_id=prepared.source_id,
        records=tuple(build_record_preview(record) for record in preview),
    )


async def enqueue_quick_collect(
    session: AsyncSession,
    body: QuickCollectRequest,
    *,
    workspace: Workspace | None = None,
) -> QuickCollectQueuedOutcome:
    """异步提交一次 quick-collect。

    Source、Task 与 ``runs`` 行在同一个事务里提交。
    worker 用 ``runs.task_id`` 找到要执行的任务。

    ``runs`` 表不可用时抛 ``RunQueueUnavailableError``。
    路由把它映射为 503。同步路径不受影响。
    """
    prepared = await _prepare_quick_collect(session, body, workspace)
    run_id = await enqueue_run(
        session,
        values={
            "workspace_id": prepared.workspace.id,
            "project_id": body.project_id,
            "task_id": prepared.task_id,
            "trigger": "api",
        },
    )
    await session.commit()
    return QuickCollectQueuedOutcome(
        run_id=run_id,
        task_id=prepared.task_id,
        source_id=prepared.source_id,
    )


async def _prepare_quick_collect(
    session: AsyncSession,
    body: QuickCollectRequest,
    workspace: Workspace | None,
) -> PreparedQuickCollect:
    """校验请求并落 Source 与 CollectionTask。

    只 flush，不 commit。调用方决定事务边界。
    同步路径在提交后执行。异步路径在同一次提交里再写一行 runs。
    """
    resolved = workspace if workspace is not None else await get_demo_workspace(session)
    if resolved is None:
        raise QuickCollectDemoWorkspaceUnavailableError()

    # 必须先确认 project 存在：sources/tasks 有 project_id 外键，
    # 直接插入会撞 ForeignKeyViolation → 500 并把 SQL 栈回给调用方。
    if await get_project(session, resolved.id, body.project_id) is None:
        raise QuickCollectUnknownProjectError(str(body.project_id))

    collector_type = _ENDPOINT_TO_COLLECTOR.get(body.endpoint_type)
    if collector_type is None:
        raise QuickCollectUnknownEndpointError(repr(body.endpoint_type))

    await ensure_collectors_seeded(session)
    collector_db = await get_collector_by_type(session, collector_type)
    if collector_db is None or not collector_db.enabled:
        raise QuickCollectCollectorUnavailableError(collector_type)

    config = build_collector_config(body.endpoint_type, collector_type, body.params)

    try:
        validated = validate_collector_config(collector_type, config)
    except (CollectorConfigError, CollectorNotFoundError) as exc:
        raise QuickCollectExecutionError.invalid_config(exc) from exc

    # Validators 只返回采集参数白名单。endpoint_type 必须保留：
    # 数据集平台归因要读 task.config["endpoint_type"]。
    validated["endpoint_type"] = body.endpoint_type
    validated["execution_origin"] = "quick_collect"
    validated["schedule_policy"] = "manual_refresh_only"
    if body.tool_call:
        validated["tool_call"] = body.tool_call

    label = (body.label or body.endpoint_type).strip()[:200]

    source = Source(
        workspace_id=resolved.id,
        project_id=body.project_id,
        name=f"[quick] {label}",
        type=collector_type,
        url=None,
        config=validated,
        schedule_cron=None,
        enabled=True,
    )
    session.add(source)
    await session.flush()

    task = CollectionTask(
        workspace_id=resolved.id,
        project_id=body.project_id,
        source_id=source.id,
        collector_type=collector_type,
        name=f"[quick] {label}",
        schedule_cron=None,
        status="enabled",
        config=validated,
    )
    session.add(task)
    await session.flush()

    return PreparedQuickCollect(
        workspace=resolved,
        task=task,
        source_id=source.id,
        task_id=task.id,
        collector_type=collector_type,
    )


def _decimal_text(value: Any) -> str | None:
    return None if value is None else str(value)


def _datetime_text(value: Any) -> str | None:
    return None if value is None else value.isoformat()


def to_response(outcome: QuickCollectOutcome) -> QuickCollectResponse:
    run = outcome.run
    duration_ms: int | None = None
    if run.started_at is not None and run.finished_at is not None:
        duration_ms = round(
            (run.finished_at - run.started_at).total_seconds() * 1000
        )
    records = list(outcome.records)
    return QuickCollectResponse(
        task_run_id=run.id,
        task_id=outcome.task_id,
        source_id=outcome.source_id,
        status=run.status,
        records_count=run.records_count,
        error_message=run.error_message,
        records=records,
        output={
            "records_count": run.records_count,
            "entities_count": run.entities_count,
            "records_returned": len(records),
            "records_truncated": run.records_count > len(records),
            "limit": QUICK_COLLECT_RECORDS_PREVIEW_LIMIT,
        },
        usage={
            "provider": run.provider,
            "provider_run_id": run.provider_run_id,
            "unit": run.unit,
            "quantity": _decimal_text(run.quantity),
            "unit_price": _decimal_text(run.unit_price),
            "total_cost_usd": _decimal_text(run.total_cost_usd),
        },
        timing={
            "started_at": _datetime_text(run.started_at),
            "finished_at": _datetime_text(run.finished_at),
            "duration_ms": duration_ms,
        },
    )


def to_queued_response(outcome: QuickCollectQueuedOutcome) -> QuickCollectQueuedResponse:
    return QuickCollectQueuedResponse(
        run_id=outcome.run_id,
        task_id=outcome.task_id,
        source_id=outcome.source_id,
        status="queued",
    )
