"""``run_evidence_grades`` 表的读写。

一次 run 只写一行等级结果。``run_id`` 唯一约束挡住重复写入。
仓储只调用 ``flush``。本模块不调用 ``commit``。

字段与 B2 的 ``RunEvidenceGrade`` dataclass 一一对应。
等级值只允许契约 §2.5 的五个取值。
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.run_evidence_grade import RunEvidenceGradeRecord
from data_intelligence_hub.tool_catalog.evidence_grade import EvidenceGrade


def _grade_value(grade: EvidenceGrade | str) -> str:
    """取等级字符串。StrEnum 与普通字符串都接受。"""
    value = grade.value if isinstance(grade, EvidenceGrade) else grade
    allowed = {item.value for item in EvidenceGrade}
    if value not in allowed:
        raise ValueError(f"未知的等级：{value}")
    return value


async def create_grade(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    live_call: bool,
    authorization_id: uuid.UUID | None,
    sample_n: int,
    required_n: int,
    window_days: int,
    required_window_days: int,
    source_count: int,
    required_source_count: int,
    grade: EvidenceGrade | str,
    entity_count: int = 0,
    required_entity_count: int = 0,
) -> RunEvidenceGradeRecord:
    """写入一行等级结果并 flush。

    ``run_id`` 已存在时，唯一约束会拒绝本次写入。
    调用方必须先确认本次 run 还没有等级行。
    """
    record = RunEvidenceGradeRecord(
        run_id=run_id,
        live_call=live_call,
        authorization_id=authorization_id,
        sample_n=sample_n,
        required_n=required_n,
        window_days=window_days,
        required_window_days=required_window_days,
        source_count=source_count,
        required_source_count=required_source_count,
        entity_count=entity_count,
        required_entity_count=required_entity_count,
        grade=_grade_value(grade),
    )
    session.add(record)
    await session.flush()
    return record


async def get_grade_by_run(
    session: AsyncSession,
    run_id: uuid.UUID,
) -> RunEvidenceGradeRecord | None:
    """按 run 取等级行。未命中返回 None。"""
    result = await session.execute(
        select(RunEvidenceGradeRecord).where(RunEvidenceGradeRecord.run_id == run_id)
    )
    return result.scalar_one_or_none()


__all__ = ["create_grade", "get_grade_by_run"]
