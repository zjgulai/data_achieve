"""列表富集：输入行 + 输出 schema，持久队列逐行处理。

创建接口只写 ``status=queued``。``EnrichmentWorkerRuntime`` 从数据库领取，
因此 API 进程重启后仍可恢复未完成任务。
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from string import Formatter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from data_intelligence_hub.collectors.exa_collector import ExaSearchCollector
from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.models.enrichment import EnrichmentJob, EnrichmentRow
from data_intelligence_hub.models.workspace import Workspace

_MAX_ROWS = 100
_PII_TOKENS = frozenset({
    "email", "e-mail", "phone", "telephone", "mobile", "contact",
    "邮箱", "电话", "手机", "联系人",
})
_RUN_COST_USD = "0.007"
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
    project_key_id: uuid.UUID | None = None,
) -> EnrichmentJob:
    normalized_name = name.strip()
    if not normalized_name:
        raise EnrichmentError("enrichment_name_required")
    if not items or len(items) > _MAX_ROWS:
        raise EnrichmentError("enrichment_rows_invalid")
    if not isinstance(output_schema, dict) or not output_schema:
        raise EnrichmentError("enrichment_schema_required")
    serialized_schema = str(output_schema).casefold()
    if any(token in serialized_schema for token in _PII_TOKENS):
        raise EnrichmentError("enrichment_pii_not_allowed")
    field_names = {field_name for item in items for field_name in item}
    try:
        formatter_fields = {
            field_name.split(".", 1)[0].split("[", 1)[0]
            for _, field_name, _, _ in Formatter().parse(query_template)
            if field_name
        }
    except ValueError as exc:
        raise EnrichmentError("enrichment_template_placeholder_required") from exc
    if not formatter_fields or not formatter_fields <= field_names:
        raise EnrichmentError("enrichment_template_placeholder_required")

    job = EnrichmentJob(
        workspace_id=workspace.id,
        project_id=project_id,
        name=normalized_name,
        query_template=query_template,
        output_schema=output_schema,
        project_key_id=project_key_id,
        status="queued",
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


async def process_job(
    job_id: uuid.UUID,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    before_row: Callable[[], Awaitable[None]] | None = None,
) -> None:
    """处理一条已领取任务。逐行提交；异常行不终止其余行。"""
    factory = session_factory or _session_factory
    async with factory() as session:
        job = await session.get(EnrichmentJob, job_id)
        if job is None:
            return
        rows = await get_rows(session, job_id)

    for row in rows:
        async with factory() as session:
            current = await session.get(EnrichmentRow, row.id)
            job = await session.get(EnrichmentJob, job_id)
            if current is None or job is None or current.status == "completed":
                continue
            try:
                if before_row is not None:
                    await before_row()
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

    async with factory() as session:
        job = await session.get(EnrichmentJob, job_id)
        if job is not None:
            job.status = "completed" if job.failed == 0 else "partial"
            job.finished_at = datetime.now(UTC)
            await session.commit()


async def _run_row(
    query: str, output_schema: dict[str, Any]
) -> tuple[dict[str, Any] | None, list[Any]]:
    result = None
    for attempt in range(3):
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
        if not result.errors:
            break
        transient = any(
            marker in " ".join(result.errors).lower()
            for marker in ("429", "500", "502", "503", "504", "timeout")
        )
        if not transient or attempt == 2:
            raise EnrichmentError("; ".join(result.errors[:2]))
        await asyncio.sleep(2**attempt)
    assert result is not None
    if not result.raw_records:
        raise EnrichmentError("enrichment_no_result")
    content = result.raw_records[0].content
    output = content.get("structured_output")
    if output is not None and not isinstance(output, dict):
        raise EnrichmentError("enrichment_output_not_object")
    citations = [
        {
            "url": record.content.get("url"),
            "request_id": record.content.get("request_id"),
            "grounding": record.content.get("grounding"),
        }
        for record in result.raw_records
        if record.content.get("url")
    ]
    return output, citations
