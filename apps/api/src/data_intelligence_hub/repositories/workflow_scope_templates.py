from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.workflow_plan import (
    MonitoringScope,
    WorkflowPlanSaveRequest,
    WorkflowVersion,
    WorkflowVersionScope,
)
from data_intelligence_hub.models.workflow_scope_template import MonitoringScopeTemplate


async def get_monitoring_scope(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
) -> MonitoringScope | None:
    result = await session.execute(
        select(MonitoringScope).where(
            MonitoringScope.workspace_id == workspace_id,
            MonitoringScope.project_id == project_id,
            MonitoringScope.id == scope_id,
        )
    )
    return result.scalar_one_or_none()


async def get_workflow_version_by_id(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    version_id: uuid.UUID,
) -> WorkflowVersion | None:
    result = await session.execute(
        select(WorkflowVersion).where(
            WorkflowVersion.workspace_id == workspace_id,
            WorkflowVersion.project_id == project_id,
            WorkflowVersion.id == version_id,
        )
    )
    return result.scalar_one_or_none()


async def get_workflow_version_scope(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    scope_id: uuid.UUID,
) -> WorkflowVersionScope | None:
    result = await session.execute(
        select(WorkflowVersionScope).where(
            WorkflowVersionScope.workspace_id == workspace_id,
            WorkflowVersionScope.project_id == project_id,
            WorkflowVersionScope.workflow_version_id == version_id,
            WorkflowVersionScope.monitoring_scope_id == scope_id,
        )
    )
    return result.scalar_one_or_none()


async def add_monitoring_scope_template(
    session: AsyncSession,
    template: MonitoringScopeTemplate,
) -> MonitoringScopeTemplate:
    session.add(template)
    await session.flush()
    return template


async def add_scope_template_copy_request(
    session: AsyncSession,
    request: WorkflowPlanSaveRequest,
) -> WorkflowPlanSaveRequest:
    session.add(request)
    await session.flush()
    return request


__all__ = [
    "add_monitoring_scope_template",
    "add_scope_template_copy_request",
    "get_monitoring_scope",
    "get_workflow_version_by_id",
    "get_workflow_version_scope",
]
