from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import check_database
from data_intelligence_hub.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> JSONResponse:
    settings = get_settings()
    database_status = await check_database()
    is_ready = database_status == "connected"
    response = HealthResponse(
        service=settings.app_name,
        environment=settings.app_env,
        status="ok" if is_ready else "degraded",
        database=database_status,
        scheduler_enabled=settings.scheduler_enabled,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=response.model_dump(),
    )
