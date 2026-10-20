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


class QuickCollectResponse(BaseModel):
    task_run_id: uuid.UUID
    task_id: uuid.UUID
    source_id: uuid.UUID
    status: str
    records_count: int
    error_message: str | None


@dataclass(frozen=True)
class QuickCollectOutcome:
    """服务返回值。与响应模型分开，便于调用方按需取字段。"""

    run: TaskRun
    task_id: uuid.UUID
    source_id: uuid.UUID


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
    """执行一次 quick-collect。

    workspace 为 None 时回退 demo workspace。HTTP 路由必须显式传入，
    否则 fail-closed 鉴权形同虚设。
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
    source_id = source.id
    task_id = task.id
    await session.commit()

    try:
        run: TaskRun = await execute_collection_task(
            session, resolved, task, trigger="quick_collect"
        )
    except Exception as exc:
        raise QuickCollectExecutionError(str(exc)) from exc

    return QuickCollectOutcome(run=run, task_id=task_id, source_id=source_id)


def to_response(outcome: QuickCollectOutcome) -> QuickCollectResponse:
    return QuickCollectResponse(
        task_run_id=outcome.run.id,
        task_id=outcome.task_id,
        source_id=outcome.source_id,
        status=outcome.run.status,
        records_count=outcome.run.records_count,
        error_message=outcome.run.error_message,
    )
