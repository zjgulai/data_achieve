"""用量与成本接口。

按工作区隔离。``/summary`` 返回聚合；``/runs`` 返回逐次运行账本。
两者共用同一套成本口径，逐行之和等于聚合总量（unknown 除外）。
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from data_intelligence_hub.api.deps import AuthenticatedContextDep, SessionDep
from data_intelligence_hub.services.usage_service import (
    get_run_ledger,
    get_usage_summary,
)

router = APIRouter(tags=["usage"])


@router.get("/summary")
async def usage_summary(
    session: SessionDep,
    context: AuthenticatedContextDep,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict[str, object]:
    return await get_usage_summary(
        session,
        workspace_id=context.workspace.id,
        days=days,
        project_id=project_id,
    )


@router.get("/runs")
async def usage_runs(
    session: SessionDep,
    context: AuthenticatedContextDep,
    days: Annotated[int, Query(ge=1, le=365)] = 7,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    task_run_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict[str, object]:
    """逐次运行账本。

    回答「每次运行值不值」。每行带 ``cost_source``：

    - ``actual``：上游回报的真实花费。
    - ``estimated``：按价格簿估算。
    - ``unknown``：价格簿无此端点或计价方式无法换算。

    ``totals.cost_usd`` 只累加已知金额；``totals.unknown_cost_runs``
    单独计数，避免把「不知情」当成 0 而低估成本。
    """
    return await get_run_ledger(
        session,
        workspace_id=context.workspace.id,
        days=days,
        limit=limit,
        project_id=project_id,
        task_run_id=task_run_id,
    )
