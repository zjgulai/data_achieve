from __future__ import annotations

import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.dataset import Dataset, DatasetDriftEvent, DatasetVersion


async def get_dataset_by_name(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    name: str,
) -> Dataset | None:
    result = await session.execute(
        select(Dataset).where(
            Dataset.workspace_id == workspace_id,
            Dataset.name == name,
        )
    )
    return result.scalar_one_or_none()


async def get_dataset(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
) -> Dataset | None:
    result = await session.execute(
        select(Dataset).where(
            Dataset.workspace_id == workspace_id,
            Dataset.id == dataset_id,
        )
    )
    return result.scalar_one_or_none()


async def list_datasets(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    limit: int = 50,
) -> list[Dataset]:
    statement = select(Dataset).where(Dataset.workspace_id == workspace_id)
    if project_id is not None:
        statement = statement.where(Dataset.project_id == project_id)
    statement = statement.order_by(desc(Dataset.created_at)).limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_latest_dataset_version(
    session: AsyncSession,
    dataset_id: uuid.UUID,
) -> DatasetVersion | None:
    result = await session.execute(
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset_id)
        .order_by(desc(DatasetVersion.version_number))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_dataset_versions(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
    limit: int = 50,
) -> list[DatasetVersion]:
    result = await session.execute(
        select(DatasetVersion)
        .where(
            DatasetVersion.workspace_id == workspace_id,
            DatasetVersion.dataset_id == dataset_id,
        )
        .order_by(desc(DatasetVersion.version_number))
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_dataset_versions(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(DatasetVersion)
        .where(
            DatasetVersion.workspace_id == workspace_id,
            DatasetVersion.dataset_id == dataset_id,
        )
    )
    return int(result.scalar_one())


async def get_dataset_version(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
) -> DatasetVersion | None:
    result = await session.execute(
        select(DatasetVersion).where(
            DatasetVersion.workspace_id == workspace_id,
            DatasetVersion.dataset_id == dataset_id,
            DatasetVersion.id == version_id,
        )
    )
    return result.scalar_one_or_none()


async def create_dataset_drift_event(
    session: AsyncSession,
    event: DatasetDriftEvent,
) -> DatasetDriftEvent:
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


async def get_dataset_drift_event(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    event_id: uuid.UUID,
) -> DatasetDriftEvent | None:
    result = await session.execute(
        select(DatasetDriftEvent).where(
            DatasetDriftEvent.workspace_id == workspace_id,
            DatasetDriftEvent.id == event_id,
        )
    )
    return result.scalar_one_or_none()


async def count_dataset_drift_events(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID | None = None,
    dataset_version_id: uuid.UUID | None = None,
) -> int:
    statement = (
        select(func.count())
        .select_from(DatasetDriftEvent)
        .where(DatasetDriftEvent.workspace_id == workspace_id)
    )
    if dataset_id is not None:
        statement = statement.where(DatasetDriftEvent.dataset_id == dataset_id)
    if dataset_version_id is not None:
        statement = statement.where(DatasetDriftEvent.dataset_version_id == dataset_version_id)
    result = await session.execute(statement)
    return int(result.scalar_one())


async def list_dataset_drift_events(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID | None = None,
    dataset_version_id: uuid.UUID | None = None,
    limit: int = 20,
) -> list[DatasetDriftEvent]:
    statement = select(DatasetDriftEvent).where(DatasetDriftEvent.workspace_id == workspace_id)
    if dataset_id is not None:
        statement = statement.where(DatasetDriftEvent.dataset_id == dataset_id)
    if dataset_version_id is not None:
        statement = statement.where(DatasetDriftEvent.dataset_version_id == dataset_version_id)
    statement = statement.order_by(desc(DatasetDriftEvent.created_at)).limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())
