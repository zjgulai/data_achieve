from __future__ import annotations

import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.dataset import CleaningPlan


async def create_cleaning_plan(
    session: AsyncSession,
    cleaning_plan: CleaningPlan,
) -> CleaningPlan:
    session.add(cleaning_plan)
    await session.flush()
    return cleaning_plan


async def commit_and_refresh_cleaning_plan(
    session: AsyncSession,
    cleaning_plan: CleaningPlan,
) -> CleaningPlan:
    await session.commit()
    await session.refresh(cleaning_plan)
    return cleaning_plan


async def get_cleaning_plan(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    cleaning_plan_id: uuid.UUID,
) -> CleaningPlan | None:
    result = await session.execute(
        select(CleaningPlan).where(
            CleaningPlan.workspace_id == workspace_id,
            CleaningPlan.id == cleaning_plan_id,
        )
    )
    return result.scalar_one_or_none()


async def list_cleaning_plans(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    limit: int = 50,
) -> list[CleaningPlan]:
    statement = select(CleaningPlan).where(CleaningPlan.workspace_id == workspace_id)
    if project_id is not None:
        statement = statement.where(CleaningPlan.project_id == project_id)
    statement = statement.order_by(desc(CleaningPlan.created_at)).limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def count_cleaning_plans(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
) -> int:
    statement = select(func.count()).select_from(CleaningPlan).where(
        CleaningPlan.workspace_id == workspace_id,
    )
    if project_id is not None:
        statement = statement.where(CleaningPlan.project_id == project_id)
    result = await session.execute(statement)
    return int(result.scalar_one())


async def next_cleaning_plan_version(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    name: str,
) -> int:
    result = await session.execute(
        select(func.max(CleaningPlan.version_number)).where(
            CleaningPlan.workspace_id == workspace_id,
            CleaningPlan.name == name,
        )
    )
    current = result.scalar_one_or_none()
    return int(current or 0) + 1
