from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_auth_context
from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.schemas.automation import (
    AutomationBrowserAutomationPlanRequest,
    AutomationBrowserAutomationPlanResponse,
    AutomationBrowserDiagnosticJobCreateRequest,
    AutomationBrowserDiagnosticJobListResponse,
    AutomationBrowserDiagnosticJobResponse,
    AutomationBrowserDiagnosticRunListResponse,
    AutomationBrowserExecutableSpecDryRunRequest,
    AutomationBrowserExecutableSpecDryRunResponse,
    AutomationBrowserExecutorContractRequest,
    AutomationBrowserExecutorContractResponse,
    AutomationBrowserLocalRunnerRequest,
    AutomationBrowserLocalRunnerResultListResponse,
    AutomationBrowserLocalRunnerResultResponse,
    AutomationCapabilityProbeListResponse,
    AutomationCleaningPlanCreateRequest,
    AutomationCleaningPlanCreateResponse,
    AutomationCleaningPlanDryRunRequest,
    AutomationCleaningPlanDryRunResponse,
    AutomationCleaningPlanListResponse,
    AutomationExtractionPlanCreateRequest,
    AutomationExtractionPlanResponse,
    AutomationGitHubToolDatasetPreviewRequest,
    AutomationGitHubToolDatasetSaveRequest,
    AutomationGitHubToolDriftCheckRequest,
    AutomationGitHubToolDriftEventSaveRequest,
    AutomationGitHubToolReportAssetCreateRequest,
    AutomationGitHubToolReportAssetResponse,
    AutomationGitHubToolReportRequest,
    AutomationGitHubToolReportResponse,
    AutomationPlatformPackageListResponse,
    AutomationPlatformPackageResponse,
    AutomationProductBatchRunRequest,
    AutomationProductBatchRunResponse,
    AutomationProductDatasetExportCreateRequest,
    AutomationProductDatasetExportJobResponse,
    AutomationProductDatasetExportListResponse,
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
    AutomationSiteAnalysisDetailResponse,
    AutomationSiteAnalysisListResponse,
    AutomationSiteAnalysisRequest,
    AutomationSiteAnalysisResponse,
)
from data_intelligence_hub.services.automation_service import (
    analyze_site_for_collection,
    approve_product_schedule,
    build_browser_executor_contract,
    cancel_browser_diagnostic_job_asset,
    check_github_tool_drift,
    check_product_drift,
    create_browser_diagnostic_job_asset,
    create_cleaning_plan_asset,
    create_extraction_plan_from_site_analysis,
    create_github_tool_report_asset,
    create_product_dataset_export,
    create_product_drift_alert_events,
    create_product_drift_alert_rule,
    create_reviewed_product_fanout,
    discover_products_for_collection,
    dry_run_browser_executable_spec,
    dry_run_cleaning_plan,
    generate_github_tool_report,
    get_browser_diagnostic_job_asset,
    get_platform_package,
    get_product_dataset_export_file,
    get_site_analysis_history_detail,
    list_browser_diagnostic_job_assets,
    list_browser_diagnostic_job_run_assets,
    list_browser_diagnostics,
    list_capability_probes,
    list_cleaning_plan_assets,
    list_platform_packages,
    list_product_dataset_exports,
    list_product_dataset_versions,
    list_product_datasets,
    list_product_drift_events,
    list_site_analysis_history,
    persist_site_analysis_plan,
    preview_github_tool_dataset,
    preview_product_dataset,
    preview_product_drift_alert_rule,
    preview_product_fanout,
    run_browser_diagnostic_job_local,
    run_reviewed_product_batch,
    save_browser_automation_plan,
    save_github_tool_dataset_version,
    save_github_tool_drift_event,
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


@router.get("/platform-packages", response_model=AutomationPlatformPackageListResponse)
async def list_platform_packages_route(
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationPlatformPackageListResponse:
    del context
    return list_platform_packages()


@router.get(
    "/platform-packages/{package_id}",
    response_model=AutomationPlatformPackageResponse,
)
async def get_platform_package_route(
    package_id: str,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationPlatformPackageResponse:
    del context
    try:
        return get_platform_package(package_id)
    except CollectorError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/capability-probes", response_model=AutomationCapabilityProbeListResponse)
async def list_capability_probes_route(
    context: Annotated[AuthContext, Depends(get_auth_context)],
    platform_id: str | None = None,
) -> AutomationCapabilityProbeListResponse:
    del context
    try:
        return list_capability_probes(platform_id=platform_id)
    except CollectorError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/site-analysis", response_model=AutomationSiteAnalysisResponse)
async def analyze_site(
    payload: AutomationSiteAnalysisRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationSiteAnalysisResponse:
    try:
        result = await analyze_site_for_collection(payload)
        return await persist_site_analysis_plan(
            session,
            context.workspace,
            context.user,
            payload,
            result,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/site-analyses", response_model=AutomationSiteAnalysisListResponse)
async def list_site_analyses_route(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    project_id: uuid.UUID | None = None,
    target: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AutomationSiteAnalysisListResponse:
    return await list_site_analysis_history(
        session,
        context.workspace,
        project_id=project_id,
        target=target,
        limit=limit,
    )


@router.get(
    "/site-analyses/{site_analysis_id}",
    response_model=AutomationSiteAnalysisDetailResponse,
)
async def get_site_analysis_route(
    site_analysis_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationSiteAnalysisDetailResponse:
    try:
        return await get_site_analysis_history_detail(
            session,
            context.workspace,
            site_analysis_id,
        )
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/site-analyses/{site_analysis_id}/extraction-plans",
    response_model=AutomationExtractionPlanResponse,
)
async def create_extraction_plan_route(
    site_analysis_id: uuid.UUID,
    payload: AutomationExtractionPlanCreateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationExtractionPlanResponse:
    try:
        return await create_extraction_plan_from_site_analysis(
            session,
            context.workspace,
            context.user,
            site_analysis_id,
            payload,
        )
    except CollectorError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if str(exc) == "site_analysis_not_found"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.post(
    "/browser-automation-plans",
    response_model=AutomationBrowserAutomationPlanResponse,
)
async def save_browser_automation_plan_route(
    payload: AutomationBrowserAutomationPlanRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationBrowserAutomationPlanResponse:
    try:
        return await save_browser_automation_plan(
            session,
            context.workspace,
            context.user,
            payload,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/browser-diagnostics",
    response_model=AutomationBrowserDiagnosticRunListResponse,
)
async def list_browser_diagnostics_route(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    project_id: uuid.UUID | None = None,
    site_analysis_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AutomationBrowserDiagnosticRunListResponse:
    return await list_browser_diagnostics(
        session,
        context.workspace,
        project_id=project_id,
        site_analysis_id=site_analysis_id,
        limit=limit,
    )


@router.post(
    "/browser-automation-spec-dry-run",
    response_model=AutomationBrowserExecutableSpecDryRunResponse,
)
async def dry_run_browser_automation_spec_route(
    payload: AutomationBrowserExecutableSpecDryRunRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationBrowserExecutableSpecDryRunResponse:
    try:
        return await dry_run_browser_executable_spec(
            session,
            context.workspace,
            payload,
        )
    except CollectorError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if str(exc) in {"site_analysis_not_found", "extraction_plan_not_found"}
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.post(
    "/browser-diagnostic-jobs",
    response_model=AutomationBrowserDiagnosticJobResponse,
)
async def create_browser_diagnostic_job_route(
    payload: AutomationBrowserDiagnosticJobCreateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationBrowserDiagnosticJobResponse:
    try:
        return await create_browser_diagnostic_job_asset(
            session,
            context.workspace,
            context.user,
            payload,
        )
    except CollectorError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if str(exc)
            in {
                "site_analysis_not_found",
                "extraction_plan_not_found",
                "browser_diagnostic_run_not_found",
            }
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.get(
    "/browser-diagnostic-jobs",
    response_model=AutomationBrowserDiagnosticJobListResponse,
)
async def list_browser_diagnostic_jobs_route(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    project_id: uuid.UUID | None = None,
    site_analysis_id: uuid.UUID | None = None,
    extraction_plan_id: uuid.UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AutomationBrowserDiagnosticJobListResponse:
    return await list_browser_diagnostic_job_assets(
        session,
        context.workspace,
        project_id=project_id,
        site_analysis_id=site_analysis_id,
        extraction_plan_id=extraction_plan_id,
        status=status_filter,
        limit=limit,
    )


@router.get(
    "/browser-diagnostic-jobs/{diagnostic_job_id}",
    response_model=AutomationBrowserDiagnosticJobResponse,
)
async def get_browser_diagnostic_job_route(
    diagnostic_job_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationBrowserDiagnosticJobResponse:
    try:
        return await get_browser_diagnostic_job_asset(
            session,
            context.workspace,
            diagnostic_job_id,
        )
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/browser-diagnostic-jobs/{diagnostic_job_id}/cancel",
    response_model=AutomationBrowserDiagnosticJobResponse,
)
async def cancel_browser_diagnostic_job_route(
    diagnostic_job_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationBrowserDiagnosticJobResponse:
    try:
        return await cancel_browser_diagnostic_job_asset(
            session,
            context.workspace,
            diagnostic_job_id,
        )
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/browser-diagnostic-jobs/{diagnostic_job_id}/executor-contract",
    response_model=AutomationBrowserExecutorContractResponse,
)
async def build_browser_executor_contract_route(
    diagnostic_job_id: uuid.UUID,
    payload: AutomationBrowserExecutorContractRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationBrowserExecutorContractResponse:
    try:
        return await build_browser_executor_contract(
            session,
            context.workspace,
            diagnostic_job_id,
            payload,
        )
    except CollectorError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if str(exc) == "browser_diagnostic_job_not_found"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.post(
    "/browser-diagnostic-jobs/{diagnostic_job_id}/local-run",
    response_model=AutomationBrowserLocalRunnerResultResponse,
)
async def run_browser_diagnostic_job_local_route(
    diagnostic_job_id: uuid.UUID,
    payload: AutomationBrowserLocalRunnerRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationBrowserLocalRunnerResultResponse:
    try:
        return await run_browser_diagnostic_job_local(
            session,
            context.workspace,
            diagnostic_job_id,
            payload,
        )
    except CollectorError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if str(exc)
            in {
                "browser_diagnostic_job_not_found",
                "browser_diagnostic_run_not_found",
            }
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.get(
    "/browser-diagnostic-job-runs",
    response_model=AutomationBrowserLocalRunnerResultListResponse,
)
async def list_browser_diagnostic_job_runs_route(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    diagnostic_job_id: Annotated[uuid.UUID | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AutomationBrowserLocalRunnerResultListResponse:
    return await list_browser_diagnostic_job_run_assets(
        session,
        context.workspace,
        project_id=project_id,
        diagnostic_job_id=diagnostic_job_id,
        status=status_filter,
        limit=limit,
    )


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


@router.post(
    "/github-tool-dataset-preview",
    response_model=AutomationProductDatasetPreviewResponse,
)
async def preview_github_tool_dataset_route(
    payload: AutomationGitHubToolDatasetPreviewRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationProductDatasetPreviewResponse:
    try:
        return await preview_github_tool_dataset(session, context.workspace, payload)
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/cleaning-plan-dry-run", response_model=AutomationCleaningPlanDryRunResponse)
async def dry_run_cleaning_plan_route(
    payload: AutomationCleaningPlanDryRunRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationCleaningPlanDryRunResponse:
    try:
        return await dry_run_cleaning_plan(session, context.workspace, payload)
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/cleaning-plans", response_model=AutomationCleaningPlanCreateResponse)
async def create_cleaning_plan_route(
    payload: AutomationCleaningPlanCreateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationCleaningPlanCreateResponse:
    try:
        return await create_cleaning_plan_asset(
            session,
            context.workspace,
            context.user,
            payload,
        )
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/cleaning-plans", response_model=AutomationCleaningPlanListResponse)
async def list_cleaning_plans_route(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    project_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AutomationCleaningPlanListResponse:
    return await list_cleaning_plan_assets(
        session,
        context.workspace,
        project_id=project_id,
        limit=limit,
    )


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


@router.post("/github-tool-dataset-save", response_model=AutomationProductDatasetSaveResponse)
async def save_github_tool_dataset_route(
    payload: AutomationGitHubToolDatasetSaveRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationProductDatasetSaveResponse:
    try:
        return await save_github_tool_dataset_version(
            session,
            context.workspace,
            context.user,
            payload,
        )
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


@router.post("/github-tool-drift-check", response_model=AutomationProductDriftCheckResponse)
async def check_github_tool_drift_route(
    payload: AutomationGitHubToolDriftCheckRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationProductDriftCheckResponse:
    try:
        return await check_github_tool_drift(session, context.workspace, payload)
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


@router.post("/github-tool-drift-events", response_model=AutomationProductDriftEventResponse)
async def save_github_tool_drift_event_route(
    payload: AutomationGitHubToolDriftEventSaveRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationProductDriftEventResponse:
    try:
        return await save_github_tool_drift_event(session, context.workspace, payload)
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


@router.get("/github-tool-drift-events", response_model=AutomationProductDriftEventListResponse)
async def list_github_tool_drift_events_route(
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


@router.post("/github-tool-report", response_model=AutomationGitHubToolReportResponse)
async def generate_github_tool_report_route(
    payload: AutomationGitHubToolReportRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationGitHubToolReportResponse:
    try:
        return await generate_github_tool_report(session, context.workspace, payload)
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/github-tool-report-assets",
    response_model=AutomationGitHubToolReportAssetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_github_tool_report_asset_route(
    payload: AutomationGitHubToolReportAssetCreateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationGitHubToolReportAssetResponse:
    try:
        return await create_github_tool_report_asset(
            session,
            context.workspace,
            context.user,
            payload,
        )
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


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


@router.post(
    "/product-dataset-exports",
    response_model=AutomationProductDatasetExportJobResponse,
)
async def create_product_dataset_export_route(
    payload: AutomationProductDatasetExportCreateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AutomationProductDatasetExportJobResponse:
    try:
        return await create_product_dataset_export(
            session,
            context.workspace,
            context.user,
            payload,
        )
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/product-datasets/{dataset_id}/exports",
    response_model=AutomationProductDatasetExportListResponse,
)
async def list_product_dataset_exports_route(
    dataset_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    dataset_version_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AutomationProductDatasetExportListResponse:
    try:
        return await list_product_dataset_exports(
            session,
            context.workspace,
            dataset_id=dataset_id,
            dataset_version_id=dataset_version_id,
            limit=limit,
        )
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("/product-datasets/{dataset_id}/versions/{version_id}/exports/{export_job_id}/download")
async def download_product_dataset_export_route(
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    export_job_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> FileResponse:
    try:
        export_job, artifact_path = await get_product_dataset_export_file(
            session,
            context.workspace,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            export_job_id=export_job_id,
        )
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return FileResponse(
        artifact_path,
        media_type=export_job.content_type,
        filename=export_job.filename,
    )
