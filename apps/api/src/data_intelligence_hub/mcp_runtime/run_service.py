"""MCP 的运行查询服务。

只读。复用 ``runs``、``run_steps`` 与 ``raw_records``，不新建状态。
MCP 使用全局 token，没有工作区绑定；调用方必须自行提供 run_id。
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select

from data_intelligence_hub.collectors.exa_agent import cancel_agent_run
from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.models.authorization import Authorization
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.run_ledger import RunLedgerEntry
from data_intelligence_hub.models.task import TaskRun
from data_intelligence_hub.repositories import runs as runs_repository
from data_intelligence_hub.schemas.run import RunResponse, RunStepResponse
from data_intelligence_hub.services.raw_record_service import build_record_preview

RECORDS_PREVIEW_LIMIT = 20
RECORDS_MAX_LIMIT = 100


def _run_out_of_scope(
    run: Run,
    workspace_id: uuid.UUID | None,
    project_id: uuid.UUID | None,
) -> bool:
    """判断运行是否在调用方可见范围之外。

    ``workspace_id`` 与 ``project_id`` 都是可选上限：给 None 表示该维度不设限
    （全局 token 路径）。两个维度同时给出时都要满足。跨项目与跨工作区
    返回同一个 not-found，不区分「不存在」与「不属于」，防探测。
    """
    if workspace_id is not None and run.workspace_id != workspace_id:
        return True
    return project_id is not None and run.project_id != project_id


async def get_run_detail(
    run_id: uuid.UUID,
    *,
    workspace_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """返回一次运行的平铺摘要与步骤。项目密钥路径按 workspace 与项目隔离。"""
    async with async_session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None or _run_out_of_scope(run, workspace_id, project_id):
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
            "provider_run_id": payload["provider_run_id"],
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
    workspace_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """按运行分页返回原始记录。

    ``limit`` 限制在 1..100。``cursor`` 是上一页返回的偏移量字符串。
    先按 run_id 找到 task_runs，再按 task_run_id 查 raw_records。
    ``workspace_id`` 与 ``project_id`` 是归属上限，规则见 ``_run_out_of_scope``。
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
        if run is None or _run_out_of_scope(run, workspace_id, project_id):
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


async def stop_run(
    run_id: uuid.UUID,
    *,
    workspace_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """取消一次运行。项目密钥路径必须传 workspace_id 与 project_id 做租户隔离。"""
    async with async_session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None or _run_out_of_scope(run, workspace_id, project_id):
            raise ValueError("run_not_found")
        resolved_workspace_id = run.workspace_id
        previous_status = run.status
        provider_run_id = await session.scalar(
            select(TaskRun.provider_run_id)
            .where(
                TaskRun.run_id == run_id,
                TaskRun.provider_run_id.is_not(None),
            )
            .order_by(TaskRun.created_at.desc())
            .limit(1)
        )
        updated = await runs_repository.cancel_run(
            session,
            workspace_id=resolved_workspace_id,
            run_id=run_id,
        )
        await session.commit()
        remote_cancelled = (
            await cancel_agent_run(provider_run_id) if provider_run_id else None
        )
        if updated is not None:
            return {
                "run_id": str(run_id),
                "previous_status": previous_status,
                "status": updated.status,
                "cancelled": True,
                "provider_cancelled": remote_cancelled,
            }
        current = await session.get(Run, run_id)
        return {
            "run_id": str(run_id),
            "previous_status": previous_status,
            "status": current.status if current is not None else "unknown",
            "cancelled": False,
        }


async def get_project_balance(project_id: uuid.UUID) -> dict[str, Any]:
    """返回项目账本分项与有效授权上限。

    账本按 ``entry_kind`` 分开返回，不把预估值、预留额或权责发生额
    混成「已花费」。``spent_usd`` 只取 settle 与 release；
    没有任何结算行时为 ``None``，不把 0 当成已知花费。
    """
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                select(
                    RunLedgerEntry.entry_kind,
                    func.coalesce(func.sum(RunLedgerEntry.amount_usd), 0),
                    func.count(),
                )
                .join(Run, Run.id == RunLedgerEntry.run_id)
                .where(Run.project_id == project_id)
                .group_by(RunLedgerEntry.entry_kind)
            )
        ).all()
        budget = await session.scalar(
            select(func.sum(Authorization.max_cost_usd)).where(
                Authorization.project_id == project_id,
                Authorization.gate_status == "pass",
                Authorization.revoked_at.is_(None),
                Authorization.expires_at > func.now(),
            )
        )
        auth_count = await session.scalar(
            select(func.count())
            .select_from(Authorization)
            .where(
                Authorization.project_id == project_id,
                Authorization.gate_status == "pass",
                Authorization.revoked_at.is_(None),
                Authorization.expires_at > func.now(),
            )
        )

    amounts = {kind: amount for kind, amount, _count in rows}
    counts = {kind: int(count) for kind, _amount, count in rows}
    settled = [amounts[kind] for kind in ("settle", "release") if kind in amounts]
    spent = sum(settled) if settled else None
    budget_text = None if budget is None else str(budget)
    remaining = (
        str(budget - spent)
        if budget is not None and spent is not None and (auth_count or 0) == 1
        else None
    )
    if spent is not None:
        metering_status = "metered"
    elif amounts.get("accrued") is not None:
        metering_status = "accrued_only"
    else:
        metering_status = "unavailable"
    return {
        "project_id": str(project_id),
        "currency": "USD",
        "metering_status": metering_status,
        "spent_usd": None if spent is None else str(spent),
        "accrued_usd": str(amounts.get("accrued", 0)),
        "estimated_usd": str(amounts.get("estimate", 0)),
        "reserved_usd": str(amounts.get("reserve", 0)),
        "blocked_usd": str(amounts.get("block", 0)),
        "authorized_ceiling_usd": budget_text,
        "remaining_against_ceiling_usd": remaining,
        "ledger_entries": sum(counts.values()),
        "authorization_count": int(auth_count or 0),
    }
