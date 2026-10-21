"""列表富集：输入行 + 输出 schema，逐行取结构化结果。

首版在 API 进程内用 asyncio 后台任务执行，逐行提交，状态可轮询。
进程重启会让未完成的任务停在 running；重跑请重新提交。
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.collectors.exa_collector import ExaSearchCollector
from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.models.enrichment import EnrichmentJob, EnrichmentRow
from data_intelligence_hub.models.workspace import Workspace

_MAX_ROWS = 100
_RUN_COST_USD = "0.007"
_background_tasks: set[asyncio.Task[Any]] = set()
# 测试可以替换为内存 sqlite 的 sessionmaker。
_session_factory = async_session_factory


class EnrichmentError(ValueError):
    """富集任务的业务错误。"""


async def start_enrichment(
    session: AsyncSession,
    *,
    workspace: Workspace,
    project_id: uuid.UUID,
    name: str,
    query_template: str,
    items: list[dict[str, Any]],
    output_schema: dict[str, Any],
) -> EnrichmentJob:
    normalized_name = name.strip()
    if not normalized_name:
        raise EnrichmentError("enrichment_name_required")
    if not items or len(items) > _MAX_ROWS:
        raise EnrichmentError("enrichment_rows_invalid")
    if not isinstance(output_schema, dict) or not output_schema:
        raise EnrichmentError("enrichment_schema_required")
    if "{" not in query_template:
        raise EnrichmentError("enrichment_template_placeholder_required")

    job = EnrichmentJob(
        workspace_id=workspace.id,
        project_id=project_id,
        name=normalized_name,
        query_template=query_template,
        output_schema=output_schema,
        status="running",
        total=len(items),
    )
    session.add(job)
    await session.flush()
    for index, item in enumerate(items):
        session.add(
            EnrichmentRow(
                job_id=job.id,
                row_index=index,
                input=item,
                status="pending",
                updated_at=datetime.now(UTC),
            )
        )
    await session.commit()
    await session.refresh(job)

    task = asyncio.create_task(_process_job(job.id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return job


async def list_jobs(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
) -> list[EnrichmentJob]:
    statement = select(EnrichmentJob).where(EnrichmentJob.workspace_id == workspace_id)
    if project_id is not None:
        statement = statement.where(EnrichmentJob.project_id == project_id)
    statement = statement.order_by(EnrichmentJob.created_at.desc())
    return list((await session.execute(statement)).scalars().all())


async def get_job(
    session: AsyncSession, workspace_id: uuid.UUID, job_id: uuid.UUID
) -> EnrichmentJob | None:
    job = await session.get(EnrichmentJob, job_id)
    if job is None or job.workspace_id != workspace_id:
        return None
    return job


async def get_rows(session: AsyncSession, job_id: uuid.UUID) -> list[EnrichmentRow]:
    rows = await session.execute(
        select(EnrichmentRow)
        .where(EnrichmentRow.job_id == job_id)
        .order_by(EnrichmentRow.row_index)
    )
    return list(rows.scalars().all())


async def _process_job(job_id: uuid.UUID) -> None:
    async with _session_factory() as session:
        job = await session.get(EnrichmentJob, job_id)
        if job is None:
            return
        rows = await get_rows(session, job_id)

    for row in rows:
        async with _session_factory() as session:
            current = await session.get(EnrichmentRow, row.id)
            job = await session.get(EnrichmentJob, job_id)
            if current is None or job is None:
                continue
            try:
                query = job.query_template.format(**current.input)
                output, citations = await _run_row(query, job.output_schema)
                current.output = output
                current.citations = citations
                current.status = "completed"
                current.cost_usd = _RUN_COST_USD
                current.error = None
                job.processed += 1
            except Exception as exc:  # noqa: BLE001 - 单行失败不终止任务
                current.status = "failed"
                current.error = f"{type(exc).__name__}: {exc}"[:500]
                job.failed += 1
            current.updated_at = datetime.now(UTC)
            await session.commit()

    async with _session_factory() as session:
        job = await session.get(EnrichmentJob, job_id)
        if job is not None:
            job.status = "completed" if job.failed == 0 else "partial"
            job.finished_at = datetime.now(UTC)
            await session.commit()


async def _run_row(
    query: str, output_schema: dict[str, Any]
) -> tuple[dict[str, Any] | None, list[Any]]:
    collector = ExaSearchCollector(
        {
            "query": query,
            "search_type": "auto",
            "num_results": 3,
            "contents_mode": "highlights",
            "output_schema": output_schema,
        }
    )
    result = await collector.collect()
    if result.errors:
        raise EnrichmentError("; ".join(result.errors[:2]))
    if not result.raw_records:
        raise EnrichmentError("enrichment_no_result")
    content = result.raw_records[0].content
    citations = [
        record.content.get("url")
        for record in result.raw_records
        if record.content.get("url")
    ]
    return content.get("structured_output"), citations