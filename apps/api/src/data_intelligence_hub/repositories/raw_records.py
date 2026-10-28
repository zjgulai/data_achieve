from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.raw_record import RawRecord


async def list_raw_records(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    source_id: uuid.UUID | None = None,
    task_run_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    domain: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[RawRecord]:
    """按工作区列原始记录，可按来源、运行、项目或业务域收窄。

    ``domain`` 走 ``raw_records.project_id -> projects.domain`` 的连接：
    记录本身没有域字段，域是项目属性。业务域页需要「该域采集到的真实
    记录」，没有这个参数时只能展示全域混合列表。
    """
    statement = select(RawRecord).where(RawRecord.workspace_id == workspace_id)
    if source_id is not None:
        statement = statement.where(RawRecord.source_id == source_id)
    if task_run_id is not None:
        statement = statement.where(RawRecord.task_run_id == task_run_id)
    if project_id is not None:
        statement = statement.where(RawRecord.project_id == project_id)
    if domain is not None:
        statement = statement.join(
            Project, Project.id == RawRecord.project_id
        ).where(Project.domain == domain)
    statement = statement.order_by(RawRecord.collected_at.desc()).limit(limit).offset(offset)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_raw_record(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    raw_record_id: uuid.UUID,
) -> RawRecord | None:
    result = await session.execute(
        select(RawRecord).where(
            RawRecord.id == raw_record_id,
            RawRecord.workspace_id == workspace_id,
        )
    )
    return result.scalar_one_or_none()


async def get_raw_record_by_hash(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    content_hash: str,
) -> RawRecord | None:
    result = await session.execute(
        select(RawRecord).where(
            RawRecord.workspace_id == workspace_id,
            RawRecord.source_id == source_id,
            RawRecord.content_hash == content_hash,
        )
    )
    return result.scalar_one_or_none()
