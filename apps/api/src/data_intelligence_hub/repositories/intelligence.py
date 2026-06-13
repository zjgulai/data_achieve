from __future__ import annotations

import uuid
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.entity import Entity
from data_intelligence_hub.models.intelligence import (
    Evidence,
    IntelligenceFeedback,
    IntelligenceItem,
)
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.signal import Signal
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import TaskRun


class EvidenceWithTrace(NamedTuple):
    evidence: Evidence
    screenshot_url: str | None
    signal: Signal | None
    entity: Entity | None
    raw_record: RawRecord | None
    task_run: TaskRun | None
    source: Source | None


async def list_intelligence_items(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    intelligence_type: str | None = None,
    status: str | None = None,
    domain: str | None = None,
    sort: str | None = None,
) -> list[IntelligenceItem]:
    statement = select(IntelligenceItem).where(IntelligenceItem.workspace_id == workspace_id)
    if project_id is not None:
        statement = statement.where(IntelligenceItem.project_id == project_id)
    if intelligence_type is not None:
        statement = statement.where(IntelligenceItem.intelligence_type == intelligence_type)
    if status is not None:
        statement = statement.where(IntelligenceItem.status == status)
    if domain is not None:
        statement = statement.where(IntelligenceItem.domain == domain)

    if sort in {"created_at", "created"}:
        statement = statement.order_by(IntelligenceItem.created_at.desc())
    elif sort in {"updated_at", "updated"}:
        statement = statement.order_by(IntelligenceItem.updated_at.desc())
    else:
        statement = statement.order_by(
            IntelligenceItem.final_score.desc(),
            IntelligenceItem.created_at.desc(),
        )

    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_intelligence_item(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    intelligence_id: uuid.UUID,
) -> IntelligenceItem | None:
    result = await session.execute(
        select(IntelligenceItem).where(
            IntelligenceItem.workspace_id == workspace_id,
            IntelligenceItem.id == intelligence_id,
        )
    )
    return result.scalar_one_or_none()


async def get_intelligence_item_for_signal(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    signal_id: uuid.UUID,
) -> IntelligenceItem | None:
    result = await session.execute(
        select(IntelligenceItem)
        .join(Evidence, Evidence.intelligence_id == IntelligenceItem.id)
        .where(
            IntelligenceItem.workspace_id == workspace_id,
            Evidence.signal_id == signal_id,
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_evidences(
    session: AsyncSession,
    intelligence_id: uuid.UUID,
) -> list[Evidence]:
    result = await session.execute(
        select(Evidence)
        .where(Evidence.intelligence_id == intelligence_id)
        .order_by(Evidence.created_at.asc())
    )
    return list(result.scalars().all())


async def list_evidences_with_trace(
    session: AsyncSession,
    intelligence_id: uuid.UUID,
) -> list[EvidenceWithTrace]:
    result = await session.execute(
        select(Evidence, RawRecord.screenshot_url, Signal, Entity, RawRecord, TaskRun, Source)
        .outerjoin(RawRecord, Evidence.raw_record_id == RawRecord.id)
        .outerjoin(Signal, Evidence.signal_id == Signal.id)
        .outerjoin(Entity, Evidence.entity_id == Entity.id)
        .outerjoin(TaskRun, RawRecord.task_run_id == TaskRun.id)
        .outerjoin(Source, RawRecord.source_id == Source.id)
        .where(Evidence.intelligence_id == intelligence_id)
        .order_by(Evidence.created_at.asc())
    )
    return [
        EvidenceWithTrace(
            evidence=evidence,
            screenshot_url=screenshot_url,
            signal=signal,
            entity=entity,
            raw_record=raw_record,
            task_run=task_run,
            source=source,
        )
        for evidence, screenshot_url, signal, entity, raw_record, task_run, source in result.all()
    ]


async def count_evidences(
    session: AsyncSession,
    intelligence_id: uuid.UUID,
) -> int:
    result = await session.execute(
        select(func.count(Evidence.id)).where(Evidence.intelligence_id == intelligence_id)
    )
    return int(result.scalar_one())


async def count_evidences_for_items(
    session: AsyncSession,
    intelligence_ids: list[uuid.UUID],
) -> dict[uuid.UUID, int]:
    if not intelligence_ids:
        return {}
    result = await session.execute(
        select(Evidence.intelligence_id, func.count(Evidence.id))
        .where(Evidence.intelligence_id.in_(intelligence_ids))
        .group_by(Evidence.intelligence_id)
    )
    return {row[0]: int(row[1]) for row in result.all()}


async def create_feedback(
    session: AsyncSession,
    intelligence_id: uuid.UUID,
    user_id: uuid.UUID,
    feedback_type: str,
    comment: str | None,
) -> IntelligenceFeedback:
    feedback = IntelligenceFeedback(
        intelligence_id=intelligence_id,
        user_id=user_id,
        feedback_type=feedback_type,
        comment=comment,
    )
    session.add(feedback)
    await session.flush()
    return feedback
