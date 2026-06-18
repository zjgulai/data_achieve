from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_auth_context
from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.schemas.automation import (
    AutomationProductBatchRunRequest,
    AutomationProductBatchRunResponse,
    AutomationProductDatasetListResponse,
    AutomationProductDatasetPreviewRequest,
    AutomationProductDatasetPreviewResponse,
    AutomationProductDatasetSaveRequest,
    AutomationProductDatasetSaveResponse,
    AutomationProductDatasetVersionListResponse,
    AutomationProductDiscoveryRequest,
    AutomationProductDiscoveryResponse,
    AutomationProductDriftAlertEmailSendRequest,
    AutomationProductDriftAlertEmailSendResponse,
    AutomationProductDriftAlertEventCreateRequest,
    AutomationProductDriftAlertEventCreateResponse,
    AutomationProductDriftAlertNotificationSendRequest,
    AutomationProductDriftAlertNotificationSendResponse,
    AutomationProductDriftAlertPreviewRequest,
    AutomationProductDriftAlertPreviewResponse,
    AutomationProductDriftAlertRuleCreateRequest,
    AutomationProductDriftAlertRuleCreateResponse,
    AutomationProductDriftCheckRequest,
    AutomationProductDriftCheckResponse,
    AutomationProductDriftEventListResponse,
    AutomationProductDriftEventResponse,
    AutomationProductDriftEventSaveRequest,
    AutomationProductFanoutCreateRequest,
    AutomationProductFanoutCreateResponse,
    AutomationProductFanoutPreviewRequest,
    AutomationProductFanoutPreviewResponse,
    AutomationProductScheduleApproveRequest,
    AutomationProductScheduleApproveResponse,
    AutomationSiteAnalysisRequest,
    AutomationSiteAnalysisResponse,
)
from data_intelligence_hub.services.automation_service import (
    analyze_site_for_collection,
    approve_product_schedule,
    check_product_drift,
    create_product_drift_alert_events,
    create_product_drift_alert_rule,
    create_reviewed_product_fanout,
    discover_products_for_collection,
    list_product_dataset_versions,
    list_product_datasets,
    list_product_drift_events,
    preview_product_dataset,
    preview_product_drift_alert_rule,
    preview_product_fanout,
    run_reviewed_product_batch,
    save_product_dataset_version,
    save_product_drift_event,
    send_product_drift_alert_emails,
    send_product_drift_alert_notifications,
)
from data_intelligence_hub.services.exceptions import (
    CollectorConfigError,
    CollectorNotFoundError,
    ProjectNotFoundError,
)

router = APIRouter(tags=["automation"])


@router.post("/site-analysis", response_model=AutomationSiteAnalysisResponse)
async def analyze_site(
    payload: AutomationSiteAnalysisRequest,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationSiteAnalysisResponse:
    del context
    try:
        return await analyze_site_for_collection(payload)
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/product-discovery", response_model=AutomationProductDiscoveryResponse)
async def discover_products(
    payload: AutomationProductDiscoveryRequest,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationProductDiscoveryResponse:
    del context
    try:
        return await discover_products_for_collection(payload)
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/product-fanout-preview", response_model=AutomationProductFanoutPreviewResponse)
async def preview_product_fanout_route(
    payload: AutomationProductFanoutPreviewRequest,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationProductFanoutPreviewResponse:
    del context
    try:
        return await preview_product_fanout(payload)
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/product-fanout-create", response_model=AutomationProductFanoutCreateResponse)
async def create_product_fanout_route(
    payload: AutomationProductFanoutCreateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationProductFanoutCreateResponse:
    try:
        return await create_reviewed_product_fanout(session, context.workspace, payload)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except (CollectorError, CollectorNotFoundError, CollectorConfigError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/product-batch-run", response_model=AutomationProductBatchRunResponse)
async def run_product_batch_route(
    payload: AutomationProductBatchRunRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationProductBatchRunResponse:
    try:
        return await run_reviewed_product_batch(session, context.workspace, payload)
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/product-dataset-preview", response_model=AutomationProductDatasetPreviewResponse)
async def preview_product_dataset_route(
    payload: AutomationProductDatasetPreviewRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationProductDatasetPreviewResponse:
    try:
        return await preview_product_dataset(session, context.workspace, payload)
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/product-dataset-save", response_model=AutomationProductDatasetSaveResponse)
async def save_product_dataset_route(
    payload: AutomationProductDatasetSaveRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationProductDatasetSaveResponse:
    try:
        return await save_product_dataset_version(session, context.workspace, context.user, payload)
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/product-schedule-approve", response_model=AutomationProductScheduleApproveResponse)
async def approve_product_schedule_route(
    payload: AutomationProductScheduleApproveRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationProductScheduleApproveResponse:
    try:
        return await approve_product_schedule(session, context.workspace, payload)
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/product-drift-check", response_model=AutomationProductDriftCheckResponse)
async def check_product_drift_route(
    payload: AutomationProductDriftCheckRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationProductDriftCheckResponse:
    try:
        return await check_product_drift(session, context.workspace, payload)
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/product-drift-events", response_model=AutomationProductDriftEventResponse)
async def save_product_drift_event_route(
    payload: AutomationProductDriftEventSaveRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationProductDriftEventResponse:
    try:
        return await save_product_drift_event(session, context.workspace, payload)
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/product-drift-events", response_model=AutomationProductDriftEventListResponse)
async def list_product_drift_events_route(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    dataset_id: uuid.UUID | None = None,
    dataset_version_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AutomationProductDriftEventListResponse:
    return await list_product_drift_events(
        session,
        context.workspace,
        dataset_id=dataset_id,
        dataset_version_id=dataset_version_id,
        limit=limit,
    )


@router.post(
    "/product-drift-alert-preview",
    response_model=AutomationProductDriftAlertPreviewResponse,
)
async def preview_product_drift_alert_rule_route(
    payload: AutomationProductDriftAlertPreviewRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationProductDriftAlertPreviewResponse:
    try:
        return await preview_product_drift_alert_rule(session, context.workspace, payload)
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/product-drift-alert-rules",
    response_model=AutomationProductDriftAlertRuleCreateResponse,
)
async def create_product_drift_alert_rule_route(
    payload: AutomationProductDriftAlertRuleCreateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationProductDriftAlertRuleCreateResponse:
    try:
        return await create_product_drift_alert_rule(session, context.workspace, payload)
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/product-drift-alert-events",
    response_model=AutomationProductDriftAlertEventCreateResponse,
)
async def create_product_drift_alert_events_route(
    payload: AutomationProductDriftAlertEventCreateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationProductDriftAlertEventCreateResponse:
    try:
        return await create_product_drift_alert_events(session, context.workspace, payload)
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/product-drift-alert-notifications",
    response_model=AutomationProductDriftAlertNotificationSendResponse,
)
async def send_product_drift_alert_notifications_route(
    payload: AutomationProductDriftAlertNotificationSendRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationProductDriftAlertNotificationSendResponse:
    try:
        return await send_product_drift_alert_notifications(session, context.workspace, payload)
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/product-drift-alert-emails",
    response_model=AutomationProductDriftAlertEmailSendResponse,
)
async def send_product_drift_alert_emails_route(
    payload: AutomationProductDriftAlertEmailSendRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationProductDriftAlertEmailSendResponse:
    try:
        return await send_product_drift_alert_emails(session, context.workspace, payload)
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/product-datasets", response_model=AutomationProductDatasetListResponse)
async def list_product_datasets_route(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    project_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AutomationProductDatasetListResponse:
    return await list_product_datasets(
        session,
        context.workspace,
        project_id=project_id,
        limit=limit,
    )


@router.get(
    "/product-datasets/{dataset_id}/versions",
    response_model=AutomationProductDatasetVersionListResponse,
)
async def list_product_dataset_versions_route(
    dataset_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AutomationProductDatasetVersionListResponse:
    try:
        return await list_product_dataset_versions(
            session,
            context.workspace,
            dataset_id=dataset_id,
            limit=limit,
        )
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
