from __future__ import annotations

import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.automation_plan import ExtractionPlan, SiteAnalysis


async def create_site_analysis(
    session: AsyncSession,
    site_analysis: SiteAnalysis,
) -> SiteAnalysis:
    session.add(site_analysis)
    await session.flush()
    return site_analysis


async def create_extraction_plan(
    session: AsyncSession,
    extraction_plan: ExtractionPlan,
) -> ExtractionPlan:
    session.add(extraction_plan)
    await session.flush()
    return extraction_plan


async def commit_and_refresh_site_analysis_plan(
    session: AsyncSession,
    site_analysis: SiteAnalysis,
    extraction_plan: ExtractionPlan,
) -> tuple[SiteAnalysis, ExtractionPlan]:
    await session.commit()
    await session.refresh(site_analysis)
    await session.refresh(extraction_plan)
    return site_analysis, extraction_plan


async def commit_and_refresh_extraction_plan(
    session: AsyncSession,
    extraction_plan: ExtractionPlan,
) -> ExtractionPlan:
    await session.commit()
    await session.refresh(extraction_plan)
    return extraction_plan


async def get_site_analysis(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    site_analysis_id: uuid.UUID,
) -> SiteAnalysis | None:
    result = await session.execute(
        select(SiteAnalysis).where(
            SiteAnalysis.workspace_id == workspace_id,
            SiteAnalysis.id == site_analysis_id,
        )
    )
    return result.scalar_one_or_none()


async def list_site_analyses(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    target: str | None = None,
    limit: int = 50,
) -> list[SiteAnalysis]:
    statement = select(SiteAnalysis).where(SiteAnalysis.workspace_id == workspace_id)
    if project_id is not None:
        statement = statement.where(SiteAnalysis.project_id == project_id)
    if target is not None:
        statement = statement.where(SiteAnalysis.target == target)
    statement = statement.order_by(desc(SiteAnalysis.created_at)).limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def count_site_analyses(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    target: str | None = None,
) -> int:
    statement = select(func.count()).select_from(SiteAnalysis).where(
        SiteAnalysis.workspace_id == workspace_id,
    )
    if project_id is not None:
        statement = statement.where(SiteAnalysis.project_id == project_id)
    if target is not None:
        statement = statement.where(SiteAnalysis.target == target)
    result = await session.execute(statement)
    return int(result.scalar_one())


async def list_extraction_plans(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    site_analysis_id: uuid.UUID,
    limit: int = 50,
) -> list[ExtractionPlan]:
    result = await session.execute(
        select(ExtractionPlan)
        .where(
            ExtractionPlan.workspace_id == workspace_id,
            ExtractionPlan.site_analysis_id == site_analysis_id,
        )
        .order_by(desc(ExtractionPlan.version_number))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_latest_extraction_plan(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    site_analysis_id: uuid.UUID,
) -> ExtractionPlan | None:
    result = await session.execute(
        select(ExtractionPlan)
        .where(
            ExtractionPlan.workspace_id == workspace_id,
            ExtractionPlan.site_analysis_id == site_analysis_id,
        )
        .order_by(desc(ExtractionPlan.version_number))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def next_extraction_plan_version(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    site_analysis_id: uuid.UUID,
) -> int:
    result = await session.execute(
        select(func.max(ExtractionPlan.version_number)).where(
            ExtractionPlan.workspace_id == workspace_id,
            ExtractionPlan.site_analysis_id == site_analysis_id,
        )
    )
    current = result.scalar_one_or_none()
    return int(current or 0) + 1
