from __future__ import annotations

import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from data_intelligence_hub.models.automation_plan import (
    BrowserDiagnosticJob,
    BrowserDiagnosticJobRun,
    BrowserDiagnosticRun,
    ExtractionPlan,
    SiteAnalysis,
)


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


async def create_browser_diagnostic_run(
    session: AsyncSession,
    diagnostic_run: BrowserDiagnosticRun,
) -> BrowserDiagnosticRun:
    session.add(diagnostic_run)
    await session.flush()
    return diagnostic_run


async def create_browser_diagnostic_job(
    session: AsyncSession,
    diagnostic_job: BrowserDiagnosticJob,
) -> BrowserDiagnosticJob:
    session.add(diagnostic_job)
    await session.flush()
    return diagnostic_job


async def create_browser_diagnostic_job_run(
    session: AsyncSession,
    diagnostic_job_run: BrowserDiagnosticJobRun,
) -> BrowserDiagnosticJobRun:
    session.add(diagnostic_job_run)
    await session.flush()
    return diagnostic_job_run


async def commit_and_refresh_browser_diagnostic_job(
    session: AsyncSession,
    diagnostic_job: BrowserDiagnosticJob,
) -> BrowserDiagnosticJob:
    await session.commit()
    await session.refresh(diagnostic_job)
    return diagnostic_job


async def commit_and_refresh_browser_diagnostic_job_run(
    session: AsyncSession,
    diagnostic_job_run: BrowserDiagnosticJobRun,
) -> BrowserDiagnosticJobRun:
    await session.commit()
    await session.refresh(diagnostic_job_run)
    return diagnostic_job_run


async def get_browser_diagnostic_run(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    diagnostic_run_id: uuid.UUID,
) -> BrowserDiagnosticRun | None:
    result = await session.execute(
        select(BrowserDiagnosticRun).where(
            BrowserDiagnosticRun.workspace_id == workspace_id,
            BrowserDiagnosticRun.id == diagnostic_run_id,
        )
    )
    return result.scalar_one_or_none()


async def get_browser_diagnostic_job(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    diagnostic_job_id: uuid.UUID,
) -> BrowserDiagnosticJob | None:
    result = await session.execute(
        select(BrowserDiagnosticJob).where(
            BrowserDiagnosticJob.workspace_id == workspace_id,
            BrowserDiagnosticJob.id == diagnostic_job_id,
        )
    )
    return result.scalar_one_or_none()


async def get_browser_diagnostic_job_run(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    diagnostic_job_run_id: uuid.UUID,
) -> BrowserDiagnosticJobRun | None:
    result = await session.execute(
        select(BrowserDiagnosticJobRun).where(
            BrowserDiagnosticJobRun.workspace_id == workspace_id,
            BrowserDiagnosticJobRun.id == diagnostic_job_run_id,
        )
    )
    return result.scalar_one_or_none()


async def get_browser_diagnostic_job_by_fingerprint(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    request_fingerprint: str,
) -> BrowserDiagnosticJob | None:
    result = await session.execute(
        select(BrowserDiagnosticJob).where(
            BrowserDiagnosticJob.workspace_id == workspace_id,
            BrowserDiagnosticJob.request_fingerprint == request_fingerprint,
        )
    )
    return result.scalar_one_or_none()


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


async def list_browser_diagnostic_runs(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    site_analysis_id: uuid.UUID | None = None,
    limit: int = 50,
) -> list[BrowserDiagnosticRun]:
    statement = select(BrowserDiagnosticRun).where(
        BrowserDiagnosticRun.workspace_id == workspace_id
    )
    if project_id is not None:
        statement = statement.where(BrowserDiagnosticRun.project_id == project_id)
    if site_analysis_id is not None:
        statement = statement.where(BrowserDiagnosticRun.site_analysis_id == site_analysis_id)
    statement = statement.order_by(desc(BrowserDiagnosticRun.created_at)).limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def list_browser_diagnostic_jobs(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    site_analysis_id: uuid.UUID | None = None,
    extraction_plan_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[BrowserDiagnosticJob]:
    statement = select(BrowserDiagnosticJob).where(
        BrowserDiagnosticJob.workspace_id == workspace_id
    )
    if project_id is not None:
        statement = statement.where(BrowserDiagnosticJob.project_id == project_id)
    if site_analysis_id is not None:
        statement = statement.where(BrowserDiagnosticJob.site_analysis_id == site_analysis_id)
    if extraction_plan_id is not None:
        statement = statement.where(BrowserDiagnosticJob.extraction_plan_id == extraction_plan_id)
    if status is not None:
        statement = statement.where(BrowserDiagnosticJob.status == status)
    statement = statement.order_by(desc(BrowserDiagnosticJob.created_at)).limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def list_browser_diagnostic_job_runs(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    diagnostic_job_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[BrowserDiagnosticJobRun]:
    statement = (
        select(BrowserDiagnosticJobRun)
        .options(selectinload(BrowserDiagnosticJobRun.browser_diagnostic_job))
        .where(BrowserDiagnosticJobRun.workspace_id == workspace_id)
    )
    if project_id is not None:
        statement = statement.where(BrowserDiagnosticJobRun.project_id == project_id)
    if diagnostic_job_id is not None:
        statement = statement.where(
            BrowserDiagnosticJobRun.browser_diagnostic_job_id == diagnostic_job_id
        )
    if status is not None:
        statement = statement.where(BrowserDiagnosticJobRun.status == status)
    statement = statement.order_by(desc(BrowserDiagnosticJobRun.created_at)).limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def count_browser_diagnostic_runs(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    site_analysis_id: uuid.UUID | None = None,
) -> int:
    statement = select(func.count()).select_from(BrowserDiagnosticRun).where(
        BrowserDiagnosticRun.workspace_id == workspace_id,
    )
    if project_id is not None:
        statement = statement.where(BrowserDiagnosticRun.project_id == project_id)
    if site_analysis_id is not None:
        statement = statement.where(BrowserDiagnosticRun.site_analysis_id == site_analysis_id)
    result = await session.execute(statement)
    return int(result.scalar_one())


async def count_browser_diagnostic_jobs(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    site_analysis_id: uuid.UUID | None = None,
    extraction_plan_id: uuid.UUID | None = None,
    status: str | None = None,
) -> int:
    statement = select(func.count()).select_from(BrowserDiagnosticJob).where(
        BrowserDiagnosticJob.workspace_id == workspace_id,
    )
    if project_id is not None:
        statement = statement.where(BrowserDiagnosticJob.project_id == project_id)
    if site_analysis_id is not None:
        statement = statement.where(BrowserDiagnosticJob.site_analysis_id == site_analysis_id)
    if extraction_plan_id is not None:
        statement = statement.where(BrowserDiagnosticJob.extraction_plan_id == extraction_plan_id)
    if status is not None:
        statement = statement.where(BrowserDiagnosticJob.status == status)
    result = await session.execute(statement)
    return int(result.scalar_one())


async def count_browser_diagnostic_job_runs(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    diagnostic_job_id: uuid.UUID | None = None,
    status: str | None = None,
) -> int:
    statement = select(func.count()).select_from(BrowserDiagnosticJobRun).where(
        BrowserDiagnosticJobRun.workspace_id == workspace_id,
    )
    if project_id is not None:
        statement = statement.where(BrowserDiagnosticJobRun.project_id == project_id)
    if diagnostic_job_id is not None:
        statement = statement.where(
            BrowserDiagnosticJobRun.browser_diagnostic_job_id == diagnostic_job_id
        )
    if status is not None:
        statement = statement.where(BrowserDiagnosticJobRun.status == status)
    result = await session.execute(statement)
    return int(result.scalar_one())


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


async def get_extraction_plan(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    extraction_plan_id: uuid.UUID,
) -> ExtractionPlan | None:
    result = await session.execute(
        select(ExtractionPlan).where(
            ExtractionPlan.workspace_id == workspace_id,
            ExtractionPlan.id == extraction_plan_id,
        )
    )
    return result.scalar_one_or_none()


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
