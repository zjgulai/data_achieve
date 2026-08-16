from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import Select, desc, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.dml import ReturningInsert

from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.workflow_plan import (
    MonitoringScope,
    QueryTerm,
    WorkflowPlan,
    WorkflowPlanSaveRequest,
    WorkflowVersion,
    WorkflowVersionScope,
)


def project_lock_statement(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> Select[tuple[Project]]:
    return (
        select(Project)
        .where(Project.workspace_id == workspace_id, Project.id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def lock_project_for_workflow_plan_save(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> Project | None:
    result = await session.execute(project_lock_statement(workspace_id, project_id))
    return result.scalar_one_or_none()


def workflow_plan_lock_statement(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
) -> Select[tuple[WorkflowPlan]]:
    return (
        select(WorkflowPlan)
        .where(
            WorkflowPlan.workspace_id == workspace_id,
            WorkflowPlan.project_id == project_id,
            WorkflowPlan.id == workflow_plan_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def get_workflow_plan_for_update(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
) -> WorkflowPlan | None:
    result = await session.execute(
        workflow_plan_lock_statement(workspace_id, project_id, workflow_plan_id)
    )
    return result.scalar_one_or_none()


async def get_workflow_plan(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
) -> WorkflowPlan | None:
    result = await session.execute(
        select(WorkflowPlan).where(
            WorkflowPlan.workspace_id == workspace_id,
            WorkflowPlan.project_id == project_id,
            WorkflowPlan.id == workflow_plan_id,
        )
    )
    return result.scalar_one_or_none()


async def list_workflow_plans(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
) -> list[WorkflowPlan]:
    result = await session.execute(
        select(WorkflowPlan)
        .where(
            WorkflowPlan.workspace_id == workspace_id,
            WorkflowPlan.project_id == project_id,
        )
        .order_by(desc(WorkflowPlan.updated_at), desc(WorkflowPlan.id))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def count_workflow_plans(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(WorkflowPlan)
        .where(
            WorkflowPlan.workspace_id == workspace_id,
            WorkflowPlan.project_id == project_id,
        )
    )
    return int(result.scalar_one())


async def get_workflow_version(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
    workflow_version_id: uuid.UUID,
) -> WorkflowVersion | None:
    result = await session.execute(
        select(WorkflowVersion).where(
            WorkflowVersion.workspace_id == workspace_id,
            WorkflowVersion.project_id == project_id,
            WorkflowVersion.workflow_plan_id == workflow_plan_id,
            WorkflowVersion.id == workflow_version_id,
        )
    )
    return result.scalar_one_or_none()


async def list_workflow_versions(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
) -> list[WorkflowVersion]:
    result = await session.execute(
        select(WorkflowVersion)
        .where(
            WorkflowVersion.workspace_id == workspace_id,
            WorkflowVersion.project_id == project_id,
            WorkflowVersion.workflow_plan_id == workflow_plan_id,
        )
        .order_by(desc(WorkflowVersion.version_number))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def list_workflow_version_scopes(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_version_id: uuid.UUID,
) -> list[WorkflowVersionScope]:
    result = await session.execute(
        select(WorkflowVersionScope)
        .where(
            WorkflowVersionScope.workspace_id == workspace_id,
            WorkflowVersionScope.project_id == project_id,
            WorkflowVersionScope.workflow_version_id == workflow_version_id,
        )
        .order_by(WorkflowVersionScope.ordinal)
    )
    return list(result.scalars().all())


async def list_query_terms_for_version(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_version_id: uuid.UUID,
) -> list[QueryTerm]:
    result = await session.execute(
        select(QueryTerm)
        .where(
            QueryTerm.workspace_id == workspace_id,
            QueryTerm.project_id == project_id,
            QueryTerm.workflow_version_id == workflow_version_id,
        )
        .order_by(QueryTerm.ordinal)
    )
    return list(result.scalars().all())


async def count_workflow_versions(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(WorkflowVersion)
        .where(
            WorkflowVersion.workspace_id == workspace_id,
            WorkflowVersion.project_id == project_id,
            WorkflowVersion.workflow_plan_id == workflow_plan_id,
        )
    )
    return int(result.scalar_one())


async def get_monitoring_scope_by_key(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    scope_key: str,
) -> MonitoringScope | None:
    result = await session.execute(
        select(MonitoringScope).where(
            MonitoringScope.workspace_id == workspace_id,
            MonitoringScope.project_id == project_id,
            MonitoringScope.scope_key == scope_key,
        )
    )
    return result.scalar_one_or_none()


async def list_monitoring_scopes(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
) -> list[MonitoringScope]:
    result = await session.execute(
        select(MonitoringScope)
        .where(
            MonitoringScope.workspace_id == workspace_id,
            MonitoringScope.project_id == project_id,
        )
        .order_by(desc(MonitoringScope.created_at), desc(MonitoringScope.id))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def count_monitoring_scopes(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(MonitoringScope)
        .where(
            MonitoringScope.workspace_id == workspace_id,
            MonitoringScope.project_id == project_id,
        )
    )
    return int(result.scalar_one())


async def get_workflow_plan_save_request(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
) -> WorkflowPlanSaveRequest | None:
    result = await session.execute(
        select(WorkflowPlanSaveRequest).where(
            WorkflowPlanSaveRequest.workspace_id == workspace_id,
            WorkflowPlanSaveRequest.created_by_user_id == created_by_user_id,
            WorkflowPlanSaveRequest.idempotency_scope == idempotency_scope,
            WorkflowPlanSaveRequest.idempotency_key_hash == idempotency_key_hash,
        )
    )
    return result.scalar_one_or_none()


def build_monitoring_scope_insert(
    values: Mapping[str, Any],
) -> ReturningInsert[tuple[uuid.UUID]]:
    return (
        insert(MonitoringScope)
        .values(**values)
        .on_conflict_do_nothing(index_elements=["project_id", "scope_key"])
        .returning(MonitoringScope.id)
    )


async def insert_monitoring_scope_on_conflict(
    session: AsyncSession,
    values: Mapping[str, Any],
) -> uuid.UUID | None:
    result = await session.execute(build_monitoring_scope_insert(values))
    return result.scalar_one_or_none()


async def add_workflow_plan(
    session: AsyncSession,
    plan: WorkflowPlan,
) -> WorkflowPlan:
    session.add(plan)
    await session.flush()
    return plan


async def add_workflow_version(
    session: AsyncSession,
    version: WorkflowVersion,
) -> WorkflowVersion:
    session.add(version)
    await session.flush()
    return version


async def add_workflow_version_scope(
    session: AsyncSession,
    association: WorkflowVersionScope,
) -> WorkflowVersionScope:
    session.add(association)
    await session.flush()
    return association


async def add_query_term(
    session: AsyncSession,
    query_term: QueryTerm,
) -> QueryTerm:
    session.add(query_term)
    await session.flush()
    return query_term


async def add_workflow_plan_save_request(
    session: AsyncSession,
    save_request: WorkflowPlanSaveRequest,
) -> WorkflowPlanSaveRequest:
    session.add(save_request)
    await session.flush()
    return save_request


__all__ = [
    "add_query_term",
    "add_workflow_plan",
    "add_workflow_plan_save_request",
    "add_workflow_version",
    "add_workflow_version_scope",
    "build_monitoring_scope_insert",
    "count_monitoring_scopes",
    "count_workflow_plans",
    "count_workflow_versions",
    "get_monitoring_scope_by_key",
    "get_workflow_plan",
    "get_workflow_plan_for_update",
    "get_workflow_plan_save_request",
    "get_workflow_version",
    "insert_monitoring_scope_on_conflict",
    "list_monitoring_scopes",
    "list_query_terms_for_version",
    "list_workflow_plans",
    "list_workflow_versions",
    "list_workflow_version_scopes",
    "lock_project_for_workflow_plan_save",
    "project_lock_statement",
    "workflow_plan_lock_statement",
]
