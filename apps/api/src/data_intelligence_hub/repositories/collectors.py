from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.collector import Collector


async def list_collectors(session: AsyncSession) -> list[Collector]:
    result = await session.execute(select(Collector).order_by(Collector.type.asc()))
    return list(result.scalars().all())


async def get_collector_by_type(session: AsyncSession, collector_type: str) -> Collector | None:
    result = await session.execute(select(Collector).where(Collector.type == collector_type))
    return result.scalar_one_or_none()
