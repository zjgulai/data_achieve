from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_auth_context
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.schemas.platform_credentials import (
    PlatformCredentialSettings,
    PlatformCredentialSettingsResponse,
    PlatformCredentialUpdateRequest,
)
from data_intelligence_hub.schemas.social_provider import SocialProviderCatalogResponse
from data_intelligence_hub.services.capability_governance.catalog_resolution import (
    CapabilityCatalogResolutionError,
    resolve_current_capability_catalog,
)
from data_intelligence_hub.services.platform_credentials import (
    PlatformCredentialCipher,
    PlatformCredentialError,
    PlatformCredentialForbiddenError,
    PlatformCredentialPlatformNotFoundError,
    PlatformCredentialVaultUnavailableError,
    list_platform_credentials,
    remove_platform_credentials,
    update_platform_credentials,
)
from data_intelligence_hub.services.social_provider import get_social_provider_catalog

router = APIRouter(tags=["settings"])


def _vault_write_enabled() -> bool:
    return get_settings().platform_credential_master_key is not None


def _credential_error(exc: PlatformCredentialError) -> HTTPException:
    if isinstance(exc, PlatformCredentialForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.code)
    if isinstance(exc, PlatformCredentialPlatformNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.code)
    if isinstance(exc, PlatformCredentialVaultUnavailableError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.code)
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.code)


async def _catalog(session: SessionDep) -> SocialProviderCatalogResponse:
    try:
        current = await resolve_current_capability_catalog(session)
        return get_social_provider_catalog(catalog=current)
    except CapabilityCatalogResolutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
        ) from exc


@router.get("/platform-credentials", response_model=PlatformCredentialSettingsResponse)
async def list_platform_credential_items(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> PlatformCredentialSettingsResponse:
    try:
        return await list_platform_credentials(
            session,
            user=context.user,
            workspace=context.workspace,
            catalog=await _catalog(session),
            vault_write_enabled=_vault_write_enabled(),
        )
    except PlatformCredentialError as exc:
        raise _credential_error(exc) from exc


@router.put(
    "/platform-credentials/{platform}",
    response_model=PlatformCredentialSettings,
)
async def update_platform_credential_item(
    platform: str,
    payload: PlatformCredentialUpdateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> PlatformCredentialSettings:
    master_key = get_settings().platform_credential_master_key
    if master_key is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="platform_credential_vault_unavailable",
        )
    try:
        return await update_platform_credentials(
            session,
            user=context.user,
            workspace=context.workspace,
            platform=platform,
            payload=payload,
            catalog=await _catalog(session),
            cipher=PlatformCredentialCipher.from_secret(master_key),
        )
    except PlatformCredentialError as exc:
        raise _credential_error(exc) from exc


@router.delete(
    "/platform-credentials/{platform}",
    response_model=PlatformCredentialSettings,
)
async def delete_platform_credential_item(
    platform: str,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> PlatformCredentialSettings:
    try:
        return await remove_platform_credentials(
            session,
            user=context.user,
            workspace=context.workspace,
            platform=platform,
            catalog=await _catalog(session),
            vault_write_enabled=_vault_write_enabled(),
        )
    except PlatformCredentialError as exc:
        raise _credential_error(exc) from exc
