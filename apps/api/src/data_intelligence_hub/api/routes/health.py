from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import (
    DatabaseSchemaStatus,
    check_database,
    check_database_schema,
)
from data_intelligence_hub.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> JSONResponse:
    settings = get_settings()
    database_status = await check_database()
    schema_status = DatabaseSchemaStatus(
        status="unavailable",
        current_revision=None,
        head_revision=None,
    )
    if database_status == "connected":
        schema_status = await check_database_schema()
    is_ready = database_status == "connected" and schema_status.status == "current"
    response = HealthResponse(
        service=settings.app_name,
        environment=settings.app_env,
        status="ok" if is_ready else "degraded",
        database=database_status,
        database_schema=schema_status.status,
        schema_revision=schema_status.current_revision,
        schema_head=schema_status.head_revision,
        scheduler_enabled=settings.scheduler_enabled,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=response.model_dump(by_alias=True),
    )
