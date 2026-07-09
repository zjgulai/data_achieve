from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from data_intelligence_hub.api.deps import AuthContext, get_auth_context
from data_intelligence_hub.schemas.social_provider import (
    SocialDatasetPreviewRequest,
    SocialDatasetPreviewResponse,
    SocialNormalizationPreviewRequest,
    SocialNormalizationPreviewResponse,
    SocialProviderAdapterPlanRequest,
    SocialProviderAdapterPlanResponse,
    SocialProviderCatalogResponse,
    SocialProviderDependencyGateRequest,
    SocialProviderDependencyGateResponse,
    SocialProviderGateRequest,
    SocialProviderGateResponse,
    SocialProviderLiveApprovalTemplateRequest,
    SocialProviderLiveApprovalTemplateResponse,
    SocialProviderReadinessRequest,
    SocialProviderReadinessResponse,
    SocialProviderSourceTemplateRequest,
    SocialProviderSourceTemplateResponse,
    SocialRawPreviewRequest,
    SocialRawPreviewResponse,
)
from data_intelligence_hub.services.exceptions import (
    SocialProviderCatalogLoadError,
    SocialProviderGateAuthorizationError,
    SocialProviderUnknownPlatformError,
)
from data_intelligence_hub.services.social_provider import (
    get_social_provider_catalog,
    prepare_social_dataset_preview,
    prepare_social_normalization_preview,
    prepare_social_provider_adapter_plan,
    prepare_social_provider_dependency_gate,
    prepare_social_provider_gate,
    prepare_social_provider_live_approval_template,
    prepare_social_provider_readiness,
    prepare_social_provider_source_template,
    prepare_social_raw_preview,
)

router = APIRouter(tags=["automation"])


@router.get("/social-provider-catalog", response_model=SocialProviderCatalogResponse)
async def get_social_provider_catalog_item(
    context: Annotated[AuthContext, Depends(get_auth_context)],
    platform: str | None = None,
    data_domain: Annotated[str | None, Query(alias="data-domain")] = None,
    resource_group: Annotated[str | None, Query(alias="resource-group")] = None,
) -> SocialProviderCatalogResponse:
    _ = context
    try:
        return get_social_provider_catalog(
            platform=platform,
            data_domain=data_domain,
            resource_group=resource_group,
        )
    except SocialProviderCatalogLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc
    except SocialProviderUnknownPlatformError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc


@router.post("/social-provider-readiness", response_model=SocialProviderReadinessResponse)
async def prepare_social_provider_readiness_item(
    payload: SocialProviderReadinessRequest,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> SocialProviderReadinessResponse:
    _ = context
    try:
        return prepare_social_provider_readiness(payload)
    except SocialProviderUnknownPlatformError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc


@router.post("/social-provider-gate", response_model=SocialProviderGateResponse)
async def prepare_social_provider_gate_item(
    payload: SocialProviderGateRequest,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> SocialProviderGateResponse:
    _ = context
    try:
        return prepare_social_provider_gate(payload)
    except SocialProviderUnknownPlatformError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except SocialProviderGateAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc


@router.post(
    "/social-provider-live-approval-template",
    response_model=SocialProviderLiveApprovalTemplateResponse,
)
async def prepare_social_provider_live_approval_template_item(
    payload: SocialProviderLiveApprovalTemplateRequest,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> SocialProviderLiveApprovalTemplateResponse:
    _ = context
    try:
        return prepare_social_provider_live_approval_template(payload)
    except SocialProviderUnknownPlatformError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc


@router.post(
    "/social-provider-dependency-gate", response_model=SocialProviderDependencyGateResponse
)
async def prepare_social_provider_dependency_gate_item(
    payload: SocialProviderDependencyGateRequest,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> SocialProviderDependencyGateResponse:
    _ = context
    try:
        return prepare_social_provider_dependency_gate(payload)
    except SocialProviderUnknownPlatformError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc


@router.post("/social-provider-adapter-plan", response_model=SocialProviderAdapterPlanResponse)
async def prepare_social_provider_adapter_plan_item(
    payload: SocialProviderAdapterPlanRequest,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> SocialProviderAdapterPlanResponse:
    _ = context
    try:
        return prepare_social_provider_adapter_plan(payload)
    except SocialProviderUnknownPlatformError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc


@router.post(
    "/social-provider-source-template",
    response_model=SocialProviderSourceTemplateResponse,
)
async def prepare_social_provider_source_template_item(
    payload: SocialProviderSourceTemplateRequest,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> SocialProviderSourceTemplateResponse:
    _ = context
    try:
        return prepare_social_provider_source_template(payload)
    except SocialProviderUnknownPlatformError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc


@router.post("/social-raw-preview", response_model=SocialRawPreviewResponse)
async def prepare_social_raw_preview_item(
    payload: SocialRawPreviewRequest,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> SocialRawPreviewResponse:
    _ = context
    try:
        return prepare_social_raw_preview(payload)
    except SocialProviderUnknownPlatformError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc


@router.post(
    "/social-normalization-preview",
    response_model=SocialNormalizationPreviewResponse,
)
async def prepare_social_normalization_preview_item(
    payload: SocialNormalizationPreviewRequest,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> SocialNormalizationPreviewResponse:
    _ = context
    try:
        return prepare_social_normalization_preview(payload)
    except SocialProviderUnknownPlatformError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc


@router.post(
    "/social-dataset-preview",
    response_model=SocialDatasetPreviewResponse,
)
async def prepare_social_dataset_preview_item(
    payload: SocialDatasetPreviewRequest,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> SocialDatasetPreviewResponse:
    _ = context
    try:
        return prepare_social_dataset_preview(payload)
    except SocialProviderUnknownPlatformError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
