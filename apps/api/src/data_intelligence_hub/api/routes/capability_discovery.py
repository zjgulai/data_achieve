from __future__ import annotations

from types import TracebackType
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from data_intelligence_hub.api.deps import AuthContext, get_auth_context
from data_intelligence_hub.schemas.capability_discovery import (
    CapabilityDiscoveryPreviewRequest,
    CapabilityDiscoveryPreviewResponse,
)
from data_intelligence_hub.services.capability_discovery.preview import (
    build_capability_discovery_preview,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityDiscoveryContractInvalidError,
    CapabilityDiscoveryFixtureInvalidError,
    CapabilityDiscoveryFixtureUnknownError,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["capability-discovery"])


def _sanitized_exc_info(
    exc: Exception,
) -> tuple[type[RuntimeError], RuntimeError, TracebackType | None]:
    safe_error = RuntimeError(type(exc).__name__)
    return RuntimeError, safe_error, exc.__traceback__


@router.post(
    "/discovery/preview",
    response_model=CapabilityDiscoveryPreviewResponse,
)
async def preview_capability_discovery(
    payload: CapabilityDiscoveryPreviewRequest,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> CapabilityDiscoveryPreviewResponse:
    _ = context
    try:
        return build_capability_discovery_preview(payload)
    except CapabilityDiscoveryFixtureUnknownError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.message,
        ) from exc
    except CapabilityDiscoveryFixtureInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.message,
        ) from exc
    except CapabilityDiscoveryContractInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
        ) from exc
    except Exception as exc:
        logger.exception(
            "capability_discovery_preview_failed",
            error_type=type(exc).__name__,
            exc_info=_sanitized_exc_info(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="internal_server_error",
        ) from exc
