"""搜索监控接口。

创建时同步建一条执行任务，调度交给现有 scheduler。
暂停/恢复同时作用于监控与执行任务。
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from data_intelligence_hub.api.deps import AuthenticatedContextDep, SessionDep
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.schemas.monitor import CreateMonitorRequest, MonitorResponse
from data_intelligence_hub.services.monitor_service import (
    MonitorError,
    create_monitor,
    get_monitor,
    list_monitors,
    set_monitor_status,
)

router = APIRouter(tags=["monitors"])


@router.post("", response_model=MonitorResponse, status_code=status.HTTP_201_CREATED)
async def create_monitor_item(
    payload: CreateMonitorRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> MonitorResponse:
    project = await get_project(session, context.workspace.id, payload.project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="project_not_found"
        )
    try:
        monitor = await create_monitor(
            session,
            workspace=context.workspace,
            project_id=payload.project_id,
            name=payload.name,
            endpoint_type=payload.endpoint_type,
            params=payload.params,
            interval_hours=payload.interval_hours,
        )
    except MonitorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return MonitorResponse.model_validate(monitor)


@router.get("", response_model=list[MonitorResponse])
async def list_monitor_items(
    session: SessionDep,
    context: AuthenticatedContextDep,
    project_id: uuid.UUID | None = None,
) -> list[MonitorResponse]:
    rows = await list_monitors(
        session, workspace_id=context.workspace.id, project_id=project_id
    )
    return [MonitorResponse.model_validate(row) for row in rows]


async def _monitor_or_404(session, context, monitor_id):
    monitor = await get_monitor(session, context.workspace.id, monitor_id)
    if monitor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="monitor_not_found"
        )
    return monitor


@router.post("/{monitor_id}/pause", response_model=MonitorResponse)
async def pause_monitor_item(
    monitor_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> MonitorResponse:
    monitor = await _monitor_or_404(session, context, monitor_id)
    await set_monitor_status(session, monitor, "paused")
    return MonitorResponse.model_validate(monitor)


@router.post("/{monitor_id}/resume", response_model=MonitorResponse)
async def resume_monitor_item(
    monitor_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> MonitorResponse:
    monitor = await _monitor_or_404(session, context, monitor_id)
    await set_monitor_status(session, monitor, "enabled")
    return MonitorResponse.model_validate(monitor)