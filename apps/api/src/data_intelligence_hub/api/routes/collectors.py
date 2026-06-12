from __future__ import annotations

from fastapi import APIRouter

from data_intelligence_hub.api.deps import SessionDep
from data_intelligence_hub.repositories.collectors import list_collectors
from data_intelligence_hub.schemas.collector import CollectorResponse
from data_intelligence_hub.services.collector_catalog import ensure_collectors_seeded

router = APIRouter(tags=["collectors"])


@router.get("", response_model=list[CollectorResponse])
async def list_collector_items(session: SessionDep) -> list[CollectorResponse]:
    await ensure_collectors_seeded(session)
    collectors = await list_collectors(session)
    return [CollectorResponse.model_validate(collector) for collector in collectors]
