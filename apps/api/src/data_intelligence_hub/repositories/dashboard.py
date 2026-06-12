from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, NamedTuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.alert import AlertEvent, AlertRule
from data_intelligence_hub.models.entity import Entity, EntitySnapshot
from data_intelligence_hub.models.intelligence import Evidence, IntelligenceItem
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.signal import Signal
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun


class TopIntelligenceRow(NamedTuple):
    item: IntelligenceItem
    evidence_count: int


class RecentFailureRow(NamedTuple):
    task_id: uuid.UUID
    task_name: str
    status: str
    error_message: str | None
    created_at: datetime


async def count_sources(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    domain: str | None,
) -> int:
    statement = select(func.count(Source.id)).join(Project, Source.project_id == Project.id).where(
        Source.workspace_id == workspace_id
    )
    statement = _apply_project_filters(statement, Project, project_id, domain)
    result = await session.execute(statement)
    return int(result.scalar_one())


async def count_intelligence(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    domain: str | None,
    from_time: datetime | None,
    to_time: datetime | None,
) -> int:
    statement = select(func.count(IntelligenceItem.id)).where(
        IntelligenceItem.workspace_id == workspace_id
    )
    statement = _apply_intelligence_filters(statement, project_id, domain, from_time, to_time)
    result = await session.execute(statement)
    return int(result.scalar_one())


async def count_intelligence_by_type(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    domain: str | None,
    from_time: datetime | None,
    to_time: datetime | None,
) -> dict[str, int]:
    statement = (
        select(IntelligenceItem.intelligence_type, func.count(IntelligenceItem.id))
        .where(IntelligenceItem.workspace_id == workspace_id)
        .group_by(IntelligenceItem.intelligence_type)
    )
    statement = _apply_intelligence_filters(statement, project_id, domain, from_time, to_time)
    result = await session.execute(statement)
    return {row[0]: int(row[1]) for row in result.all()}


async def list_top_intelligence(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    domain: str | None,
    from_time: datetime | None,
    to_time: datetime | None,
    limit: int,
) -> list[TopIntelligenceRow]:
    evidence_counts = (
        select(Evidence.intelligence_id, func.count(Evidence.id).label("evidence_count"))
        .group_by(Evidence.intelligence_id)
        .subquery()
    )
    statement = (
        select(IntelligenceItem, func.coalesce(evidence_counts.c.evidence_count, 0))
        .outerjoin(evidence_counts, evidence_counts.c.intelligence_id == IntelligenceItem.id)
        .where(IntelligenceItem.workspace_id == workspace_id)
        .order_by(IntelligenceItem.final_score.desc(), IntelligenceItem.created_at.desc())
        .limit(limit)
    )
    statement = _apply_intelligence_filters(statement, project_id, domain, from_time, to_time)
    result = await session.execute(statement)
    return [
        TopIntelligenceRow(item=item, evidence_count=int(evidence_count))
        for item, evidence_count in result.all()
    ]


async def count_projects_by_domain(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    domain: str | None,
) -> dict[str, int]:
    statement = (
        select(Project.domain, func.count(Project.id))
        .where(Project.workspace_id == workspace_id)
        .group_by(Project.domain)
    )
    if domain is not None:
        statement = statement.where(Project.domain == domain)
    result = await session.execute(statement)
    return {row[0]: int(row[1]) for row in result.all()}


async def count_intelligence_by_domain(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    domain: str | None,
    from_time: datetime | None,
    to_time: datetime | None,
) -> dict[str, int]:
    statement = (
        select(IntelligenceItem.domain, func.count(IntelligenceItem.id))
        .where(IntelligenceItem.workspace_id == workspace_id)
        .group_by(IntelligenceItem.domain)
    )
    statement = _apply_intelligence_filters(statement, None, domain, from_time, to_time)
    result = await session.execute(statement)
    return {row[0]: int(row[1]) for row in result.all()}


async def count_signals_by_domain(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    domain: str | None,
    from_time: datetime | None,
    to_time: datetime | None,
) -> dict[str, int]:
    statement = (
        select(Project.domain, func.count(Signal.id))
        .join(Project, Signal.project_id == Project.id)
        .where(Signal.workspace_id == workspace_id)
        .group_by(Project.domain)
    )
    statement = _apply_signal_filters(statement, Project, None, domain, from_time, to_time)
    result = await session.execute(statement)
    return {row[0]: int(row[1]) for row in result.all()}


async def count_tasks(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    domain: str | None,
) -> tuple[int, int]:
    statement = select(CollectionTask.status).join(Project).where(
        CollectionTask.workspace_id == workspace_id
    )
    statement = _apply_project_filters(statement, Project, project_id, domain)
    result = await session.execute(statement)
    statuses = list(result.scalars().all())
    return len(statuses), sum(1 for status in statuses if status == "enabled")


async def task_run_status_counts(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    domain: str | None,
    from_time: datetime | None,
    to_time: datetime | None,
) -> dict[str, int]:
    statement = (
        select(TaskRun.status, func.count(TaskRun.id))
        .join(CollectionTask, TaskRun.task_id == CollectionTask.id)
        .join(Project, CollectionTask.project_id == Project.id)
        .where(TaskRun.workspace_id == workspace_id)
        .group_by(TaskRun.status)
    )
    statement = _apply_task_run_filters(statement, Project, project_id, domain, from_time, to_time)
    result = await session.execute(statement)
    return {row[0]: int(row[1]) for row in result.all()}


async def count_latest_failed_tasks(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    domain: str | None,
) -> int:
    latest_runs = (
        select(TaskRun.task_id, func.max(TaskRun.created_at).label("latest_created_at"))
        .where(TaskRun.workspace_id == workspace_id)
        .group_by(TaskRun.task_id)
        .subquery()
    )
    statement = (
        select(func.count(TaskRun.id))
        .join(
            latest_runs,
            (TaskRun.task_id == latest_runs.c.task_id)
            & (TaskRun.created_at == latest_runs.c.latest_created_at),
        )
        .join(CollectionTask, TaskRun.task_id == CollectionTask.id)
        .join(Project, CollectionTask.project_id == Project.id)
        .where(TaskRun.workspace_id == workspace_id, TaskRun.status == "failed")
    )
    statement = _apply_project_filters(statement, Project, project_id, domain)
    result = await session.execute(statement)
    return int(result.scalar_one())


async def count_active_alerts(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    domain: str | None,
    from_time: datetime | None,
    to_time: datetime | None,
) -> int:
    statement = (
        select(func.count(AlertEvent.id))
        .join(AlertRule, AlertEvent.rule_id == AlertRule.id)
        .join(Signal, AlertEvent.signal_id == Signal.id)
        .join(Project, Signal.project_id == Project.id)
        .where(
            AlertRule.workspace_id == workspace_id,
            AlertEvent.status.in_(["triggered", "sent", "acknowledged"]),
        )
    )
    statement = _apply_signal_filters(statement, Project, project_id, domain, from_time, to_time)
    result = await session.execute(statement)
    return int(result.scalar_one())


async def list_recent_failures(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    domain: str | None,
    limit: int,
) -> list[RecentFailureRow]:
    statement = (
        select(
            CollectionTask.id,
            CollectionTask.name,
            TaskRun.status,
            TaskRun.error_message,
            TaskRun.created_at,
        )
        .join(CollectionTask, TaskRun.task_id == CollectionTask.id)
        .join(Project, CollectionTask.project_id == Project.id)
        .where(TaskRun.workspace_id == workspace_id, TaskRun.status == "failed")
        .order_by(TaskRun.created_at.desc())
        .limit(limit)
    )
    statement = _apply_project_filters(statement, Project, project_id, domain)
    result = await session.execute(statement)
    return [
        RecentFailureRow(
            task_id=task_id,
            task_name=task_name,
            status=status,
            error_message=error_message,
            created_at=created_at,
        )
        for task_id, task_name, status, error_message, created_at in result.all()
    ]


async def list_snapshot_metrics(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    domain: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    statement = (
        select(EntitySnapshot.metrics)
        .join(Entity, EntitySnapshot.entity_id == Entity.id)
        .join(Project, Entity.project_id == Project.id)
        .where(Entity.workspace_id == workspace_id)
        .order_by(EntitySnapshot.created_at.desc())
        .limit(limit)
    )
    statement = _apply_project_filters(statement, Project, project_id, domain)
    result = await session.execute(statement)
    return [dict(item) for item in result.scalars().all()]


def _apply_intelligence_filters(
    statement: Any,
    project_id: uuid.UUID | None,
    domain: str | None,
    from_time: datetime | None,
    to_time: datetime | None,
) -> Any:
    if project_id is not None:
        statement = statement.where(IntelligenceItem.project_id == project_id)
    if domain is not None:
        statement = statement.where(IntelligenceItem.domain == domain)
    if from_time is not None:
        statement = statement.where(IntelligenceItem.created_at >= from_time)
    if to_time is not None:
        statement = statement.where(IntelligenceItem.created_at <= to_time)
    return statement


def _apply_signal_filters(
    statement: Any,
    project_model: type[Project],
    project_id: uuid.UUID | None,
    domain: str | None,
    from_time: datetime | None,
    to_time: datetime | None,
) -> Any:
    statement = _apply_project_filters(statement, project_model, project_id, domain)
    if from_time is not None:
        statement = statement.where(Signal.detected_at >= from_time)
    if to_time is not None:
        statement = statement.where(Signal.detected_at <= to_time)
    return statement


def _apply_task_run_filters(
    statement: Any,
    project_model: type[Project],
    project_id: uuid.UUID | None,
    domain: str | None,
    from_time: datetime | None,
    to_time: datetime | None,
) -> Any:
    statement = _apply_project_filters(statement, project_model, project_id, domain)
    if from_time is not None:
        statement = statement.where(TaskRun.created_at >= from_time)
    if to_time is not None:
        statement = statement.where(TaskRun.created_at <= to_time)
    return statement


def _apply_project_filters(
    statement: Any,
    project_model: type[Project],
    project_id: uuid.UUID | None,
    domain: str | None,
) -> Any:
    if project_id is not None:
        statement = statement.where(project_model.id == project_id)
    if domain is not None:
        statement = statement.where(project_model.domain == domain)
    return statement
