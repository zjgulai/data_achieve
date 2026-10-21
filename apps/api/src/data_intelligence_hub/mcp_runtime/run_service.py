"""MCP 的运行查询服务。

只读。复用 ``runs``、``run_steps`` 与 ``raw_records``，不新建状态。
MCP 使用全局 token，没有工作区绑定；调用方必须自行提供 run_id。
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.task import TaskRun
from data_intelligence_hub.repositories import runs as runs_repository
from data_intelligence_hub.schemas.run import RunResponse, RunStepResponse
from data_intelligence_hub.services.raw_record_service import build_record_preview

RECORDS_PREVIEW_LIMIT = 20
RECORDS_MAX_LIMIT = 100


async def get_run_detail(run_id: uuid.UUID) -> dict[str, Any]:
    """返回一次运行的平铺摘要与步骤。未找到时抛 ``run_not_found``。"""
    async with async_session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None:
            raise ValueError("run_not_found")
        steps = await runs_repository.list_steps(session, run_id=run_id)
        payload = RunResponse.model_validate(run).model_dump(mode="json")
        return {
            "run_id": payload["id"],
            "status": payload["status"],
            "outcome": payload["outcome"],
            "records_count": payload["records_count"],
            "evidence_grade": payload["evidence_grade"],
            "cost": {
                "total_cost_usd": payload["total_cost_usd"],
            },
            "error_message": payload["error_message"],
            "started_at": payload["started_at"],
            "finished_at": payload["finished_at"],
            "steps": [
                RunStepResponse.model_validate(step).model_dump(mode="json")
                for step in steps
            ],
        }


async def list_run_records(
    run_id: uuid.UUID,
    *,
    limit: int = RECORDS_PREVIEW_LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    """按运行分页返回原始记录。

    ``limit`` 限制在 1..100。``cursor`` 是上一页返回的偏移量字符串。
    先按 run_id 找到 task_runs，再按 task_run_id 查 raw_records。
    """
    if limit < 1:
        raise ValueError("limit_invalid")
    if cursor is None or cursor == "":
        offset = 0
    else:
        try:
            offset = int(cursor)
        except ValueError as exc:
            raise ValueError("cursor_invalid") from exc
        if offset < 0:
            raise ValueError("cursor_invalid")
    limit = min(limit, RECORDS_MAX_LIMIT)

    async with async_session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None:
            raise ValueError("run_not_found")
        task_run_ids = list(
            (
                await session.scalars(
                    select(TaskRun.id).where(TaskRun.run_id == run_id)
                )
            ).all()
        )
        if not task_run_ids:
            return {
                "run_id": str(run_id),
                "items": [],
                "next_cursor": None,
                "records_total": 0,
            }
        total = await session.scalar(
            select(func.count())
            .select_from(RawRecord)
            .where(RawRecord.task_run_id.in_(task_run_ids))
        )
        rows = (
            await session.scalars(
                select(RawRecord)
                .where(RawRecord.task_run_id.in_(task_run_ids))
                .order_by(RawRecord.collected_at.desc(), RawRecord.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        total_count = int(total or 0)
        next_offset = offset + len(rows)
        return {
            "run_id": str(run_id),
            "items": [build_record_preview(row) for row in rows],
            "next_cursor": str(next_offset) if next_offset < total_count else None,
            "records_total": total_count,
        }
