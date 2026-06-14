from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.scheduler import SchedulerTick


async def create_scheduler_tick(
    session: AsyncSession,
    tick: SchedulerTick,
) -> SchedulerTick:
    session.add(tick)
    await session.commit()
    await session.refresh(tick)
    return tick


async def get_latest_scheduler_tick(session: AsyncSession) -> SchedulerTick | None:
    statement = select(SchedulerTick).order_by(SchedulerTick.finished_at.desc()).limit(1)
    result = await session.execute(statement)
    return result.scalar_one_or_none()
