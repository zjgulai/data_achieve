from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_auth_context
from data_intelligence_hub.schemas.capability_catalog import (
    AccessChannel,
    CapabilityAssertion,
    CapabilityImplementation,
    CapabilityOperation,
    CapabilityStatus,
    PlatformId,
    ResourceType,
)
from data_intelligence_hub.schemas.capability_matrix import (
    CapabilityImplementationDetail,
    CapabilityMatrixResponse,
)
from data_intelligence_hub.services.capability_governance.catalog_resolution import (
    CapabilityCatalogResolutionError,
    resolve_current_capability_catalog,
)
from data_intelligence_hub.services.capability_matrix import (
    build_capability_matrix,
    get_capability_implementation_detail,
    list_capability_assertions,
    list_capability_implementations,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityCatalogLoadError,
    CapabilityImplementationNotFoundError,
)

router = APIRouter(tags=["capabilities"])


@router.get("/matrix", response_model=CapabilityMatrixResponse)
async def get_capability_matrix(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> CapabilityMatrixResponse:
    _ = context
    try:
        catalog = await resolve_current_capability_catalog(session)
        return build_capability_matrix(catalog=catalog)
    except CapabilityCatalogResolutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
        ) from exc
    except CapabilityCatalogLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
        ) from exc


@router.get("/assertions", response_model=list[CapabilityAssertion])
async def get_capability_assertions(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    platform: PlatformId | None = None,
    access_channel: AccessChannel | None = None,
    resource_type: ResourceType | None = None,
    operation: CapabilityOperation | None = None,
    support_status: CapabilityStatus | None = None,
) -> list[CapabilityAssertion]:
    _ = context
    try:
        catalog = await resolve_current_capability_catalog(session)
        return list_capability_assertions(
            platform=platform,
            access_channel=access_channel,
            resource_type=resource_type,
            operation=operation,
            support_status=support_status,
            catalog=catalog,
        )
    except CapabilityCatalogResolutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
        ) from exc
    except CapabilityCatalogLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
        ) from exc


@router.get("/implementations", response_model=list[CapabilityImplementation])
async def get_capability_implementations(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    platform: PlatformId | None = None,
    access_channel: AccessChannel | None = None,
) -> list[CapabilityImplementation]:
    _ = context
    try:
        catalog = await resolve_current_capability_catalog(session)
        return list_capability_implementations(
            platform=platform,
            access_channel=access_channel,
            catalog=catalog,
        )
    except CapabilityCatalogResolutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
        ) from exc
    except CapabilityCatalogLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
        ) from exc


@router.get(
    "/implementations/{implementation_id}",
    response_model=CapabilityImplementationDetail,
)
async def get_capability_implementation(
    implementation_id: str,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> CapabilityImplementationDetail:
    _ = context
    try:
        catalog = await resolve_current_capability_catalog(session)
        return get_capability_implementation_detail(
            implementation_id,
            catalog=catalog,
        )
    except CapabilityCatalogResolutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
        ) from exc
    except CapabilityCatalogLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
        ) from exc
    except CapabilityImplementationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
