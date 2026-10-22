"""异步深度研究：创建任务并入队。

复用 B3 的 runs 队列与 worker：创建一条临时采集任务，写入
``status=queued`` 的运行，worker 领取后由 ExaAgentCollector 执行。
调用方用 run_id 轮询结果。
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.collectors.endpoint_catalog import _ENDPOINT_TO_COLLECTOR
from data_intelligence_hub.models.run import RunStatus
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.runs import create_run
from data_intelligence_hub.services.collector_catalog import validate_collector_config


class ResearchError(ValueError):
    """研究任务的业务错误。"""


async def start_research(
    session: AsyncSession,
    *,
    workspace: Workspace,
    project_id: uuid.UUID,
    query: str,
    effort: str = "medium",
    output_schema: dict[str, Any] | None = None,
    max_cost_dollars: float = 5,
    timeout_seconds: int = 600,
    label: str | None = None,
    trigger: str = "api",
) -> uuid.UUID:
    endpoint_type = "exa_agent_research"
    collector_type = _ENDPOINT_TO_COLLECTOR.get(endpoint_type)
    if collector_type is None:
        raise ResearchError("research_endpoint_unavailable")
    # 执行层的外层预算读 run_timeout_seconds；它必须大于采集器自身等待预算，
    # 否则 Agent 在完成前会被 asyncio.wait_for 取消。最多再留 30 秒收尾。
    outer_timeout = min(timeout_seconds + 30, 1800)
    config: dict[str, Any] = {
        "endpoint_type": endpoint_type,
        "query": query,
        "effort": effort,
        "max_cost_dollars": max_cost_dollars,
        "timeout_seconds": timeout_seconds,
        "run_timeout_seconds": outer_timeout,
    }
    if output_schema is not None:
        config["output_schema"] = output_schema
    try:
        validate_collector_config(collector_type, config)
    except Exception as exc:  # noqa: BLE001 - 统一翻译成业务错误码
        raise ResearchError(f"research_params_invalid: {exc}") from exc

    name = f"[research] {(label or query).strip()[:120]}"
    source = Source(
        workspace_id=workspace.id,
        project_id=project_id,
        name=name,
        type=collector_type,
        url=None,
        config=config,
        schedule_cron=None,
        enabled=True,
    )
    session.add(source)
    await session.flush()
    task = CollectionTask(
        workspace_id=workspace.id,
        project_id=project_id,
        source_id=source.id,
        collector_type=collector_type,
        name=name,
        schedule_cron=None,
        status="enabled",
        config=config,
    )
    session.add(task)
    await session.flush()

    run = await create_run(
        session,
        workspace_id=workspace.id,
        project_id=project_id,
        task_id=task.id,
        status=RunStatus.QUEUED,
        trigger=trigger,
    )
    await session.commit()
    return run.id