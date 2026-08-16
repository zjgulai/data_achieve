from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.provider_health import (
    ProviderHealthRouteFeedback,
    ProviderHealthSnapshot,
)


async def get_provider_health_snapshot_by_aggregation_key(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    aggregation_key: str,
) -> ProviderHealthSnapshot | None:
    result = await session.execute(
        select(ProviderHealthSnapshot).where(
            ProviderHealthSnapshot.workspace_id == workspace_id,
            ProviderHealthSnapshot.project_id == project_id,
            ProviderHealthSnapshot.aggregation_key == aggregation_key,
        )
    )
    return result.scalar_one_or_none()


async def list_provider_health_snapshots_for_scope(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    scope_key: str,
    for_update: bool = False,
) -> tuple[ProviderHealthSnapshot, ...]:
    statement = (
        select(ProviderHealthSnapshot)
        .where(
            ProviderHealthSnapshot.workspace_id == workspace_id,
            ProviderHealthSnapshot.project_id == project_id,
            ProviderHealthSnapshot.scope_key == scope_key,
        )
        .order_by(
            asc(ProviderHealthSnapshot.snapshot_version),
            asc(ProviderHealthSnapshot.id),
        )
    )
    if for_update:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    result = await session.execute(statement)
    return tuple(result.scalars().all())


async def list_provider_health_snapshots_for_candidates(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    platform_id: str,
    resource_type: str,
    operation: str,
    implementation_ids: Sequence[str],
) -> tuple[ProviderHealthSnapshot, ...]:
    result = await session.execute(
        select(ProviderHealthSnapshot)
        .where(
            ProviderHealthSnapshot.workspace_id == workspace_id,
            ProviderHealthSnapshot.project_id == project_id,
            ProviderHealthSnapshot.platform_id == platform_id,
            ProviderHealthSnapshot.resource_type == resource_type,
            ProviderHealthSnapshot.operation == operation,
            ProviderHealthSnapshot.implementation_id.in_(tuple(implementation_ids)),
        )
        .order_by(
            asc(ProviderHealthSnapshot.implementation_id),
            asc(ProviderHealthSnapshot.snapshot_version),
            asc(ProviderHealthSnapshot.id),
        )
    )
    return tuple(result.scalars().all())


async def add_provider_health_snapshot(
    session: AsyncSession,
    snapshot: ProviderHealthSnapshot,
) -> ProviderHealthSnapshot:
    session.add(snapshot)
    await session.flush()
    return snapshot


async def get_provider_health_feedback_by_key(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    feedback_key: str,
) -> ProviderHealthRouteFeedback | None:
    result = await session.execute(
        select(ProviderHealthRouteFeedback).where(
            ProviderHealthRouteFeedback.workspace_id == workspace_id,
            ProviderHealthRouteFeedback.project_id == project_id,
            ProviderHealthRouteFeedback.feedback_key == feedback_key,
        )
    )
    return result.scalar_one_or_none()


async def list_provider_health_feedbacks_for_route(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    route_key: str,
    for_update: bool = False,
) -> tuple[ProviderHealthRouteFeedback, ...]:
    statement = (
        select(ProviderHealthRouteFeedback)
        .where(
            ProviderHealthRouteFeedback.workspace_id == workspace_id,
            ProviderHealthRouteFeedback.project_id == project_id,
            ProviderHealthRouteFeedback.route_key == route_key,
        )
        .order_by(
            asc(ProviderHealthRouteFeedback.feedback_version),
            asc(ProviderHealthRouteFeedback.id),
        )
    )
    if for_update:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    result = await session.execute(statement)
    return tuple(result.scalars().all())


async def list_latest_provider_health_feedbacks(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    limit: int = 100,
) -> tuple[ProviderHealthRouteFeedback, ...]:
    if not 1 <= limit <= 100:
        raise ValueError("provider_health_feedback_page_size_invalid")
    result = await session.execute(
        select(ProviderHealthRouteFeedback)
        .where(
            ProviderHealthRouteFeedback.workspace_id == workspace_id,
            ProviderHealthRouteFeedback.project_id == project_id,
        )
        .order_by(
            desc(ProviderHealthRouteFeedback.evaluated_at),
            desc(ProviderHealthRouteFeedback.id),
        )
        .limit(limit)
    )
    return tuple(result.scalars().all())


async def add_provider_health_feedback(
    session: AsyncSession,
    feedback: ProviderHealthRouteFeedback,
) -> ProviderHealthRouteFeedback:
    session.add(feedback)
    await session.flush()
    return feedback


__all__ = [
    "add_provider_health_feedback",
    "add_provider_health_snapshot",
    "get_provider_health_feedback_by_key",
    "get_provider_health_snapshot_by_aggregation_key",
    "list_latest_provider_health_feedbacks",
    "list_provider_health_feedbacks_for_route",
    "list_provider_health_snapshots_for_candidates",
    "list_provider_health_snapshots_for_scope",
]
