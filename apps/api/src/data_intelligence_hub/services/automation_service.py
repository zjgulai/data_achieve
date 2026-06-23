from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urldefrag, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.collectors.ecommerce_product_discovery import (
    EcommerceProductDiscoveryCollector,
)
from data_intelligence_hub.collectors.ecommerce_product_page import (
    ECOMMERCE_PRODUCT_FIELDS,
    EcommerceProductPageCollector,
)
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.models.alert import AlertEvent, AlertRule
from data_intelligence_hub.models.automation_plan import (
    BrowserDiagnosticJob,
    BrowserDiagnosticJobRun,
    BrowserDiagnosticRun,
    ExtractionPlan,
    SiteAnalysis,
)
from data_intelligence_hub.models.dataset import (
    CleaningPlan,
    Dataset,
    DatasetDriftEvent,
    DatasetExportJob,
    DatasetVersion,
)
from data_intelligence_hub.models.entity import Entity, EntitySnapshot
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.report import Report, ReportAuditEvent
from data_intelligence_hub.models.signal import Signal
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.alerts import (
    get_alert_event,
    get_alert_rule,
    list_alert_rules,
)
from data_intelligence_hub.repositories.automation_plans import (
    commit_and_refresh_browser_diagnostic_job,
    commit_and_refresh_browser_diagnostic_job_run,
    commit_and_refresh_extraction_plan,
    commit_and_refresh_site_analysis_plan,
    count_browser_diagnostic_job_runs,
    count_browser_diagnostic_jobs,
    count_browser_diagnostic_runs,
    count_site_analyses,
    create_browser_diagnostic_job_run,
    create_browser_diagnostic_run,
    create_extraction_plan,
    create_site_analysis,
    get_browser_diagnostic_job,
    get_browser_diagnostic_job_by_fingerprint,
    get_browser_diagnostic_run,
    get_extraction_plan,
    get_latest_extraction_plan,
    get_site_analysis,
    list_browser_diagnostic_job_runs,
    list_browser_diagnostic_jobs,
    list_browser_diagnostic_runs,
    list_extraction_plans,
    list_site_analyses,
    next_extraction_plan_version,
)
from data_intelligence_hub.repositories.automation_plans import (
    create_browser_diagnostic_job as insert_browser_diagnostic_job,
)
from data_intelligence_hub.repositories.cleaning_plans import (
    commit_and_refresh_cleaning_plan,
    count_cleaning_plans,
    create_cleaning_plan,
    get_cleaning_plan,
    list_cleaning_plans,
    next_cleaning_plan_version,
)
from data_intelligence_hub.repositories.datasets import (
    count_dataset_drift_events,
    count_dataset_versions,
    create_dataset_drift_event,
    create_dataset_export_job,
    get_dataset,
    get_dataset_by_name,
    get_dataset_drift_event,
    get_dataset_export_job,
    get_dataset_version,
    get_latest_dataset_version,
    list_dataset_drift_events,
    list_dataset_export_jobs,
    list_dataset_versions,
    list_datasets,
)
from data_intelligence_hub.repositories.entities import (
    get_entity_by_external_id,
    get_entity_snapshot,
)
from data_intelligence_hub.repositories.notifications import get_notification_by_reference
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.repositories.raw_records import list_raw_records
from data_intelligence_hub.repositories.reports import create_report, create_report_audit_event
from data_intelligence_hub.repositories.signals import get_signal, list_signals
from data_intelligence_hub.repositories.sources import get_source_by_type_url
from data_intelligence_hub.repositories.tasks import get_task, list_task_runs
from data_intelligence_hub.repositories.users import get_user_by_id
from data_intelligence_hub.scheduler.cron import UnsupportedCronExpression, cron_interval
from data_intelligence_hub.schemas.alert import (
    AlertEventResponse,
    AlertRuleCreateRequest,
    AlertRuleResponse,
)
from data_intelligence_hub.schemas.automation import (
    AutomationAgentReachChannelProbeResponse,
    AutomationBrowserAutomationPlanRequest,
    AutomationBrowserAutomationPlanResponse,
    AutomationBrowserCleaningRuleRequest,
    AutomationBrowserDiagnosticJobCreateRequest,
    AutomationBrowserDiagnosticJobListResponse,
    AutomationBrowserDiagnosticJobResponse,
    AutomationBrowserDiagnosticRunListResponse,
    AutomationBrowserDiagnosticRunResponse,
    AutomationBrowserExecutableSpecCheckResponse,
    AutomationBrowserExecutableSpecDryRunRequest,
    AutomationBrowserExecutableSpecDryRunResponse,
    AutomationBrowserExecutableSpecDryRunSummaryResponse,
    AutomationBrowserExecutorContractRequest,
    AutomationBrowserExecutorContractResponse,
    AutomationBrowserExecutorReadinessCheckResponse,
    AutomationBrowserFieldContractFieldRequest,
    AutomationBrowserLocalRunnerRequest,
    AutomationBrowserLocalRunnerResultListResponse,
    AutomationBrowserLocalRunnerResultResponse,
    AutomationCapabilityProbeBackendCandidateResponse,
    AutomationCapabilityProbeListResponse,
    AutomationCapabilityProbeResponse,
    AutomationCleaningPlanCreateRequest,
    AutomationCleaningPlanCreateResponse,
    AutomationCleaningPlanDryRunRequest,
    AutomationCleaningPlanDryRunResponse,
    AutomationCleaningPlanDryRunRowResponse,
    AutomationCleaningPlanDryRunSummaryResponse,
    AutomationCleaningPlanListResponse,
    AutomationCleaningPlanResponse,
    AutomationCleaningRuleInput,
    AutomationCleaningStepResponse,
    AutomationDatasetResponse,
    AutomationDatasetVersionResponse,
    AutomationDiscoveryPageStructureResponse,
    AutomationDiscoveryPlanResponse,
    AutomationExtractionPlanCreateRequest,
    AutomationExtractionPlanResponse,
    AutomationFanoutBatchPlanResponse,
    AutomationFanoutCandidateStatusResponse,
    AutomationFanoutCreateSummaryResponse,
    AutomationFanoutPersistedSourceResponse,
    AutomationFieldCandidateResponse,
    AutomationGitHubToolDatasetPreviewRequest,
    AutomationGitHubToolDatasetSaveRequest,
    AutomationGitHubToolDriftCheckRequest,
    AutomationGitHubToolDriftEventSaveRequest,
    AutomationGitHubToolReportAssetCreateRequest,
    AutomationGitHubToolReportAssetResponse,
    AutomationGitHubToolReportRepositoryResponse,
    AutomationGitHubToolReportRequest,
    AutomationGitHubToolReportResponse,
    AutomationGitHubToolReportSummaryResponse,
    AutomationPageStructureResponse,
    AutomationPlatformPackageCleaningRuleResponse,
    AutomationPlatformPackageFieldResponse,
    AutomationPlatformPackageFixtureResponse,
    AutomationPlatformPackageListResponse,
    AutomationPlatformPackageResponse,
    AutomationPlatformPackageRiskBoundaryResponse,
    AutomationPlatformPackageSampleUrlResponse,
    AutomationPlatformPackageSopLinkResponse,
    AutomationPlatformPackageStrategyResponse,
    AutomationPlatformProfileResponse,
    AutomationProductBatchFieldCompletenessResponse,
    AutomationProductBatchRunItemResponse,
    AutomationProductBatchRunRequest,
    AutomationProductBatchRunResponse,
    AutomationProductBatchRunSummaryResponse,
    AutomationProductCandidateResponse,
    AutomationProductDatasetExportCreateRequest,
    AutomationProductDatasetExportJobResponse,
    AutomationProductDatasetExportListResponse,
    AutomationProductDatasetListItemResponse,
    AutomationProductDatasetListResponse,
    AutomationProductDatasetPreviewRequest,
    AutomationProductDatasetPreviewResponse,
    AutomationProductDatasetRowResponse,
    AutomationProductDatasetSaveRequest,
    AutomationProductDatasetSaveResponse,
    AutomationProductDatasetSummaryResponse,
    AutomationProductDatasetVersionListResponse,
    AutomationProductDiscoveryRequest,
    AutomationProductDiscoveryResponse,
    AutomationProductDriftAlertEmailDeliveryResponse,
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
    AutomationProductDriftAlertRuleDraftResponse,
    AutomationProductDriftAlertSummaryResponse,
    AutomationProductDriftCheckRequest,
    AutomationProductDriftCheckResponse,
    AutomationProductDriftEventListResponse,
    AutomationProductDriftEventResponse,
    AutomationProductDriftEventSaveRequest,
    AutomationProductDriftItemResponse,
    AutomationProductDriftSummaryResponse,
    AutomationProductFanoutCreateRequest,
    AutomationProductFanoutCreateResponse,
    AutomationProductFanoutPreviewRequest,
    AutomationProductFanoutPreviewResponse,
    AutomationProductScheduleApproveRequest,
    AutomationProductScheduleApproveResponse,
    AutomationProductScheduleApproveSummaryResponse,
    AutomationScheduleApprovedTaskResponse,
    AutomationScheduleBlockedTaskResponse,
    AutomationSiteAnalysisDetailResponse,
    AutomationSiteAnalysisHistoryItemResponse,
    AutomationSiteAnalysisListResponse,
    AutomationSiteAnalysisRequest,
    AutomationSiteAnalysisResponse,
    AutomationSourceDraftResponse,
    AutomationToolRecommendationResponse,
)
from data_intelligence_hub.schemas.notification import NotificationResponse
from data_intelligence_hub.schemas.report import ReportResponse
from data_intelligence_hub.schemas.signal import SignalResponse
from data_intelligence_hub.schemas.source import SourceCreateRequest, SourceResponse
from data_intelligence_hub.schemas.task import CollectionTaskResponse
from data_intelligence_hub.services.alert_service import (
    create_alert_rule as create_alert_rule_from_payload,
)
from data_intelligence_hub.services.alert_service import (
    match_alert_rules_for_signal,
)
from data_intelligence_hub.services.exceptions import (
    ProjectNotFoundError,
    TaskAlreadyRunningError,
    TaskNotFoundError,
    TaskNotRunnableError,
)
from data_intelligence_hub.services.notification_service import (
    create_in_app_notification,
    send_email_notification,
)
from data_intelligence_hub.services.source_service import create_source, enable_source
from data_intelligence_hub.services.task_service import get_task_or_raise, run_task_now

DATASET_EXPORT_CONTENT_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "jsonl": "application/x-ndjson; charset=utf-8",
}

GITHUB_TOOL_DATASET_SCHEMA_VERSION = "github_tool_radar.v2"
GITHUB_TOOL_COLLECTOR_SCHEMA_VERSIONS = ("github_repo.v3", "github_topic.v3")
GITHUB_TOOL_RELEASE_STALE_DAYS = 180

GITHUB_TOOL_FIELDS = (
    "repo_full_name",
    "owner_login",
    "owner_type",
    "description",
    "stars",
    "forks",
    "open_issues",
    "watchers",
    "language",
    "topics",
    "license_spdx_id",
    "default_branch",
    "latest_release_tag",
    "latest_release_published_at",
    "archived",
    "fork",
    "html_url",
    "homepage",
    "created_at",
    "updated_at",
    "pushed_at",
    "readme_detected",
    "readme_name",
    "readme_path",
    "readme_html_url",
    "readme_download_url",
    "readme_sha",
    "readme_size",
    "issue_activity_open_count",
    "issue_activity_status",
    "issue_activity_updated_at",
    "commit_freshness_days",
    "commit_freshness_status",
)

GITHUB_TOOL_FIELD_SOURCES = {
    "repo_full_name": "github.repository.full_name",
    "owner_login": "github.repository.owner.login",
    "owner_type": "github.repository.owner.type",
    "description": "github.repository.description",
    "stars": "github.repository.stargazers_count",
    "forks": "github.repository.forks_count",
    "open_issues": "github.repository.open_issues_count",
    "watchers": "github.repository.watchers_count",
    "language": "github.repository.language",
    "topics": "github.repository.topics",
    "license_spdx_id": "github.repository.license.spdx_id",
    "default_branch": "github.repository.default_branch",
    "latest_release_tag": "github.repository.releases.latest.tag_name",
    "latest_release_published_at": "github.repository.releases.latest.published_at",
    "archived": "github.repository.archived",
    "fork": "github.repository.fork",
    "html_url": "github.repository.html_url",
    "homepage": "github.repository.homepage",
    "created_at": "github.repository.created_at",
    "updated_at": "github.repository.updated_at",
    "pushed_at": "github.repository.pushed_at",
    "readme_detected": "github.repository.readme.exists",
    "readme_name": "github.repository.readme.name",
    "readme_path": "github.repository.readme.path",
    "readme_html_url": "github.repository.readme.html_url",
    "readme_download_url": "github.repository.readme.download_url",
    "readme_sha": "github.repository.readme.sha",
    "readme_size": "github.repository.readme.size",
    "issue_activity_open_count": "derived.github.repository.open_issues_count",
    "issue_activity_status": "derived.github.repository.open_issues_count",
    "issue_activity_updated_at": "github.repository.updated_at",
    "commit_freshness_days": "derived.github.repository.pushed_at",
    "commit_freshness_status": "derived.github.repository.pushed_at",
}

DRIFT_LAYER_BY_ISSUE = {
    "latest_run_missing": "run_health",
    "latest_run_failed": "run_health",
    "completeness_drift_exceeded": "completeness",
    "approved_fields_missing": "field_missingness",
    "freshness_target_missed": "task_freshness",
    "product_added": "catalog_presence",
    "product_removed": "catalog_presence",
    "price_changed": "price_change",
    "stars_changed": "stars",
    "forks_changed": "forks",
    "issue_activity_changed": "issue_activity",
    "release_freshness_missing": "release_freshness",
    "release_freshness_stale": "release_freshness",
}

ProductRowChange = Literal["unchanged", "added", "removed", "mixed"]


@dataclass(frozen=True)
class ProductRowDrift:
    row_change: ProductRowChange
    added_row_count: int
    removed_row_count: int
    price_change_percent: float | None
    issues: list[str]


def list_platform_packages() -> AutomationPlatformPackageListResponse:
    packages = _platform_packages()
    return AutomationPlatformPackageListResponse(
        items=packages,
        total=len(packages),
        run_started=False,
    )


def get_platform_package(package_id: str) -> AutomationPlatformPackageResponse:
    for package in _platform_packages():
        if package.id == package_id:
            return package
    raise CollectorError("platform_package_not_found")


def list_capability_probes(platform_id: str | None = None) -> AutomationCapabilityProbeListResponse:
    generated_at = datetime.now(UTC).isoformat()
    agent_reach = _probe_agent_reach_channel()
    probes = _capability_probe_catalog(generated_at, agent_reach)
    if platform_id:
        probes = [probe for probe in probes if probe.platform_id == platform_id]
        if not probes:
            raise CollectorError("capability_probe_platform_not_found")
    return AutomationCapabilityProbeListResponse(
        generated_at=generated_at,
        items=probes,
        total=len(probes),
        run_started=False,
        collection_resources_written=False,
    )


async def analyze_site_for_collection(
    payload: AutomationSiteAnalysisRequest,
    http_client: httpx.AsyncClient | None = None,
) -> AutomationSiteAnalysisResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    fields = payload.fields or list(ECOMMERCE_PRODUCT_FIELDS)
    collector = EcommerceProductPageCollector(
        {"url": payload.url, "fields": fields, "platform_hint": "auto"},
        http_client=http_client,
    )
    result = await collector.collect()
    content = result.raw_records[0].content
    if not isinstance(content, dict):
        raise CollectorError("automation_analysis_invalid_content")

    platform_profile = content["platform_profile"]
    page_structure = content["page_structure"]
    field_candidates = content["field_schema"]
    tool_recommendations = content["tool_recommendations"]
    cleaning_plan = content["cleaning_plan"]
    selected_fields = [
        candidate["key"]
        for candidate in field_candidates
        if candidate.get("selected") and candidate.get("value") is not None
    ]
    blocked_reasons = _blocked_reasons(page_structure, selected_fields)
    title = page_structure.get("title") or "Ecommerce Product Page"
    return AutomationSiteAnalysisResponse(
        requested_url=payload.url.strip(),
        analyzed_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        platform_profile=AutomationPlatformProfileResponse(**platform_profile),
        page_structure=AutomationPageStructureResponse(**page_structure),
        field_candidates=[
            AutomationFieldCandidateResponse(**candidate) for candidate in field_candidates
        ],
        tool_recommendations=[
            AutomationToolRecommendationResponse(**recommendation)
            for recommendation in tool_recommendations
        ],
        cleaning_plan=[AutomationCleaningStepResponse(**step) for step in cleaning_plan],
        source_draft=AutomationSourceDraftResponse(
            type="ecommerce_product_page",
            config={
                "url": payload.url.strip(),
                "fields": selected_fields or fields,
                "platform_hint": platform_profile["platform_type"],
            },
            suggested_name=f"商品页采集：{title[:80]}",
            schedule_cron=None,
        ),
        blocked_reasons=blocked_reasons,
    )


async def persist_site_analysis_plan(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    payload: AutomationSiteAnalysisRequest,
    result: AutomationSiteAnalysisResponse,
) -> AutomationSiteAnalysisResponse:
    if payload.project_id is None:
        return result
    project = await get_project(session, workspace.id, payload.project_id)
    if project is None:
        raise ProjectNotFoundError

    platform_profile = result.platform_profile.model_dump(mode="json")
    page_structure = result.page_structure.model_dump(mode="json")
    source_draft = result.source_draft.model_dump(mode="json")
    selected_fields = _selected_fields_from_source_draft(source_draft)
    risk_level = str(platform_profile.get("risk_level") or "unknown")
    now = datetime.now(UTC)
    site_analysis = SiteAnalysis(
        workspace_id=workspace.id,
        project_id=project.id,
        created_by_user_id=user.id,
        requested_url=result.requested_url,
        target=payload.target,
        status="analyzed",
        authorization_confirmed=result.authorization_confirmed,
        analyzed_at=result.analyzed_at,
        platform_profile=platform_profile,
        page_structure=page_structure,
        field_candidates=[
            candidate.model_dump(mode="json") for candidate in result.field_candidates
        ],
        tool_recommendations=[
            recommendation.model_dump(mode="json")
            for recommendation in result.tool_recommendations
        ],
        cleaning_plan=[step.model_dump(mode="json") for step in result.cleaning_plan],
        source_draft=source_draft,
        blocked_reasons=result.blocked_reasons,
    )
    await create_site_analysis(session, site_analysis)
    extraction_plan = ExtractionPlan(
        workspace_id=workspace.id,
        project_id=project.id,
        site_analysis_id=site_analysis.id,
        created_by_user_id=user.id,
        name=result.source_draft.suggested_name,
        version_number=1,
        collector_type=result.source_draft.type,
        selected_fields=selected_fields,
        source_draft=source_draft,
        schedule_cron=result.source_draft.schedule_cron,
        status="draft",
        risk_level=risk_level,
        audit_events=[
            {
                "event": "extraction_plan_created_from_site_analysis",
                "site_analysis_id": str(site_analysis.id),
                "created_at": now.isoformat(),
                "run_started": False,
            }
        ],
    )
    await create_extraction_plan(session, extraction_plan)
    site_analysis, extraction_plan = await commit_and_refresh_site_analysis_plan(
        session,
        site_analysis,
        extraction_plan,
    )
    plan_response = _extraction_plan_response(extraction_plan)
    result.site_analysis = _site_analysis_history_item(site_analysis, plan_response)
    result.extraction_plan = plan_response
    result.site_analysis_created = True
    result.extraction_plan_created = True
    result.run_started = False
    return result


async def list_site_analysis_history(
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID | None = None,
    target: str | None = None,
    limit: int = 50,
) -> AutomationSiteAnalysisListResponse:
    analyses = await list_site_analyses(
        session,
        workspace.id,
        project_id=project_id,
        target=target,
        limit=limit,
    )
    items: list[AutomationSiteAnalysisHistoryItemResponse] = []
    for analysis in analyses:
        latest_plan = await get_latest_extraction_plan(session, workspace.id, analysis.id)
        items.append(
            _site_analysis_history_item(
                analysis,
                _extraction_plan_response(latest_plan) if latest_plan else None,
            )
        )
    total = await count_site_analyses(
        session,
        workspace.id,
        project_id=project_id,
        target=target,
    )
    return AutomationSiteAnalysisListResponse(items=items, total=total, run_started=False)


async def get_site_analysis_history_detail(
    session: AsyncSession,
    workspace: Workspace,
    site_analysis_id: uuid.UUID,
) -> AutomationSiteAnalysisDetailResponse:
    analysis = await get_site_analysis(session, workspace.id, site_analysis_id)
    if analysis is None:
        raise CollectorError("site_analysis_not_found")
    plans = await list_extraction_plans(session, workspace.id, analysis.id)
    plan_responses = [_extraction_plan_response(plan) for plan in plans]
    latest_plan = plan_responses[0] if plan_responses else None
    return AutomationSiteAnalysisDetailResponse(
        site_analysis=_site_analysis_history_item(analysis, latest_plan),
        platform_profile=AutomationPlatformProfileResponse(**analysis.platform_profile),
        page_structure=AutomationPageStructureResponse(**analysis.page_structure),
        field_candidates=[
            AutomationFieldCandidateResponse(**candidate)
            for candidate in analysis.field_candidates
        ],
        tool_recommendations=[
            AutomationToolRecommendationResponse(**recommendation)
            for recommendation in analysis.tool_recommendations
        ],
        cleaning_plan=[AutomationCleaningStepResponse(**step) for step in analysis.cleaning_plan],
        source_draft=AutomationSourceDraftResponse(**analysis.source_draft),
        extraction_plans=plan_responses,
        blocked_reasons=analysis.blocked_reasons,
        run_started=False,
    )


async def create_extraction_plan_from_site_analysis(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    site_analysis_id: uuid.UUID,
    payload: AutomationExtractionPlanCreateRequest,
) -> AutomationExtractionPlanResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    analysis = await get_site_analysis(session, workspace.id, site_analysis_id)
    if analysis is None:
        raise CollectorError("site_analysis_not_found")

    source_draft = dict(analysis.source_draft)
    raw_source_config = source_draft.get("config")
    source_config = dict(raw_source_config) if isinstance(raw_source_config, dict) else {}
    selected_fields = payload.fields or _selected_fields_from_source_draft(source_draft)
    source_config["fields"] = selected_fields
    source_draft["config"] = source_config
    source_draft["schedule_cron"] = payload.schedule_cron
    version_number = await next_extraction_plan_version(session, workspace.id, analysis.id)
    now = datetime.now(UTC)
    extraction_plan = ExtractionPlan(
        workspace_id=workspace.id,
        project_id=analysis.project_id,
        site_analysis_id=analysis.id,
        created_by_user_id=user.id,
        name=(payload.name or source_draft.get("suggested_name") or "Extraction plan").strip(),
        version_number=version_number,
        collector_type=str(source_draft["type"]),
        selected_fields=selected_fields,
        source_draft=source_draft,
        schedule_cron=payload.schedule_cron,
        status="draft",
        risk_level=str(analysis.platform_profile.get("risk_level") or "unknown"),
        audit_events=[
            {
                "event": "extraction_plan_created_from_history",
                "site_analysis_id": str(analysis.id),
                "created_at": now.isoformat(),
                "run_started": False,
            }
        ],
    )
    await create_extraction_plan(session, extraction_plan)
    extraction_plan = await commit_and_refresh_extraction_plan(session, extraction_plan)
    return _extraction_plan_response(extraction_plan)


async def save_browser_automation_plan(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    payload: AutomationBrowserAutomationPlanRequest,
) -> AutomationBrowserAutomationPlanResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    project = await get_project(session, workspace.id, payload.project_id)
    if project is None:
        raise ProjectNotFoundError

    selected_fields = [
        field.key.strip()
        for field in payload.field_contract.fields
        if field.selected and field.key.strip()
    ]
    selected_fields = list(dict.fromkeys(selected_fields))
    if not selected_fields:
        raise CollectorError("browser_automation_fields_required")

    final_url = payload.browser_diagnostic.final_url.strip()
    requested_url = payload.requested_url.strip()
    confidence = _browser_confidence_ratio(payload.browser_diagnostic.confidence)
    name = (
        payload.name.strip()
        if isinstance(payload.name, str) and payload.name.strip()
        else f"Browser Automation: {_browser_plan_host_label(final_url or requested_url)}"
    )
    field_contract = {
        "fields": [
            field.model_dump(mode="json") for field in payload.field_contract.fields
        ],
        "cleaning_rules": [
            rule.model_dump(mode="json") for rule in payload.field_contract.cleaning_rules
        ],
    }
    browser_diagnostic = payload.browser_diagnostic.model_dump(mode="json")
    diagnostic_payload = _browser_diagnostic_payload(payload.diagnostic_payload, payload)
    diagnostic_run_id = uuid.uuid4()
    guardrails = _browser_guardrails(payload.guardrails)
    executable_spec = _browser_executable_spec(
        fields=payload.field_contract.fields,
        api_candidates=payload.api_candidates,
        guardrails=guardrails,
        risk_level=payload.risk_level,
        field_stability=payload.browser_diagnostic.field_stability,
    )
    source_draft = {
        "type": "browser_automation",
        "config": {
            "browser_diagnostic_run_id": str(diagnostic_run_id),
            "start_url": final_url,
            "requested_url": requested_url,
            "runner": payload.runner,
            "execution_mode": payload.execution_mode,
            "fields": selected_fields,
            "field_contract": field_contract,
            "browser_diagnostic": browser_diagnostic,
            "executable_spec": executable_spec,
            "api_candidates": payload.api_candidates,
            "guardrails": guardrails,
            "run_started": False,
        },
        "suggested_name": name,
        "schedule_cron": None,
    }
    platform_profile = {
        "platform_type": "dynamic_browser_page",
        "confidence": confidence,
        "indicators": [
            "browser_structure_diagnostic",
            f"recommended_path:{payload.browser_diagnostic.recommended_path}",
            f"field_stability:{payload.browser_diagnostic.field_stability or 'unknown'}",
        ],
        "risk_level": payload.risk_level,
    }
    page_structure = {
        "page_type": "browser_runtime",
        "title": None,
        "canonical_url": final_url,
        "script_count": 0,
        "form_count": 0,
        "image_count": 0,
        "product_schema_count": 0,
        "same_origin_link_count": 0,
        "text_sample": "Browser-harness diagnostic evidence imported as read-only draft.",
    }
    field_candidates = _browser_field_candidates(
        payload.field_contract.fields,
        payload.field_contract.cleaning_rules,
        confidence,
    )
    tool_recommendations = [
        {
            "tool": "browser-harness + Playwright/Crawlee",
            "collector_type": "browser_automation",
            "fit": _browser_tool_fit(payload.risk_level),
            "risk_level": payload.risk_level,
            "reason": "静态预检不足以稳定提取字段，先保存只读浏览器自动化方案与证据。",
        }
    ]
    cleaning_plan = _browser_cleaning_plan(payload.field_contract.cleaning_rules)
    now = datetime.now(UTC)
    site_analysis = SiteAnalysis(
        workspace_id=workspace.id,
        project_id=project.id,
        created_by_user_id=user.id,
        requested_url=requested_url,
        target="browser_automation",
        status="draft",
        authorization_confirmed=payload.authorized,
        analyzed_at=now,
        platform_profile=platform_profile,
        page_structure=page_structure,
        field_candidates=field_candidates,
        tool_recommendations=tool_recommendations,
        cleaning_plan=cleaning_plan,
        source_draft=source_draft,
        blocked_reasons=[
            "当前仅保存只读 browser automation 方案，尚未启动浏览器运行、创建采集源或写入采集结果。"
        ],
    )
    await create_site_analysis(session, site_analysis)
    diagnostic_run = BrowserDiagnosticRun(
        id=diagnostic_run_id,
        workspace_id=workspace.id,
        project_id=project.id,
        created_by_user_id=user.id,
        site_analysis_id=site_analysis.id,
        requested_url=requested_url,
        final_url=final_url,
        status="draft",
        authorization_confirmed=payload.authorized,
        schema_version=payload.browser_diagnostic.schema_version,
        recommended_path=payload.browser_diagnostic.recommended_path,
        confidence=confidence,
        field_stability=payload.browser_diagnostic.field_stability,
        evidence_source=payload.browser_diagnostic.evidence_source,
        screenshot_path=payload.browser_diagnostic.screenshot_path,
        run_policy=_browser_diagnostic_run_policy(payload, diagnostic_payload),
        page_summary=_browser_diagnostic_page_summary(diagnostic_payload),
        network_summary=_browser_diagnostic_network_summary(
            diagnostic_payload,
            payload.api_candidates,
        ),
        accessibility_summary=_browser_diagnostic_accessibility_summary(diagnostic_payload),
        risk_flags=_browser_diagnostic_risk_flags(diagnostic_payload),
        extraction_strategy=_browser_diagnostic_extraction_strategy(
            diagnostic_payload,
            payload,
        ),
        diagnostic_payload=diagnostic_payload,
        blocked_reasons=[
            "浏览器诊断已保存为只读资产，尚未启动浏览器运行、创建采集源或写入采集结果。"
        ],
        run_started=False,
    )
    await create_browser_diagnostic_run(session, diagnostic_run)
    extraction_plan = ExtractionPlan(
        workspace_id=workspace.id,
        project_id=project.id,
        site_analysis_id=site_analysis.id,
        created_by_user_id=user.id,
        name=name,
        version_number=1,
        collector_type="browser_automation",
        selected_fields=selected_fields,
        source_draft=source_draft,
        schedule_cron=None,
        status="draft",
        risk_level=payload.risk_level,
        audit_events=[
            {
                "event": "browser_automation_plan_saved",
                "site_analysis_id": str(site_analysis.id),
                "browser_diagnostic_run_id": str(diagnostic_run.id),
                "evidence_source": payload.browser_diagnostic.evidence_source,
                "execution_mode": payload.execution_mode,
                "created_at": now.isoformat(),
                "run_started": False,
            }
        ],
    )
    await create_extraction_plan(session, extraction_plan)
    site_analysis, extraction_plan = await commit_and_refresh_site_analysis_plan(
        session,
        site_analysis,
        extraction_plan,
    )
    await session.refresh(diagnostic_run)
    plan_response = _extraction_plan_response(extraction_plan)
    return AutomationBrowserAutomationPlanResponse(
        site_analysis=_site_analysis_history_item(site_analysis, plan_response),
        extraction_plan=plan_response,
        browser_diagnostic=_browser_diagnostic_run_response(diagnostic_run),
        site_analysis_created=True,
        extraction_plan_created=True,
        browser_diagnostic_created=True,
        run_started=False,
    )


async def list_browser_diagnostics(
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID | None = None,
    site_analysis_id: uuid.UUID | None = None,
    limit: int = 50,
) -> AutomationBrowserDiagnosticRunListResponse:
    runs = await list_browser_diagnostic_runs(
        session,
        workspace.id,
        project_id=project_id,
        site_analysis_id=site_analysis_id,
        limit=limit,
    )
    total = await count_browser_diagnostic_runs(
        session,
        workspace.id,
        project_id=project_id,
        site_analysis_id=site_analysis_id,
    )
    return AutomationBrowserDiagnosticRunListResponse(
        items=[_browser_diagnostic_run_response(run) for run in runs],
        total=total,
        run_started=False,
    )


async def dry_run_browser_executable_spec(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationBrowserExecutableSpecDryRunRequest,
) -> AutomationBrowserExecutableSpecDryRunResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    if not payload.confirm_review:
        raise CollectorError("browser_spec_review_confirmation_required")

    analysis = await get_site_analysis(session, workspace.id, payload.site_analysis_id)
    if analysis is None:
        raise CollectorError("site_analysis_not_found")
    plan = await get_extraction_plan(session, workspace.id, payload.extraction_plan_id)
    if plan is None:
        raise CollectorError("extraction_plan_not_found")
    if plan.site_analysis_id != analysis.id:
        raise CollectorError("extraction_plan_site_analysis_mismatch")

    source_draft = dict(plan.source_draft)
    source_config = _dict_value(source_draft, "config")
    executable_spec = _dict_value(source_config, "executable_spec")
    diagnostic_run_id = payload.browser_diagnostic_run_id or _uuid_from_config(
        source_config,
        "browser_diagnostic_run_id",
    )
    diagnostic_run = (
        await get_browser_diagnostic_run(session, workspace.id, diagnostic_run_id)
        if diagnostic_run_id is not None
        else None
    )
    checks = _browser_executable_spec_checks(
        analysis=analysis,
        plan=plan,
        source_config=source_config,
        executable_spec=executable_spec,
        diagnostic_run=diagnostic_run,
    )
    summary = _browser_executable_spec_summary(checks, executable_spec)
    plan_response = _extraction_plan_response(plan)
    return AutomationBrowserExecutableSpecDryRunResponse(
        site_analysis=_site_analysis_history_item(analysis, plan_response),
        extraction_plan=plan_response,
        browser_diagnostic=(
            _browser_diagnostic_run_response(diagnostic_run)
            if diagnostic_run is not None
            else None
        ),
        summary=summary,
        checks=checks,
        executable_spec=executable_spec,
        blocked_reasons=[check.message for check in checks if check.status == "blocked"],
        audit_events=[
            {
                "event": "browser_automation_spec_dry_run_validated",
                "site_analysis_id": str(analysis.id),
                "extraction_plan_id": str(plan.id),
                "browser_diagnostic_run_id": (
                    str(diagnostic_run.id) if diagnostic_run is not None else None
                ),
                "status": summary.status,
                "write_allowed": summary.write_allowed,
                "run_started": False,
                "created_at": datetime.now(UTC).isoformat(),
            }
        ],
        run_started=False,
    )


async def create_browser_diagnostic_job_asset(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    payload: AutomationBrowserDiagnosticJobCreateRequest,
) -> AutomationBrowserDiagnosticJobResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    if not payload.confirm_create:
        raise CollectorError("browser_diagnostic_job_confirmation_required")

    analysis = await get_site_analysis(session, workspace.id, payload.site_analysis_id)
    if analysis is None:
        raise CollectorError("site_analysis_not_found")
    plan = await get_extraction_plan(session, workspace.id, payload.extraction_plan_id)
    if plan is None:
        raise CollectorError("extraction_plan_not_found")
    if plan.site_analysis_id != analysis.id:
        raise CollectorError("extraction_plan_site_analysis_mismatch")

    source_draft = dict(plan.source_draft)
    source_config = _dict_value(source_draft, "config")
    executable_spec = _dict_value(source_config, "executable_spec")
    diagnostic_run_id = payload.browser_diagnostic_run_id or _uuid_from_config(
        source_config,
        "browser_diagnostic_run_id",
    )
    if diagnostic_run_id is None:
        raise CollectorError("browser_diagnostic_run_not_found")
    diagnostic_run = await get_browser_diagnostic_run(
        session,
        workspace.id,
        diagnostic_run_id,
    )
    if diagnostic_run is None:
        raise CollectorError("browser_diagnostic_run_not_found")

    checks = _browser_executable_spec_checks(
        analysis=analysis,
        plan=plan,
        source_config=source_config,
        executable_spec=executable_spec,
        diagnostic_run=diagnostic_run,
    )
    summary = _browser_executable_spec_summary(checks, executable_spec)
    if summary.blocked_checks > 0 or not summary.can_dry_run_after_review:
        raise CollectorError("browser_diagnostic_job_spec_blocked")

    selector_scope = _list_of_dicts(executable_spec.get("selector_contract"))
    wait_policy = _list_of_dicts(executable_spec.get("wait_conditions"))
    api_candidates = _string_list(executable_spec.get("api_candidates"))
    network_policy = _browser_diagnostic_job_network_policy(
        payload.network_observation_mode,
        api_candidates,
    )
    artifact_policy = _browser_diagnostic_job_artifact_policy(
        payload.artifact_mode,
        diagnostic_run,
    )
    safety_flags = _browser_diagnostic_job_safety_flags(
        _string_list(executable_spec.get("guardrails")),
    )
    dry_run_summary = summary.model_dump(mode="json")
    request_fingerprint = _browser_diagnostic_job_fingerprint(
        workspace_id=workspace.id,
        site_analysis_id=analysis.id,
        extraction_plan_id=plan.id,
        browser_diagnostic_run_id=diagnostic_run.id,
        network_policy=network_policy,
        artifact_policy=artifact_policy,
    )
    existing = await get_browser_diagnostic_job_by_fingerprint(
        session,
        workspace.id,
        request_fingerprint,
    )
    if existing is not None:
        return _browser_diagnostic_job_response(existing)

    now = datetime.now(UTC)
    note = payload.note.strip() if isinstance(payload.note, str) and payload.note.strip() else None
    audit_event = {
        "event": "browser_diagnostic_job_created",
        "site_analysis_id": str(analysis.id),
        "extraction_plan_id": str(plan.id),
        "browser_diagnostic_run_id": str(diagnostic_run.id),
        "status": "ready_for_manual_execution",
        "network_observation_mode": payload.network_observation_mode,
        "artifact_mode": payload.artifact_mode,
        "write_allowed": False,
        "run_started": False,
        "created_at": now.isoformat(),
    }
    if note is not None:
        audit_event["note"] = note

    diagnostic_job = BrowserDiagnosticJob(
        workspace_id=workspace.id,
        project_id=plan.project_id,
        created_by_user_id=user.id,
        site_analysis_id=analysis.id,
        extraction_plan_id=plan.id,
        browser_diagnostic_run_id=diagnostic_run.id,
        request_fingerprint=request_fingerprint,
        requested_url=analysis.requested_url,
        final_url=diagnostic_run.final_url,
        status="ready_for_manual_execution",
        authorization_confirmed=payload.authorized,
        runner=str(source_config.get("runner") or "browser_harness"),
        execution_mode=str(source_config.get("execution_mode") or "read_only_browser_harness"),
        selector_scope=selector_scope,
        wait_policy=wait_policy,
        network_observation_policy=network_policy,
        artifact_policy=artifact_policy,
        safety_flags=safety_flags,
        dry_run_summary=dry_run_summary,
        executable_spec_snapshot=executable_spec,
        blocked_reasons=[
            "browser_diagnostic_job_created_no_runner",
            "no_source_task_taskrun_dataset_notification_or_scheduler_side_effect",
        ],
        audit_events=[audit_event],
        run_started=False,
        cancelled_at=None,
    )
    await insert_browser_diagnostic_job(session, diagnostic_job)
    diagnostic_job = await commit_and_refresh_browser_diagnostic_job(
        session,
        diagnostic_job,
    )
    return _browser_diagnostic_job_response(diagnostic_job)


async def list_browser_diagnostic_job_assets(
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID | None = None,
    site_analysis_id: uuid.UUID | None = None,
    extraction_plan_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 50,
) -> AutomationBrowserDiagnosticJobListResponse:
    jobs = await list_browser_diagnostic_jobs(
        session,
        workspace.id,
        project_id=project_id,
        site_analysis_id=site_analysis_id,
        extraction_plan_id=extraction_plan_id,
        status=status,
        limit=limit,
    )
    total = await count_browser_diagnostic_jobs(
        session,
        workspace.id,
        project_id=project_id,
        site_analysis_id=site_analysis_id,
        extraction_plan_id=extraction_plan_id,
        status=status,
    )
    return AutomationBrowserDiagnosticJobListResponse(
        items=[_browser_diagnostic_job_response(job) for job in jobs],
        total=total,
        run_started=False,
    )


async def get_browser_diagnostic_job_asset(
    session: AsyncSession,
    workspace: Workspace,
    diagnostic_job_id: uuid.UUID,
) -> AutomationBrowserDiagnosticJobResponse:
    job = await get_browser_diagnostic_job(session, workspace.id, diagnostic_job_id)
    if job is None:
        raise CollectorError("browser_diagnostic_job_not_found")
    return _browser_diagnostic_job_response(job)


async def cancel_browser_diagnostic_job_asset(
    session: AsyncSession,
    workspace: Workspace,
    diagnostic_job_id: uuid.UUID,
) -> AutomationBrowserDiagnosticJobResponse:
    job = await get_browser_diagnostic_job(session, workspace.id, diagnostic_job_id)
    if job is None:
        raise CollectorError("browser_diagnostic_job_not_found")
    if job.status == "cancelled":
        return _browser_diagnostic_job_response(job)

    now = datetime.now(UTC)
    job.status = "cancelled"
    job.cancelled_at = now
    job.blocked_reasons = [
        *job.blocked_reasons,
        "browser_diagnostic_job_cancelled_before_runner_start",
    ]
    job.audit_events = [
        *job.audit_events,
        {
            "event": "browser_diagnostic_job_cancelled",
            "job_id": str(job.id),
            "run_started": False,
            "created_at": now.isoformat(),
        },
    ]
    job = await commit_and_refresh_browser_diagnostic_job(session, job)
    return _browser_diagnostic_job_response(job)


async def build_browser_executor_contract(
    session: AsyncSession,
    workspace: Workspace,
    diagnostic_job_id: uuid.UUID,
    payload: AutomationBrowserExecutorContractRequest,
) -> AutomationBrowserExecutorContractResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    if not payload.confirm_review:
        raise CollectorError("browser_executor_contract_review_required")

    job = await get_browser_diagnostic_job(session, workspace.id, diagnostic_job_id)
    if job is None:
        raise CollectorError("browser_diagnostic_job_not_found")

    readiness_checks = _browser_executor_readiness_checks(job)
    blocked_reasons = [
        check.message for check in readiness_checks if check.status == "blocked"
    ]
    artifact_policy = _browser_executor_artifact_retention_policy(job, payload)
    now = datetime.now(UTC)
    return AutomationBrowserExecutorContractResponse(
        job=_browser_diagnostic_job_response(job),
        adapter=_browser_executor_adapter_contract(job),
        runtime_isolation=_browser_executor_runtime_isolation(job),
        artifact_retention_policy=artifact_policy,
        allowed_actions=_browser_executor_allowed_actions(job),
        denied_actions=_browser_executor_denied_actions(),
        readiness_checks=readiness_checks,
        blocked_reasons=blocked_reasons,
        audit_events=[
            {
                "event": "browser_executor_contract_built",
                "job_id": str(job.id),
                "status": "blocked" if blocked_reasons else "ready",
                "artifact_retention_days": payload.artifact_retention_days,
                "max_preview_rows": payload.max_preview_rows,
                "write_files_now": False,
                "run_started": False,
                "execution_started": False,
                "created_at": now.isoformat(),
                **(
                    {"note": payload.note.strip()}
                    if isinstance(payload.note, str) and payload.note.strip()
                    else {}
                ),
            }
        ],
        run_started=False,
        execution_started=False,
    )


async def list_browser_diagnostic_job_run_assets(
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID | None = None,
    diagnostic_job_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 50,
) -> AutomationBrowserLocalRunnerResultListResponse:
    items = await list_browser_diagnostic_job_runs(
        session,
        workspace.id,
        project_id=project_id,
        diagnostic_job_id=diagnostic_job_id,
        status=status,
        limit=limit,
    )
    total = await count_browser_diagnostic_job_runs(
        session,
        workspace.id,
        project_id=project_id,
        diagnostic_job_id=diagnostic_job_id,
        status=status,
    )
    return AutomationBrowserLocalRunnerResultListResponse(
        items=[_browser_local_runner_result_response(item) for item in items],
        total=total,
        browser_started=any(item.browser_started for item in items),
        files_written=any(item.files_written for item in items),
        collection_resources_written=any(
            item.collection_resources_written for item in items
        ),
    )


async def run_browser_diagnostic_job_local(
    session: AsyncSession,
    workspace: Workspace,
    diagnostic_job_id: uuid.UUID,
    payload: AutomationBrowserLocalRunnerRequest,
) -> AutomationBrowserLocalRunnerResultResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    if not payload.confirm_execute:
        raise CollectorError("browser_local_runner_confirmation_required")
    if (
        payload.run_mode == "ephemeral_browser_harness_probe"
        and not payload.confirm_real_browser_probe
    ):
        raise CollectorError("browser_harness_probe_confirmation_required")

    job = await get_browser_diagnostic_job(session, workspace.id, diagnostic_job_id)
    if job is None:
        raise CollectorError("browser_diagnostic_job_not_found")
    if job.status != "ready_for_manual_execution":
        raise CollectorError("browser_diagnostic_job_not_ready_for_local_run")
    if job.run_started:
        raise CollectorError("browser_diagnostic_job_already_marked_running")

    contract = await build_browser_executor_contract(
        session,
        workspace,
        diagnostic_job_id,
        AutomationBrowserExecutorContractRequest(
            authorized=payload.authorized,
            confirm_review=True,
            artifact_retention_days=payload.artifact_retention_days,
            max_preview_rows=payload.max_preview_rows,
            include_screenshot=payload.include_screenshot,
            include_trace_summary=payload.include_trace_summary,
            include_har_summary=payload.include_har_summary,
            note=payload.note,
        ),
    )
    if contract.blocked_reasons:
        raise CollectorError("browser_executor_contract_blocked")

    diagnostic_run = await get_browser_diagnostic_run(
        session,
        workspace.id,
        job.browser_diagnostic_run_id,
    )
    if diagnostic_run is None:
        raise CollectorError("browser_diagnostic_run_not_found")

    now = datetime.now(UTC)
    selector_results = _browser_local_runner_selector_results(job, diagnostic_run)
    preview_rows = _browser_local_runner_preview_rows(
        job=job,
        selector_results=selector_results,
        max_rows=payload.max_preview_rows,
    )
    artifact_manifest = _browser_local_runner_artifact_manifest(
        contract=contract,
        diagnostic_run=diagnostic_run,
        preview_rows=preview_rows,
    )
    network_summary = _browser_local_runner_network_summary(
        job=job,
        diagnostic_run=diagnostic_run,
    )
    error_summary = _browser_local_runner_error_summary(diagnostic_run)
    note = payload.note.strip() if isinstance(payload.note, str) and payload.note.strip() else None
    status = "completed_snapshot_replay"
    browser_started = False
    blocked_reasons = [
        "browser_local_runner_snapshot_replay_only",
        "no_real_browser_started_no_files_written_no_collection_resources_created",
    ]
    audit_event: dict[str, Any] = {
        "event": "browser_local_runner_snapshot_replay_completed",
        "job_id": str(job.id),
        "run_mode": payload.run_mode,
        "preview_row_count": len(preview_rows),
        "selector_result_count": len(selector_results),
        "execution_started": True,
        "browser_started": False,
        "files_written": False,
        "collection_resources_written": False,
        "created_at": now.isoformat(),
    }
    if payload.run_mode == "ephemeral_browser_harness_probe":
        probe_result = await asyncio.to_thread(
            _run_browser_harness_ephemeral_probe,
            job,
            payload,
        )
        browser_started = probe_result.get("status") == "completed"
        status = {
            "completed": "completed_ephemeral_probe",
            "blocked": "blocked_ephemeral_probe",
        }.get(str(probe_result.get("status")), "failed_ephemeral_probe")
        artifact_manifest = _browser_harness_probe_artifact_manifest(
            artifact_manifest,
            probe_result,
        )
        network_summary = _browser_harness_probe_network_summary(
            network_summary,
            probe_result,
        )
        error_summary = _browser_harness_probe_error_summary(error_summary, probe_result)
        blocked_reasons = [
            "browser_harness_ephemeral_probe_only",
            "no_files_written_no_collection_resources_created",
        ]
        if status == "blocked_ephemeral_probe":
            blocked_reasons.append("browser_harness_binary_unavailable")
        if status == "failed_ephemeral_probe":
            blocked_reasons.append("browser_harness_probe_failed")
        audit_event = {
            "event": "browser_harness_ephemeral_probe_completed",
            "job_id": str(job.id),
            "run_mode": payload.run_mode,
            "probe_status": probe_result.get("status"),
            "probe_exit_code": probe_result.get("exit_code"),
            "target_tab_closed": probe_result.get("target_tab_closed") is True,
            "preview_row_count": len(preview_rows),
            "selector_result_count": len(selector_results),
            "execution_started": True,
            "browser_started": browser_started,
            "files_written": False,
            "collection_resources_written": False,
            "created_at": now.isoformat(),
        }
    if note is not None:
        audit_event["note"] = note

    run_asset = BrowserDiagnosticJobRun(
        workspace_id=workspace.id,
        project_id=job.project_id,
        created_by_user_id=job.created_by_user_id,
        browser_diagnostic_job_id=job.id,
        site_analysis_id=job.site_analysis_id,
        extraction_plan_id=job.extraction_plan_id,
        browser_diagnostic_run_id=job.browser_diagnostic_run_id,
        requested_url=job.requested_url,
        final_url=job.final_url,
        status=status,
        runner="browser_harness_read_only_local",
        run_mode=payload.run_mode,
        contract_snapshot=contract.model_dump(mode="json"),
        artifact_manifest=artifact_manifest,
        selector_results=selector_results,
        preview_rows=preview_rows,
        network_observation_summary=network_summary,
        error_summary=error_summary,
        blocked_reasons=blocked_reasons,
        audit_events=[audit_event],
        execution_started=True,
        browser_started=browser_started,
        files_written=False,
        collection_resources_written=False,
        started_at=now,
        finished_at=now,
        browser_diagnostic_job=job,
        browser_diagnostic_run=diagnostic_run,
    )
    await create_browser_diagnostic_job_run(session, run_asset)
    run_asset = await commit_and_refresh_browser_diagnostic_job_run(session, run_asset)
    return _browser_local_runner_result_response(run_asset)


async def discover_products_for_collection(
    payload: AutomationProductDiscoveryRequest,
    http_client: httpx.AsyncClient | None = None,
) -> AutomationProductDiscoveryResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    collector = EcommerceProductDiscoveryCollector(
        {
            "url": payload.url,
            "max_products": payload.max_products,
            "platform_hint": "auto",
        },
        http_client=http_client,
    )
    result = await collector.collect()
    content = result.raw_records[0].content
    if not isinstance(content, dict):
        raise CollectorError("automation_discovery_invalid_content")

    platform_profile = content["platform_profile"]
    page_structure = content["page_structure"]
    product_candidates = content["product_candidates"]
    tool_recommendations = content["tool_recommendations"]
    discovery_plan = content["discovery_plan"]
    blocked_reasons = _discovery_blocked_reasons(product_candidates)
    title = page_structure.get("title") or "Ecommerce Product Discovery"
    return AutomationProductDiscoveryResponse(
        requested_url=payload.url.strip(),
        analyzed_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        platform_profile=AutomationPlatformProfileResponse(**platform_profile),
        page_structure=AutomationDiscoveryPageStructureResponse(**page_structure),
        product_candidates=[
            AutomationProductCandidateResponse(**candidate) for candidate in product_candidates
        ],
        tool_recommendations=[
            AutomationToolRecommendationResponse(**recommendation)
            for recommendation in tool_recommendations
        ],
        discovery_plan=AutomationDiscoveryPlanResponse(**discovery_plan),
        source_draft=AutomationSourceDraftResponse(
            type="ecommerce_product_discovery",
            config={
                "url": payload.url.strip(),
                "max_products": payload.max_products,
                "platform_hint": platform_profile["platform_type"],
            },
            suggested_name=f"商品链接发现：{title[:80]}",
            schedule_cron=None,
        ),
        blocked_reasons=blocked_reasons,
    )


async def preview_product_fanout(
    payload: AutomationProductFanoutPreviewRequest,
) -> AutomationProductFanoutPreviewResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    parent_url = payload.parent_url.strip()
    parent_origin = _origin(parent_url)
    if parent_origin is None:
        raise CollectorError("parent_url must be an absolute HTTP or HTTPS URL")
    fields = _fanout_fields(payload.fields)
    statuses: list[AutomationFanoutCandidateStatusResponse] = []
    source_drafts: list[AutomationSourceDraftResponse] = []
    seen_urls: set[str] = set()

    for candidate in payload.candidates:
        candidate_url = _normalize_candidate_url(candidate.url)
        reason = _candidate_block_reason(
            candidate_url,
            parent_origin,
            seen_urls,
            len(source_drafts),
            payload.max_sources,
        )
        if reason is None and candidate_url is not None:
            seen_urls.add(candidate_url)
            source_drafts.append(
                AutomationSourceDraftResponse(
                    type="ecommerce_product_page",
                    config={
                        "url": candidate_url,
                        "fields": fields,
                        "platform_hint": "auto",
                    },
                    suggested_name=_fanout_source_name(candidate.title, candidate_url),
                    schedule_cron=None,
                )
            )
        statuses.append(
            AutomationFanoutCandidateStatusResponse(
                url=candidate_url or candidate.url.strip(),
                title=candidate.title,
                source=candidate.source,
                confidence=candidate.confidence,
                status="blocked" if reason else "ready",
                reason=reason,
            )
        )

    blocked_count = len([status for status in statuses if status.status == "blocked"])
    blocked_reasons = _fanout_blocked_reasons(source_drafts, blocked_count)
    return AutomationProductFanoutPreviewResponse(
        requested_parent_url=parent_url,
        analyzed_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        candidate_statuses=statuses,
        source_drafts=source_drafts,
        batch_plan=AutomationFanoutBatchPlanResponse(
            run_mode="preview_only",
            next_collector_type="ecommerce_product_page",
            ready_count=len(source_drafts),
            blocked_count=blocked_count,
            max_sources=payload.max_sources,
            fields=fields,
            manual_review_required=True,
            execution_boundary="preview_only_no_database_write",
        ),
        blocked_reasons=blocked_reasons,
    )


async def create_reviewed_product_fanout(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductFanoutCreateRequest,
) -> AutomationProductFanoutCreateResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")

    preview = await preview_product_fanout(
        AutomationProductFanoutPreviewRequest(
            parent_url=payload.parent_url,
            authorized=payload.authorized,
            candidates=payload.candidates,
            fields=payload.fields,
            max_sources=payload.max_sources,
        )
    )
    persisted_sources: list[AutomationFanoutPersistedSourceResponse] = []
    audit_events: list[dict[str, object]] = [
        {
            "event": "fanout_create_requested",
            "parent_url": preview.requested_parent_url,
            "candidate_count": len(payload.candidates),
            "preview_ready_count": preview.batch_plan.ready_count,
            "preview_blocked_count": preview.batch_plan.blocked_count,
            "enable_tasks": payload.enable_tasks,
        }
    ]

    created_sources = 0
    reused_sources = 0
    enabled_tasks = 0

    for draft in preview.source_drafts:
        url = _draft_url(draft)
        if url is None:
            audit_events.append({"event": "fanout_source_skipped", "reason": "draft_url_missing"})
            continue
        existing_source = await get_source_by_type_url(
            session,
            workspace.id,
            payload.project_id,
            "ecommerce_product_page",
            url,
        )
        if existing_source is None:
            source = await create_source(
                session,
                workspace,
                SourceCreateRequest(
                    project_id=payload.project_id,
                    name=draft.suggested_name,
                    type="ecommerce_product_page",
                    url=url,
                    config=draft.config,
                    schedule_cron=None,
                ),
            )
            action = "created"
            created_sources += 1
        else:
            source = existing_source
            action = "reused"
            reused_sources += 1

        task_response: CollectionTaskResponse | None = None
        if payload.enable_tasks:
            _source, task = await enable_source(session, workspace, source.id)
            task_response = CollectionTaskResponse.from_task(task)
            enabled_tasks += 1

        persisted_sources.append(
            AutomationFanoutPersistedSourceResponse(
                url=url,
                action=action,
                source=SourceResponse.model_validate(source),
                task=task_response,
            )
        )
        audit_events.append(
            {
                "event": "fanout_source_persisted",
                "url": url,
                "action": action,
                "source_id": str(source.id),
                "task_enabled": task_response is not None,
                "run_started": False,
            }
        )

    blocked_reasons = list(preview.blocked_reasons)
    if persisted_sources:
        blocked_reasons.append("已完成持久化创建或复用，但尚未启动任何采集运行。")
    else:
        blocked_reasons.append("没有创建或复用任何商品页采集源。")
    return AutomationProductFanoutCreateResponse(
        requested_parent_url=preview.requested_parent_url,
        created_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        persisted_sources=persisted_sources,
        candidate_statuses=preview.candidate_statuses,
        summary=AutomationFanoutCreateSummaryResponse(
            created_sources=created_sources,
            reused_sources=reused_sources,
            enabled_tasks=enabled_tasks,
            blocked_candidates=preview.batch_plan.blocked_count,
            run_started=False,
        ),
        audit_events=audit_events,
        blocked_reasons=blocked_reasons,
    )


async def run_reviewed_product_batch(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductBatchRunRequest,
) -> AutomationProductBatchRunResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    if len(payload.task_ids) > payload.max_tasks:
        raise CollectorError("batch_task_limit_exceeded")

    items: list[AutomationProductBatchRunItemResponse] = []
    audit_events: list[dict[str, object]] = [
        {
            "event": "product_batch_run_requested",
            "requested_tasks": len(payload.task_ids),
            "max_tasks": payload.max_tasks,
            "collector_type": "ecommerce_product_page",
        }
    ]
    seen_task_ids: set[uuid.UUID] = set()

    for task_id in payload.task_ids:
        if task_id in seen_task_ids:
            items.append(_blocked_batch_item(task_id, "duplicate_task_id"))
            audit_events.append(
                {
                    "event": "product_batch_task_blocked",
                    "task_id": str(task_id),
                    "reason": "duplicate_task_id",
                }
            )
            continue
        seen_task_ids.add(task_id)

        try:
            task = await get_task_or_raise(session, workspace, task_id)
        except TaskNotFoundError:
            items.append(_blocked_batch_item(task_id, "task_not_found"))
            audit_events.append(
                {
                    "event": "product_batch_task_blocked",
                    "task_id": str(task_id),
                    "reason": "task_not_found",
                }
            )
            continue

        if task.collector_type != "ecommerce_product_page":
            items.append(_blocked_batch_item_from_task(task, "unsupported_collector_type"))
            audit_events.append(
                {
                    "event": "product_batch_task_blocked",
                    "task_id": str(task.id),
                    "collector_type": task.collector_type,
                    "reason": "unsupported_collector_type",
                }
            )
            continue
        if task.status != "enabled":
            items.append(_blocked_batch_item_from_task(task, "task_not_enabled"))
            audit_events.append(
                {
                    "event": "product_batch_task_blocked",
                    "task_id": str(task.id),
                    "task_status": task.status,
                    "reason": "task_not_enabled",
                }
            )
            continue

        try:
            run = await run_task_now(session, workspace, task.id)
        except (TaskAlreadyRunningError, TaskNotRunnableError) as exc:
            items.append(_blocked_batch_item_from_task(task, exc.message))
            audit_events.append(
                {
                    "event": "product_batch_task_blocked",
                    "task_id": str(task.id),
                    "reason": exc.message,
                }
            )
            continue

        raw_records, reused_deduplicated_records = await _product_records_for_task_run(
            session=session,
            workspace_id=workspace.id,
            task_run_id=run.id,
            limit=500,
        )
        field_completeness = _product_field_completeness(task, raw_records)
        item_status = (
            "run_completed" if run.status in {"success", "partial_success"} else "run_failed"
        )
        effective_records_count = (
            len(raw_records) if reused_deduplicated_records else run.records_count
        )
        items.append(
            AutomationProductBatchRunItemResponse(
                task_id=task.id,
                task_name=task.name,
                source_id=task.source_id,
                source_url=_task_source_url(task),
                status=item_status,
                blocked_reason=None,
                run=run,
                records_count=effective_records_count,
                entities_count=run.entities_count,
                field_completeness=field_completeness,
                error_message=run.error_message,
            )
        )
        audit_events.append(
            {
                "event": "product_batch_task_run_completed",
                "task_id": str(task.id),
                "run_id": str(run.id),
                "status": run.status,
                "records_count": effective_records_count,
                "entities_count": run.entities_count,
                "completeness_percent": field_completeness.completeness_percent,
                "deduplicated_source_records_reused": reused_deduplicated_records,
            }
        )

    summary = _product_batch_summary(payload.task_ids, items)
    blocked_reasons: list[str] = []
    if summary.blocked_tasks > 0:
        blocked_reasons.append("部分任务未运行，需查看 blocked_reason 后再重试。")
    if summary.run_tasks == 0:
        blocked_reasons.append("没有任何商品页任务被启动。")
    else:
        blocked_reasons.append("本次仅执行用户确认的小批量任务，没有创建调度或自动循环。")

    return AutomationProductBatchRunResponse(
        created_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        items=items,
        summary=summary,
        audit_events=audit_events,
        blocked_reasons=blocked_reasons,
    )


async def preview_product_dataset(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductDatasetPreviewRequest,
) -> AutomationProductDatasetPreviewResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")

    selected_fields = _dataset_fields(payload.fields)
    rows: list[AutomationProductDatasetRowResponse] = []
    matched_run_ids: set[uuid.UUID] = set()
    audit_events: list[dict[str, object]] = [
        {
            "event": "product_dataset_preview_requested",
            "requested_runs": len(payload.task_run_ids),
            "max_rows": payload.max_rows,
            "fields": selected_fields,
        }
    ]

    for task_run_id in payload.task_run_ids:
        product_records, reused_deduplicated_records = await _product_records_for_task_run(
            session=session,
            workspace_id=workspace.id,
            task_run_id=task_run_id,
            limit=payload.max_rows,
        )
        if not product_records:
            audit_events.append(
                {
                    "event": "product_dataset_run_skipped",
                    "task_run_id": str(task_run_id),
                    "reason": "no_product_page_records",
                }
            )
            continue
        if reused_deduplicated_records:
            audit_events.append(
                {
                    "event": "product_dataset_run_reused_deduplicated_source_records",
                    "task_run_id": str(task_run_id),
                    "records_count": len(product_records),
                }
            )
        matched_run_ids.add(task_run_id)
        for raw_record in product_records:
            if len(rows) >= payload.max_rows:
                break
            row = _dataset_row(raw_record, selected_fields)
            rows.append(row)
        if len(rows) >= payload.max_rows:
            audit_events.append(
                {
                    "event": "product_dataset_row_limit_reached",
                    "max_rows": payload.max_rows,
                }
            )
            break

    summary = _dataset_summary(payload.task_run_ids, matched_run_ids, rows, selected_fields)
    blocked_reasons: list[str] = []
    if summary.rows_count == 0:
        blocked_reasons.append("未找到可进入数据集预览的商品页采集记录。")
    if summary.rows_count >= payload.max_rows:
        blocked_reasons.append("数据集预览已达到本次最大行数限制。")
    blocked_reasons.append("当前为只读数据集预览，尚未保存 Dataset 或写出导出文件。")

    return AutomationProductDatasetPreviewResponse(
        created_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        rows=rows,
        summary=summary,
        cleaning_script_draft=_cleaning_script_draft(selected_fields),
        export_preview=_dataset_export_preview(rows, selected_fields),
        audit_events=audit_events,
        blocked_reasons=blocked_reasons,
    )


async def preview_github_tool_dataset(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationGitHubToolDatasetPreviewRequest,
) -> AutomationProductDatasetPreviewResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")

    selected_fields = _github_tool_dataset_fields(payload.fields)
    rows: list[AutomationProductDatasetRowResponse] = []
    matched_run_ids: set[uuid.UUID] = set()
    audit_events: list[dict[str, object]] = [
        {
            "event": "github_tool_dataset_preview_requested",
            "requested_runs": len(payload.task_run_ids),
            "max_rows": payload.max_rows,
            "fields": selected_fields,
            "run_started": False,
        }
    ]

    for task_run_id in payload.task_run_ids:
        raw_records = await _github_tool_raw_records_for_task_run(
            session=session,
            workspace_id=workspace.id,
            task_run_id=task_run_id,
            limit=payload.max_rows,
        )
        if not raw_records:
            audit_events.append(
                {
                    "event": "github_tool_dataset_run_skipped",
                    "task_run_id": str(task_run_id),
                    "reason": "no_github_topic_or_repo_records",
                    "run_started": False,
                }
            )
            continue
        matched_run_ids.add(task_run_id)
        for raw_record in raw_records:
            for row in _github_tool_rows(raw_record, selected_fields):
                if len(rows) >= payload.max_rows:
                    break
                rows.append(row)
            if len(rows) >= payload.max_rows:
                break
        if len(rows) >= payload.max_rows:
            audit_events.append(
                {
                    "event": "github_tool_dataset_row_limit_reached",
                    "max_rows": payload.max_rows,
                    "run_started": False,
                }
            )
            break

    summary = _dataset_summary(payload.task_run_ids, matched_run_ids, rows, selected_fields)
    blocked_reasons: list[str] = []
    if summary.rows_count == 0:
        blocked_reasons.append("未找到可进入工具情报数据集的 GitHub topic/repo 采集记录。")
    if summary.rows_count >= payload.max_rows:
        blocked_reasons.append("工具情报数据集预览已达到本次最大行数限制。")
    blocked_reasons.append("当前为只读工具数据集预览，尚未保存 Dataset 或写出导出文件。")

    return AutomationProductDatasetPreviewResponse(
        created_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        rows=rows,
        summary=summary,
        cleaning_script_draft=_github_tool_cleaning_script_draft(selected_fields),
        export_preview=_github_tool_export_preview(rows, selected_fields),
        audit_events=audit_events,
        blocked_reasons=blocked_reasons,
    )


async def save_github_tool_dataset_version(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    payload: AutomationGitHubToolDatasetSaveRequest,
) -> AutomationProductDatasetSaveResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    dataset_name = payload.name.strip()
    if not dataset_name:
        raise CollectorError("dataset_name_required")

    preview = await preview_github_tool_dataset(session, workspace, payload)
    if not preview.rows:
        raise CollectorError("dataset_preview_empty")

    raw_records = await _dataset_github_tool_raw_records(
        session,
        workspace.id,
        payload.task_run_ids,
        payload.max_rows,
    )
    project_ids = {raw_record.project_id for raw_record in raw_records}
    if len(project_ids) != 1:
        raise CollectorError("dataset_project_lineage_ambiguous")
    project_id = next(iter(project_ids))

    await _lock_workspace_for_dataset_save(session, workspace.id)
    dataset = await get_dataset_by_name(session, workspace.id, dataset_name)
    created_dataset = False
    if dataset is None:
        dataset = Dataset(
            workspace_id=workspace.id,
            project_id=project_id,
            name=dataset_name,
            dataset_type="github_tool_radar",
            status="active",
            description=payload.description.strip() if payload.description else None,
        )
        session.add(dataset)
        await session.flush()
        created_dataset = True
    elif dataset.project_id != project_id:
        raise CollectorError("dataset_project_lineage_conflict")
    elif dataset.dataset_type != "github_tool_radar":
        raise CollectorError("dataset_type_conflict")

    latest_version = await get_latest_dataset_version(session, dataset.id)
    next_version_number = 1 if latest_version is None else latest_version.version_number + 1
    created_at = datetime.now(UTC)
    version = DatasetVersion(
        dataset_id=dataset.id,
        workspace_id=workspace.id,
        project_id=dataset.project_id,
        created_by_user_id=user.id,
        cleaning_plan_id=None,
        version_number=next_version_number,
        source_task_run_ids=[str(task_run_id) for task_run_id in payload.task_run_ids],
        selected_fields=preview.summary.selected_fields,
        cleaning_script=preview.cleaning_script_draft,
        rows=[
            {
                "schema_version": GITHUB_TOOL_DATASET_SCHEMA_VERSION,
                "row_id": row.row_id,
                "task_run_id": str(row.task_run_id),
                "raw_record_id": str(row.raw_record_id),
                "source_url": row.source_url,
                "values": row.values,
                "missing_fields": row.missing_fields,
                "field_sources": _github_tool_field_sources(row.values.keys()),
                "missing_field_sources": _github_tool_field_sources(row.missing_fields),
                "completeness_percent": row.completeness_percent,
            }
            for row in preview.rows
        ],
        export_preview=preview.export_preview,
        row_count=len(preview.rows),
        average_completeness_percent=preview.summary.average_completeness_percent,
        status="saved",
        created_at=created_at,
    )
    session.add(version)
    await session.commit()
    await session.refresh(dataset)
    await session.refresh(version)

    return AutomationProductDatasetSaveResponse(
        saved_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        dataset=_dataset_response(dataset),
        version=_dataset_version_response(version),
        audit_events=[
            {
                "event": "github_tool_dataset_version_saved",
                "dataset_id": str(dataset.id),
                "version_id": str(version.id),
                "version_number": version.version_number,
                "created_dataset": created_dataset,
                "row_count": version.row_count,
                "schema_version": GITHUB_TOOL_DATASET_SCHEMA_VERSION,
                "collector_schema_versions": list(GITHUB_TOOL_COLLECTOR_SCHEMA_VERSIONS),
                "run_started": False,
            }
        ],
        blocked_reasons=[
            "工具情报 Dataset 版本已保存；尚未写出文件、创建漂移快照或生成报告。"
        ],
    )


async def dry_run_cleaning_plan(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationCleaningPlanDryRunRequest,
) -> AutomationCleaningPlanDryRunResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")

    preview = await preview_product_dataset(
        session,
        workspace,
        AutomationProductDatasetPreviewRequest(
            authorized=payload.authorized,
            task_run_ids=payload.task_run_ids,
            fields=payload.fields,
            max_rows=payload.max_rows,
        ),
    )
    selected_fields = preview.summary.selected_fields
    rows = [
        _cleaning_plan_dry_run_row(row, selected_fields, payload.rules)
        for row in preview.rows
    ]
    rows_changed = len([row for row in rows if row.changed_fields])
    cleaning_script = _cleaning_script_from_rules(payload.rules)
    export_preview = _cleaning_export_preview(rows, selected_fields)
    return AutomationCleaningPlanDryRunResponse(
        created_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        rows=rows,
        summary=AutomationCleaningPlanDryRunSummaryResponse(
            rows_count=len(rows),
            rows_changed=rows_changed,
            rules_count=len(payload.rules),
            selected_fields=selected_fields,
            dataset_version_created=False,
            cleaning_plan_created=False,
            run_started=False,
        ),
        cleaning_script=cleaning_script,
        export_preview=export_preview,
        audit_events=[
            {
                "event": "cleaning_plan_dry-run_requested",
                "requested_runs": len(payload.task_run_ids),
                "max_rows": payload.max_rows,
                "rules_count": len(payload.rules),
                "rows_changed": rows_changed,
                "run_started": False,
                "dataset_version_created": False,
            }
        ],
        blocked_reasons=[
            "清洗规则试跑只转换样本行，不会保存数据集版本。",
        ],
    )


async def create_cleaning_plan_asset(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    payload: AutomationCleaningPlanCreateRequest,
) -> AutomationCleaningPlanCreateResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    name = payload.name.strip()
    if not name:
        raise CollectorError("cleaning_plan_name_required")

    dry_run = await dry_run_cleaning_plan(session, workspace, payload)
    project_id = await _single_project_id_for_task_runs(
        session,
        workspace.id,
        payload.task_run_ids,
        payload.max_rows,
    )
    version_number = await next_cleaning_plan_version(session, workspace.id, name)
    cleaning_plan = CleaningPlan(
        workspace_id=workspace.id,
        project_id=project_id,
        created_by_user_id=user.id,
        name=name,
        version_number=version_number,
        target="ecommerce_product",
        selected_fields=dry_run.summary.selected_fields,
        source_task_run_ids=[str(task_run_id) for task_run_id in payload.task_run_ids],
        rules=[rule.model_dump(mode="json", exclude_none=True) for rule in payload.rules],
        cleaning_script=dry_run.cleaning_script,
        dry_run_preview=dry_run.model_dump(mode="json"),
        status="draft",
    )
    await create_cleaning_plan(session, cleaning_plan)
    cleaning_plan = await commit_and_refresh_cleaning_plan(session, cleaning_plan)
    plan_response = _cleaning_plan_response(cleaning_plan)
    return AutomationCleaningPlanCreateResponse(
        saved_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        cleaning_plan=plan_response,
        dry_run=dry_run,
        cleaning_plan_created=True,
        dataset_version_created=False,
        run_started=False,
        audit_events=[
            {
                "event": "cleaning_plan_created",
                "cleaning_plan_id": str(cleaning_plan.id),
                "version_number": cleaning_plan.version_number,
                "dataset_version_created": False,
                "run_started": False,
            }
        ],
        blocked_reasons=[
            "清洗计划已保存为草案；尚未保存数据集版本或启动采集。",
        ],
    )


async def list_cleaning_plan_assets(
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID | None = None,
    limit: int = 50,
) -> AutomationCleaningPlanListResponse:
    plans = await list_cleaning_plans(
        session,
        workspace.id,
        project_id=project_id,
        limit=limit,
    )
    total = await count_cleaning_plans(session, workspace.id, project_id=project_id)
    return AutomationCleaningPlanListResponse(
        items=[_cleaning_plan_response(plan) for plan in plans],
        total=total,
        dataset_version_created=False,
        run_started=False,
    )


async def save_product_dataset_version(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    payload: AutomationProductDatasetSaveRequest,
) -> AutomationProductDatasetSaveResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    dataset_name = payload.name.strip()
    if not dataset_name:
        raise CollectorError("dataset_name_required")
    cleaning_plan: CleaningPlan | None = None
    if payload.cleaning_plan_id is not None:
        cleaning_plan = await get_cleaning_plan(session, workspace.id, payload.cleaning_plan_id)
        if cleaning_plan is None:
            raise CollectorError("cleaning_plan_not_found")

    preview = await preview_product_dataset(session, workspace, payload)
    if not preview.rows:
        raise CollectorError("dataset_preview_empty")
    rows_for_version = preview.rows
    selected_fields = preview.summary.selected_fields
    cleaning_script = preview.cleaning_script_draft
    export_preview = preview.export_preview
    average_completeness_percent = preview.summary.average_completeness_percent

    if cleaning_plan is not None:
        dry_run = await dry_run_cleaning_plan(
            session,
            workspace,
            AutomationCleaningPlanDryRunRequest(
                authorized=payload.authorized,
                task_run_ids=payload.task_run_ids,
                fields=payload.fields or cleaning_plan.selected_fields,
                rules=[
                    AutomationCleaningRuleInput(**rule)
                    for rule in cleaning_plan.rules
                ],
                max_rows=payload.max_rows,
            ),
        )
        rows_for_version = _dataset_rows_from_cleaning_dry_run(
            dry_run.rows,
            dry_run.summary.selected_fields,
        )
        selected_fields = dry_run.summary.selected_fields
        cleaning_script = cleaning_plan.cleaning_script
        export_preview = dry_run.export_preview
        average_completeness_percent = _average_dataset_completeness(rows_for_version)

    raw_records = await _dataset_product_raw_records(
        session,
        workspace.id,
        payload.task_run_ids,
        payload.max_rows,
    )
    project_ids = {raw_record.project_id for raw_record in raw_records}
    if len(project_ids) != 1:
        raise CollectorError("dataset_project_lineage_ambiguous")
    project_id = next(iter(project_ids))
    if cleaning_plan is not None and cleaning_plan.project_id != project_id:
        raise CollectorError("cleaning_plan_project_lineage_conflict")

    await _lock_workspace_for_dataset_save(session, workspace.id)
    dataset = await get_dataset_by_name(session, workspace.id, dataset_name)
    created_dataset = False
    if dataset is None:
        dataset = Dataset(
            workspace_id=workspace.id,
            project_id=project_id,
            name=dataset_name,
            dataset_type="ecommerce_product",
            status="active",
            description=payload.description.strip() if payload.description else None,
        )
        session.add(dataset)
        await session.flush()
        created_dataset = True
    elif dataset.project_id != project_id:
        raise CollectorError("dataset_project_lineage_conflict")

    latest_version = await get_latest_dataset_version(session, dataset.id)
    next_version_number = 1 if latest_version is None else latest_version.version_number + 1
    created_at = datetime.now(UTC)
    version = DatasetVersion(
        dataset_id=dataset.id,
        workspace_id=workspace.id,
        project_id=dataset.project_id,
        created_by_user_id=user.id,
        cleaning_plan_id=cleaning_plan.id if cleaning_plan is not None else None,
        version_number=next_version_number,
        source_task_run_ids=[str(task_run_id) for task_run_id in payload.task_run_ids],
        selected_fields=selected_fields,
        cleaning_script=cleaning_script,
        rows=[
            {
                "row_id": row.row_id,
                "task_run_id": str(row.task_run_id),
                "raw_record_id": str(row.raw_record_id),
                "source_url": row.source_url,
                "values": row.values,
                "missing_fields": row.missing_fields,
                "completeness_percent": row.completeness_percent,
            }
            for row in rows_for_version
        ],
        export_preview=export_preview,
        row_count=len(rows_for_version),
        average_completeness_percent=average_completeness_percent,
        status="saved",
        created_at=created_at,
    )
    session.add(version)
    await session.commit()
    await session.refresh(dataset)
    await session.refresh(version)

    return AutomationProductDatasetSaveResponse(
        saved_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        dataset=AutomationDatasetResponse(
            id=dataset.id,
            project_id=dataset.project_id,
            name=dataset.name,
            dataset_type=dataset.dataset_type,
            status=dataset.status,
            description=dataset.description,
        ),
        version=AutomationDatasetVersionResponse(
            id=version.id,
            dataset_id=version.dataset_id,
            cleaning_plan_id=version.cleaning_plan_id,
            version_number=version.version_number,
            source_task_run_ids=version.source_task_run_ids,
            selected_fields=version.selected_fields,
            cleaning_script=version.cleaning_script,
            row_count=version.row_count,
            average_completeness_percent=version.average_completeness_percent,
            status=version.status,
            created_at=version.created_at,
            export_preview=version.export_preview,
        ),
        audit_events=[
            {
                "event": "product_dataset_version_saved",
                "dataset_id": str(dataset.id),
                "version_id": str(version.id),
                "version_number": version.version_number,
                "created_dataset": created_dataset,
                "row_count": version.row_count,
                "cleaning_plan_id": (
                    str(cleaning_plan.id) if cleaning_plan is not None else None
                ),
            }
        ],
        blocked_reasons=[
            "Dataset 版本已保存；尚未写出文件、对象存储导出或自动调度。"
        ],
    )


async def approve_product_schedule(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductScheduleApproveRequest,
) -> AutomationProductScheduleApproveResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")

    dataset = await get_dataset(session, workspace.id, payload.dataset_id)
    version = await get_dataset_version(
        session,
        workspace.id,
        payload.dataset_id,
        payload.dataset_version_id,
    )
    if dataset is None or version is None:
        raise CollectorError("dataset_version_not_found")
    if version.average_completeness_percent < payload.minimum_completeness_percent:
        raise CollectorError("dataset_quality_gate_failed")

    schedule_cron = payload.schedule_cron.strip() if payload.schedule_cron else None
    if schedule_cron is not None:
        try:
            cron_interval(schedule_cron)
        except UnsupportedCronExpression as exc:
            raise CollectorError("schedule_cron_unsupported") from exc

    approved_at = datetime.now(UTC)
    approved_tasks: list[AutomationScheduleApprovedTaskResponse] = []
    blocked_tasks: list[AutomationScheduleBlockedTaskResponse] = []
    seen_task_ids: set[uuid.UUID] = set()

    for task_id in payload.task_ids:
        if task_id in seen_task_ids:
            blocked_tasks.append(
                AutomationScheduleBlockedTaskResponse(
                    task_id=task_id,
                    reason="duplicate_task_id",
                )
            )
            continue
        seen_task_ids.add(task_id)
        task = await get_task(session, workspace.id, task_id)
        reason = _schedule_task_block_reason(task, dataset)
        if reason is not None:
            blocked_tasks.append(
                AutomationScheduleBlockedTaskResponse(task_id=task_id, reason=reason)
            )
            continue

        assert task is not None
        task.schedule_cron = schedule_cron
        task.config = _approved_schedule_config(
            task.config,
            dataset=dataset,
            version=version,
            payload=payload,
            approved_at=approved_at,
        )
        approved_tasks.append(
            AutomationScheduleApprovedTaskResponse(
                task_id=task.id,
                task_name=task.name,
                status=task.status,
                schedule_cron=task.schedule_cron,
                schedule_policy=payload.schedule_policy,
                freshness_target_hours=payload.freshness_target_hours,
                dataset_id=dataset.id,
                dataset_version_id=version.id,
                approved_at=approved_at,
            )
        )

    await session.commit()

    blocked_reasons = ["调度审批只更新任务配置，不会立即启动采集运行。"]
    if blocked_tasks:
        blocked_reasons.append("部分任务未通过调度审批条件，已在阻断任务列表中列出。")
    if not approved_tasks:
        blocked_reasons.append("没有任务进入已审批调度状态。")

    return AutomationProductScheduleApproveResponse(
        approved_at=approved_at,
        authorization_confirmed=payload.authorized,
        dataset=AutomationDatasetResponse(
            id=dataset.id,
            project_id=dataset.project_id,
            name=dataset.name,
            dataset_type=dataset.dataset_type,
            status=dataset.status,
            description=dataset.description,
        ),
        version=AutomationDatasetVersionResponse(
            id=version.id,
            dataset_id=version.dataset_id,
            version_number=version.version_number,
            source_task_run_ids=version.source_task_run_ids,
            selected_fields=version.selected_fields,
            cleaning_script=version.cleaning_script,
            row_count=version.row_count,
            average_completeness_percent=version.average_completeness_percent,
            status=version.status,
            created_at=version.created_at,
            export_preview=version.export_preview,
        ),
        approved_tasks=approved_tasks,
        blocked_tasks=blocked_tasks,
        summary=AutomationProductScheduleApproveSummaryResponse(
            requested_tasks=len(payload.task_ids),
            approved_tasks=len(approved_tasks),
            blocked_tasks=len(blocked_tasks),
            run_started=False,
        ),
        audit_events=[
            {
                "event": "product_schedule_approved",
                "dataset_id": str(dataset.id),
                "dataset_version_id": str(version.id),
                "approved_tasks": len(approved_tasks),
                "blocked_tasks": len(blocked_tasks),
                "run_started": False,
            }
        ],
        blocked_reasons=blocked_reasons,
    )


async def check_product_drift(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductDriftCheckRequest,
) -> AutomationProductDriftCheckResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")

    dataset = await get_dataset(session, workspace.id, payload.dataset_id)
    version = await get_dataset_version(
        session,
        workspace.id,
        payload.dataset_id,
        payload.dataset_version_id,
    )
    if dataset is None or version is None:
        raise CollectorError("dataset_version_not_found")

    checked_at = datetime.now(UTC)
    items: list[AutomationProductDriftItemResponse] = []
    audit_events: list[dict[str, object]] = [
        {
            "event": "product_drift_check_requested",
            "dataset_id": str(dataset.id),
            "dataset_version_id": str(version.id),
            "requested_tasks": len(payload.task_ids),
            "completeness_drop_threshold_percent": payload.completeness_drop_threshold_percent,
            "freshness_grace_hours": payload.freshness_grace_hours,
            "run_started": False,
            "alert_created": False,
        }
    ]
    seen_task_ids: set[uuid.UUID] = set()

    for task_id in payload.task_ids:
        if task_id in seen_task_ids:
            items.append(_blocked_drift_item(task_id, version, "duplicate_task_id"))
            audit_events.append(
                {
                    "event": "product_drift_task_blocked",
                    "task_id": str(task_id),
                    "reason": "duplicate_task_id",
                }
            )
            continue
        seen_task_ids.add(task_id)

        task = await get_task(session, workspace.id, task_id)
        reason = _drift_task_block_reason(task, dataset, version)
        if reason is not None:
            items.append(_blocked_drift_item(task_id, version, reason, task))
            audit_events.append(
                {
                    "event": "product_drift_task_blocked",
                    "task_id": str(task_id),
                    "reason": reason,
                }
            )
            continue

        assert task is not None
        latest_runs = await list_task_runs(session, workspace.id, task.id)
        latest_run = latest_runs[0] if latest_runs else None
        approved_fields = _dataset_fields(version.selected_fields)
        issues: list[str] = []
        latest_completeness_percent: int | None = None
        completeness_drop_percent: int | None = None
        missing_fields: list[str] = []
        new_missing_fields: list[str] = []
        row_change = "unchanged"
        added_row_count = 0
        removed_row_count = 0
        price_change_percent: float | None = None
        reused_deduplicated_records = False

        if latest_run is None:
            issues.append("latest_run_missing")
        elif latest_run.status not in {"success", "partial_success"}:
            issues.append("latest_run_failed")
        else:
            product_records, reused_deduplicated_records = await _product_records_for_task_run(
                session=session,
                workspace_id=workspace.id,
                task_run_id=latest_run.id,
                limit=500,
            )
            field_completeness = _product_field_completeness_for_fields(
                product_records,
                approved_fields,
            )
            latest_completeness_percent = field_completeness.completeness_percent
            completeness_drop_percent = max(
                version.average_completeness_percent - latest_completeness_percent,
                0,
            )
            missing_fields = field_completeness.missing_fields
            new_missing_fields = [
                field for field in approved_fields if field in field_completeness.missing_fields
            ]
            row_drift = _product_row_drift(
                version,
                product_records,
                task,
            )
            row_change = row_drift.row_change
            added_row_count = row_drift.added_row_count
            removed_row_count = row_drift.removed_row_count
            price_change_percent = row_drift.price_change_percent
            issues.extend(row_drift.issues)
            if completeness_drop_percent > payload.completeness_drop_threshold_percent:
                issues.append("completeness_drift_exceeded")
            if new_missing_fields:
                issues.append("approved_fields_missing")

        freshness_target_hours, stale_hours = _task_freshness_drift(
            task,
            checked_at,
            payload.freshness_grace_hours,
        )
        if stale_hours is not None and stale_hours > 0:
            issues.append("freshness_target_missed")

        status = _drift_status(issues)
        items.append(
            AutomationProductDriftItemResponse(
                task_id=task.id,
                task_name=task.name,
                source_url=_task_source_url(task),
                status=status,
                blocked_reason=None,
                latest_run_id=latest_run.id if latest_run else None,
                latest_run_status=latest_run.status if latest_run else None,
                dataset_version_completeness_percent=version.average_completeness_percent,
                latest_completeness_percent=latest_completeness_percent,
                completeness_drop_percent=completeness_drop_percent,
                missing_fields=missing_fields,
                new_missing_fields=new_missing_fields,
                row_change=row_change,
                added_row_count=added_row_count,
                removed_row_count=removed_row_count,
                price_change_percent=price_change_percent,
                freshness_target_hours=freshness_target_hours,
                stale_hours=stale_hours,
                issues=issues,
            )
        )
        audit_events.append(
            {
                "event": "product_drift_task_checked",
                "task_id": str(task.id),
                "latest_run_id": str(latest_run.id) if latest_run else None,
                "status": status,
                "issues": issues,
                "row_change": row_change,
                "added_row_count": added_row_count,
                "removed_row_count": removed_row_count,
                "price_change_percent": price_change_percent,
                "run_started": False,
                "alert_created": False,
                "deduplicated_source_records_reused": (
                    reused_deduplicated_records if latest_run else False
                ),
            }
        )

    summary = _product_drift_summary(payload.task_ids, items)
    blocked_reasons = ["漂移检查为只读评估，不会启动采集、创建告警或发送通知。"]
    if summary.blocked_tasks:
        blocked_reasons.append("部分任务未通过数据集版本审批谱系或类型校验。")
    if summary.critical_tasks:
        blocked_reasons.append("存在关键漂移，请先复核字段缺失、采集失败或数据集基准。")
    elif summary.warning_tasks:
        blocked_reasons.append("存在轻度漂移或新鲜度风险，建议在下次调度前复核。")

    return AutomationProductDriftCheckResponse(
        checked_at=checked_at,
        authorization_confirmed=payload.authorized,
        dataset=AutomationDatasetResponse(
            id=dataset.id,
            project_id=dataset.project_id,
            name=dataset.name,
            dataset_type=dataset.dataset_type,
            status=dataset.status,
            description=dataset.description,
        ),
        version=AutomationDatasetVersionResponse(
            id=version.id,
            dataset_id=version.dataset_id,
            version_number=version.version_number,
            source_task_run_ids=version.source_task_run_ids,
            selected_fields=version.selected_fields,
            cleaning_script=version.cleaning_script,
            row_count=version.row_count,
            average_completeness_percent=version.average_completeness_percent,
            status=version.status,
            created_at=version.created_at,
            export_preview=version.export_preview,
        ),
        items=items,
        summary=summary,
        audit_events=audit_events,
        blocked_reasons=blocked_reasons,
    )


async def check_github_tool_drift(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationGitHubToolDriftCheckRequest,
) -> AutomationProductDriftCheckResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")

    dataset = await get_dataset(session, workspace.id, payload.dataset_id)
    version = await get_dataset_version(
        session,
        workspace.id,
        payload.dataset_id,
        payload.dataset_version_id,
    )
    if dataset is None or version is None:
        raise CollectorError("dataset_version_not_found")
    if dataset.dataset_type != "github_tool_radar":
        raise CollectorError("dataset_type_not_github_tool_radar")

    checked_at = datetime.now(UTC)
    anchor_task_ids = await _dataset_version_task_ids(session, workspace, version)
    items: list[AutomationProductDriftItemResponse] = []
    audit_events: list[dict[str, object]] = [
        {
            "event": "github_tool_drift_check_requested",
            "dataset_id": str(dataset.id),
            "dataset_version_id": str(version.id),
            "requested_tasks": len(payload.task_ids),
            "completeness_drop_threshold_percent": payload.completeness_drop_threshold_percent,
            "freshness_grace_hours": payload.freshness_grace_hours,
            "run_started": False,
            "alert_created": False,
        }
    ]
    seen_task_ids: set[uuid.UUID] = set()

    for task_id in payload.task_ids:
        if task_id in seen_task_ids:
            items.append(_blocked_drift_item(task_id, version, "duplicate_task_id"))
            audit_events.append(
                {
                    "event": "github_tool_drift_task_blocked",
                    "task_id": str(task_id),
                    "reason": "duplicate_task_id",
                }
            )
            continue
        seen_task_ids.add(task_id)

        task = await get_task(session, workspace.id, task_id)
        reason = _github_tool_drift_task_block_reason(task, dataset, anchor_task_ids)
        if reason is not None:
            items.append(_blocked_drift_item(task_id, version, reason, task))
            audit_events.append(
                {
                    "event": "github_tool_drift_task_blocked",
                    "task_id": str(task_id),
                    "reason": reason,
                }
            )
            continue

        assert task is not None
        latest_runs = await list_task_runs(session, workspace.id, task.id)
        latest_run = latest_runs[0] if latest_runs else None
        approved_fields = _github_tool_dataset_fields(version.selected_fields)
        issues: list[str] = []
        latest_completeness_percent: int | None = None
        completeness_drop_percent: int | None = None
        missing_fields: list[str] = []
        new_missing_fields: list[str] = []
        layer_issues: list[str] = []
        signal_groups: dict[str, list[str]] = {}

        if latest_run is None:
            issues.append("latest_run_missing")
        elif latest_run.status not in {"success", "partial_success"}:
            issues.append("latest_run_failed")
        else:
            github_records = await _github_tool_raw_records_for_task_run(
                session=session,
                workspace_id=workspace.id,
                task_run_id=latest_run.id,
                limit=500,
            )
            field_completeness = _github_tool_field_completeness_for_fields(
                github_records,
                approved_fields,
            )
            latest_rows: list[AutomationProductDatasetRowResponse] = []
            for raw_record in github_records:
                latest_rows.extend(_github_tool_rows(raw_record, approved_fields))
            latest_completeness_percent = field_completeness.completeness_percent
            completeness_drop_percent = max(
                version.average_completeness_percent - latest_completeness_percent,
                0,
            )
            missing_fields = field_completeness.missing_fields
            new_missing_fields = [
                field for field in approved_fields if field in field_completeness.missing_fields
            ]
            if completeness_drop_percent > payload.completeness_drop_threshold_percent:
                issues.append("completeness_drift_exceeded")
            if new_missing_fields:
                issues.append("approved_fields_missing")
            layer_issues = _github_tool_metric_drift_issues(
                saved_rows=version.rows,
                latest_rows=latest_rows,
                selected_fields=approved_fields,
                checked_at=checked_at,
            )
            for issue in layer_issues:
                if issue not in issues:
                    issues.append(issue)
            signal_groups = _github_tool_drift_signal_groups(
                version=version,
                raw_records=github_records,
                approved_fields=approved_fields,
                new_missing_fields=new_missing_fields,
            )
            for issue in _github_tool_signal_group_issues(signal_groups):
                if issue not in issues:
                    issues.append(issue)

        freshness_target_hours, stale_hours = _task_freshness_drift(
            task,
            checked_at,
            payload.freshness_grace_hours,
        )
        if stale_hours is not None and stale_hours > 0:
            issues.append("freshness_target_missed")

        status = _drift_status(issues)
        items.append(
            AutomationProductDriftItemResponse(
                task_id=task.id,
                task_name=task.name,
                source_url=_task_source_url(task),
                status=status,
                blocked_reason=None,
                latest_run_id=latest_run.id if latest_run else None,
                latest_run_status=latest_run.status if latest_run else None,
                dataset_version_completeness_percent=version.average_completeness_percent,
                latest_completeness_percent=latest_completeness_percent,
                completeness_drop_percent=completeness_drop_percent,
                missing_fields=missing_fields,
                new_missing_fields=new_missing_fields,
                freshness_target_hours=freshness_target_hours,
                stale_hours=stale_hours,
                issues=issues,
                signal_groups=signal_groups,
            )
        )
        audit_events.append(
            {
                "event": "github_tool_drift_task_checked",
                "task_id": str(task.id),
                "latest_run_id": str(latest_run.id) if latest_run else None,
                "status": status,
                "issues": issues,
                "drift_layers": _drift_layer_counts_for_issues(issues),
                "metric_issues": layer_issues,
                "signal_groups": signal_groups,
                "run_started": False,
                "alert_created": False,
            }
        )

    summary = _product_drift_summary(payload.task_ids, items)
    blocked_reasons = ["GitHub 工具漂移检查为只读评估，不会启动采集、创建告警或发送通知。"]
    if summary.blocked_tasks:
        blocked_reasons.append("部分任务未通过 GitHub 工具数据集谱系或类型校验。")
    if summary.critical_tasks:
        blocked_reasons.append("存在关键工具情报漂移，请复核字段缺失、采集失败或基准版本。")
    elif summary.warning_tasks:
        blocked_reasons.append("存在轻度工具情报漂移或新鲜度风险，建议复核后再进入培训材料。")

    return AutomationProductDriftCheckResponse(
        checked_at=checked_at,
        authorization_confirmed=payload.authorized,
        dataset=_dataset_response(dataset),
        version=_dataset_version_response(version),
        items=items,
        summary=summary,
        audit_events=audit_events,
        blocked_reasons=blocked_reasons,
    )


async def save_product_drift_event(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductDriftEventSaveRequest,
) -> AutomationProductDriftEventResponse:
    checked = await check_product_drift(session, workspace, payload)
    created_at = datetime.now(UTC)
    event_status = _drift_event_status(checked.summary)
    summary_json = checked.summary.model_dump(mode="json")
    items_json = [item.model_dump(mode="json") for item in checked.items]
    idempotency_key = _product_drift_event_idempotency_key(
        dataset_id=checked.dataset.id,
        dataset_version_id=checked.version.id,
        task_ids=payload.task_ids,
        thresholds={
            "completeness_drop_threshold_percent": payload.completeness_drop_threshold_percent,
            "freshness_grace_hours": payload.freshness_grace_hours,
        },
        summary=summary_json,
        items=items_json,
        note=payload.note,
    )
    existing_event = await _existing_product_drift_event(
        session=session,
        workspace=workspace,
        dataset_id=checked.dataset.id,
        dataset_version_id=checked.version.id,
        idempotency_key=idempotency_key,
    )
    if existing_event is not None:
        existing_event.audit_events = [
            *existing_event.audit_events,
            {
                "event": "product_drift_event_reused",
                "dataset_id": str(checked.dataset.id),
                "dataset_version_id": str(checked.version.id),
                "status": existing_event.status,
                "idempotency_key": idempotency_key,
                "run_started": False,
                "alert_created": False,
            },
        ]
        await session.commit()
        await session.refresh(existing_event)
        return _drift_event_response(existing_event, checked.dataset, checked.version)

    audit_events = [
        *checked.audit_events,
        {
            "event": "product_drift_event_saved",
            "dataset_id": str(checked.dataset.id),
            "dataset_version_id": str(checked.version.id),
            "status": event_status,
            "idempotency_key": idempotency_key,
            "run_started": False,
            "alert_created": False,
        },
    ]
    event = DatasetDriftEvent(
        workspace_id=workspace.id,
        project_id=checked.dataset.project_id,
        dataset_id=checked.dataset.id,
        dataset_version_id=checked.version.id,
        event_type="ecommerce_product_drift",
        status=event_status,
        thresholds={
            "completeness_drop_threshold_percent": payload.completeness_drop_threshold_percent,
            "freshness_grace_hours": payload.freshness_grace_hours,
        },
        summary={**summary_json, "idempotency_key": idempotency_key},
        items=items_json,
        audit_events=audit_events,
        note=payload.note.strip() if payload.note and payload.note.strip() else None,
        created_at=created_at,
    )
    saved_event = await create_dataset_drift_event(session, event)
    return _drift_event_response(saved_event, checked.dataset, checked.version)


async def save_github_tool_drift_event(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationGitHubToolDriftEventSaveRequest,
) -> AutomationProductDriftEventResponse:
    checked = await check_github_tool_drift(session, workspace, payload)
    created_at = datetime.now(UTC)
    event_status = _drift_event_status(checked.summary)
    summary_json = checked.summary.model_dump(mode="json")
    items_json = [item.model_dump(mode="json") for item in checked.items]
    idempotency_key = _dataset_drift_event_idempotency_key(
        event_type="github_tool_radar_drift",
        dataset_id=checked.dataset.id,
        dataset_version_id=checked.version.id,
        task_ids=payload.task_ids,
        thresholds={
            "completeness_drop_threshold_percent": payload.completeness_drop_threshold_percent,
            "freshness_grace_hours": payload.freshness_grace_hours,
        },
        summary=summary_json,
        items=items_json,
        note=payload.note,
    )
    existing_event = await _existing_product_drift_event(
        session=session,
        workspace=workspace,
        dataset_id=checked.dataset.id,
        dataset_version_id=checked.version.id,
        idempotency_key=idempotency_key,
    )
    if existing_event is not None:
        existing_event.audit_events = [
            *existing_event.audit_events,
            {
                "event": "github_tool_drift_event_reused",
                "dataset_id": str(checked.dataset.id),
                "dataset_version_id": str(checked.version.id),
                "status": existing_event.status,
                "idempotency_key": idempotency_key,
                "run_started": False,
                "alert_created": False,
            },
        ]
        await session.commit()
        await session.refresh(existing_event)
        return _drift_event_response(existing_event, checked.dataset, checked.version)

    audit_events = [
        *checked.audit_events,
        {
            "event": "github_tool_drift_event_saved",
            "dataset_id": str(checked.dataset.id),
            "dataset_version_id": str(checked.version.id),
            "status": event_status,
            "idempotency_key": idempotency_key,
            "run_started": False,
            "alert_created": False,
        },
    ]
    event = DatasetDriftEvent(
        workspace_id=workspace.id,
        project_id=checked.dataset.project_id,
        dataset_id=checked.dataset.id,
        dataset_version_id=checked.version.id,
        event_type="github_tool_radar_drift",
        status=event_status,
        thresholds={
            "completeness_drop_threshold_percent": payload.completeness_drop_threshold_percent,
            "freshness_grace_hours": payload.freshness_grace_hours,
        },
        summary={**summary_json, "idempotency_key": idempotency_key},
        items=items_json,
        audit_events=audit_events,
        note=payload.note.strip() if payload.note and payload.note.strip() else None,
        created_at=created_at,
    )
    saved_event = await create_dataset_drift_event(session, event)
    return _drift_event_response(saved_event, checked.dataset, checked.version)


async def generate_github_tool_report(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationGitHubToolReportRequest,
) -> AutomationGitHubToolReportResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")

    dataset = await get_dataset(session, workspace.id, payload.dataset_id)
    version = await get_dataset_version(
        session,
        workspace.id,
        payload.dataset_id,
        payload.dataset_version_id,
    )
    if dataset is None or version is None:
        raise CollectorError("dataset_version_not_found")
    if dataset.dataset_type != "github_tool_radar":
        raise CollectorError("dataset_type_not_github_tool_radar")

    repositories = _github_tool_report_repositories(version.rows)
    top_repositories = sorted(
        repositories,
        key=lambda repository: repository.stars,
        reverse=True,
    )[: payload.top_limit]
    total_stars = sum(repository.stars for repository in repositories)
    languages = _count_repository_languages(repositories)
    top_topics = _count_repository_topics(repositories)
    high_value_count = len([
        repository
        for repository in repositories
        if repository.stars >= payload.min_stars
    ])
    licensed_count = len([
        repository
        for repository in repositories
        if repository.license_spdx_id
    ])
    release_tagged_count = len([
        repository
        for repository in repositories
        if repository.latest_release_tag
    ])
    readme_documented_count = len([
        repository
        for repository in repositories
        if repository.readme_detected is True
    ])
    issue_active_count = len([
        repository
        for repository in repositories
        if repository.issue_activity_status == "active"
    ])
    fresh_commit_count = len([
        repository
        for repository in repositories
        if repository.commit_freshness_status == "fresh"
    ])
    archived_count = len([
        repository
        for repository in repositories
        if repository.archived is True
    ])
    fork_count = len([
        repository
        for repository in repositories
        if repository.fork is True
    ])
    recommendations = _github_tool_report_recommendations(top_repositories, payload.min_stars)
    risk_sections = _github_tool_report_risk_sections(repositories)

    return AutomationGitHubToolReportResponse(
        generated_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        dataset=_dataset_response(dataset),
        version=_dataset_version_response(version),
        summary=AutomationGitHubToolReportSummaryResponse(
            repository_count=len(repositories),
            total_stars=total_stars,
            high_value_repositories=high_value_count,
            licensed_repositories=licensed_count,
            release_tagged_repositories=release_tagged_count,
            readme_documented_repositories=readme_documented_count,
            issue_active_repositories=issue_active_count,
            fresh_commit_repositories=fresh_commit_count,
            archived_repositories=archived_count,
            fork_repositories=fork_count,
            languages=languages,
            top_topics=top_topics,
            report_created=False,
            run_started=False,
        ),
        top_repositories=top_repositories,
        recommendations=recommendations,
        risk_sections=risk_sections,
        audit_events=[
            {
                "event": "github_tool_report_generated",
                "dataset_id": str(dataset.id),
                "dataset_version_id": str(version.id),
                "repository_count": len(repositories),
                "top_limit": payload.top_limit,
                "min_stars": payload.min_stars,
                "readme_documented_repositories": readme_documented_count,
                "issue_active_repositories": issue_active_count,
                "fresh_commit_repositories": fresh_commit_count,
                "risk_sections": risk_sections,
                "report_created": False,
                "run_started": False,
            }
        ],
        blocked_reasons=[
            "GitHub 工具雷达报告为只读生成，不会启动采集、创建报告资产或发送通知。"
        ],
    )


async def create_github_tool_report_asset(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    payload: AutomationGitHubToolReportAssetCreateRequest,
) -> AutomationGitHubToolReportAssetResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    if not payload.confirm_create:
        raise CollectorError("github_tool_report_asset_confirmation_required")

    generated = await generate_github_tool_report(session, workspace, payload)
    created_at = datetime.now(UTC)
    title = (
        f"GitHub 工具雷达报告 - {generated.dataset.name} "
        f"v{generated.version.version_number}"
    )
    report = Report(
        workspace_id=workspace.id,
        project_id=generated.dataset.project_id,
        report_type="github_tool_radar",
        title=title,
        content=_render_github_tool_report_asset_content(generated),
        status="generated",
        period_start=generated.version.created_at,
        period_end=created_at,
    )
    await create_report(session, report)
    await create_report_audit_event(
        session,
        ReportAuditEvent(
            workspace_id=workspace.id,
            report_id=report.id,
            actor_id=user.id,
            event_type="github_tool_report_asset_created",
            from_status=None,
            to_status=report.status,
            metadata_json=json.dumps(
                {
                    "dataset_id": str(generated.dataset.id),
                    "dataset_version_id": str(generated.version.id),
                    "repository_count": str(generated.summary.repository_count),
                    "top_limit": str(payload.top_limit),
                    "min_stars": str(payload.min_stars),
                    "report_created": "true",
                    "run_started": "false",
                    "notification_created": "false",
                },
                ensure_ascii=False,
            ),
            created_at=created_at,
        ),
    )
    await session.commit()
    await session.refresh(report)

    summary = generated.summary.model_copy(update={"report_created": True})
    audit_events = [
        *generated.audit_events,
        {
            "event": "github_tool_report_asset_created",
            "dataset_id": str(generated.dataset.id),
            "dataset_version_id": str(generated.version.id),
            "report_id": str(report.id),
            "report_created": True,
            "run_started": False,
            "notification_created": False,
        },
    ]
    return AutomationGitHubToolReportAssetResponse(
        generated_at=created_at,
        authorization_confirmed=generated.authorization_confirmed,
        dataset=generated.dataset,
        version=generated.version,
        summary=summary,
        top_repositories=generated.top_repositories,
        recommendations=generated.recommendations,
        risk_sections=generated.risk_sections,
        audit_events=audit_events,
        blocked_reasons=[
            "报告资产已保存到 Report 中心；不会启动采集、创建通知或发送邮件。"
        ],
        report=ReportResponse.from_model(report),
        notification_created=False,
    )


async def list_product_drift_events(
    session: AsyncSession,
    workspace: Workspace,
    dataset_id: uuid.UUID | None = None,
    dataset_version_id: uuid.UUID | None = None,
    limit: int = 20,
) -> AutomationProductDriftEventListResponse:
    events = await list_dataset_drift_events(
        session,
        workspace.id,
        dataset_id=dataset_id,
        dataset_version_id=dataset_version_id,
        limit=limit,
    )
    responses: list[AutomationProductDriftEventResponse] = []
    for event in events:
        dataset = await get_dataset(session, workspace.id, event.dataset_id)
        version = await get_dataset_version(
            session,
            workspace.id,
            event.dataset_id,
            event.dataset_version_id,
        )
        if dataset is None or version is None:
            continue
        responses.append(_drift_event_response(event, dataset, version))
    return AutomationProductDriftEventListResponse(
        items=responses,
        total=len(responses),
        run_started=False,
        alert_created=False,
    )


async def list_product_datasets(
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID | None = None,
    limit: int = 50,
) -> AutomationProductDatasetListResponse:
    datasets = await list_datasets(
        session,
        workspace.id,
        project_id=project_id,
        limit=limit,
    )
    items: list[AutomationProductDatasetListItemResponse] = []
    for dataset in datasets:
        latest_version = await get_latest_dataset_version(session, dataset.id)
        latest_events = await list_dataset_drift_events(
            session,
            workspace.id,
            dataset_id=dataset.id,
            limit=1,
        )
        latest_drift_event: AutomationProductDriftEventResponse | None = None
        if latest_events:
            event = latest_events[0]
            event_version = await get_dataset_version(
                session,
                workspace.id,
                event.dataset_id,
                event.dataset_version_id,
            )
            if event_version is not None:
                latest_drift_event = _drift_event_response(event, dataset, event_version)
        items.append(
            AutomationProductDatasetListItemResponse(
                dataset=_dataset_response(dataset),
                latest_version=(
                    _dataset_version_response(latest_version)
                    if latest_version is not None
                    else None
                ),
                version_count=await count_dataset_versions(session, workspace.id, dataset.id),
                latest_drift_event=latest_drift_event,
                drift_event_count=await count_dataset_drift_events(
                    session,
                    workspace.id,
                    dataset_id=dataset.id,
                ),
            )
        )
    return AutomationProductDatasetListResponse(
        items=items,
        total=len(items),
        run_started=False,
        alert_created=False,
    )


async def list_product_dataset_versions(
    session: AsyncSession,
    workspace: Workspace,
    dataset_id: uuid.UUID,
    limit: int = 50,
) -> AutomationProductDatasetVersionListResponse:
    dataset = await get_dataset(session, workspace.id, dataset_id)
    if dataset is None:
        raise CollectorError("dataset_not_found")
    versions = await list_dataset_versions(
        session,
        workspace.id,
        dataset_id,
        limit=limit,
    )
    return AutomationProductDatasetVersionListResponse(
        dataset=_dataset_response(dataset),
        versions=[_dataset_version_response(version) for version in versions],
        total=await count_dataset_versions(session, workspace.id, dataset_id),
        run_started=False,
        alert_created=False,
    )


async def create_product_dataset_export(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    payload: AutomationProductDatasetExportCreateRequest,
) -> AutomationProductDatasetExportJobResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    if not payload.confirm_create:
        raise CollectorError("dataset_export_confirmation_required")

    dataset, version = await _get_dataset_and_version(
        session,
        workspace,
        payload.dataset_id,
        payload.dataset_version_id,
    )
    export_format = payload.export_format
    job_id = uuid.uuid4()
    created_at = datetime.now(UTC)
    filename = _dataset_export_filename(dataset, version, job_id, export_format)
    target_path = _dataset_export_path(
        workspace_id=workspace.id,
        dataset_id=dataset.id,
        version_id=version.id,
        filename=filename,
    )
    audit_events: list[dict[str, object]] = [
        {
            "event": "product_dataset_export_requested",
            "dataset_id": str(dataset.id),
            "dataset_version_id": str(version.id),
            "export_format": export_format,
            "row_count": version.row_count,
            "run_started": False,
        }
    ]

    content = _render_dataset_export(dataset, version, export_format)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = target_path.with_name(f"{target_path.name}.tmp")
    temporary_path.write_bytes(content)
    temporary_path.replace(target_path)

    checksum = hashlib.sha256(content).hexdigest()
    finished_at = datetime.now(UTC)
    export_job = DatasetExportJob(
        id=job_id,
        workspace_id=workspace.id,
        project_id=dataset.project_id,
        dataset_id=dataset.id,
        dataset_version_id=version.id,
        created_by_user_id=user.id,
        export_format=export_format,
        status="success",
        filename=filename,
        content_type=DATASET_EXPORT_CONTENT_TYPES[export_format],
        artifact_path=str(target_path),
        artifact_size_bytes=len(content),
        row_count=version.row_count,
        checksum_sha256=checksum,
        error_message=None,
        audit_events=[
            *audit_events,
            {
                "event": "product_dataset_export_file_written",
                "artifact_size_bytes": len(content),
                "checksum_sha256": checksum,
                "run_started": False,
            },
        ],
        created_at=created_at,
        finished_at=finished_at,
    )
    created_job = await create_dataset_export_job(session, export_job)
    return _dataset_export_job_response(created_job, dataset, version)


async def list_product_dataset_exports(
    session: AsyncSession,
    workspace: Workspace,
    dataset_id: uuid.UUID,
    dataset_version_id: uuid.UUID | None = None,
    limit: int = 20,
) -> AutomationProductDatasetExportListResponse:
    dataset = await get_dataset(session, workspace.id, dataset_id)
    if dataset is None:
        raise CollectorError("dataset_not_found")
    if dataset_version_id is not None:
        version = await get_dataset_version(session, workspace.id, dataset.id, dataset_version_id)
        if version is None:
            raise CollectorError("dataset_version_not_found")
    jobs = await list_dataset_export_jobs(
        session,
        workspace.id,
        dataset.id,
        dataset_version_id=dataset_version_id,
        limit=limit,
    )
    items: list[AutomationProductDatasetExportJobResponse] = []
    for job in jobs:
        version = await get_dataset_version(
            session,
            workspace.id,
            job.dataset_id,
            job.dataset_version_id,
        )
        if version is None:
            continue
        items.append(_dataset_export_job_response(job, dataset, version))
    return AutomationProductDatasetExportListResponse(
        items=items,
        total=len(items),
        export_created=False,
        run_started=False,
    )


async def get_product_dataset_export_file(
    session: AsyncSession,
    workspace: Workspace,
    dataset_id: uuid.UUID,
    dataset_version_id: uuid.UUID,
    export_job_id: uuid.UUID,
) -> tuple[DatasetExportJob, Path]:
    dataset, version = await _get_dataset_and_version(
        session,
        workspace,
        dataset_id,
        dataset_version_id,
    )
    export_job = await get_dataset_export_job(
        session,
        workspace.id,
        dataset.id,
        version.id,
        export_job_id,
    )
    if export_job is None:
        raise CollectorError("dataset_export_not_found")
    if export_job.status != "success":
        raise CollectorError("dataset_export_not_ready")
    artifact_path = Path(export_job.artifact_path).resolve()
    export_root = _dataset_export_root().resolve()
    try:
        artifact_path.relative_to(export_root)
    except ValueError as exc:
        raise CollectorError("dataset_export_artifact_outside_root") from exc
    if not artifact_path.is_file():
        raise CollectorError("dataset_export_file_missing")
    return export_job, artifact_path


async def preview_product_drift_alert_rule(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductDriftAlertPreviewRequest,
) -> AutomationProductDriftAlertPreviewResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    dataset = await get_dataset(session, workspace.id, payload.dataset_id)
    if dataset is None:
        raise CollectorError("dataset_not_found")
    latest_version = (
        await get_dataset_version(
            session,
            workspace.id,
            dataset.id,
            payload.dataset_version_id,
        )
        if payload.dataset_version_id is not None
        else await get_latest_dataset_version(session, dataset.id)
    )
    if payload.dataset_version_id is not None and latest_version is None:
        raise CollectorError("dataset_version_not_found")

    statuses = _drift_alert_statuses(payload.min_status)
    events = await list_dataset_drift_events(
        session,
        workspace.id,
        dataset_id=dataset.id,
        dataset_version_id=payload.dataset_version_id,
        limit=payload.limit,
    )
    matched_event_models = [event for event in events if event.status in statuses]
    matched_events: list[AutomationProductDriftEventResponse] = []
    for event in matched_event_models:
        event_version = await get_dataset_version(
            session,
            workspace.id,
            event.dataset_id,
            event.dataset_version_id,
        )
        if event_version is None:
            continue
        matched_events.append(_drift_event_response(event, dataset, event_version))

    rule_draft = _drift_alert_rule_draft(
        dataset=dataset,
        latest_version=latest_version,
        min_status=payload.min_status,
        channel=payload.channel,
        enabled=payload.enabled,
        name=payload.name,
    )
    return _drift_alert_preview_response(
        dataset=dataset,
        latest_version=latest_version,
        rule_draft=rule_draft,
        matched_events=matched_events,
        authorization_confirmed=payload.authorized,
        alert_rule_created=False,
    )


async def create_product_drift_alert_rule(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductDriftAlertRuleCreateRequest,
) -> AutomationProductDriftAlertRuleCreateResponse:
    if not payload.confirm_create:
        raise CollectorError("drift_alert_rule_confirmation_required")
    preview = await preview_product_drift_alert_rule(session, workspace, payload)
    existing_rule = await _existing_product_drift_alert_rule(
        session=session,
        workspace=workspace,
        rule_draft=preview.rule_draft,
    )
    if existing_rule is not None:
        return AutomationProductDriftAlertRuleCreateResponse(
            generated_at=datetime.now(UTC),
            authorization_confirmed=preview.authorization_confirmed,
            dataset=preview.dataset,
            latest_version=preview.latest_version,
            rule_draft=preview.rule_draft,
            matched_events=preview.matched_events,
            summary=AutomationProductDriftAlertSummaryResponse(
                matched_events=preview.summary.matched_events,
                critical_events=preview.summary.critical_events,
                warning_events=preview.summary.warning_events,
                alert_rule_created=False,
                signal_created=False,
                alert_event_created=False,
                notification_created=False,
                run_started=False,
            ),
            blocked_reasons=[
                (
                    "已存在匹配的 DriftEvent 告警策略，已复用现有 AlertRule；"
                    "本次不会创建重复规则、回放历史事件、创建 Signal、AlertEvent 或发送通知。"
                ),
                "后续需要 DatasetDrift 信号桥接后，规则才会进入现有 AlertEvent 生成链路。",
            ],
            alert_rule=AlertRuleResponse.from_model(existing_rule),
        )
    rule = await create_alert_rule_from_payload(
        session,
        workspace,
        AlertRuleCreateRequest(
            name=preview.rule_draft.name,
            project_id=preview.rule_draft.project_id,
            signal_type=preview.rule_draft.signal_type,
            condition=preview.rule_draft.condition,
            channel=preview.rule_draft.channel,
            enabled=preview.rule_draft.enabled,
        ),
    )
    return AutomationProductDriftAlertRuleCreateResponse(
        generated_at=datetime.now(UTC),
        authorization_confirmed=preview.authorization_confirmed,
        dataset=preview.dataset,
        latest_version=preview.latest_version,
        rule_draft=preview.rule_draft,
        matched_events=preview.matched_events,
        summary=AutomationProductDriftAlertSummaryResponse(
            matched_events=preview.summary.matched_events,
            critical_events=preview.summary.critical_events,
            warning_events=preview.summary.warning_events,
            alert_rule_created=True,
            signal_created=False,
            alert_event_created=False,
            notification_created=False,
            run_started=False,
        ),
        blocked_reasons=[
            (
                "已创建 DriftEvent 告警策略；本次不会回放历史事件、"
                "创建 Signal、AlertEvent 或发送通知。"
            ),
            "后续需要 DatasetDrift 信号桥接后，规则才会进入现有 AlertEvent 生成链路。",
        ],
        alert_rule=AlertRuleResponse.from_model(rule),
    )


async def create_product_drift_alert_events(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductDriftAlertEventCreateRequest,
) -> AutomationProductDriftAlertEventCreateResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    if not payload.confirm_create:
        raise CollectorError("drift_alert_event_confirmation_required")

    dataset = await get_dataset(session, workspace.id, payload.dataset_id)
    if dataset is None:
        raise CollectorError("dataset_not_found")
    version = await get_dataset_version(
        session,
        workspace.id,
        dataset.id,
        payload.dataset_version_id,
    )
    if version is None:
        raise CollectorError("dataset_version_not_found")
    drift_event = await get_dataset_drift_event(
        session,
        workspace.id,
        payload.drift_event_id,
    )
    if drift_event is None:
        raise CollectorError("dataset_drift_event_not_found")
    if drift_event.dataset_id != dataset.id or drift_event.dataset_version_id != version.id:
        raise CollectorError("dataset_drift_event_lineage_mismatch")

    signal, signal_created = await _create_or_reuse_dataset_drift_signal(
        session=session,
        workspace=workspace,
        dataset=dataset,
        version=version,
        drift_event=drift_event,
    )
    alert_events = await match_alert_rules_for_signal(
        session,
        workspace,
        signal,
        intelligence=None,
        deliver_notifications=False,
    )
    await session.commit()
    await session.refresh(signal)
    for event in alert_events:
        await session.refresh(event)

    return AutomationProductDriftAlertEventCreateResponse(
        generated_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        dataset=_dataset_response(dataset),
        version=_dataset_version_response(version),
        drift_event=_drift_event_response(drift_event, dataset, version),
        signal=SignalResponse.from_model(signal),
        alert_events=[AlertEventResponse.from_model(event) for event in alert_events],
        summary=AutomationProductDriftAlertSummaryResponse(
            matched_events=1,
            critical_events=1 if drift_event.status == "critical" else 0,
            warning_events=1 if drift_event.status == "warning" else 0,
            alert_rule_created=False,
            signal_created=signal_created,
            alert_event_created=bool(alert_events),
            notification_created=False,
            run_started=False,
        ),
        blocked_reasons=[
            (
                "本次只桥接已保存 DriftEvent 到 Signal/AlertEvent；"
                "不会启动采集、创建 TaskRun、发送通知或写出文件。"
            ),
        ],
    )


async def send_product_drift_alert_notifications(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductDriftAlertNotificationSendRequest,
) -> AutomationProductDriftAlertNotificationSendResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    if not payload.confirm_send:
        raise CollectorError("drift_alert_notification_confirmation_required")

    dataset = await get_dataset(session, workspace.id, payload.dataset_id)
    if dataset is None:
        raise CollectorError("dataset_not_found")
    version = await get_dataset_version(
        session,
        workspace.id,
        dataset.id,
        payload.dataset_version_id,
    )
    if version is None:
        raise CollectorError("dataset_version_not_found")
    drift_event = await get_dataset_drift_event(
        session,
        workspace.id,
        payload.drift_event_id,
    )
    if drift_event is None:
        raise CollectorError("dataset_drift_event_not_found")
    if drift_event.dataset_id != dataset.id or drift_event.dataset_version_id != version.id:
        raise CollectorError("dataset_drift_event_lineage_mismatch")

    alert_events = []
    notifications = []
    notification_created = False
    now = datetime.now(UTC)
    for alert_event_id in list(dict.fromkeys(payload.alert_event_ids)):
        event = await get_alert_event(session, workspace.id, alert_event_id)
        if event is None:
            raise CollectorError("alert_event_not_found")
        signal = await get_signal(session, workspace.id, event.signal_id)
        if signal is None:
            raise CollectorError("alert_event_signal_not_found")
        _assert_dataset_drift_alert_event_matches(
            signal=signal,
            dataset=dataset,
            version=version,
            drift_event=drift_event,
        )
        rule = await get_alert_rule(session, workspace.id, event.rule_id)
        if rule is None:
            raise CollectorError("alert_event_rule_not_found")
        if rule.channel not in {"in_app", "both"}:
            raise CollectorError("alert_event_channel_not_in_app")

        notification = await get_notification_by_reference(
            session=session,
            user_id=workspace.owner_id,
            reference_type="alert_event",
            reference_id=event.id,
            notification_type="alert",
        )
        if notification is None:
            notification = await create_in_app_notification(
                session=session,
                user_id=workspace.owner_id,
                title=f"数据集漂移告警：{dataset.name}",
                body=(
                    f"{drift_event.event_type} 已命中 {rule.name}；"
                    f"状态 {drift_event.status}，请复核字段完整率与刷新策略。"
                ),
                notification_type="alert",
                reference_type="alert_event",
                reference_id=event.id,
            )
            notification_created = True
        event.status = "sent"
        if event.sent_at is None:
            event.sent_at = now
        alert_events.append(event)
        notifications.append(notification)

    await session.commit()
    for event in alert_events:
        await session.refresh(event)
    for notification in notifications:
        await session.refresh(notification)

    return AutomationProductDriftAlertNotificationSendResponse(
        generated_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        dataset=_dataset_response(dataset),
        version=_dataset_version_response(version),
        drift_event=_drift_event_response(drift_event, dataset, version),
        alert_events=[AlertEventResponse.from_model(event) for event in alert_events],
        notifications=[
            NotificationResponse.from_model(notification) for notification in notifications
        ],
        summary=AutomationProductDriftAlertSummaryResponse(
            matched_events=len(alert_events),
            critical_events=len(alert_events) if drift_event.status == "critical" else 0,
            warning_events=len(alert_events) if drift_event.status == "warning" else 0,
            alert_rule_created=False,
            signal_created=False,
            alert_event_created=False,
            notification_created=notification_created,
            run_started=False,
        ),
        blocked_reasons=[
            (
                "本次只发送已生成 AlertEvent 的站内通知；不会启动采集、"
                "创建 TaskRun、发送邮件、修改调度或写出文件。"
            ),
        ],
    )


async def send_product_drift_alert_emails(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductDriftAlertEmailSendRequest,
) -> AutomationProductDriftAlertEmailSendResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    if not payload.confirm_send:
        raise CollectorError("drift_alert_email_confirmation_required")

    dataset = await get_dataset(session, workspace.id, payload.dataset_id)
    if dataset is None:
        raise CollectorError("dataset_not_found")
    version = await get_dataset_version(
        session,
        workspace.id,
        dataset.id,
        payload.dataset_version_id,
    )
    if version is None:
        raise CollectorError("dataset_version_not_found")
    drift_event = await get_dataset_drift_event(
        session,
        workspace.id,
        payload.drift_event_id,
    )
    if drift_event is None:
        raise CollectorError("dataset_drift_event_not_found")
    if drift_event.dataset_id != dataset.id or drift_event.dataset_version_id != version.id:
        raise CollectorError("dataset_drift_event_lineage_mismatch")

    owner = await get_user_by_id(session, workspace.owner_id)
    if owner is None:
        raise CollectorError("workspace_owner_not_found")
    recipient_email = payload.recipient_email or owner.email

    email_deliveries: list[AutomationProductDriftAlertEmailDeliveryResponse] = []
    alert_events: list[AlertEvent] = []
    now = datetime.now(UTC)
    for alert_event_id in list(dict.fromkeys(payload.alert_event_ids)):
        event = await get_alert_event(session, workspace.id, alert_event_id)
        if event is None:
            raise CollectorError("alert_event_not_found")
        signal = await get_signal(session, workspace.id, event.signal_id)
        if signal is None:
            raise CollectorError("alert_event_signal_not_found")
        _assert_dataset_drift_alert_event_matches(
            signal=signal,
            dataset=dataset,
            version=version,
            drift_event=drift_event,
        )
        rule = await get_alert_rule(session, workspace.id, event.rule_id)
        if rule is None:
            raise CollectorError("alert_event_rule_not_found")
        if rule.channel not in {"email", "both"}:
            raise CollectorError("alert_event_channel_not_email")

        email_result = await send_email_notification(
            recipient_email=recipient_email,
            subject=f"数据集漂移告警：{dataset.name}",
            body=(
                f"漂移事件 {drift_event.event_type} 已命中 {rule.name}。"
                f"状态：{drift_event.status}，请复核字段完整率与刷新策略。"
            ),
        )
        email_deliveries.append(
            AutomationProductDriftAlertEmailDeliveryResponse(
                alert_event_id=event.id,
                recipient_email=recipient_email,
                delivered=email_result.delivered,
                delivered_at=now if email_result.delivered else None,
                reason=email_result.reason,
            )
        )
        alert_events.append(event)

    return AutomationProductDriftAlertEmailSendResponse(
        generated_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        dataset=_dataset_response(dataset),
        version=_dataset_version_response(version),
        drift_event=_drift_event_response(drift_event, dataset, version),
        alert_events=[AlertEventResponse.from_model(event) for event in alert_events],
        email_deliveries=email_deliveries,
        summary=AutomationProductDriftAlertSummaryResponse(
            matched_events=len(alert_events),
            critical_events=len(alert_events) if drift_event.status == "critical" else 0,
            warning_events=len(alert_events) if drift_event.status == "warning" else 0,
            alert_rule_created=False,
            signal_created=False,
            alert_event_created=False,
            notification_created=False,
            run_started=False,
        ),
        blocked_reasons=[
            (
                "本次只发送已生成 AlertEvent 的邮件告警；不会启动采集、"
                "创建 TaskRun、发送站内通知、修改调度或写出文件。"
            ),
        ],
    )


def _assert_dataset_drift_alert_event_matches(
    *,
    signal: Signal,
    dataset: Dataset,
    version: DatasetVersion,
    drift_event: DatasetDriftEvent,
) -> None:
    if signal.signal_type != "dataset_drift":
        raise CollectorError("alert_event_signal_type_mismatch")
    if signal.project_id != dataset.project_id:
        raise CollectorError("alert_event_project_mismatch")
    metadata = signal.metadata_json if isinstance(signal.metadata_json, dict) else {}
    expected = {
        "source": "dataset_drift_event",
        "dataset_id": str(dataset.id),
        "dataset_version_id": str(version.id),
        "drift_event_id": str(drift_event.id),
        "event_type": drift_event.event_type,
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise CollectorError("alert_event_dataset_drift_mismatch")


def _drift_alert_statuses(min_status: str) -> set[str]:
    if min_status == "warning":
        return {"warning", "critical"}
    return {"critical"}


def _drift_alert_severities(min_status: str) -> list[str]:
    if min_status == "warning":
        return ["medium", "high"]
    return ["high"]


def _drift_alert_rule_draft(
    *,
    dataset: Dataset,
    latest_version: DatasetVersion | None,
    min_status: str,
    channel: str,
    enabled: bool,
    name: str | None,
) -> AutomationProductDriftAlertRuleDraftResponse:
    normalized_name = name.strip() if name and name.strip() else None
    return AutomationProductDriftAlertRuleDraftResponse(
        name=normalized_name or f"Dataset drift alert: {dataset.name}",
        project_id=dataset.project_id,
        signal_type="dataset_drift",
        condition={
            "field": "severity",
            "op": "in",
            "value": _drift_alert_severities(min_status),
            "source": "dataset_drift_event",
            "dataset_id": str(dataset.id),
            "dataset_version_id": str(latest_version.id) if latest_version else None,
            "drift_statuses": sorted(_drift_alert_statuses(min_status)),
            "event_type": "ecommerce_product_drift",
        },
        channel=channel,
        enabled=enabled,
    )


def _product_drift_event_idempotency_key(
    *,
    dataset_id: uuid.UUID,
    dataset_version_id: uuid.UUID,
    task_ids: list[uuid.UUID],
    thresholds: dict[str, Any],
    summary: dict[str, Any],
    items: list[dict[str, Any]],
    note: str | None,
) -> str:
    return _dataset_drift_event_idempotency_key(
        event_type="ecommerce_product_drift",
        dataset_id=dataset_id,
        dataset_version_id=dataset_version_id,
        task_ids=task_ids,
        thresholds=thresholds,
        summary=summary,
        items=items,
        note=note,
    )


def _dataset_drift_event_idempotency_key(
    *,
    event_type: str,
    dataset_id: uuid.UUID,
    dataset_version_id: uuid.UUID,
    task_ids: list[uuid.UUID],
    thresholds: dict[str, Any],
    summary: dict[str, Any],
    items: list[dict[str, Any]],
    note: str | None,
) -> str:
    normalized_items = sorted(items, key=lambda item: str(item.get("task_id") or ""))
    return _stable_json_hash(
        {
            "event_type": event_type,
            "dataset_id": str(dataset_id),
            "dataset_version_id": str(dataset_version_id),
            "task_ids": sorted(str(task_id) for task_id in task_ids),
            "thresholds": thresholds,
            "summary": summary,
            "items": normalized_items,
            "note": note.strip() if note and note.strip() else None,
        }
    )


async def _existing_product_drift_event(
    *,
    session: AsyncSession,
    workspace: Workspace,
    dataset_id: uuid.UUID,
    dataset_version_id: uuid.UUID,
    idempotency_key: str,
) -> DatasetDriftEvent | None:
    events = await list_dataset_drift_events(
        session,
        workspace.id,
        dataset_id=dataset_id,
        dataset_version_id=dataset_version_id,
        limit=100,
    )
    for event in events:
        summary = event.summary if isinstance(event.summary, dict) else {}
        if summary.get("idempotency_key") == idempotency_key:
            return event
    return None


async def _existing_product_drift_alert_rule(
    *,
    session: AsyncSession,
    workspace: Workspace,
    rule_draft: AutomationProductDriftAlertRuleDraftResponse,
) -> AlertRule | None:
    rules = await list_alert_rules(session, workspace.id, enabled=rule_draft.enabled)
    expected_condition = _canonical_json(rule_draft.condition)
    for rule in rules:
        if rule.project_id != rule_draft.project_id:
            continue
        if rule.signal_type != rule_draft.signal_type:
            continue
        if rule.channel != rule_draft.channel:
            continue
        if _canonical_json(rule.condition) == expected_condition:
            return rule
    return None


def _drift_alert_preview_response(
    *,
    dataset: Dataset,
    latest_version: DatasetVersion | None,
    rule_draft: AutomationProductDriftAlertRuleDraftResponse,
    matched_events: list[AutomationProductDriftEventResponse],
    authorization_confirmed: bool,
    alert_rule_created: bool,
) -> AutomationProductDriftAlertPreviewResponse:
    critical_events = len([event for event in matched_events if event.status == "critical"])
    warning_events = len([event for event in matched_events if event.status == "warning"])
    blocked_reasons = [
        "告警策略预览只读取已保存 DriftEvent，不会创建 AlertRule、Signal、AlertEvent 或通知。",
    ]
    if not matched_events:
        blocked_reasons.append("当前筛选条件下没有匹配的历史 DriftEvent；策略仍可用于后续事件。")
    return AutomationProductDriftAlertPreviewResponse(
        generated_at=datetime.now(UTC),
        authorization_confirmed=authorization_confirmed,
        dataset=_dataset_response(dataset),
        latest_version=(
            _dataset_version_response(latest_version)
            if latest_version is not None
            else None
        ),
        rule_draft=rule_draft,
        matched_events=matched_events,
        summary=AutomationProductDriftAlertSummaryResponse(
            matched_events=len(matched_events),
            critical_events=critical_events,
            warning_events=warning_events,
            alert_rule_created=alert_rule_created,
            signal_created=False,
            alert_event_created=False,
            notification_created=False,
            run_started=False,
        ),
        blocked_reasons=blocked_reasons,
    )


async def _create_or_reuse_dataset_drift_signal(
    *,
    session: AsyncSession,
    workspace: Workspace,
    dataset: Dataset,
    version: DatasetVersion,
    drift_event: DatasetDriftEvent,
) -> tuple[Signal, bool]:
    existing = await _existing_dataset_drift_signal(session, workspace, drift_event)
    if existing is not None:
        return existing, False

    task_run, task = await _dataset_version_anchor_task(session, workspace, version)
    now = datetime.now(UTC)
    raw_record = RawRecord(
        workspace_id=workspace.id,
        project_id=dataset.project_id,
        source_id=task.source_id,
        task_run_id=task_run.id,
        record_type="dataset_drift_event",
        source_url=dataset.name,
        content={
            "source": "dataset_drift_event",
            "dataset_id": str(dataset.id),
            "dataset_version_id": str(version.id),
            "drift_event_id": str(drift_event.id),
            "event_type": drift_event.event_type,
            "status": drift_event.status,
            "summary": drift_event.summary,
            "thresholds": drift_event.thresholds,
            "items": drift_event.items,
        },
        content_hash=_stable_json_hash(
            {
                "record_type": "dataset_drift_event",
                "drift_event_id": str(drift_event.id),
            }
        ),
        screenshot_url=None,
        collected_at=drift_event.created_at,
        created_at=now,
    )
    session.add(raw_record)
    await session.flush()

    entity = await _upsert_dataset_entity(
        session=session,
        workspace=workspace,
        dataset=dataset,
        version=version,
        drift_event=drift_event,
    )
    previous_snapshot = (
        await get_entity_snapshot(session, entity.latest_snapshot_id)
        if entity.latest_snapshot_id is not None
        else None
    )
    if previous_snapshot is None:
        previous_snapshot = EntitySnapshot(
            entity_id=entity.id,
            raw_record_id=raw_record.id,
            snapshot_data={
                "dataset_id": str(dataset.id),
                "dataset_version_id": str(version.id),
                "event_type": "dataset_baseline",
                "status": version.status,
                "selected_fields": version.selected_fields,
                "row_count": version.row_count,
                "average_completeness_percent": version.average_completeness_percent,
            },
            metrics={
                "critical_tasks": 0,
                "warning_tasks": 0,
                "missing_field_tasks": 0,
                "average_completeness_percent": version.average_completeness_percent,
            },
            captured_at=version.created_at,
            created_at=now,
        )
        session.add(previous_snapshot)
        await session.flush()

    current_snapshot = EntitySnapshot(
        entity_id=entity.id,
        raw_record_id=raw_record.id,
        snapshot_data={
            "dataset_id": str(dataset.id),
            "dataset_version_id": str(version.id),
            "drift_event_id": str(drift_event.id),
            "event_type": drift_event.event_type,
            "status": drift_event.status,
            "summary": drift_event.summary,
            "thresholds": drift_event.thresholds,
            "items": drift_event.items,
        },
        metrics={
            "critical_tasks": _summary_number(drift_event.summary, "critical_tasks"),
            "warning_tasks": _summary_number(drift_event.summary, "warning_tasks"),
            "missing_field_tasks": _summary_number(drift_event.summary, "missing_field_tasks"),
            "checked_tasks": _summary_number(drift_event.summary, "checked_tasks"),
        },
        captured_at=drift_event.created_at,
        created_at=now,
    )
    session.add(current_snapshot)
    await session.flush()

    entity.latest_snapshot_id = current_snapshot.id
    entity.last_seen_at = drift_event.created_at
    entity.name = dataset.name

    current_value = _dataset_drift_signal_value(drift_event)
    signal = Signal(
        workspace_id=workspace.id,
        project_id=dataset.project_id,
        entity_id=entity.id,
        signal_type="dataset_drift",
        previous_snapshot_id=previous_snapshot.id,
        current_snapshot_id=current_snapshot.id,
        current_value=current_value,
        previous_value=0.0,
        delta=current_value,
        delta_ratio=None,
        confidence=90.0 if drift_event.status == "critical" else 80.0,
        severity=_dataset_drift_signal_severity(drift_event.status),
        metadata_json={
            "source": "dataset_drift_event",
            "dataset_id": str(dataset.id),
            "dataset_version_id": str(version.id),
            "drift_event_id": str(drift_event.id),
            "event_type": drift_event.event_type,
            "status": drift_event.status,
            "summary": drift_event.summary,
        },
        detected_at=datetime.now(UTC),
    )
    session.add(signal)
    await session.flush()
    return signal, True


async def _existing_dataset_drift_signal(
    session: AsyncSession,
    workspace: Workspace,
    drift_event: DatasetDriftEvent,
) -> Signal | None:
    signals = await list_signals(
        session,
        workspace.id,
        project_id=drift_event.project_id,
        signal_type="dataset_drift",
    )
    drift_event_id = str(drift_event.id)
    for signal in signals:
        metadata = signal.metadata_json if isinstance(signal.metadata_json, dict) else {}
        if metadata.get("drift_event_id") == drift_event_id:
            return signal
    return None


async def _dataset_version_anchor_task(
    session: AsyncSession,
    workspace: Workspace,
    version: DatasetVersion,
) -> tuple[TaskRun, CollectionTask]:
    for raw_id in version.source_task_run_ids:
        try:
            run_id = uuid.UUID(raw_id)
        except (TypeError, ValueError):
            continue
        task_run = await session.get(TaskRun, run_id)
        if task_run is None or task_run.workspace_id != workspace.id:
            continue
        task = await get_task(session, workspace.id, task_run.task_id)
        if task is None or task.project_id != version.project_id:
            continue
        return task_run, task
    raise CollectorError("dataset_drift_signal_bridge_lineage_missing")


async def _dataset_version_task_ids(
    session: AsyncSession,
    workspace: Workspace,
    version: DatasetVersion,
) -> set[uuid.UUID]:
    task_ids: set[uuid.UUID] = set()
    for raw_id in version.source_task_run_ids:
        try:
            run_id = uuid.UUID(raw_id)
        except (TypeError, ValueError):
            continue
        task_run = await session.get(TaskRun, run_id)
        if task_run is None or task_run.workspace_id != workspace.id:
            continue
        task = await get_task(session, workspace.id, task_run.task_id)
        if task is None or task.project_id != version.project_id:
            continue
        task_ids.add(task.id)
    return task_ids


async def _upsert_dataset_entity(
    *,
    session: AsyncSession,
    workspace: Workspace,
    dataset: Dataset,
    version: DatasetVersion,
    drift_event: DatasetDriftEvent,
) -> Entity:
    external_id = f"dataset:{dataset.id}"
    entity = await get_entity_by_external_id(session, workspace.id, "dataset", external_id)
    if entity is not None:
        return entity
    entity = Entity(
        workspace_id=workspace.id,
        project_id=dataset.project_id,
        entity_type="dataset",
        external_id=external_id,
        canonical_url=None,
        name=dataset.name,
        domain="ecommerce",
        latest_snapshot_id=None,
        first_seen_at=version.created_at,
        last_seen_at=drift_event.created_at,
    )
    session.add(entity)
    await session.flush()
    return entity


def _dataset_drift_signal_value(drift_event: DatasetDriftEvent) -> float:
    critical_tasks = _summary_number(drift_event.summary, "critical_tasks")
    missing_fields = _summary_number(drift_event.summary, "missing_field_tasks")
    return max(critical_tasks, missing_fields)


def _dataset_drift_signal_severity(status: str) -> str:
    if status == "critical":
        return "high"
    if status == "warning":
        return "medium"
    return "low"


def _summary_number(summary: dict[str, object], key: str) -> float:
    value = summary.get(key)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _stable_json_hash(value: dict[str, object]) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _probe_agent_reach_channel() -> AutomationAgentReachChannelProbeResponse:
    command_path = shutil.which("agent-reach")
    if not command_path:
        return AutomationAgentReachChannelProbeResponse(
            installed=False,
            command_path=None,
            doctor_status="missing_tool",
            active_backend=None,
            requires_login=False,
            requires_proxy=False,
            blocked_reason="agent_reach_not_installed",
            platforms=[],
            read_invoked=False,
            search_invoked=False,
            raw_summary={
                "checked_command": "agent-reach",
                "side_effects": "no_read_no_search_no_write",
            },
        )

    try:
        result = subprocess.run(
            [command_path, "doctor", "--json"],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return AutomationAgentReachChannelProbeResponse(
            installed=True,
            command_path=command_path,
            doctor_status="blocked",
            active_backend=None,
            requires_login=False,
            requires_proxy=False,
            blocked_reason=type(exc).__name__,
            platforms=[],
            read_invoked=False,
            search_invoked=False,
            raw_summary={"error": str(exc), "side_effects": "doctor_only"},
        )

    parsed: dict[str, Any] = {}
    if result.stdout.strip():
        try:
            loaded = json.loads(result.stdout)
            if isinstance(loaded, dict):
                parsed = loaded
        except json.JSONDecodeError:
            parsed = {"stdout_preview": result.stdout[:500]}
    status_text = json.dumps(parsed, ensure_ascii=False).lower()
    requires_login = any(token in status_text for token in ("login", "cookie", "browser_profile"))
    requires_proxy = "proxy" in status_text
    platforms = _agent_reach_platforms(parsed)
    active_backend = _agent_reach_active_backend(parsed)
    doctor_status: Literal[
        "available",
        "missing_tool",
        "not_configured",
        "requires_login",
        "requires_proxy",
        "blocked",
        "unknown",
    ]
    if result.returncode == 0:
        doctor_status = "available"
    elif requires_login:
        doctor_status = "requires_login"
    elif requires_proxy:
        doctor_status = "requires_proxy"
    else:
        doctor_status = "blocked"
    return AutomationAgentReachChannelProbeResponse(
        installed=True,
        command_path=command_path,
        doctor_status=doctor_status,
        active_backend=active_backend,
        requires_login=requires_login,
        requires_proxy=requires_proxy,
        blocked_reason=None if result.returncode == 0 else f"doctor_exit_{result.returncode}",
        platforms=platforms,
        read_invoked=False,
        search_invoked=False,
        raw_summary={
            "exit_code": result.returncode,
            "stdout_keys": sorted(parsed.keys())[:20],
            "stderr_preview": result.stderr[:500] if result.stderr else "",
            "side_effects": "doctor_only_no_read_no_search_no_write",
        },
    )


def _agent_reach_platforms(payload: dict[str, Any]) -> list[str]:
    for key in ("platforms", "channels", "tools"):
        value = payload.get(key)
        if isinstance(value, list):
            platforms: list[str] = []
            for item in value:
                if isinstance(item, str):
                    platforms.append(item)
                elif isinstance(item, dict):
                    name = item.get("name") or item.get("platform") or item.get("id")
                    if isinstance(name, str):
                        platforms.append(name)
            return sorted(set(platforms))
        if isinstance(value, dict):
            return sorted(str(item) for item in value)
    return []


def _agent_reach_active_backend(payload: dict[str, Any]) -> str | None:
    for key in ("active_backend", "backend", "selected_backend"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    channels = payload.get("channels")
    if isinstance(channels, dict):
        for value in channels.values():
            if isinstance(value, dict):
                backend = value.get("active_backend") or value.get("backend")
                if isinstance(backend, str) and backend:
                    return backend
    return None


def _candidate(
    backend_id: str,
    label: str,
    priority: int,
    status: Literal[
        "available",
        "missing_tool",
        "not_configured",
        "requires_login",
        "requires_proxy",
        "manual_review",
        "blocked",
        "unknown",
    ],
    credential_mode: Literal[
        "none",
        "token",
        "cookie",
        "browser_profile",
        "manual_export",
        "unknown",
    ],
    *,
    requires_login: bool = False,
    requires_proxy: bool = False,
    evidence_level: Literal[
        "L0-unverified",
        "L1-repo-or-runtime",
        "L2-fixture-or-dry-run",
        "L3-production-read-only",
        "L4-authorized-live",
    ] = "L1-repo-or-runtime",
    notes: list[str] | None = None,
) -> AutomationCapabilityProbeBackendCandidateResponse:
    return AutomationCapabilityProbeBackendCandidateResponse(
        backend_id=backend_id,
        label=label,
        priority=priority,
        status=status,
        credential_mode=credential_mode,
        requires_login=requires_login,
        requires_proxy=requires_proxy,
        evidence_level=evidence_level,
        notes=notes or [],
    )


def _agent_reach_candidate(
    agent_reach: AutomationAgentReachChannelProbeResponse,
    priority: int,
    *,
    requires_login: bool = False,
    requires_proxy: bool = False,
    notes: list[str] | None = None,
) -> AutomationCapabilityProbeBackendCandidateResponse:
    status = agent_reach.doctor_status
    return _candidate(
        "agent_reach_channel",
        "Agent Reach channel probe",
        priority,
        status,
        "unknown",
        requires_login=requires_login or agent_reach.requires_login,
        requires_proxy=requires_proxy or agent_reach.requires_proxy,
        notes=[
            *(notes or []),
            (
                "Only `agent-reach doctor --json` is allowed in this probe; "
                "read/search are not invoked."
            ),
        ],
    )


def _capability_probe_catalog(
    generated_at: str,
    agent_reach: AutomationAgentReachChannelProbeResponse,
) -> list[AutomationCapabilityProbeResponse]:
    browser_harness_path = shutil.which("browser-harness")
    browser_harness_status: Literal["available", "missing_tool"] = (
        "available" if browser_harness_path else "missing_tool"
    )
    common_forbidden = [
        "submit_form",
        "login_bypass",
        "cookie_export",
        "anti_detect",
        "notification_send",
        "scheduler_mutation",
    ]
    return [
        AutomationCapabilityProbeResponse(
            platform_id="github",
            platform_label="GitHub API-first",
            generated_at=generated_at,
            doctor_status="available",
            credential_mode="token",
            execution_boundary="executable",
            risk_level="low",
            backend_candidates=[
                _candidate(
                    "official_github_api",
                    "GitHub REST/Search API",
                    1,
                    "available",
                    "token",
                    notes=["Formal facts should continue to come from the official GitHub API."],
                ),
                _agent_reach_candidate(
                    agent_reach,
                    2,
                    notes=[
                        (
                            "Use only as router/doctor or supplemental local lookup, "
                            "not as source of record."
                        )
                    ],
                ),
            ],
            agent_reach=agent_reach,
            allowed_outputs=["Source", "TaskRun", "RawRecord", "DatasetVersion", "Report"],
            forbidden_actions=common_forbidden,
            next_actions=[
                "Deepen release, README, license, issue activity, and freshness fields.",
                "Keep GitHub API as source of record.",
            ],
            run_started=False,
            collection_resources_written=False,
        ),
        AutomationCapabilityProbeResponse(
            platform_id="public_web_rss_docs",
            platform_label="Public Web / RSS / Docs",
            generated_at=generated_at,
            doctor_status="available",
            credential_mode="none",
            execution_boundary="read_only_probe",
            risk_level="low",
            backend_candidates=[
                _candidate(
                    "generic_web",
                    "Generic Web collector",
                    1,
                    "available",
                    "none",
                    notes=["Available for public URL snapshots after authorization."],
                ),
                _candidate(
                    "rss_feedparser",
                    "RSS/Atom parser",
                    2,
                    "manual_review",
                    "none",
                    notes=["Planned P1 package; not yet a stable collector in this project."],
                ),
                _agent_reach_candidate(agent_reach, 3),
            ],
            agent_reach=agent_reach,
            allowed_outputs=["ExternalToolSnapshot", "RawRecord", "DatasetVersion"],
            forbidden_actions=common_forbidden,
            next_actions=[
                "Define public-web-rss-docs platform package.",
                "Add fixture coverage for one public docs page and one public feed.",
            ],
            run_started=False,
            collection_resources_written=False,
        ),
        AutomationCapabilityProbeResponse(
            platform_id="browser_preflight",
            platform_label="Browser Harness read-only evidence",
            generated_at=generated_at,
            doctor_status=browser_harness_status,
            credential_mode="browser_profile",
            execution_boundary="read_only_probe",
            risk_level="medium",
            backend_candidates=[
                _candidate(
                    "browser_harness_probe",
                    "browser-harness CLI",
                    1,
                    browser_harness_status,
                    "browser_profile",
                    notes=[
                        "Use only for bounded page info, selector, and network evidence.",
                        "Do not create Source/Task/Dataset from the probe result directly.",
                    ],
                ),
                _candidate(
                    "snapshot_replay",
                    "Saved diagnostic snapshot replay",
                    2,
                    "available",
                    "none",
                    evidence_level="L2-fixture-or-dry-run",
                    notes=["Existing local replay asset stays no-run and no-file-write."],
                ),
            ],
            agent_reach=None,
            allowed_outputs=["BrowserDiagnosticJobRun"],
            forbidden_actions=common_forbidden,
            next_actions=[
                "Extend BrowserDiagnosticJobRun with selector evaluation and network metadata.",
                "Keep files_written=false until artifact retention is approved.",
            ],
            run_started=False,
            collection_resources_written=False,
        ),
        AutomationCapabilityProbeResponse(
            platform_id="video_public_transcript",
            platform_label="YouTube / Bilibili public transcript import",
            generated_at=generated_at,
            doctor_status="manual_review",
            credential_mode="none",
            execution_boundary="import_only",
            risk_level="medium",
            backend_candidates=[
                _agent_reach_candidate(
                    agent_reach,
                    1,
                    notes=[
                        (
                            "Candidate for metadata/transcript import only; "
                            "media download is forbidden by default."
                        )
                    ],
                ),
                _candidate(
                    "manual_transcript_import",
                    "Manual metadata/transcript import",
                    2,
                    "manual_review",
                    "manual_export",
                    notes=["First production-safe path is reviewed import, not crawler execution."],
                ),
            ],
            agent_reach=agent_reach,
            allowed_outputs=["ExternalToolSnapshot", "DatasetVersion"],
            forbidden_actions=[*common_forbidden, "media_download"],
            next_actions=[
                "Define metadata/transcript import template.",
                "Record transcript source, URL, publish time, and rights boundary.",
            ],
            run_started=False,
            collection_resources_written=False,
        ),
        AutomationCapabilityProbeResponse(
            platform_id="marketplace_authorized_import",
            platform_label="Marketplace API/export/import",
            generated_at=generated_at,
            doctor_status="manual_review",
            credential_mode="manual_export",
            execution_boundary="import_only",
            risk_level="medium",
            backend_candidates=[
                _candidate(
                    "official_marketplace_api",
                    "Official API or authorized export",
                    1,
                    "manual_review",
                    "token",
                    notes=["Amazon/SP-API or seller-console export must be separately authorized."],
                ),
                _candidate(
                    "browser_structure_assessment",
                    "Public page structure assessment",
                    2,
                    "manual_review",
                    "none",
                    notes=[
                        "Browser evidence can assess structure, not default scraping permission."
                    ],
                ),
            ],
            agent_reach=None,
            allowed_outputs=["ExternalToolSnapshot", "DatasetVersion"],
            forbidden_actions=common_forbidden,
            next_actions=[
                "Create one marketplace CSV/API import template.",
                "Keep page scraping blocked until authorization and platform policy are explicit.",
            ],
            run_started=False,
            collection_resources_written=False,
        ),
        AutomationCapabilityProbeResponse(
            platform_id="social_sop_import_only",
            platform_label="Twitter/X, Xiaohongshu, Instagram, LinkedIn",
            generated_at=generated_at,
            doctor_status="blocked",
            credential_mode="manual_export",
            execution_boundary="sop_only",
            risk_level="high",
            backend_candidates=[
                _agent_reach_candidate(
                    agent_reach,
                    1,
                    requires_login=True,
                    notes=[
                        (
                            "External support does not promote these platforms to "
                            "product-level collection."
                        )
                    ],
                ),
                _candidate(
                    "manual_sop_import",
                    "Reviewed SOP/import template",
                    2,
                    "manual_review",
                    "manual_export",
                    notes=["Default safe path is SOP/import-only."],
                ),
            ],
            agent_reach=agent_reach,
            allowed_outputs=["ExternalToolSnapshot"],
            forbidden_actions=[
                *common_forbidden,
                "bulk_scroll_collection",
                "personal_profile_enrichment",
            ],
            next_actions=[
                "Keep automatic collection disabled.",
                "Create field templates and manual import SOP only.",
            ],
            run_started=False,
            collection_resources_written=False,
        ),
    ]


def _platform_packages() -> list[AutomationPlatformPackageResponse]:
    return [
        AutomationPlatformPackageResponse(
            id="shopify-independent-ecommerce",
            name="独立站 / Shopify-style 商品采集",
            category="ecommerce",
            summary=(
                "面向公开商品详情页和集合页，优先读取 Product JSON-LD、"
                "页面结构和同源商品链接，适合作为电商平台自动化采集首个可执行包。"
            ),
            supported_targets=["ecommerce_product", "ecommerce_product_collection"],
            collector_types=["ecommerce_product_discovery", "ecommerce_product_page"],
            field_schema=[
                AutomationPlatformPackageFieldResponse(
                    key="title",
                    label="商品标题",
                    data_type="string",
                    required=True,
                    source="json_ld_or_dom",
                    cleaning_rule="strip_text",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="price",
                    label="价格",
                    data_type="decimal",
                    required=False,
                    source="json_ld_or_dom",
                    cleaning_rule="parse_decimal",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="price_min",
                    label="最低价",
                    data_type="decimal",
                    required=False,
                    source="json_ld_offer_list",
                    cleaning_rule="parse_decimal",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="price_max",
                    label="最高价",
                    data_type="decimal",
                    required=False,
                    source="json_ld_offer_list",
                    cleaning_rule="parse_decimal",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="currency",
                    label="货币",
                    data_type="string",
                    required=False,
                    source="json_ld_or_dom",
                    cleaning_rule="uppercase",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="availability",
                    label="库存状态",
                    data_type="enum",
                    required=False,
                    source="json_ld_or_dom",
                    cleaning_rule="normalize_availability",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="availability_detail",
                    label="库存明细",
                    data_type="string",
                    required=False,
                    source="json_ld_offer_list",
                    cleaning_rule="strip_text",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="sku",
                    label="SKU",
                    data_type="string",
                    required=False,
                    source="json_ld_or_dom",
                    cleaning_rule="fill_default",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="variant",
                    label="变体",
                    data_type="string",
                    required=False,
                    source="json_ld_variant_or_offer",
                    cleaning_rule="strip_text",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="brand",
                    label="品牌",
                    data_type="string",
                    required=False,
                    source="json_ld_or_meta",
                    cleaning_rule="strip_text",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="category",
                    label="分类",
                    data_type="string",
                    required=False,
                    source="json_ld_or_meta",
                    cleaning_rule="strip_text",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="image_url",
                    label="主图",
                    data_type="url",
                    required=False,
                    source="json_ld_or_meta",
                    cleaning_rule="normalize_url",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="canonical_url",
                    label="规范 URL",
                    data_type="url",
                    required=True,
                    source="page_url_or_canonical",
                    cleaning_rule="normalize_url",
                ),
            ],
            default_entrypoint="product-discovery",
            sample_urls=[
                AutomationPlatformPackageSampleUrlResponse(
                    label="集合页样例",
                    entrypoint="product-discovery",
                    url="https://shop.example/collections/summer-bags",
                    description="用于从公开集合页发现商品 URL，再进入 fan-out 小批量采集。",
                ),
                AutomationPlatformPackageSampleUrlResponse(
                    label="商品页样例",
                    entrypoint="site-analysis",
                    url="https://shop.example/products/demo-bag",
                    description="用于直接验证 Product JSON-LD、价格、SKU 和 canonical URL 字段。",
                ),
            ],
            cleaning_rules=[
                AutomationPlatformPackageCleaningRuleResponse(
                    field="title",
                    operation="strip_text",
                    description="去除商品标题首尾空白并合并重复空格。",
                ),
                AutomationPlatformPackageCleaningRuleResponse(
                    field="price",
                    operation="parse_decimal",
                    description="将价格字段转换为可排序的 decimal number。",
                ),
                AutomationPlatformPackageCleaningRuleResponse(
                    field="sku",
                    operation="fill_default",
                    value="UNKNOWN-SKU",
                    description="缺失 SKU 时保留可审计默认值，避免主键生成断裂。",
                ),
                AutomationPlatformPackageCleaningRuleResponse(
                    field="price_min",
                    operation="parse_decimal",
                    description="从多 offer 或变体价格中提取最低 decimal number。",
                ),
                AutomationPlatformPackageCleaningRuleResponse(
                    field="price_max",
                    operation="parse_decimal",
                    description="从多 offer 或变体价格中提取最高 decimal number。",
                ),
                AutomationPlatformPackageCleaningRuleResponse(
                    field="currency",
                    operation="uppercase",
                    description="把货币代码统一为大写，便于跨站点合并。",
                ),
                AutomationPlatformPackageCleaningRuleResponse(
                    field="availability",
                    operation="normalize_availability",
                    description="库存状态归一为 in_stock/out_of_stock/unknown。",
                ),
                AutomationPlatformPackageCleaningRuleResponse(
                    field="availability_detail",
                    operation="strip_text",
                    description="保留变体或 offer 级库存状态，便于人工复核。",
                ),
                AutomationPlatformPackageCleaningRuleResponse(
                    field="variant",
                    operation="strip_text",
                    description="保留商品变体名称或维度摘要。",
                ),
                AutomationPlatformPackageCleaningRuleResponse(
                    field="category",
                    operation="strip_text",
                    description="保留商品分类层级，便于跨站点聚合。",
                ),
                AutomationPlatformPackageCleaningRuleResponse(
                    field="image_url",
                    operation="normalize_url",
                    description="规范主图 URL，便于证据回溯。",
                ),
                AutomationPlatformPackageCleaningRuleResponse(
                    field="canonical_url",
                    operation="normalize_url",
                    description="规范 URL 字段，降低重复商品记录。",
                ),
            ],
            operator_checklist=[
                "确认目标页面公开可访问，不依赖登录态、验证码或购物车状态。",
                "优先从集合页或 sitemap 发现 5-20 个候选商品 URL，再人工剔除无关链接。",
                (
                    "保留 title、price、canonical_url 作为最小必选字段；"
                    "SKU、variant、category、image_url 可作为质量加分字段。"
                ),
                "检查 pagination、canonical 去重和 skipped reason 后再 fan-out。",
                "先执行清洗计划试跑，确认价格和库存字段正常后再保存数据集版本。",
            ],
            strategy_matrix=[
                AutomationPlatformPackageStrategyResponse(
                    id="collection-to-products",
                    label="集合页发现商品 URL",
                    entrypoint="product-discovery",
                    collector_type="ecommerce_product_discovery",
                    fit="high",
                    can_start_from_automation=True,
                    review_required=True,
                    description="从公开集合页发现商品链接，人工确认后 fan-out 创建商品页任务。",
                ),
                AutomationPlatformPackageStrategyResponse(
                    id="single-product-analysis",
                    label="单商品页字段解析",
                    entrypoint="site-analysis",
                    collector_type="ecommerce_product_page",
                    fit="high",
                    can_start_from_automation=True,
                    review_required=False,
                    description="直接解析一个公开商品详情页，生成字段候选和采集计划。",
                ),
            ],
            risk_boundaries=[
                AutomationPlatformPackageRiskBoundaryResponse(
                    condition="页面公开访问且不需要登录态",
                    severity="info",
                    guidance="可在授权确认后进入 Automation 小批量采集链路。",
                ),
                AutomationPlatformPackageRiskBoundaryResponse(
                    condition="出现验证码、登录墙、购物车态或个人数据",
                    severity="blocked",
                    guidance="停止自动采集，改为人工评估或平台官方 API。",
                ),
                AutomationPlatformPackageRiskBoundaryResponse(
                    condition="字段缺失率高于质量阈值",
                    severity="warning",
                    guidance="先调整字段选择和清洗计划，再保存数据集版本。",
                ),
            ],
            sop_links=[
                AutomationPlatformPackageSopLinkResponse(
                    label="平台方法卡",
                    href="/toolkit?category=platform_method",
                ),
                AutomationPlatformPackageSopLinkResponse(
                    label="采集工作台",
                    href="/automation",
                ),
            ],
            sample_fixture=AutomationPlatformPackageFixtureResponse(
                fixture_type="deterministic_html",
                available=True,
                description="E2E 使用固定商品页和集合页 fixture 验证 discovery、fan-out、dataset。",
            ),
            execution_boundary="executable",
            run_started=False,
        ),
        AutomationPlatformPackageResponse(
            id="github-api-first",
            name="GitHub API-first 工具情报采集",
            category="developer_platform",
            summary=(
                "面向 GitHub topic、repo 和开源采集工具情报；优先使用官方 API、"
                "限速信息和公开仓库元数据，不默认进入网页抓取。"
            ),
            supported_targets=["tool_repository", "topic_radar", "release_monitor"],
            collector_types=["github_topic", "github_repo"],
            field_schema=[
                AutomationPlatformPackageFieldResponse(
                    key="repo_full_name",
                    label="仓库全名",
                    data_type="string",
                    required=True,
                    source="github_api",
                    cleaning_rule="strip_text",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="stars",
                    label="Star 数",
                    data_type="integer",
                    required=False,
                    source="github_api",
                    cleaning_rule="parse_integer",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="topics",
                    label="Topic 标签",
                    data_type="string_array",
                    required=False,
                    source="github_api",
                    cleaning_rule="normalize_tags",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="license_spdx_id",
                    label="License SPDX",
                    data_type="string",
                    required=False,
                    source="github_api",
                    cleaning_rule="strip_text",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="default_branch",
                    label="默认分支",
                    data_type="string",
                    required=False,
                    source="github_api",
                    cleaning_rule="strip_text",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="latest_release_tag",
                    label="最新 release tag",
                    data_type="string",
                    required=False,
                    source="github_api_releases",
                    cleaning_rule="strip_text",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="latest_release_published_at",
                    label="最新 release 发布时间",
                    data_type="datetime",
                    required=False,
                    source="github_api_releases",
                    cleaning_rule="preserve_timestamp",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="pushed_at",
                    label="最近推送时间",
                    data_type="datetime",
                    required=False,
                    source="github_api",
                    cleaning_rule="preserve_timestamp",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="html_url",
                    label="仓库 URL",
                    data_type="url",
                    required=True,
                    source="github_api",
                    cleaning_rule="normalize_url",
                ),
            ],
            default_entrypoint="source-create",
            sample_urls=[
                AutomationPlatformPackageSampleUrlResponse(
                    label="Topic 样例",
                    entrypoint="source-create",
                    url="https://github.com/topics/web-scraping",
                    description="用于从公开 topic 创建 GitHub API-first 采集源、任务并小批量运行。",
                ),
            ],
            cleaning_rules=[
                AutomationPlatformPackageCleaningRuleResponse(
                    field="repo_full_name",
                    operation="strip_text",
                    description="去除仓库全名首尾空白。",
                ),
                AutomationPlatformPackageCleaningRuleResponse(
                    field="html_url",
                    operation="normalize_url",
                    description="规范仓库 URL。",
                ),
                AutomationPlatformPackageCleaningRuleResponse(
                    field="license_spdx_id",
                    operation="strip_text",
                    description="保留 GitHub API 返回的 SPDX id，缺失时显式留空。",
                ),
                AutomationPlatformPackageCleaningRuleResponse(
                    field="latest_release_published_at",
                    operation="fill_default",
                    value="NO_RELEASE",
                    description="单仓库 latest release 缺失时保留可审计空值标记，不阻断采集。",
                ),
            ],
            operator_checklist=[
                "确认 GitHub API rate limit、token 权限和 topic 范围。",
                "优先使用官方 API，不解析登录态页面。",
                (
                    "将 stars、license、default_branch、release、pushed_at 和 "
                    "html_url 作为工具情报排序与溯源字段。"
                ),
            ],
            strategy_matrix=[
                AutomationPlatformPackageStrategyResponse(
                    id="topic-radar-import",
                    label="Topic 工具雷达导入",
                    entrypoint="source-create",
                    collector_type="github_topic",
                    fit="high",
                    can_start_from_automation=True,
                    review_required=True,
                    description=(
                        "从 Automation 创建 GitHub topic 采集源、启用任务，"
                        "并执行一次小批量 API 采集。"
                    ),
                ),
                AutomationPlatformPackageStrategyResponse(
                    id="repo-detail-import",
                    label="单仓库详情导入",
                    entrypoint="source-create",
                    collector_type="github_repo",
                    fit="medium",
                    can_start_from_automation=False,
                    review_required=True,
                    description="通过 Sources 创建 GitHub repo 采集源，适合补充重点项目画像。",
                ),
            ],
            risk_boundaries=[
                AutomationPlatformPackageRiskBoundaryResponse(
                    condition="未配置 GitHub token 时使用公开 API 低频采集",
                    severity="warning",
                    guidance=(
                        "限制 max_results 和手动运行次数；"
                        "触发 rate limit 后不要自动重试放大请求。"
                    ),
                ),
                AutomationPlatformPackageRiskBoundaryResponse(
                    condition="仓库内容涉及个人数据、issue 评论或私有上下文",
                    severity="blocked",
                    guidance="只保留公开项目元数据，不采集个人级内容。",
                ),
                AutomationPlatformPackageRiskBoundaryResponse(
                    condition="需要网页补充 README 或 release 详情",
                    severity="warning",
                    guidance="优先走官方 API；网页解析作为人工确认后的补充步骤。",
                ),
            ],
            sop_links=[
                AutomationPlatformPackageSopLinkResponse(
                    label="GitHub/API-first SOP",
                    href="/toolkit?category=platform_method&platform=github",
                ),
                AutomationPlatformPackageSopLinkResponse(
                    label="采集源配置",
                    href="/sources",
                ),
            ],
            sample_fixture=AutomationPlatformPackageFixtureResponse(
                fixture_type="api_fixture",
                available=True,
                description="单元测试覆盖 GitHub collector 配置校验和 API 响应解析。",
            ),
            execution_boundary="executable",
            run_started=False,
        ),
        AutomationPlatformPackageResponse(
            id="public-page-structure-preflight",
            name="公开网页结构解析预检",
            category="browser_preflight",
            summary=(
                "面向任意公开网页的采集前置诊断；先检查授权、robots、"
                "sitemap、重定向、DOM 摘要和链接结构，再决定是否进入 generic_web "
                "或浏览器自动化采集。"
            ),
            supported_targets=["public_web_page", "site_structure", "field_contract_draft"],
            collector_types=["toolkit_preflight", "generic_web"],
            field_schema=[
                AutomationPlatformPackageFieldResponse(
                    key="page_title",
                    label="页面标题",
                    data_type="string",
                    required=True,
                    source="html_title",
                    cleaning_rule="strip_text",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="canonical_url",
                    label="规范 URL",
                    data_type="url",
                    required=True,
                    source="canonical_or_final_url",
                    cleaning_rule="normalize_url",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="meta_description",
                    label="页面描述",
                    data_type="string",
                    required=False,
                    source="meta_description",
                    cleaning_rule="strip_text",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="headings",
                    label="标题层级",
                    data_type="string_array",
                    required=False,
                    source="dom_h1_h2_h3",
                    cleaning_rule="strip_text",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="same_origin_links",
                    label="同源链接",
                    data_type="integer",
                    required=False,
                    source="dom_links",
                    cleaning_rule="fill_default",
                ),
                AutomationPlatformPackageFieldResponse(
                    key="text_sample",
                    label="正文样本",
                    data_type="text",
                    required=False,
                    source="visible_text",
                    cleaning_rule="strip_text",
                ),
            ],
            default_entrypoint="preflight",
            sample_urls=[
                AutomationPlatformPackageSampleUrlResponse(
                    label="公开网页样例",
                    entrypoint="preflight",
                    url="https://example.com",
                    description=(
                        "用于生成采集前置预检报告，确认 URL、robots、DOM、"
                        "链接结构和后续采集工具选择。"
                    ),
                )
            ],
            cleaning_rules=[
                AutomationPlatformPackageCleaningRuleResponse(
                    field="page_title",
                    operation="strip_text",
                    description="去除页面标题首尾空白并合并重复空格。",
                ),
                AutomationPlatformPackageCleaningRuleResponse(
                    field="canonical_url",
                    operation="normalize_url",
                    description="规范最终 URL 和 canonical URL，降低重复页面记录。",
                ),
                AutomationPlatformPackageCleaningRuleResponse(
                    field="meta_description",
                    operation="strip_text",
                    description="清理 meta description，用作页面摘要候选。",
                ),
                AutomationPlatformPackageCleaningRuleResponse(
                    field="text_sample",
                    operation="strip_text",
                    description="压缩正文样本文本空白，便于人工判断字段价值。",
                ),
            ],
            operator_checklist=[
                "确认目标 URL 属于自有、授权或明确允许分析的公开页面。",
                "先看 robots、sitemap、security.txt 和表单数量，再决定是否继续。",
                "把 title、canonical_url、headings、text_sample 作为首轮字段契约。",
                "脚本多或关键内容不可见时，再升级到 Playwright/browser-use 等浏览器方案。",
            ],
            strategy_matrix=[
                AutomationPlatformPackageStrategyResponse(
                    id="public-url-structure-preflight",
                    label="公开 URL 结构预检",
                    entrypoint="preflight",
                    collector_type="toolkit_preflight",
                    fit="high",
                    can_start_from_automation=True,
                    review_required=True,
                    description=(
                        "从 Automation 直接调用预检 API，输出授权 gate、DOM 摘要、"
                        "资源线索和后续工具建议。"
                    ),
                ),
                AutomationPlatformPackageStrategyResponse(
                    id="preflight-to-generic-web",
                    label="预检后创建 generic_web 采集源",
                    entrypoint="source-create",
                    collector_type="generic_web",
                    fit="medium",
                    can_start_from_automation=True,
                    review_required=True,
                    description=(
                        "预检未触发阻断项后，将最终 URL 创建为 generic_web 采集源，"
                        "执行一次公开页面采集。"
                    ),
                ),
            ],
            risk_boundaries=[
                AutomationPlatformPackageRiskBoundaryResponse(
                    condition="公开页面、robots 未给出全站禁止信号，且不依赖账号态",
                    severity="info",
                    guidance="可在授权确认后生成预检报告，并小批量验证 generic_web 采集。",
                ),
                AutomationPlatformPackageRiskBoundaryResponse(
                    condition="出现登录墙、验证码、私网地址、账号参数或个人数据",
                    severity="blocked",
                    guidance="停止自动化采集，转入人工授权或官方 API 路线。",
                ),
                AutomationPlatformPackageRiskBoundaryResponse(
                    condition="页面脚本重、正文样本不足或关键字段由交互加载",
                    severity="warning",
                    guidance="先用浏览器解析实验室定位 DOM、network 和 selector，再决定工具升级。",
                ),
            ],
            sop_links=[
                AutomationPlatformPackageSopLinkResponse(
                    label="授权 URL 预检向导",
                    href="/toolkit?category=governance",
                ),
                AutomationPlatformPackageSopLinkResponse(
                    label="浏览器解析实验室",
                    href="/toolkit?category=browser_automation",
                ),
            ],
            sample_fixture=AutomationPlatformPackageFixtureResponse(
                fixture_type="http_preflight_fixture",
                available=True,
                description="单元测试使用固定 HTML、robots 和 sitemap 响应验证预检报告。",
            ),
            execution_boundary="executable",
            run_started=False,
        ),
    ]


def _blocked_reasons(page_structure: dict[str, object], selected_fields: list[str]) -> list[str]:
    blocked: list[str] = []
    if not selected_fields:
        blocked.append("未识别到可直接结构化保存的商品字段。")
    if page_structure.get("form_count", 0) and page_structure.get("product_schema_count", 0) == 0:
        blocked.append("页面包含表单且缺少 Product schema，需人工确认是否涉及登录态。")
    return blocked


def _browser_confidence_ratio(confidence: float) -> float:
    if confidence > 1:
        return round(confidence / 100, 4)
    return round(confidence, 4)


def _browser_plan_host_label(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or parsed.path or "browser-page"


def _browser_guardrails(guardrails: list[str]) -> list[str]:
    defaults = [
        "只读执行，不提交表单、不点击购买或发布类按钮。",
        "必须保留诊断 JSON、截图路径和最终 URL 作为审计证据。",
        "先小批量验证字段稳定性，再进入任务调度。",
    ]
    merged = [item.strip() for item in [*guardrails, *defaults] if item.strip()]
    return list(dict.fromkeys(merged))


def _browser_tool_fit(risk_level: str) -> str:
    if risk_level == "high":
        return "low"
    if risk_level == "medium":
        return "medium"
    return "high"


def _browser_field_candidates(
    fields: list[AutomationBrowserFieldContractFieldRequest],
    cleaning_rules: list[AutomationBrowserCleaningRuleRequest],
    confidence: float,
) -> list[dict[str, object]]:
    cleaning_rule_by_field = {
        rule.field: rule.operation for rule in cleaning_rules if rule.field.strip()
    }
    return [
        {
            "key": field.key,
            "label": field.label,
            "value": field.selector_hint or None,
            "data_type": "string",
            "source": field.source,
            "confidence": confidence,
            "selected": field.selected,
            "cleaning_rule": cleaning_rule_by_field.get(field.key, "manual_review"),
        }
        for field in fields
    ]


def _browser_cleaning_plan(
    cleaning_rules: list[AutomationBrowserCleaningRuleRequest],
) -> list[dict[str, str]]:
    if cleaning_rules:
        return [rule.model_dump(mode="json") for rule in cleaning_rules]
    return [
        {
            "field": "selected_fields",
            "operation": "manual_review",
            "description": "首次执行前人工复核 selector hint 与字段样本稳定性。",
        }
    ]


def _browser_diagnostic_payload(
    raw_payload: dict[str, Any],
    payload: AutomationBrowserAutomationPlanRequest,
) -> dict[str, Any]:
    if raw_payload:
        return raw_payload
    return {
        "schema_version": payload.browser_diagnostic.schema_version,
        "requested_url": payload.requested_url,
        "final_url": payload.browser_diagnostic.final_url,
        "run_policy": {
            "authorization_confirmed": payload.authorized,
            "execution_mode": payload.execution_mode,
            "production_write": False,
            "login_or_private_page_allowed": False,
            "cookies_exported": False,
        },
        "extraction_strategy": {
            "recommended_path": payload.browser_diagnostic.recommended_path,
            "confidence": payload.browser_diagnostic.confidence,
            "field_stability": payload.browser_diagnostic.field_stability,
        },
        "network_summary": {"api_candidates": payload.api_candidates},
        "evidence": {
            "source": payload.browser_diagnostic.evidence_source,
            "screenshot_path": payload.browser_diagnostic.screenshot_path,
            "errors": [],
        },
    }


def _browser_diagnostic_run_policy(
    payload: AutomationBrowserAutomationPlanRequest,
    diagnostic_payload: dict[str, Any],
) -> dict[str, Any]:
    raw_policy = _dict_value(diagnostic_payload, "run_policy")
    return {
        **raw_policy,
        "runner": payload.runner,
        "execution_mode": payload.execution_mode,
        "authorization_confirmed": payload.authorized,
        "read_only": True,
        "run_started": False,
        "source_created": False,
        "task_run_created": False,
        "production_write": False,
        "login_or_private_page_allowed": False,
        "cookies_exported": False,
    }


def _browser_diagnostic_page_summary(diagnostic_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "visible_text": _dict_value(diagnostic_payload, "visible_text"),
        "dom_counters": _dict_value(diagnostic_payload, "dom_counters"),
        "final_url": diagnostic_payload.get("final_url"),
        "generated_at": diagnostic_payload.get("generated_at"),
    }


def _browser_diagnostic_network_summary(
    diagnostic_payload: dict[str, Any],
    api_candidates: list[str],
) -> dict[str, Any]:
    raw_network = _dict_value(diagnostic_payload, "network_summary")
    if "api_candidates" not in raw_network:
        raw_network["api_candidates"] = api_candidates
    raw_network["api_candidate_count"] = len(raw_network.get("api_candidates") or [])
    return raw_network


def _browser_diagnostic_accessibility_summary(
    diagnostic_payload: dict[str, Any],
) -> dict[str, Any]:
    return _dict_value(diagnostic_payload, "accessibility_summary")


def _browser_diagnostic_risk_flags(
    diagnostic_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    raw_flags = diagnostic_payload.get("risk_flags")
    if not isinstance(raw_flags, list):
        return []
    normalized: list[dict[str, Any]] = []
    for flag in raw_flags:
        if isinstance(flag, dict):
            normalized.append(flag)
        elif isinstance(flag, str) and flag.strip():
            normalized.append({"flag": flag.strip(), "severity": "review"})
    return normalized


def _browser_diagnostic_extraction_strategy(
    diagnostic_payload: dict[str, Any],
    payload: AutomationBrowserAutomationPlanRequest,
) -> dict[str, Any]:
    raw_strategy = _dict_value(diagnostic_payload, "extraction_strategy")
    return {
        **raw_strategy,
        "recommended_path": payload.browser_diagnostic.recommended_path,
        "confidence": payload.browser_diagnostic.confidence,
        "field_stability": payload.browser_diagnostic.field_stability,
        "run_started": False,
    }


def _browser_executable_spec(
    fields: list[AutomationBrowserFieldContractFieldRequest],
    api_candidates: list[str],
    guardrails: list[str],
    risk_level: str,
    field_stability: str | None,
) -> dict[str, Any]:
    selected = [field for field in fields if field.selected]
    return {
        "schema_version": "browser_automation_executable_spec.v1",
        "status": "draft",
        "run_started": False,
        "manual_review_required": risk_level != "low" or field_stability in {None, "low"},
        "selector_contract": [
            {
                "field": field.key,
                "label": field.label,
                "source": field.source,
                "required": field.required,
                "selector_hint": field.selector_hint,
                "stability": field_stability or "unknown",
            }
            for field in selected
        ],
        "wait_conditions": [
            {"type": "domcontentloaded", "timeout_seconds": 15},
            {"type": "network_idle_probe", "timeout_seconds": 10},
        ],
        "pagination_hypothesis": {
            "strategy": "not_configured",
            "review_required": True,
            "note": "首次规格仅覆盖单页字段验证，分页需要独立人工确认。",
        },
        "api_candidates": api_candidates,
        "dry_run_limits": {
            "max_pages": 1,
            "max_records": 20,
            "timeout_seconds": 30,
            "write_allowed": False,
        },
        "guardrails": guardrails,
    }


def _browser_executable_spec_checks(
    analysis: SiteAnalysis,
    plan: ExtractionPlan,
    source_config: dict[str, Any],
    executable_spec: dict[str, Any],
    diagnostic_run: BrowserDiagnosticRun | None,
) -> list[AutomationBrowserExecutableSpecCheckResponse]:
    selector_contract = _list_of_dicts(executable_spec.get("selector_contract"))
    wait_conditions = _list_of_dicts(executable_spec.get("wait_conditions"))
    api_candidates = _string_list(executable_spec.get("api_candidates"))
    guardrails = _string_list(executable_spec.get("guardrails"))
    dry_run_limits = _dict_value(executable_spec, "dry_run_limits")
    selected_field_set = {str(field) for field in plan.selected_fields}
    selector_field_set = {
        str(item.get("field"))
        for item in selector_contract
        if item.get("field") is not None
    }
    missing_selected_fields = sorted(selected_field_set - selector_field_set)
    required_missing_hints = [
        str(item.get("field"))
        for item in selector_contract
        if item.get("required") is True and not str(item.get("selector_hint") or "").strip()
    ]
    write_allowed = dry_run_limits.get("write_allowed") is True
    checks = [
        _spec_check(
            "site-analysis-target",
            "站点分析类型",
            "passed" if analysis.target == "browser_automation" else "blocked",
            (
                "站点分析目标为 browser automation。"
                if analysis.target == "browser_automation"
                else "站点分析目标不是 browser automation，不能校验该执行规格。"
            ),
            {"target": analysis.target},
        ),
        _spec_check(
            "collector-type",
            "采集器类型",
            "passed" if plan.collector_type == "browser_automation" else "blocked",
            (
                "执行计划绑定 browser automation。"
                if plan.collector_type == "browser_automation"
                else "执行计划未绑定 browser automation。"
            ),
            {"collector_type": plan.collector_type},
        ),
        _spec_check(
            "schema-version",
            "规格版本",
            (
                "passed"
                if executable_spec.get("schema_version")
                == "browser_automation_executable_spec.v1"
                else "blocked"
            ),
            (
                "执行规格版本可识别。"
                if executable_spec.get("schema_version")
                == "browser_automation_executable_spec.v1"
                else "缺少可识别的 browser automation 执行规格版本。"
            ),
            {"schema_version": executable_spec.get("schema_version")},
        ),
        _spec_check(
            "selector-contract",
            "字段 selector 合约",
            "blocked" if not selector_contract or missing_selected_fields else "passed",
            (
                "selector 合约覆盖已选字段。"
                if selector_contract and not missing_selected_fields
                else "selector 合约为空或未覆盖所有已选字段。"
            ),
            {
                "selector_count": len(selector_contract),
                "selected_fields": sorted(selected_field_set),
                "missing_selected_fields": missing_selected_fields,
            },
        ),
        _spec_check(
            "selector-hints",
            "关键字段定位线索",
            "review" if required_missing_hints else "passed",
            (
                "关键字段均包含定位线索。"
                if not required_missing_hints
                else "部分关键字段缺少 selector hint，需要人工补全。"
            ),
            {"required_missing_hints": required_missing_hints},
        ),
        _spec_check(
            "wait-conditions",
            "等待条件",
            "passed" if wait_conditions else "review",
            (
                "已定义页面等待条件。"
                if wait_conditions
                else "缺少等待条件，后续真实 dry-run 前需要补充。"
            ),
            {"wait_condition_count": len(wait_conditions)},
        ),
        _spec_check(
            "api-candidates",
            "API 候选",
            "passed" if api_candidates else "review",
            (
                "已记录 API 候选，可优先评估 API-first 路径。"
                if api_candidates
                else "没有 API 候选，后续执行更依赖 DOM selector 稳定性。"
            ),
            {"api_candidate_count": len(api_candidates)},
        ),
        _spec_check(
            "dry-run-limits",
            "只读 dry-run 限制",
            "blocked" if write_allowed else "passed",
            (
                "dry-run 限制禁止写入。"
                if not write_allowed
                else "dry-run 限制允许写入，违反当前阶段边界。"
            ),
            {
                "write_allowed": write_allowed,
                "max_pages": dry_run_limits.get("max_pages"),
                "max_records": dry_run_limits.get("max_records"),
            },
        ),
        _spec_check(
            "guardrails",
            "执行护栏",
            "passed" if _guardrails_include_read_only(guardrails) else "review",
            (
                "执行护栏包含只读边界。"
                if _guardrails_include_read_only(guardrails)
                else "执行护栏未明确只读边界，需要补充。"
            ),
            {"guardrails": guardrails},
        ),
        _browser_diagnostic_lineage_check(
            analysis=analysis,
            source_config=source_config,
            diagnostic_run=diagnostic_run,
        ),
        _spec_check(
            "manual-review",
            "人工复核",
            "review" if executable_spec.get("manual_review_required") is True else "passed",
            (
                "执行规格标记为需要人工复核。"
                if executable_spec.get("manual_review_required") is True
                else "执行规格未要求额外人工复核。"
            ),
            {"manual_review_required": executable_spec.get("manual_review_required")},
        ),
    ]
    return checks


def _browser_diagnostic_lineage_check(
    analysis: SiteAnalysis,
    source_config: dict[str, Any],
    diagnostic_run: BrowserDiagnosticRun | None,
) -> AutomationBrowserExecutableSpecCheckResponse:
    if diagnostic_run is None:
        return _spec_check(
            "diagnostic-lineage",
            "诊断资产链路",
            "blocked",
            "未找到关联的浏览器诊断资产。",
            {},
        )
    final_url_matches = diagnostic_run.final_url == source_config.get("start_url")
    same_analysis = diagnostic_run.site_analysis_id == analysis.id
    read_only = diagnostic_run.run_policy.get("read_only") is True
    no_browser_run = diagnostic_run.run_started is False
    status: Literal["passed", "review", "blocked"] = (
        "passed"
        if same_analysis and final_url_matches and read_only and no_browser_run
        else "blocked"
    )
    return _spec_check(
        "diagnostic-lineage",
        "诊断资产链路",
        status,
        (
            "诊断资产与执行规格链路一致，且保持只读。"
            if status == "passed"
            else "诊断资产与执行规格链路不一致或不满足只读边界。"
        ),
        {
            "browser_diagnostic_run_id": str(diagnostic_run.id),
            "same_site_analysis": same_analysis,
            "final_url_matches": final_url_matches,
            "read_only": read_only,
            "run_started": diagnostic_run.run_started,
        },
    )


def _browser_executable_spec_summary(
    checks: list[AutomationBrowserExecutableSpecCheckResponse],
    executable_spec: dict[str, Any],
) -> AutomationBrowserExecutableSpecDryRunSummaryResponse:
    blocked_checks = sum(1 for check in checks if check.status == "blocked")
    review_checks = sum(1 for check in checks if check.status == "review")
    passed_checks = sum(1 for check in checks if check.status == "passed")
    status: Literal["ready", "review", "blocked"]
    if blocked_checks:
        status = "blocked"
    elif review_checks:
        status = "review"
    else:
        status = "ready"
    selector_contract = _list_of_dicts(executable_spec.get("selector_contract"))
    wait_conditions = _list_of_dicts(executable_spec.get("wait_conditions"))
    api_candidates = _string_list(executable_spec.get("api_candidates"))
    dry_run_limits = _dict_value(executable_spec, "dry_run_limits")
    write_allowed = dry_run_limits.get("write_allowed") is True
    return AutomationBrowserExecutableSpecDryRunSummaryResponse(
        status=status,
        total_checks=len(checks),
        passed_checks=passed_checks,
        review_checks=review_checks,
        blocked_checks=blocked_checks,
        selector_count=len(selector_contract),
        wait_condition_count=len(wait_conditions),
        api_candidate_count=len(api_candidates),
        manual_review_required=executable_spec.get("manual_review_required") is True,
        can_dry_run_after_review=status in {"ready", "review"} and not write_allowed,
        write_allowed=write_allowed,
        run_started=False,
    )


def _browser_diagnostic_job_network_policy(
    mode: str,
    api_candidates: list[str],
) -> dict[str, Any]:
    return {
        "mode": mode,
        "same_origin_only": mode == "same_origin_api_candidates",
        "capture_body": False,
        "capture_headers": False,
        "write_allowed": False,
        "api_candidates": api_candidates if mode == "same_origin_api_candidates" else [],
    }


def _browser_diagnostic_job_artifact_policy(
    mode: str,
    diagnostic_run: BrowserDiagnosticRun,
) -> dict[str, Any]:
    return {
        "mode": mode,
        "write_files": False,
        "retain_screenshot_path": (
            diagnostic_run.screenshot_path
            if mode == "screenshot_reference_only"
            else None
        ),
        "retain_diagnostic_json": mode == "diagnostic_json_reference",
        "object_storage_write": False,
    }


def _browser_diagnostic_job_safety_flags(guardrails: list[str]) -> list[str]:
    default_flags = [
        "read_only",
        "no_browser_run_started",
        "no_login_state_reuse",
        "no_cookie_export",
        "no_form_submit",
        "no_source_task_taskrun_creation",
        "no_dataset_write",
        "no_notification_or_email",
        "no_scheduler_mutation",
    ]
    return list(dict.fromkeys([*default_flags, *guardrails]))


def _browser_diagnostic_job_fingerprint(
    workspace_id: uuid.UUID,
    site_analysis_id: uuid.UUID,
    extraction_plan_id: uuid.UUID,
    browser_diagnostic_run_id: uuid.UUID,
    network_policy: dict[str, Any],
    artifact_policy: dict[str, Any],
) -> str:
    payload = {
        "workspace_id": str(workspace_id),
        "site_analysis_id": str(site_analysis_id),
        "extraction_plan_id": str(extraction_plan_id),
        "browser_diagnostic_run_id": str(browser_diagnostic_run_id),
        "network_policy": network_policy,
        "artifact_policy": artifact_policy,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _browser_executor_adapter_contract(job: BrowserDiagnosticJob) -> dict[str, Any]:
    return {
        "schema_version": "browser_executor_adapter_contract.v1",
        "adapter_name": "browser_harness_read_only_local",
        "adapter_kind": "local_manual_runner",
        "job_id": str(job.id),
        "input_contract": {
            "final_url": job.final_url,
            "selector_scope": job.selector_scope,
            "wait_policy": job.wait_policy,
            "network_observation_policy": job.network_observation_policy,
        },
        "output_contract": {
            "artifact_manifest": "json",
            "field_preview_rows": "in_memory_only_until_runner_phase",
            "network_observation_summary": "metadata_only",
            "execution_log": "structured_steps",
        },
        "execution_policy": {
            "manual_operator_required": True,
            "automatic_api_worker_start": False,
            "production_enabled": False,
            "write_allowed": False,
            "run_started": False,
        },
    }


def _browser_executor_runtime_isolation(job: BrowserDiagnosticJob) -> dict[str, Any]:
    return {
        "mode": "local_ephemeral_browser_context",
        "runner": job.runner,
        "execution_mode": job.execution_mode,
        "reuse_user_profile": False,
        "cookie_export_allowed": False,
        "login_state_allowed": False,
        "private_page_allowed": False,
        "network_scope": job.network_observation_policy.get("mode", "metadata_only"),
        "filesystem_write_allowed": False,
        "secrets_allowed": False,
    }


def _browser_executor_artifact_retention_policy(
    job: BrowserDiagnosticJob,
    payload: AutomationBrowserExecutorContractRequest,
) -> dict[str, Any]:
    return {
        "schema_version": "browser_artifact_retention_policy.v1",
        "base_path": f"tmp/browser-diagnostic-runs/{job.id}",
        "write_files_now": False,
        "retention_days": payload.artifact_retention_days,
        "max_preview_rows": payload.max_preview_rows,
        "screenshot": {
            "enabled": payload.include_screenshot,
            "source_reference": job.artifact_policy.get("retain_screenshot_path"),
        },
        "trace_summary": {
            "enabled": payload.include_trace_summary,
            "full_trace_capture": False,
        },
        "har_summary": {
            "enabled": payload.include_har_summary,
            "capture_headers": False,
            "capture_body": False,
        },
        "redaction": {
            "drop_headers": ["authorization", "cookie", "set-cookie"],
            "drop_query_params": ["token", "key", "session", "password"],
            "drop_private_page_content": True,
        },
    }


def _browser_executor_allowed_actions(job: BrowserDiagnosticJob) -> list[str]:
    actions = [
        "open_authorized_final_url",
        "wait_domcontentloaded",
        "read_visible_text",
        "read_accessibility_snapshot",
        "evaluate_declared_selectors",
        "produce_in_memory_preview_rows",
    ]
    if job.network_observation_policy.get("mode") == "same_origin_api_candidates":
        actions.append("observe_same_origin_network_metadata")
    else:
        actions.append("observe_network_metadata_counts")
    return actions


def _browser_executor_denied_actions() -> list[str]:
    return [
        "reuse_user_chrome_profile",
        "export_cookies",
        "login_or_private_page_access",
        "submit_forms",
        "click_purchase_or_publish_actions",
        "download_files",
        "write_source_or_task",
        "create_task_run",
        "write_dataset_or_export",
        "send_notification_or_email",
        "mutate_scheduler",
    ]


def _browser_executor_readiness_checks(
    job: BrowserDiagnosticJob,
) -> list[AutomationBrowserExecutorReadinessCheckResponse]:
    dry_run_summary = dict(job.dry_run_summary)
    safety_flags = set(job.safety_flags)
    network_policy = dict(job.network_observation_policy)
    artifact_policy = dict(job.artifact_policy)
    return [
        _executor_check(
            "job-status",
            "任务状态",
            "passed" if job.status == "ready_for_manual_execution" else "blocked",
            (
                "诊断任务已审核，等待人工执行。"
                if job.status == "ready_for_manual_execution"
                else "诊断任务不是可执行状态。"
            ),
            {"status": job.status},
        ),
        _executor_check(
            "no-run-started",
            "运行状态",
            "passed" if job.run_started is False else "blocked",
            (
                "任务尚未启动运行。"
                if job.run_started is False
                else "任务已有运行标记，不能生成新的本地执行合同。"
            ),
            {"run_started": job.run_started},
        ),
        _executor_check(
            "execution-mode",
            "执行模式",
            "passed" if job.execution_mode == "read_only_browser_harness" else "blocked",
            (
                "执行模式限定为 read-only browser harness。"
                if job.execution_mode == "read_only_browser_harness"
                else "执行模式不是 read-only browser harness。"
            ),
            {"execution_mode": job.execution_mode},
        ),
        _executor_check(
            "selector-scope",
            "字段范围",
            "passed" if job.selector_scope else "blocked",
            (
                "已定义 selector scope。"
                if job.selector_scope
                else "缺少 selector scope。"
            ),
            {"selector_count": len(job.selector_scope)},
        ),
        _executor_check(
            "wait-policy",
            "等待策略",
            "passed" if job.wait_policy else "review",
            (
                "已定义等待策略。"
                if job.wait_policy
                else "缺少等待策略，真实执行前需要补齐。"
            ),
            {"wait_condition_count": len(job.wait_policy)},
        ),
        _executor_check(
            "network-policy",
            "网络观察",
            (
                "passed"
                if network_policy.get("write_allowed") is False
                and network_policy.get("capture_body") is False
                else "blocked"
            ),
            (
                "网络策略仅允许元数据观察。"
                if network_policy.get("write_allowed") is False
                and network_policy.get("capture_body") is False
                else "网络策略允许写入或正文捕获。"
            ),
            network_policy,
        ),
        _executor_check(
            "artifact-policy",
            "产物策略",
            (
                "passed"
                if artifact_policy.get("write_files") is False
                and artifact_policy.get("object_storage_write") is False
                else "blocked"
            ),
            (
                "当前阶段不写文件或对象存储。"
                if artifact_policy.get("write_files") is False
                and artifact_policy.get("object_storage_write") is False
                else "产物策略允许文件或对象存储写入。"
            ),
            artifact_policy,
        ),
        _executor_check(
            "safety-flags",
            "安全边界",
            (
                "passed"
                if {"read_only", "no_login_state_reuse", "no_cookie_export"}
                <= safety_flags
                else "review"
            ),
            (
                "安全边界包含只读、无登录态复用、无 cookie 导出。"
                if {"read_only", "no_login_state_reuse", "no_cookie_export"}
                <= safety_flags
                else "安全边界需要补充登录态和 cookie 限制。"
            ),
            {"safety_flags": job.safety_flags},
        ),
        _executor_check(
            "dry-run-summary",
            "规格校验摘要",
            (
                "passed"
                if dry_run_summary.get("write_allowed") is False
                and dry_run_summary.get("status") != "blocked"
                else "blocked"
            ),
            (
                "执行规格校验允许进入人工执行合同。"
                if dry_run_summary.get("write_allowed") is False
                and dry_run_summary.get("status") != "blocked"
                else "执行规格校验仍处于阻断或允许写入状态。"
            ),
            dry_run_summary,
        ),
    ]


def _browser_local_runner_selector_results(
    job: BrowserDiagnosticJob,
    diagnostic_run: BrowserDiagnosticRun,
) -> list[dict[str, Any]]:
    snapshot_values = _browser_local_runner_snapshot_values(diagnostic_run)
    results: list[dict[str, Any]] = []
    for selector in job.selector_scope:
        field = str(selector.get("field") or selector.get("key") or "unknown_field")
        selector_hint = selector.get("selector_hint") or selector.get("selector")
        value = snapshot_values.get(field)
        results.append(
            {
                "field": field,
                "label": selector.get("label") or field,
                "selector_hint": selector_hint,
                "required": selector.get("required") is True,
                "status": (
                    "observed_from_diagnostic_snapshot"
                    if value is not None
                    else "not_observed_in_diagnostic_snapshot"
                ),
                "value": value,
                "source": "diagnostic_snapshot_replay",
                "browser_started": False,
            }
        )
    return results


def _browser_local_runner_snapshot_values(
    diagnostic_run: BrowserDiagnosticRun,
) -> dict[str, str | int | float | bool | None]:
    visible_text = _dict_value(diagnostic_run.page_summary, "visible_text")
    sample = str(visible_text.get("sample") or "").strip()
    first_line = next((line.strip() for line in sample.splitlines() if line.strip()), None)
    network_summary = dict(diagnostic_run.network_summary)
    api_candidates = network_summary.get("api_candidates")
    first_api_candidate: str | None = None
    if isinstance(api_candidates, list):
        for candidate in api_candidates:
            if isinstance(candidate, dict) and isinstance(candidate.get("url"), str):
                first_api_candidate = candidate["url"]
                break
            if isinstance(candidate, str):
                first_api_candidate = candidate
                break
    return {
        "page_title": first_line,
        "visible_text_sample": sample or None,
        "api_candidate": first_api_candidate,
        "final_url": diagnostic_run.final_url,
        "requested_url": diagnostic_run.requested_url,
        "screenshot_path": diagnostic_run.screenshot_path,
    }


def _browser_local_runner_preview_rows(
    job: BrowserDiagnosticJob,
    selector_results: list[dict[str, Any]],
    max_rows: int,
) -> list[dict[str, Any]]:
    if max_rows < 1:
        return []
    values = {
        str(result["field"]): result.get("value")
        for result in selector_results
        if result.get("field") and result.get("value") is not None
    }
    if not values:
        return []
    return [
        {
            "row_index": 1,
            "source": "diagnostic_snapshot_replay",
            "requested_url": job.requested_url,
            "final_url": job.final_url,
            "values": values,
            "selector_statuses": {
                str(result["field"]): result.get("status")
                for result in selector_results
                if result.get("field")
            },
        }
    ]


def _browser_local_runner_artifact_manifest(
    contract: AutomationBrowserExecutorContractResponse,
    diagnostic_run: BrowserDiagnosticRun,
    preview_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    retention_policy = dict(contract.artifact_retention_policy)
    return {
        "schema_version": "browser_local_runner_artifact_manifest.v1",
        "base_path": retention_policy.get("base_path"),
        "retention_days": retention_policy.get("retention_days"),
        "files_written": False,
        "object_storage_write": False,
        "preview_rows_count": len(preview_rows),
        "screenshot": {
            "enabled": _dict_value(retention_policy, "screenshot").get("enabled") is True,
            "referenced_path": diagnostic_run.screenshot_path,
            "generated_path": None,
        },
        "trace_summary": {
            "enabled": _dict_value(retention_policy, "trace_summary").get("enabled") is True,
            "generated_path": None,
        },
        "har_summary": {
            "enabled": _dict_value(retention_policy, "har_summary").get("enabled") is True,
            "capture_headers": False,
            "capture_body": False,
            "generated_path": None,
        },
    }


def _browser_local_runner_network_summary(
    job: BrowserDiagnosticJob,
    diagnostic_run: BrowserDiagnosticRun,
) -> dict[str, Any]:
    network = dict(diagnostic_run.network_summary)
    api_candidates = network.get("api_candidates") if isinstance(network, dict) else []
    if not isinstance(api_candidates, list):
        api_candidates = []
    return {
        "mode": job.network_observation_policy.get("mode", "metadata_only"),
        "same_origin_only": job.network_observation_policy.get("same_origin_only") is True,
        "capture_headers": False,
        "capture_body": False,
        "observed_from_diagnostic_snapshot": True,
        "browser_started": False,
        "resource_count": network.get("resource_count"),
        "api_candidate_count": len(api_candidates),
        "api_candidates": api_candidates,
    }


def _browser_local_runner_error_summary(
    diagnostic_run: BrowserDiagnosticRun,
) -> dict[str, Any]:
    evidence = _dict_value(diagnostic_run.diagnostic_payload, "evidence")
    raw_errors = evidence.get("errors")
    errors = [str(error)[:300] for error in raw_errors] if isinstance(raw_errors, list) else []
    return {
        "error_count": len(errors),
        "errors": errors,
        "redacted": True,
        "browser_started": False,
    }


def _browser_local_runner_selector_evaluations(
    selector_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    evaluations: list[dict[str, Any]] = []
    for result in selector_results:
        value = result.get("value")
        observed = value is not None
        field = str(result.get("field") or "unknown_field")
        evaluations.append(
            {
                "schema_version": "browser_selector_evaluation.v1",
                "field": field,
                "label": result.get("label") or field,
                "selector_hint": result.get("selector_hint"),
                "required": result.get("required") is True,
                "status": result.get("status") or (
                    "observed" if observed else "not_observed"
                ),
                "match_count": 1 if observed else 0,
                "sample_text": _browser_local_runner_sample_text(value),
                "missing_reason": None
                if observed
                else "not_observed_in_diagnostic_snapshot",
                "source": result.get("source") or "diagnostic_snapshot_replay",
                "browser_started": result.get("browser_started") is True,
            }
        )
    return evaluations


def _browser_local_runner_sample_text(value: Any, limit: int = 180) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = (
            _browser_probe_sanitize_url(value)
            if value.startswith(("http://", "https://"))
            else value
        )
    else:
        text = json.dumps(value, ensure_ascii=False, default=str)
    text = " ".join(text.strip().split())
    if not text:
        return None
    return text[:limit]


def _browser_local_runner_network_metadata_summary(
    summary: dict[str, Any],
) -> dict[str, Any]:
    api_candidates = _browser_local_runner_api_candidates(summary.get("api_candidates"))
    ephemeral_probe = summary.get("ephemeral_probe")
    result = {
        "schema_version": "browser_network_metadata_summary.v1",
        "mode": summary.get("mode") or "metadata_only",
        "same_origin_only": summary.get("same_origin_only") is True,
        "metadata_only": True,
        "capture_headers": False,
        "capture_body": False,
        "browser_started": summary.get("browser_started") is True,
        "observed_from_diagnostic_snapshot": (
            summary.get("observed_from_diagnostic_snapshot") is True
        ),
        "resource_count": summary.get("resource_count"),
        "api_candidate_count": len(api_candidates),
        "api_candidates": api_candidates,
        "redacted": True,
    }
    if isinstance(ephemeral_probe, dict):
        result["ephemeral_probe"] = {
            "schema_version": ephemeral_probe.get("schema_version"),
            "status": ephemeral_probe.get("status"),
            "target_url": ephemeral_probe.get("target_url"),
            "page_info": ephemeral_probe.get("page_info") or {},
            "target_tab_closed": ephemeral_probe.get("target_tab_closed") is True,
            "redacted": True,
        }
    return result


def _browser_local_runner_api_candidates(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    candidates: list[Any] = []
    for candidate in value[:10]:
        if isinstance(candidate, str):
            candidates.append(_browser_probe_sanitize_url(candidate))
            continue
        if isinstance(candidate, dict):
            sanitized = dict(candidate)
            if isinstance(sanitized.get("url"), str):
                sanitized["url"] = _browser_probe_sanitize_url(str(sanitized["url"]))
            candidates.append(sanitized)
    return candidates


def _browser_local_runner_promotion_gate(
    run_asset: BrowserDiagnosticJobRun,
) -> dict[str, Any]:
    selector_evaluations = _browser_local_runner_selector_evaluations(
        run_asset.selector_results
    )
    required_missing_fields = [
        str(item["field"])
        for item in selector_evaluations
        if item.get("required") is True and int(item.get("match_count") or 0) < 1
    ]
    reasons = ["m2_read_only_contract_no_direct_promotion"]
    if required_missing_fields:
        reasons.append("required_selector_missing")
    if run_asset.files_written:
        reasons.append("unexpected_files_written")
    if run_asset.collection_resources_written:
        reasons.append("unexpected_collection_resource_write")
    return {
        "schema_version": "browser_promotion_gate.v1",
        "status": "blocked",
        "can_create_collection_resources": False,
        "review_required": True,
        "reasons": reasons,
        "required_missing_fields": required_missing_fields,
        "browser_started": run_asset.browser_started,
        "files_written": run_asset.files_written,
        "collection_resources_written": run_asset.collection_resources_written,
    }


def _browser_local_runner_redaction_summary(
    run_asset: BrowserDiagnosticJobRun,
) -> dict[str, Any]:
    return {
        "schema_version": "browser_local_runner_redaction_summary.v1",
        "cookies_captured": False,
        "headers_captured": False,
        "bodies_captured": False,
        "query_parameters_retained": False,
        "url_query_fragment_removed": True,
        "stdout_stderr_tail_redacted": True,
        "sample_text_max_chars": 180,
        "files_written": run_asset.files_written,
        "collection_resources_written": run_asset.collection_resources_written,
    }


def _run_browser_harness_ephemeral_probe(
    job: BrowserDiagnosticJob,
    payload: AutomationBrowserLocalRunnerRequest,
) -> dict[str, Any]:
    binary = (
        payload.browser_harness_binary
        or os.environ.get("BROWSER_HARNESS_BIN")
        or "/Users/pray/.local/bin/browser-harness"
    )
    script = _browser_harness_ephemeral_probe_script(job.requested_url)
    try:
        completed = subprocess.run(
            [binary],
            input=script,
            text=True,
            capture_output=True,
            timeout=payload.probe_timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return {
            "status": "blocked",
            "browser_started": False,
            "target_tab_closed": False,
            "exit_code": None,
            "binary": _browser_harness_binary_label(binary),
            "target_url": _browser_probe_sanitize_url(job.requested_url),
            "error": "browser_harness_binary_not_found",
            "stdout_tail": "",
            "stderr_tail": "",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "failed",
            "browser_started": False,
            "target_tab_closed": False,
            "exit_code": None,
            "binary": _browser_harness_binary_label(binary),
            "target_url": _browser_probe_sanitize_url(job.requested_url),
            "error": "browser_harness_probe_timeout",
            "stdout_tail": _tail_text(exc.stdout),
            "stderr_tail": _tail_text(exc.stderr),
        }

    parsed = _parse_browser_harness_json_line(completed.stdout)
    if completed.returncode != 0:
        return {
            "status": "failed",
            "browser_started": False,
            "target_tab_closed": False,
            "exit_code": completed.returncode,
            "binary": _browser_harness_binary_label(binary),
            "target_url": _browser_probe_sanitize_url(job.requested_url),
            "error": "browser_harness_probe_nonzero_exit",
            "stdout_tail": _tail_text(completed.stdout),
            "stderr_tail": _tail_text(completed.stderr),
        }
    if parsed is None:
        return {
            "status": "failed",
            "browser_started": False,
            "target_tab_closed": False,
            "exit_code": completed.returncode,
            "binary": _browser_harness_binary_label(binary),
            "target_url": _browser_probe_sanitize_url(job.requested_url),
            "error": "browser_harness_probe_json_not_found",
            "stdout_tail": _tail_text(completed.stdout),
            "stderr_tail": _tail_text(completed.stderr),
        }

    page_info = parsed.get("page_info") if isinstance(parsed, dict) else None
    return {
        "status": "completed",
        "browser_started": True,
        "target_tab_closed": parsed.get("target_tab_closed") is True,
        "exit_code": completed.returncode,
        "binary": _browser_harness_binary_label(binary),
        "target_url": _browser_probe_sanitize_url(job.requested_url),
        "page_info": _sanitize_browser_harness_page_info(page_info),
        "stdout_tail": "",
        "stderr_tail": _tail_text(completed.stderr),
    }


def _browser_harness_ephemeral_probe_script(url: str) -> str:
    serialized_url = json.dumps(url)
    return f"""
import json

target_id = None
try:
    target_id = new_tab({serialized_url})
    wait_for_load(timeout=12.0)
    print(json.dumps({{
        "ok": True,
        "page_info": page_info(),
        "target_tab_closed": False,
    }}, ensure_ascii=False))
finally:
    if target_id:
        try:
            close_tab(target_id)
            print(json.dumps({{"target_tab_closed": True}}, ensure_ascii=False))
        except Exception:
            pass
"""


def _parse_browser_harness_json_line(stdout: str | bytes | None) -> dict[str, Any] | None:
    text = (
        stdout.decode("utf-8", errors="replace")
        if isinstance(stdout, bytes)
        else str(stdout or "")
    )
    parsed: dict[str, Any] | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            parsed = {**(parsed or {}), **candidate}
    return parsed


def _sanitize_browser_harness_page_info(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    allowed_keys = {"url", "title", "w", "h", "sx", "sy", "pw", "ph"}
    sanitized = {key: value.get(key) for key in allowed_keys if key in value}
    if isinstance(sanitized.get("url"), str):
        sanitized["url"] = _browser_probe_sanitize_url(str(sanitized["url"]))
    return sanitized


def _browser_probe_sanitize_url(value: str) -> str:
    parsed = urlparse(value)
    return parsed._replace(query="", fragment="").geturl()


def _browser_harness_binary_label(value: str) -> str:
    path = Path(value)
    if path.name == "browser-harness":
        return str(path)
    return path.name or "browser-harness"


def _tail_text(value: str | bytes | None, limit: int = 600) -> str:
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value or "")
    text = text.strip()
    if not text:
        return ""
    redacted = text.replace("Authorization", "[redacted-header]")
    return redacted[-limit:]


def _browser_harness_probe_artifact_manifest(
    manifest: dict[str, Any],
    probe_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        **manifest,
        "ephemeral_probe": {
            "schema_version": "browser_harness_ephemeral_probe.v1",
            "status": probe_result.get("status"),
            "binary": probe_result.get("binary"),
            "exit_code": probe_result.get("exit_code"),
            "files_written": False,
            "object_storage_write": False,
            "target_tab_closed": probe_result.get("target_tab_closed") is True,
        },
    }


def _browser_harness_probe_network_summary(
    summary: dict[str, Any],
    probe_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        **summary,
        "browser_started": probe_result.get("browser_started") is True,
        "ephemeral_probe": {
            "schema_version": "browser_harness_ephemeral_probe.v1",
            "status": probe_result.get("status"),
            "target_url": probe_result.get("target_url"),
            "page_info": probe_result.get("page_info") or {},
            "target_tab_closed": probe_result.get("target_tab_closed") is True,
            "stdout_tail": probe_result.get("stdout_tail") or "",
            "stderr_tail": probe_result.get("stderr_tail") or "",
            "redacted": True,
        },
    }


def _browser_harness_probe_error_summary(
    summary: dict[str, Any],
    probe_result: dict[str, Any],
) -> dict[str, Any]:
    errors = list(summary.get("errors") or [])
    if probe_result.get("error"):
        errors.append(str(probe_result["error"]))
    return {
        **summary,
        "error_count": len(errors),
        "errors": errors,
        "browser_started": probe_result.get("browser_started") is True,
    }


def _executor_check(
    key: str,
    label: str,
    status: Literal["passed", "review", "blocked"],
    message: str,
    evidence: dict[str, Any],
) -> AutomationBrowserExecutorReadinessCheckResponse:
    return AutomationBrowserExecutorReadinessCheckResponse(
        key=key,
        label=label,
        status=status,
        message=message,
        evidence=evidence,
    )


def _spec_check(
    key: str,
    label: str,
    status: Literal["passed", "review", "blocked"],
    message: str,
    evidence: dict[str, Any],
) -> AutomationBrowserExecutableSpecCheckResponse:
    return AutomationBrowserExecutableSpecCheckResponse(
        key=key,
        label=label,
        status=status,
        message=message,
        evidence=evidence,
    )


def _dict_value(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return dict(value) if isinstance(value, dict) else {}


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _uuid_from_config(config: dict[str, Any], key: str) -> uuid.UUID | None:
    value = config.get(key)
    if not isinstance(value, str):
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _guardrails_include_read_only(guardrails: list[str]) -> bool:
    return any("只读" in item or "read_only" in item.lower() for item in guardrails)


def _blocked_batch_item(
    task_id: uuid.UUID,
    reason: str,
) -> AutomationProductBatchRunItemResponse:
    return AutomationProductBatchRunItemResponse(
        task_id=task_id,
        task_name=None,
        source_id=None,
        source_url=None,
        status="blocked",
        blocked_reason=reason,
        run=None,
        records_count=0,
        entities_count=0,
        field_completeness=None,
        error_message=None,
    )


def _blocked_batch_item_from_task(
    task: CollectionTask,
    reason: str,
) -> AutomationProductBatchRunItemResponse:
    return AutomationProductBatchRunItemResponse(
        task_id=task.id,
        task_name=task.name,
        source_id=task.source_id,
        source_url=_task_source_url(task),
        status="blocked",
        blocked_reason=reason,
        run=None,
        records_count=0,
        entities_count=0,
        field_completeness=None,
        error_message=None,
    )


def _schedule_task_block_reason(task: CollectionTask | None, dataset: Dataset) -> str | None:
    if task is None:
        return "task_not_found"
    if task.project_id != dataset.project_id:
        return "task_project_mismatch"
    if task.collector_type != "ecommerce_product_page":
        return "unsupported_collector_type"
    if task.status != "enabled":
        return "task_not_enabled"
    return None


def _drift_task_block_reason(
    task: CollectionTask | None,
    dataset: Dataset,
    version: DatasetVersion,
) -> str | None:
    reason = _schedule_task_block_reason(task, dataset)
    if reason is not None:
        return reason
    assert task is not None
    config = task.config or {}
    if config.get("approved_dataset_id") != str(dataset.id):
        return "task_dataset_lineage_unapproved"
    if config.get("approved_dataset_version_id") != str(version.id):
        return "task_dataset_lineage_unapproved"
    return None


def _github_tool_drift_task_block_reason(
    task: CollectionTask | None,
    dataset: Dataset,
    anchor_task_ids: set[uuid.UUID],
) -> str | None:
    if task is None:
        return "task_not_found"
    if task.project_id != dataset.project_id:
        return "task_project_lineage_conflict"
    if task.collector_type not in {"github_topic", "github_repo"}:
        return "task_collector_type_not_github_tool"
    if task.id not in anchor_task_ids:
        return "task_dataset_lineage_unapproved"
    return None


def _blocked_drift_item(
    task_id: uuid.UUID,
    version: DatasetVersion,
    reason: str,
    task: CollectionTask | None = None,
) -> AutomationProductDriftItemResponse:
    return AutomationProductDriftItemResponse(
        task_id=task_id,
        task_name=task.name if task else None,
        source_url=_task_source_url(task) if task else None,
        status="blocked",
        blocked_reason=reason,
        latest_run_id=None,
        latest_run_status=None,
        dataset_version_completeness_percent=version.average_completeness_percent,
        latest_completeness_percent=None,
        completeness_drop_percent=None,
        missing_fields=[],
        new_missing_fields=[],
        freshness_target_hours=None,
        stale_hours=None,
        issues=[],
    )


def _approved_schedule_config(
    current_config: dict[str, object] | None,
    *,
    dataset: Dataset,
    version: DatasetVersion,
    payload: AutomationProductScheduleApproveRequest,
    approved_at: datetime,
) -> dict[str, object]:
    config = dict(current_config or {})
    config["schedule_policy"] = payload.schedule_policy
    config["freshness_target_hours"] = payload.freshness_target_hours
    config["approved_dataset_id"] = str(dataset.id)
    config["approved_dataset_version_id"] = str(version.id)
    config["schedule_approved_at"] = approved_at.isoformat()
    config["schedule_boundary"] = "approved_no_immediate_run"
    config["schedule_quality_gate"] = {
        "minimum_completeness_percent": payload.minimum_completeness_percent,
        "actual_completeness_percent": version.average_completeness_percent,
        "row_count": version.row_count,
        "selected_fields": version.selected_fields,
    }
    if payload.note:
        config["schedule_approval_note"] = payload.note
    else:
        config.pop("schedule_approval_note", None)
    return config


def _product_field_completeness(
    task: CollectionTask,
    raw_records: list[RawRecord],
) -> AutomationProductBatchFieldCompletenessResponse:
    configured_fields = _configured_product_fields(task)
    return _product_field_completeness_for_fields(raw_records, configured_fields)


def _product_field_completeness_for_fields(
    raw_records: list[RawRecord],
    configured_fields: list[str],
) -> AutomationProductBatchFieldCompletenessResponse:
    field_values: dict[str, object] = {}
    for raw_record in raw_records:
        extracted_fields = _raw_record_extracted_fields(raw_record)
        for field in configured_fields:
            if field in field_values:
                continue
            value = extracted_fields.get(field)
            if _has_field_value(value):
                field_values[field] = value

    extracted = [field for field in configured_fields if field in field_values]
    missing = [field for field in configured_fields if field not in field_values]
    ratio = len(extracted) / len(configured_fields) if configured_fields else 0
    return AutomationProductBatchFieldCompletenessResponse(
        configured_fields=configured_fields,
        extracted_fields=extracted,
        missing_fields=missing,
        field_values=field_values,
        completeness_ratio=round(ratio, 4),
        completeness_percent=round(ratio * 100),
    )


def _product_row_drift(
    version: DatasetVersion,
    raw_records: list[RawRecord],
    task: CollectionTask,
) -> ProductRowDrift:
    task_source_url = _task_source_url(task)
    baseline_rows = _dataset_version_rows_for_task_source(version, task_source_url)
    current_by_key: dict[str, dict[str, object]] = {}
    for raw_record in raw_records:
        values = _raw_record_extracted_fields(raw_record)
        key = _product_row_key(values, raw_record.source_url)
        if key is not None:
            current_by_key[key] = values

    baseline_by_key: dict[str, dict[str, object]] = {}
    for row in baseline_rows:
        raw_values = row.get("values")
        row_values: dict[str, object] = dict(raw_values) if isinstance(raw_values, dict) else {}
        source_url = row.get("source_url")
        key = _product_row_key(
            row_values,
            source_url if isinstance(source_url, str) else None,
        )
        if key is not None:
            baseline_by_key[key] = row_values

    baseline_keys = set(baseline_by_key)
    current_keys = set(current_by_key)
    added_count = len(current_keys - baseline_keys)
    removed_count = len(baseline_keys - current_keys)
    price_change_percent = _largest_price_change_percent(baseline_by_key, current_by_key)
    issues: list[str] = []
    if added_count:
        issues.append("product_added")
    if removed_count:
        issues.append("product_removed")
    if price_change_percent is not None:
        issues.append("price_changed")

    row_change: ProductRowChange = "unchanged"
    if added_count and removed_count:
        row_change = "mixed"
    elif added_count:
        row_change = "added"
    elif removed_count:
        row_change = "removed"

    return ProductRowDrift(
        row_change=row_change,
        added_row_count=added_count,
        removed_row_count=removed_count,
        price_change_percent=price_change_percent,
        issues=issues,
    )


def _dataset_version_rows_for_task_source(
    version: DatasetVersion,
    task_source_url: str | None,
) -> list[dict[str, object]]:
    rows = [row for row in version.rows if isinstance(row, dict)]
    if task_source_url is None:
        return rows
    matched = [
        row
        for row in rows
        if row.get("source_url") == task_source_url
        or _row_values_canonical_url(row) == task_source_url
    ]
    return matched


def _row_values_canonical_url(row: dict[str, object]) -> str | None:
    values = row.get("values")
    if not isinstance(values, dict):
        return None
    canonical_url = values.get("canonical_url")
    return str(canonical_url).strip() if _has_field_value(canonical_url) else None


def _product_row_key(values: dict[str, object], source_url: str | None) -> str | None:
    for field in ("canonical_url", "sku", "title"):
        value = values.get(field)
        if _has_field_value(value):
            return str(value).strip()
    if source_url is not None and source_url.strip():
        return source_url.strip()
    return None


def _largest_price_change_percent(
    baseline_by_key: dict[str, dict[str, object]],
    current_by_key: dict[str, dict[str, object]],
) -> float | None:
    changes: list[float] = []
    for key in sorted(set(baseline_by_key) & set(current_by_key)):
        baseline_price = _numeric_value(baseline_by_key[key].get("price"))
        current_price = _numeric_value(current_by_key[key].get("price"))
        if baseline_price is None or current_price is None or baseline_price == current_price:
            continue
        if baseline_price == 0:
            changes.append(100.0)
        else:
            changes.append(round(((current_price - baseline_price) / baseline_price) * 100, 2))
    if not changes:
        return None
    return max(changes, key=abs)


def _numeric_value(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").strip())
        except ValueError:
            return None
    return None


def _task_freshness_drift(
    task: CollectionTask,
    checked_at: datetime,
    freshness_grace_hours: int,
) -> tuple[int | None, float | None]:
    config = task.config or {}
    target = config.get("freshness_target_hours")
    freshness_target_hours = target if isinstance(target, int) else 24
    if task.last_run_at is None:
        return freshness_target_hours, None
    last_run_at = _aware_datetime(task.last_run_at)
    checked = _aware_datetime(checked_at)
    age_hours = (checked - last_run_at).total_seconds() / 3600
    stale_hours = max(age_hours - freshness_target_hours - freshness_grace_hours, 0)
    return freshness_target_hours, round(stale_hours, 2)


def _aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _drift_status(issues: list[str]) -> str:
    critical_issues = {
        "latest_run_failed",
        "completeness_drift_exceeded",
        "product_removed",
    }
    if any(issue in critical_issues for issue in issues):
        return "critical"
    if issues:
        return "warning"
    return "ok"


def _product_drift_summary(
    requested_task_ids: list[uuid.UUID],
    items: list[AutomationProductDriftItemResponse],
) -> AutomationProductDriftSummaryResponse:
    checked_items = [item for item in items if item.status != "blocked"]
    blocked_items = [item for item in items if item.status == "blocked"]
    warning_items = [item for item in items if item.status == "warning"]
    critical_items = [item for item in items if item.status == "critical"]
    return AutomationProductDriftSummaryResponse(
        requested_tasks=len(requested_task_ids),
        checked_tasks=len(checked_items),
        blocked_tasks=len(blocked_items),
        warning_tasks=len(warning_items),
        critical_tasks=len(critical_items),
        stale_tasks=len([
            item
            for item in checked_items
            if item.stale_hours is not None and item.stale_hours > 0
        ]),
        missing_field_tasks=len([item for item in checked_items if item.new_missing_fields]),
        added_rows=sum(item.added_row_count for item in checked_items),
        removed_rows=sum(item.removed_row_count for item in checked_items),
        price_changed_tasks=len([
            item for item in checked_items if item.price_change_percent is not None
        ]),
        drift_layers=_drift_layer_counts(items),
        run_started=False,
        alert_created=False,
    )


def _drift_layer_counts(items: list[AutomationProductDriftItemResponse]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        for layer, value in _drift_layer_counts_for_issues(item.issues).items():
            counts[layer] = counts.get(layer, 0) + value
    return counts


def _drift_layer_counts_for_issues(issues: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in issues:
        layer = DRIFT_LAYER_BY_ISSUE.get(issue)
        if layer is None:
            continue
        counts[layer] = counts.get(layer, 0) + 1
    return counts


def _drift_event_status(summary: AutomationProductDriftSummaryResponse) -> str:
    if summary.critical_tasks > 0:
        return "critical"
    if summary.warning_tasks > 0:
        return "warning"
    if summary.checked_tasks == 0 and summary.blocked_tasks > 0:
        return "blocked"
    if summary.blocked_tasks > 0:
        return "warning"
    return "ok"


def _selected_fields_from_source_draft(source_draft: dict[str, object]) -> list[str]:
    config = source_draft.get("config")
    if not isinstance(config, dict):
        return list(ECOMMERCE_PRODUCT_FIELDS)
    fields = config.get("fields")
    if not isinstance(fields, list):
        return list(ECOMMERCE_PRODUCT_FIELDS)
    selected_fields = [field for field in fields if isinstance(field, str) and field.strip()]
    return selected_fields or list(ECOMMERCE_PRODUCT_FIELDS)


def _source_draft_response(source_draft: dict[str, object]) -> AutomationSourceDraftResponse:
    raw_config = source_draft.get("config")
    config = dict(raw_config) if isinstance(raw_config, dict) else {}
    return AutomationSourceDraftResponse(
        type=str(source_draft.get("type") or "ecommerce_product_page"),
        config=config,
        suggested_name=str(source_draft.get("suggested_name") or "Extraction plan"),
        schedule_cron=(
            str(source_draft["schedule_cron"])
            if source_draft.get("schedule_cron") is not None
            else None
        ),
    )


def _extraction_plan_response(
    extraction_plan: ExtractionPlan,
) -> AutomationExtractionPlanResponse:
    return AutomationExtractionPlanResponse(
        id=extraction_plan.id,
        site_analysis_id=extraction_plan.site_analysis_id,
        project_id=extraction_plan.project_id,
        name=extraction_plan.name,
        version_number=extraction_plan.version_number,
        collector_type=extraction_plan.collector_type,
        selected_fields=extraction_plan.selected_fields,
        source_draft=_source_draft_response(extraction_plan.source_draft),
        schedule_cron=extraction_plan.schedule_cron,
        status=extraction_plan.status,
        risk_level=extraction_plan.risk_level,
        audit_events=extraction_plan.audit_events,
        created_at=extraction_plan.created_at,
        run_started=False,
    )


def _browser_diagnostic_run_response(
    diagnostic_run: BrowserDiagnosticRun,
) -> AutomationBrowserDiagnosticRunResponse:
    return AutomationBrowserDiagnosticRunResponse(
        id=diagnostic_run.id,
        project_id=diagnostic_run.project_id,
        site_analysis_id=diagnostic_run.site_analysis_id,
        requested_url=diagnostic_run.requested_url,
        final_url=diagnostic_run.final_url,
        status=diagnostic_run.status,
        authorization_confirmed=diagnostic_run.authorization_confirmed,
        schema_version=diagnostic_run.schema_version,
        recommended_path=diagnostic_run.recommended_path,
        confidence=diagnostic_run.confidence,
        field_stability=diagnostic_run.field_stability,
        evidence_source=diagnostic_run.evidence_source,
        screenshot_path=diagnostic_run.screenshot_path,
        run_policy=diagnostic_run.run_policy,
        page_summary=diagnostic_run.page_summary,
        network_summary=diagnostic_run.network_summary,
        accessibility_summary=diagnostic_run.accessibility_summary,
        risk_flags=diagnostic_run.risk_flags,
        extraction_strategy=diagnostic_run.extraction_strategy,
        blocked_reasons=diagnostic_run.blocked_reasons,
        created_at=diagnostic_run.created_at,
        run_started=diagnostic_run.run_started,
    )


def _browser_diagnostic_job_response(
    diagnostic_job: BrowserDiagnosticJob,
) -> AutomationBrowserDiagnosticJobResponse:
    return AutomationBrowserDiagnosticJobResponse(
        id=diagnostic_job.id,
        project_id=diagnostic_job.project_id,
        site_analysis_id=diagnostic_job.site_analysis_id,
        extraction_plan_id=diagnostic_job.extraction_plan_id,
        browser_diagnostic_run_id=diagnostic_job.browser_diagnostic_run_id,
        requested_url=diagnostic_job.requested_url,
        final_url=diagnostic_job.final_url,
        status=diagnostic_job.status,
        authorization_confirmed=diagnostic_job.authorization_confirmed,
        runner=diagnostic_job.runner,
        execution_mode=diagnostic_job.execution_mode,
        selector_scope=diagnostic_job.selector_scope,
        wait_policy=diagnostic_job.wait_policy,
        network_observation_policy=diagnostic_job.network_observation_policy,
        artifact_policy=diagnostic_job.artifact_policy,
        safety_flags=diagnostic_job.safety_flags,
        dry_run_summary=diagnostic_job.dry_run_summary,
        executable_spec_snapshot=diagnostic_job.executable_spec_snapshot,
        blocked_reasons=diagnostic_job.blocked_reasons,
        audit_events=diagnostic_job.audit_events,
        created_at=diagnostic_job.created_at,
        updated_at=diagnostic_job.updated_at,
        cancelled_at=diagnostic_job.cancelled_at,
        run_started=diagnostic_job.run_started,
    )


def _browser_local_runner_result_response(
    run_asset: BrowserDiagnosticJobRun,
) -> AutomationBrowserLocalRunnerResultResponse:
    return AutomationBrowserLocalRunnerResultResponse(
        id=run_asset.id,
        job=_browser_diagnostic_job_response(run_asset.browser_diagnostic_job),
        status=run_asset.status,
        runner=run_asset.runner,
        run_mode=run_asset.run_mode,
        contract_snapshot=run_asset.contract_snapshot,
        artifact_manifest=run_asset.artifact_manifest,
        selector_results=run_asset.selector_results,
        selector_evaluations=_browser_local_runner_selector_evaluations(
            run_asset.selector_results
        ),
        preview_rows=run_asset.preview_rows,
        network_observation_summary=run_asset.network_observation_summary,
        network_metadata_summary=_browser_local_runner_network_metadata_summary(
            run_asset.network_observation_summary
        ),
        error_summary=run_asset.error_summary,
        promotion_gate=_browser_local_runner_promotion_gate(run_asset),
        redaction_summary=_browser_local_runner_redaction_summary(run_asset),
        blocked_reasons=run_asset.blocked_reasons,
        audit_events=run_asset.audit_events,
        created_at=run_asset.created_at,
        updated_at=run_asset.updated_at,
        started_at=run_asset.started_at,
        finished_at=run_asset.finished_at,
        execution_started=run_asset.execution_started,
        browser_started=run_asset.browser_started,
        files_written=run_asset.files_written,
        collection_resources_written=run_asset.collection_resources_written,
    )


def _site_analysis_history_item(
    site_analysis: SiteAnalysis,
    latest_plan: AutomationExtractionPlanResponse | None,
) -> AutomationSiteAnalysisHistoryItemResponse:
    return AutomationSiteAnalysisHistoryItemResponse(
        id=site_analysis.id,
        project_id=site_analysis.project_id,
        requested_url=site_analysis.requested_url,
        target=site_analysis.target,
        status=site_analysis.status,
        platform_type=str(site_analysis.platform_profile.get("platform_type") or "unknown"),
        page_type=str(site_analysis.page_structure.get("page_type") or "unknown"),
        risk_level=str(site_analysis.platform_profile.get("risk_level") or "unknown"),
        analyzed_at=site_analysis.analyzed_at,
        created_at=site_analysis.created_at,
        latest_plan=latest_plan,
    )


def _dataset_response(dataset: Dataset | AutomationDatasetResponse) -> AutomationDatasetResponse:
    return AutomationDatasetResponse(
        id=dataset.id,
        project_id=dataset.project_id,
        name=dataset.name,
        dataset_type=dataset.dataset_type,
        status=dataset.status,
        description=dataset.description,
    )


def _dataset_version_response(
    version: DatasetVersion | AutomationDatasetVersionResponse,
) -> AutomationDatasetVersionResponse:
    return AutomationDatasetVersionResponse(
        id=version.id,
        dataset_id=version.dataset_id,
        cleaning_plan_id=version.cleaning_plan_id,
        version_number=version.version_number,
        source_task_run_ids=version.source_task_run_ids,
        selected_fields=version.selected_fields,
        cleaning_script=version.cleaning_script,
        row_count=version.row_count,
        average_completeness_percent=version.average_completeness_percent,
        status=version.status,
        created_at=version.created_at,
        export_preview=version.export_preview,
    )


def _cleaning_plan_response(cleaning_plan: CleaningPlan) -> AutomationCleaningPlanResponse:
    return AutomationCleaningPlanResponse(
        id=cleaning_plan.id,
        project_id=cleaning_plan.project_id,
        name=cleaning_plan.name,
        version_number=cleaning_plan.version_number,
        target=cleaning_plan.target,
        selected_fields=cleaning_plan.selected_fields,
        source_task_run_ids=cleaning_plan.source_task_run_ids,
        rules=cleaning_plan.rules,
        cleaning_script=cleaning_plan.cleaning_script,
        dry_run_preview=cleaning_plan.dry_run_preview,
        status=cleaning_plan.status,
        created_at=cleaning_plan.created_at,
    )


async def _get_dataset_and_version(
    session: AsyncSession,
    workspace: Workspace,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
) -> tuple[Dataset, DatasetVersion]:
    dataset = await get_dataset(session, workspace.id, dataset_id)
    if dataset is None:
        raise CollectorError("dataset_not_found")
    version = await get_dataset_version(session, workspace.id, dataset.id, version_id)
    if version is None:
        raise CollectorError("dataset_version_not_found")
    return dataset, version


def _dataset_export_job_response(
    export_job: DatasetExportJob,
    dataset: Dataset,
    version: DatasetVersion,
) -> AutomationProductDatasetExportJobResponse:
    download_url = None
    if export_job.status == "success":
        download_url = (
            f"/api/automation/product-datasets/{dataset.id}/versions/{version.id}"
            f"/exports/{export_job.id}/download"
        )
    return AutomationProductDatasetExportJobResponse(
        id=export_job.id,
        dataset=_dataset_response(dataset),
        version=_dataset_version_response(version),
        export_format=export_job.export_format,
        status=export_job.status,
        filename=export_job.filename,
        content_type=export_job.content_type,
        artifact_size_bytes=export_job.artifact_size_bytes,
        row_count=export_job.row_count,
        checksum_sha256=export_job.checksum_sha256,
        error_message=export_job.error_message,
        created_at=export_job.created_at,
        finished_at=export_job.finished_at,
        download_url=download_url,
        audit_events=export_job.audit_events,
        blocked_reasons=[
            "导出文件已写入受控目录；下载接口会再次校验当前账号的数据集权限。"
        ],
    )


def _dataset_export_root() -> Path:
    return Path(get_settings().dataset_export_dir).expanduser()


def _dataset_export_path(
    *,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    filename: str,
) -> Path:
    return (
        _dataset_export_root()
        / str(workspace_id)
        / str(dataset_id)
        / str(version_id)
        / filename
    ).resolve()


def _dataset_export_filename(
    dataset: Dataset,
    version: DatasetVersion,
    job_id: uuid.UUID,
    export_format: str,
) -> str:
    slug = _dataset_export_slug(dataset.name)
    return f"{slug}-v{version.version_number}-{str(job_id)[:8]}.{export_format}"


def _dataset_export_slug(value: str) -> str:
    characters: list[str] = []
    for character in value.lower():
        if character.isalnum():
            characters.append(character)
        elif characters and characters[-1] != "-":
            characters.append("-")
    slug = "".join(characters).strip("-")
    return slug[:80] or "dataset"


def _render_dataset_export(
    dataset: Dataset,
    version: DatasetVersion,
    export_format: str,
) -> bytes:
    rows = _dataset_export_rows(version)
    if export_format == "csv":
        return _render_dataset_csv(version, rows)
    if export_format == "jsonl":
        lines = [json.dumps(row, ensure_ascii=False, default=str) for row in rows]
        return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    payload = {
        "dataset": {
            "id": str(dataset.id),
            "project_id": str(dataset.project_id),
            "name": dataset.name,
            "dataset_type": dataset.dataset_type,
        },
        "version": {
            "id": str(version.id),
            "version_number": version.version_number,
            "selected_fields": version.selected_fields,
            "row_count": version.row_count,
            "average_completeness_percent": version.average_completeness_percent,
            "created_at": version.created_at.isoformat(),
        },
        "schema": version.export_preview.get("schema", {}),
        "rows": rows,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _dataset_export_rows(version: DatasetVersion) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for saved_row in version.rows:
        values = saved_row.get("values") if isinstance(saved_row, dict) else None
        if not isinstance(values, dict):
            values = {}
        row: dict[str, object] = {
            field: values.get(field)
            for field in version.selected_fields
        }
        row["row_id"] = saved_row.get("row_id")
        row["source_url"] = saved_row.get("source_url")
        row["task_run_id"] = saved_row.get("task_run_id")
        row["raw_record_id"] = saved_row.get("raw_record_id")
        row["missing_fields"] = saved_row.get("missing_fields", [])
        row["completeness_percent"] = saved_row.get("completeness_percent")
        rows.append(row)
    return rows


def _render_dataset_csv(version: DatasetVersion, rows: list[dict[str, object]]) -> bytes:
    stream = io.StringIO()
    fieldnames = [
        *version.selected_fields,
        "row_id",
        "source_url",
        "task_run_id",
        "raw_record_id",
        "missing_fields",
        "completeness_percent",
    ]
    writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_export_value(row.get(field)) for field in fieldnames})
    return stream.getvalue().encode("utf-8")


def _csv_export_value(value: object) -> str | int | float | bool | None:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def _drift_event_response(
    event: DatasetDriftEvent,
    dataset: Dataset | AutomationDatasetResponse,
    version: DatasetVersion | AutomationDatasetVersionResponse,
) -> AutomationProductDriftEventResponse:
    summary = AutomationProductDriftSummaryResponse(**event.summary)
    return AutomationProductDriftEventResponse(
        id=event.id,
        created_at=event.created_at,
        dataset=_dataset_response(dataset),
        version=_dataset_version_response(version),
        event_type=event.event_type,
        status=event.status,
        thresholds=event.thresholds,
        summary=summary,
        items=[AutomationProductDriftItemResponse(**item) for item in event.items],
        audit_events=event.audit_events,
        note=event.note,
        run_started=summary.run_started,
        alert_created=summary.alert_created,
    )


def _configured_product_fields(task: CollectionTask) -> list[str]:
    config = task.config or {}
    configured = config.get("fields")
    if not isinstance(configured, list):
        return list(ECOMMERCE_PRODUCT_FIELDS)
    fields = [field for field in configured if isinstance(field, str)]
    allowed = set(ECOMMERCE_PRODUCT_FIELDS)
    normalized = [field for field in fields if field in allowed]
    return normalized or list(ECOMMERCE_PRODUCT_FIELDS)


def _raw_record_extracted_fields(raw_record: RawRecord) -> dict[str, object]:
    content = raw_record.content
    if not isinstance(content, dict):
        return {}
    extracted = content.get("extracted_fields")
    if not isinstance(extracted, dict):
        return {}
    return extracted


def _has_field_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, set, tuple)):
        return bool(value)
    return True


def _task_source_url(task: CollectionTask) -> str | None:
    config = task.config or {}
    url = config.get("url")
    if isinstance(url, str) and url.strip():
        return url.strip()
    return None


def _product_batch_summary(
    requested_task_ids: list[uuid.UUID],
    items: list[AutomationProductBatchRunItemResponse],
) -> AutomationProductBatchRunSummaryResponse:
    run_items = [item for item in items if item.status in {"run_completed", "run_failed"}]
    blocked_items = [item for item in items if item.status == "blocked"]
    successful = [
        item
        for item in run_items
        if item.run is not None and item.run.status in {"success", "partial_success"}
    ]
    failed = [item for item in run_items if item.run is not None and item.run.status == "failed"]
    completeness_values = [
        item.field_completeness.completeness_percent
        for item in run_items
        if item.field_completeness is not None
    ]
    average = (
        round(sum(completeness_values) / len(completeness_values))
        if completeness_values
        else 0
    )
    return AutomationProductBatchRunSummaryResponse(
        requested_tasks=len(requested_task_ids),
        run_tasks=len(run_items),
        blocked_tasks=len(blocked_items),
        successful_runs=len(successful),
        failed_runs=len(failed),
        records_count=sum(item.records_count for item in run_items),
        entities_count=sum(item.entities_count for item in run_items),
        average_completeness_percent=average,
        run_started=bool(run_items),
    )


def _dataset_fields(fields: list[str] | None) -> list[str]:
    requested = fields or list(ECOMMERCE_PRODUCT_FIELDS)
    allowed = set(ECOMMERCE_PRODUCT_FIELDS)
    normalized = [field for field in requested if field in allowed]
    return normalized or list(ECOMMERCE_PRODUCT_FIELDS)


def _github_tool_dataset_fields(fields: list[str] | None) -> list[str]:
    requested = fields or [
        "repo_full_name",
        "stars",
        "forks",
        "open_issues",
        "language",
        "topics",
        "license_spdx_id",
        "default_branch",
        "latest_release_tag",
        "latest_release_published_at",
        "readme_detected",
        "issue_activity_open_count",
        "issue_activity_status",
        "commit_freshness_days",
        "commit_freshness_status",
        "html_url",
        "pushed_at",
        "updated_at",
    ]
    allowed = set(GITHUB_TOOL_FIELDS)
    normalized = [field for field in requested if field in allowed]
    return normalized or list(GITHUB_TOOL_FIELDS)


def _github_tool_field_sources(fields: object) -> dict[str, str]:
    field_names: list[str] = []
    if isinstance(fields, dict):
        field_names = [str(field) for field in fields]
    elif isinstance(fields, str):
        field_names = []
    elif isinstance(fields, Iterable):
        field_names = [str(field) for field in fields]
    else:
        field_names = []
    return {
        field: GITHUB_TOOL_FIELD_SOURCES.get(field, "github.repository")
        for field in field_names
    }


def _dataset_row(
    raw_record: RawRecord,
    selected_fields: list[str],
) -> AutomationProductDatasetRowResponse:
    extracted_fields = _raw_record_extracted_fields(raw_record)
    values = {
        field: extracted_fields.get(field)
        for field in selected_fields
        if _has_field_value(extracted_fields.get(field))
    }
    missing_fields = [field for field in selected_fields if field not in values]
    ratio = len(values) / len(selected_fields) if selected_fields else 0
    return AutomationProductDatasetRowResponse(
        row_id=f"{raw_record.task_run_id}:{raw_record.id}",
        task_run_id=raw_record.task_run_id,
        raw_record_id=raw_record.id,
        source_url=raw_record.source_url,
        values=values,
        missing_fields=missing_fields,
        completeness_percent=round(ratio * 100),
    )


def _github_tool_rows(
    raw_record: RawRecord,
    selected_fields: list[str],
) -> list[AutomationProductDatasetRowResponse]:
    content = raw_record.content if isinstance(raw_record.content, dict) else {}
    repositories = content.get("repositories")
    repo_items = repositories if isinstance(repositories, list) else []
    if not repo_items and raw_record.record_type == "github_repo":
        repo_items = [content]

    rows: list[AutomationProductDatasetRowResponse] = []
    for index, repo in enumerate(repo_items):
        if not isinstance(repo, dict):
            continue
        values_by_field = _github_tool_values(repo)
        values = {
            field: values_by_field.get(field)
            for field in selected_fields
            if _has_field_value(values_by_field.get(field))
        }
        missing_fields = [field for field in selected_fields if field not in values]
        ratio = len(values) / len(selected_fields) if selected_fields else 0
        row_key = values_by_field.get("html_url") or values_by_field.get("repo_full_name") or index
        rows.append(
            AutomationProductDatasetRowResponse(
                row_id=f"{raw_record.task_run_id}:{raw_record.id}:{row_key}",
                task_run_id=raw_record.task_run_id,
                raw_record_id=raw_record.id,
                source_url=(
                    str(values_by_field["html_url"])
                    if _has_field_value(values_by_field.get("html_url"))
                    else raw_record.source_url
                ),
                values=values,
                missing_fields=missing_fields,
                completeness_percent=round(ratio * 100),
            )
        )
    return rows


def _github_tool_values(repo: dict[str, object]) -> dict[str, object]:
    stars = repo.get("stargazers_count", repo.get("stars"))
    forks = repo.get("forks_count", repo.get("forks"))
    open_issues = repo.get("open_issues_count", repo.get("open_issues"))
    watchers = repo.get("watchers_count", repo.get("watchers"))
    full_name = repo.get("full_name") or repo.get("repo_full_name")
    html_url = repo.get("html_url") or repo.get("url")
    topics = repo.get("topics")
    owner_value = repo.get("owner")
    owner_login = repo.get("owner_login")
    owner_type = repo.get("owner_type")
    if isinstance(owner_value, dict):
        owner_login = owner_login or owner_value.get("login")
        owner_type = owner_type or owner_value.get("type")
    license_value = repo.get("license")
    latest_release = repo.get("latest_release")
    latest_release_values = latest_release if isinstance(latest_release, dict) else {}
    readme = repo.get("readme")
    readme_values = readme if isinstance(readme, dict) else {}
    issue_activity = repo.get("issue_activity")
    issue_activity_values = issue_activity if isinstance(issue_activity, dict) else {}
    commit_freshness = repo.get("commit_freshness")
    commit_freshness_values = commit_freshness if isinstance(commit_freshness, dict) else {}
    issue_activity_open_count = (
        repo.get("issue_activity_open_count")
        if _has_field_value(repo.get("issue_activity_open_count"))
        else issue_activity_values.get("open_count")
    )
    if not _has_field_value(issue_activity_open_count):
        issue_activity_open_count = open_issues
    readme_detected = repo.get("readme_detected")
    if readme_detected is None and readme_values:
        readme_detected = True
    commit_freshness_days = (
        repo.get("commit_freshness_days")
        if _has_field_value(repo.get("commit_freshness_days"))
        else commit_freshness_values.get("days_since_push")
    )
    commit_freshness_status = (
        repo.get("commit_freshness_status")
        if _has_field_value(repo.get("commit_freshness_status"))
        else commit_freshness_values.get("status")
    )
    if not _has_field_value(commit_freshness_status):
        commit_freshness_status = _commit_freshness_status(repo.get("pushed_at"))
    return {
        "repo_full_name": full_name,
        "owner_login": owner_login,
        "owner_type": owner_type,
        "description": repo.get("description"),
        "stars": stars,
        "forks": forks,
        "open_issues": open_issues,
        "watchers": watchers,
        "language": repo.get("language"),
        "topics": topics if isinstance(topics, list) else [],
        "license_spdx_id": (
            repo.get("license_spdx_id")
            or _license_spdx_id_from_value(license_value)
        ),
        "default_branch": repo.get("default_branch"),
        "latest_release_tag": (
            repo.get("latest_release_tag")
            or latest_release_values.get("tag_name")
        ),
        "latest_release_published_at": (
            repo.get("latest_release_published_at")
            or latest_release_values.get("published_at")
        ),
        "archived": repo.get("archived"),
        "fork": repo.get("fork"),
        "html_url": html_url,
        "homepage": repo.get("homepage"),
        "created_at": repo.get("created_at"),
        "updated_at": repo.get("updated_at"),
        "pushed_at": repo.get("pushed_at"),
        "readme_detected": readme_detected,
        "readme_name": repo.get("readme_name") or readme_values.get("name"),
        "readme_path": repo.get("readme_path") or readme_values.get("path"),
        "readme_html_url": repo.get("readme_html_url") or readme_values.get("html_url"),
        "readme_download_url": (
            repo.get("readme_download_url") or readme_values.get("download_url")
        ),
        "readme_sha": repo.get("readme_sha") or readme_values.get("sha"),
        "readme_size": repo.get("readme_size") or readme_values.get("size"),
        "issue_activity_open_count": issue_activity_open_count,
        "issue_activity_status": (
            repo.get("issue_activity_status")
            or issue_activity_values.get("status")
            or _issue_activity_status(issue_activity_open_count)
        ),
        "issue_activity_updated_at": (
            repo.get("issue_activity_updated_at")
            or issue_activity_values.get("updated_at")
            or repo.get("updated_at")
        ),
        "commit_freshness_days": commit_freshness_days,
        "commit_freshness_status": commit_freshness_status,
    }


def _license_spdx_id_from_value(value: object) -> str | None:
    if isinstance(value, dict):
        license_id = value.get("spdx_id") or value.get("key") or value.get("name")
        return str(license_id) if license_id else None
    if isinstance(value, str):
        return value
    return None


def _issue_activity_status(value: object) -> str:
    count = _int_or_none(value)
    if count is None:
        return "unknown"
    return "active" if count > 0 else "quiet"


def _commit_freshness_status(value: object) -> str:
    days = _days_since_iso_datetime(value)
    if days is None:
        return "unknown"
    if days <= 30:
        return "fresh"
    if days <= 180:
        return "aging"
    return "stale"


def _days_since_iso_datetime(value: object, now: datetime | None = None) -> int | None:
    parsed = _parse_iso_datetime(value)
    if parsed is None:
        return None
    current = now or datetime.now(UTC)
    return max((current - parsed).days, 0)


def _parse_iso_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _github_tool_field_completeness_for_fields(
    raw_records: list[RawRecord],
    configured_fields: list[str],
) -> AutomationProductBatchFieldCompletenessResponse:
    rows: list[AutomationProductDatasetRowResponse] = []
    for raw_record in raw_records:
        rows.extend(_github_tool_rows(raw_record, configured_fields))

    field_values: dict[str, object] = {}
    missing_fields_set: set[str] = set()
    for row in rows:
        missing_fields_set.update(row.missing_fields)
        for field in configured_fields:
            if field in field_values:
                continue
            value = row.values.get(field)
            if _has_field_value(value):
                field_values[field] = value

    if not rows:
        missing_fields_set.update(configured_fields)
        completeness_percent = 0
    else:
        completeness_percent = round(
            sum(row.completeness_percent for row in rows) / len(rows)
        )
    missing_fields = [field for field in configured_fields if field in missing_fields_set]
    extracted_fields = [field for field in configured_fields if field not in missing_fields_set]
    return AutomationProductBatchFieldCompletenessResponse(
        configured_fields=configured_fields,
        extracted_fields=extracted_fields,
        missing_fields=missing_fields,
        field_values=field_values,
        completeness_ratio=round(completeness_percent / 100, 4),
        completeness_percent=completeness_percent,
    )


def _github_tool_metric_drift_issues(
    saved_rows: list[dict[str, object]],
    latest_rows: list[AutomationProductDatasetRowResponse],
    selected_fields: list[str],
    checked_at: datetime,
) -> list[str]:
    baseline_by_repo = _github_tool_baseline_values_by_repo(saved_rows)
    selected = set(selected_fields)
    issues: list[str] = []
    for row in latest_rows:
        repo_key = _github_tool_values_repo_key(row.values)
        if repo_key is None:
            continue
        baseline = baseline_by_repo.get(repo_key)
        if baseline is None:
            continue
        if "stars" in selected and _numeric_metric_changed(
            baseline.get("stars"),
            row.values.get("stars"),
        ):
            issues.append("stars_changed")
        if "forks" in selected and _numeric_metric_changed(
            baseline.get("forks"),
            row.values.get("forks"),
        ):
            issues.append("forks_changed")
        baseline_open_issues = baseline.get("issue_activity_open_count")
        if not _has_field_value(baseline_open_issues):
            baseline_open_issues = baseline.get("open_issues")
        latest_open_issues = row.values.get("issue_activity_open_count")
        if not _has_field_value(latest_open_issues):
            latest_open_issues = row.values.get("open_issues")
        if (
            {"open_issues", "issue_activity_open_count"} & selected
            and _numeric_metric_changed(baseline_open_issues, latest_open_issues)
        ):
            issues.append("issue_activity_changed")

        if "latest_release_published_at" in selected:
            release_published_at = row.values.get("latest_release_published_at")
            if not _has_field_value(release_published_at):
                issues.append("release_freshness_missing")
            elif _release_is_stale(release_published_at, checked_at):
                issues.append("release_freshness_stale")
    return list(dict.fromkeys(issues))


def _github_tool_baseline_values_by_repo(
    saved_rows: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    baseline: dict[str, dict[str, object]] = {}
    for saved_row in saved_rows:
        values = saved_row.get("values")
        if not isinstance(values, dict):
            continue
        repo_key = _github_tool_values_repo_key(values)
        if repo_key is None:
            continue
        baseline[repo_key] = values
    return baseline


def _github_tool_values_repo_key(values: dict[str, object]) -> str | None:
    repo_full_name = values.get("repo_full_name")
    if isinstance(repo_full_name, str) and repo_full_name.strip():
        return repo_full_name.strip()
    html_url = values.get("html_url")
    if isinstance(html_url, str) and html_url.strip():
        return html_url.strip()
    return None


def _github_tool_drift_signal_groups(
    *,
    version: DatasetVersion,
    raw_records: list[RawRecord],
    approved_fields: list[str],
    new_missing_fields: list[str],
) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    if new_missing_fields:
        groups["field_missingness"] = [
            f"missing:{field}" for field in new_missing_fields
        ]

    baseline_rows = _github_tool_saved_row_values(version.rows)
    latest_rows = _github_tool_latest_row_values(raw_records, approved_fields)
    if baseline_rows and len(latest_rows) < len(baseline_rows):
        groups.setdefault("repository_coverage", []).append(
            f"row_count_decreased:{len(baseline_rows)}->{len(latest_rows)}"
        )

    latest_by_key = {
        key: values
        for values in latest_rows
        if (key := _github_tool_values_repo_key(values)) is not None
    }
    for baseline in baseline_rows:
        key = _github_tool_values_repo_key(baseline)
        if key is None:
            continue
        latest = latest_by_key.get(key)
        if latest is None:
            groups.setdefault("repository_coverage", []).append(f"missing_repo:{key}")
            continue
        _append_github_tool_metric_drift(groups, baseline, latest)
        _append_github_tool_release_drift(groups, baseline, latest)
        _append_github_tool_commit_freshness_drift(groups, baseline, latest)
    return groups


def _github_tool_saved_row_values(saved_rows: list[dict[str, Any]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for saved_row in saved_rows:
        values = saved_row.get("values")
        if isinstance(values, dict):
            rows.append(dict(values))
    return rows


def _github_tool_latest_row_values(
    raw_records: list[RawRecord],
    approved_fields: list[str],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for raw_record in raw_records:
        for row in _github_tool_rows(raw_record, approved_fields):
            rows.append(dict(row.values))
    return rows


def _append_github_tool_metric_drift(
    groups: dict[str, list[str]],
    baseline: dict[str, object],
    latest: dict[str, object],
) -> None:
    for field in ("stars", "forks"):
        baseline_value = _int_or_none(baseline.get(field))
        latest_value = _int_or_none(latest.get(field))
        if baseline_value is None or latest_value is None:
            continue
        if latest_value < baseline_value:
            groups.setdefault("popularity", []).append(
                f"{field}_decreased:{baseline_value}->{latest_value}"
            )

    baseline_issues = _int_or_none(
        baseline.get("issue_activity_open_count")
        if _has_field_value(baseline.get("issue_activity_open_count"))
        else baseline.get("open_issues")
    )
    latest_issues = _int_or_none(
        latest.get("issue_activity_open_count")
        if _has_field_value(latest.get("issue_activity_open_count"))
        else latest.get("open_issues")
    )
    if baseline_issues is None or latest_issues is None:
        return
    if latest_issues > baseline_issues:
        groups.setdefault("issue_activity", []).append(
            f"open_issues_increased:{baseline_issues}->{latest_issues}"
        )


def _append_github_tool_release_drift(
    groups: dict[str, list[str]],
    baseline: dict[str, object],
    latest: dict[str, object],
) -> None:
    baseline_tag = _string_or_none(baseline.get("latest_release_tag"))
    latest_tag = _string_or_none(latest.get("latest_release_tag"))
    if baseline_tag and not latest_tag:
        groups.setdefault("release_freshness", []).append("latest_release_tag_missing")
    elif baseline_tag and latest_tag and baseline_tag != latest_tag:
        groups.setdefault("release_freshness", []).append(
            f"latest_release_changed:{baseline_tag}->{latest_tag}"
        )

    baseline_published = _string_or_none(baseline.get("latest_release_published_at"))
    latest_published = _string_or_none(latest.get("latest_release_published_at"))
    if baseline_published and not latest_published:
        groups.setdefault("release_freshness", []).append(
            "latest_release_published_at_missing"
        )


def _append_github_tool_commit_freshness_drift(
    groups: dict[str, list[str]],
    baseline: dict[str, object],
    latest: dict[str, object],
) -> None:
    baseline_days = _int_or_none(baseline.get("commit_freshness_days"))
    latest_days = _int_or_none(latest.get("commit_freshness_days"))
    if latest_days is None:
        return
    if latest_days > GITHUB_TOOL_RELEASE_STALE_DAYS:
        groups.setdefault("commit_freshness", []).append(
            f"commit_freshness_stale:{latest_days}"
        )
    elif baseline_days is not None and latest_days - baseline_days > 30:
        groups.setdefault("commit_freshness", []).append(
            f"commit_freshness_regressed:{baseline_days}->{latest_days}"
        )


def _github_tool_signal_group_issues(signal_groups: dict[str, list[str]]) -> list[str]:
    issues: list[str] = []
    if signal_groups.get("popularity"):
        issues.append("popularity_metrics_regressed")
    if signal_groups.get("issue_activity"):
        issues.append("issue_activity_increased")
    if any(
        signal.startswith("latest_release") and signal.endswith("missing")
        for signal in signal_groups.get("release_freshness", [])
    ):
        issues.append("release_freshness_missing")
    if signal_groups.get("commit_freshness"):
        issues.append("commit_freshness_stale")
    if signal_groups.get("repository_coverage"):
        issues.append("repository_coverage_changed")
    return issues


def _numeric_metric_changed(baseline_value: object, latest_value: object) -> bool:
    baseline_number = _int_or_none(baseline_value)
    latest_number = _int_or_none(latest_value)
    if baseline_number is None or latest_number is None:
        return False
    return baseline_number != latest_number


def _release_is_stale(value: object, checked_at: datetime) -> bool:
    days = _days_since_iso_datetime(value, checked_at)
    return days is not None and days > GITHUB_TOOL_RELEASE_STALE_DAYS


def _cleaning_plan_dry_run_row(
    row: AutomationProductDatasetRowResponse,
    selected_fields: list[str],
    rules: list[AutomationCleaningRuleInput],
) -> AutomationCleaningPlanDryRunRowResponse:
    before_values = {
        field: row.values.get(field)
        for field in selected_fields
    }
    after_values = dict(before_values)
    for rule in rules:
        if rule.field not in selected_fields:
            continue
        after_values[rule.field] = _apply_cleaning_rule(
            after_values.get(rule.field),
            rule,
        )
    changed_fields = [
        field
        for field in selected_fields
        if before_values.get(field) != after_values.get(field)
    ]
    missing_fields_before = [
        field for field in selected_fields if not _has_field_value(before_values.get(field))
    ]
    missing_fields_after = [
        field for field in selected_fields if not _has_field_value(after_values.get(field))
    ]
    return AutomationCleaningPlanDryRunRowResponse(
        row_id=row.row_id,
        task_run_id=row.task_run_id,
        raw_record_id=row.raw_record_id,
        source_url=row.source_url,
        before_values=before_values,
        after_values=after_values,
        missing_fields_before=missing_fields_before,
        missing_fields_after=missing_fields_after,
        changed_fields=changed_fields,
    )


def _dataset_rows_from_cleaning_dry_run(
    rows: list[AutomationCleaningPlanDryRunRowResponse],
    selected_fields: list[str],
) -> list[AutomationProductDatasetRowResponse]:
    dataset_rows: list[AutomationProductDatasetRowResponse] = []
    for row in rows:
        values = {
            field: row.after_values.get(field)
            for field in selected_fields
            if _has_field_value(row.after_values.get(field))
        }
        missing_fields = [field for field in selected_fields if field not in values]
        ratio = len(values) / len(selected_fields) if selected_fields else 0
        dataset_rows.append(
            AutomationProductDatasetRowResponse(
                row_id=row.row_id,
                task_run_id=row.task_run_id,
                raw_record_id=row.raw_record_id,
                source_url=row.source_url,
                values=values,
                missing_fields=missing_fields,
                completeness_percent=round(ratio * 100),
            )
        )
    return dataset_rows


def _apply_cleaning_rule(
    value: object,
    rule: AutomationCleaningRuleInput,
) -> object:
    if rule.operation == "fill_default":
        return rule.value if not _has_field_value(value) else value
    if not _has_field_value(value):
        return None
    if rule.operation == "strip_text":
        return " ".join(value.split()) if isinstance(value, str) else value
    if rule.operation == "parse_decimal":
        return _parse_decimal_value(value)
    if rule.operation == "normalize_url":
        return value.strip() if isinstance(value, str) else value
    if rule.operation == "uppercase":
        return value.strip().upper() if isinstance(value, str) else value
    if rule.operation == "normalize_availability":
        return _normalize_availability_value(value)
    return value


def _parse_decimal_value(value: object) -> object:
    if isinstance(value, int | float):
        return value
    if not isinstance(value, str):
        return value
    normalized = value.strip().replace(",", "")
    numeric = "".join(
        character
        for character in normalized
        if character.isdigit() or character in {".", "-"}
    )
    if numeric in {"", ".", "-", "-."}:
        return value.strip()
    try:
        parsed = float(numeric)
    except ValueError:
        return value.strip()
    return int(parsed) if parsed.is_integer() else parsed


def _normalize_availability_value(value: object) -> object:
    if not isinstance(value, str):
        return value
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    if normalized in {"in_stock", "instock", "available", "有货"}:
        return "in_stock"
    if normalized in {"out_of_stock", "outofstock", "sold_out", "unavailable", "无货"}:
        return "out_of_stock"
    return "unknown"


def _cleaning_script_from_rules(rules: list[AutomationCleaningRuleInput]) -> list[str]:
    return [_cleaning_rule_script(rule) for rule in rules]


def _cleaning_rule_script(rule: AutomationCleaningRuleInput) -> str:
    if rule.operation == "fill_default":
        return f"fill {rule.field} with default value {rule.value}"
    if rule.operation == "strip_text":
        return f"strip whitespace and collapse repeated spaces in {rule.field}"
    if rule.operation == "parse_decimal":
        return f"parse {rule.field} as decimal when present"
    if rule.operation == "normalize_url":
        return f"normalize {rule.field} as URL string"
    if rule.operation == "uppercase":
        return f"uppercase {rule.field} when present"
    if rule.operation == "normalize_availability":
        return f"normalize {rule.field} into in_stock/out_of_stock/unknown"
    return f"apply {rule.operation} to {rule.field}"


def _cleaning_export_preview(
    rows: list[AutomationCleaningPlanDryRunRowResponse],
    selected_fields: list[str],
) -> dict[str, object]:
    return {
        "format": "json",
        "schema": {
            "fields": selected_fields,
            "primary_key": "canonical_url",
            "missing_value_policy": "explicit_null",
        },
        "rows": [
            {
                field: row.after_values.get(field)
                for field in selected_fields
            }
            for row in rows[:10]
        ],
    }


def _dataset_summary(
    requested_task_run_ids: list[uuid.UUID],
    matched_run_ids: set[uuid.UUID],
    rows: list[AutomationProductDatasetRowResponse],
    selected_fields: list[str],
) -> AutomationProductDatasetSummaryResponse:
    average = (
        round(sum(row.completeness_percent for row in rows) / len(rows))
        if rows
        else 0
    )
    return AutomationProductDatasetSummaryResponse(
        requested_runs=len(requested_task_run_ids),
        matched_runs=len(matched_run_ids),
        rows_count=len(rows),
        selected_fields=selected_fields,
        average_completeness_percent=average,
        export_format="json",
        export_ready=bool(rows),
    )


def _average_dataset_completeness(rows: list[AutomationProductDatasetRowResponse]) -> int:
    return round(sum(row.completeness_percent for row in rows) / len(rows)) if rows else 0


def _cleaning_script_draft(selected_fields: list[str]) -> list[str]:
    steps = [
        "drop rows where title is empty",
        "trim string fields and collapse repeated whitespace",
        "cast price to decimal when present",
        "normalize canonical_url and image_url as absolute URL strings",
        "keep missing values explicit as null for downstream review",
    ]
    if "currency" in selected_fields:
        steps.append("uppercase currency code when present")
    if "availability" in selected_fields:
        steps.append("map availability text into in_stock/out_of_stock/unknown")
    return steps


def _github_tool_cleaning_script_draft(selected_fields: list[str]) -> list[str]:
    steps = [
        "strip repo_full_name and html_url",
        "normalize html_url as canonical repository URL",
        "parse stars, forks, watchers and open_issues as integers when present",
        "normalize topics into lower-case tag arrays",
        "preserve license_spdx_id, default_branch and release tag as source-of-record metadata",
        "preserve README, issue activity and commit freshness fields with per-field provenance",
        "keep missing values explicit as null for downstream review",
    ]
    if (
        "updated_at" in selected_fields
        or "pushed_at" in selected_fields
        or "latest_release_published_at" in selected_fields
    ):
        steps.append("preserve GitHub timestamps as ISO strings for freshness review")
    return steps


def _dataset_export_preview(
    rows: list[AutomationProductDatasetRowResponse],
    selected_fields: list[str],
) -> dict[str, object]:
    return {
        "format": "json",
        "schema": {
            "fields": selected_fields,
            "primary_key": "canonical_url",
            "missing_value_policy": "explicit_null",
        },
        "rows": [
            {
                field: row.values.get(field)
                for field in selected_fields
            }
            for row in rows[:10]
        ],
    }


def _github_tool_export_preview(
    rows: list[AutomationProductDatasetRowResponse],
    selected_fields: list[str],
) -> dict[str, object]:
    return {
        "format": "json",
        "schema": {
            "schema_version": GITHUB_TOOL_DATASET_SCHEMA_VERSION,
            "fields": selected_fields,
            "primary_key": "html_url",
            "missing_value_policy": "explicit_null",
            "dataset_type": "github_tool_radar",
            "collector_schema_versions": list(GITHUB_TOOL_COLLECTOR_SCHEMA_VERSIONS),
            "field_sources": _github_tool_field_sources(selected_fields),
        },
        "rows": [
            {
                field: row.values.get(field)
                for field in selected_fields
            }
            for row in rows[:10]
        ],
    }


def _github_tool_report_repositories(
    saved_rows: list[dict[str, object]],
) -> list[AutomationGitHubToolReportRepositoryResponse]:
    repositories: list[AutomationGitHubToolReportRepositoryResponse] = []
    for saved_row in saved_rows:
        values = saved_row.get("values")
        if not isinstance(values, dict):
            continue
        repo_full_name = _string_or_none(values.get("repo_full_name"))
        if repo_full_name is None:
            continue
        topics_value = values.get("topics")
        topics = [
            str(topic).strip()
            for topic in topics_value
            if str(topic).strip()
        ] if isinstance(topics_value, list) else []
        license_spdx_id = _string_or_none(values.get("license_spdx_id"))
        latest_release_tag = _string_or_none(values.get("latest_release_tag"))
        archived = _bool_or_none(values.get("archived"))
        readme_detected = _bool_or_none(values.get("readme_detected"))
        issue_activity_open_count = _int_or_none(
            values.get("issue_activity_open_count")
        )
        open_issues = _int_or_none(values.get("open_issues"))
        issue_count_for_risk = (
            issue_activity_open_count
            if issue_activity_open_count is not None
            else open_issues
        )
        stars = _int_or_zero(values.get("stars"))
        commit_freshness_days = _int_or_none(values.get("commit_freshness_days"))
        language = _string_or_none(values.get("language"))
        html_url = _string_or_none(values.get("html_url"))
        risk_signals = _github_tool_repository_risk_signals(
            archived=archived,
            license_spdx_id=license_spdx_id,
            latest_release_tag=latest_release_tag,
            readme_present=readme_detected,
            commit_freshness_days=commit_freshness_days,
            commit_freshness_status=_string_or_none(values.get("commit_freshness_status")),
            open_issues=issue_count_for_risk,
            stars=stars,
        )
        repositories.append(
            AutomationGitHubToolReportRepositoryResponse(
                repo_full_name=repo_full_name,
                html_url=html_url,
                description=_string_or_none(values.get("description")),
                stars=stars,
                forks=_int_or_none(values.get("forks")),
                open_issues=open_issues,
                watchers=_int_or_none(values.get("watchers")),
                language=language,
                topics=topics,
                license_spdx_id=license_spdx_id,
                default_branch=_string_or_none(values.get("default_branch")),
                latest_release_tag=latest_release_tag,
                latest_release_published_at=_string_or_none(
                    values.get("latest_release_published_at")
                ),
                archived=archived,
                fork=_bool_or_none(values.get("fork")),
                updated_at=_string_or_none(values.get("updated_at")),
                pushed_at=_string_or_none(values.get("pushed_at")),
                readme_detected=readme_detected,
                readme_html_url=_string_or_none(values.get("readme_html_url")),
                readme_size=_int_or_none(values.get("readme_size")),
                issue_activity_open_count=issue_activity_open_count,
                issue_activity_status=_string_or_none(values.get("issue_activity_status")),
                commit_freshness_days=commit_freshness_days,
                commit_freshness_status=_string_or_none(values.get("commit_freshness_status")),
                maintenance_risk=_github_tool_maintenance_risk(risk_signals),
                risk_signals=risk_signals,
                install_sources=_github_tool_install_sources(
                    html_url=html_url,
                    latest_release_tag=latest_release_tag,
                    readme_present=readme_detected,
                ),
                recommended_use_cases=_github_tool_recommended_use_cases(
                    language=language,
                    topics=topics,
                    stars=stars,
                ),
                unsuitable_boundaries=_github_tool_unsuitable_boundaries(
                    risk_signals=risk_signals,
                    license_spdx_id=license_spdx_id,
                ),
            )
        )
    return repositories


def _github_tool_repository_risk_signals(
    *,
    archived: bool | None,
    license_spdx_id: str | None,
    latest_release_tag: str | None,
    readme_present: bool | None,
    commit_freshness_days: int | None,
    commit_freshness_status: str | None,
    open_issues: int | None,
    stars: int,
) -> list[str]:
    signals: list[str] = []
    if archived is True:
        signals.append("repository_archived")
    if license_spdx_id is None:
        signals.append("license_missing")
    if latest_release_tag is None:
        signals.append("release_missing")
    if readme_present is False:
        signals.append("readme_missing")
    if commit_freshness_days is not None and commit_freshness_days > GITHUB_TOOL_RELEASE_STALE_DAYS:
        signals.append("commit_stale_over_180_days")
    elif commit_freshness_days is not None and commit_freshness_days > 90:
        signals.append("commit_stale_over_90_days")
    elif commit_freshness_days is None:
        if commit_freshness_status == "stale":
            signals.append("commit_stale_over_180_days")
        elif commit_freshness_status == "aging":
            signals.append("commit_stale_over_90_days")
        elif commit_freshness_status != "fresh":
            signals.append("commit_freshness_unknown")
    if open_issues is not None and stars > 0 and open_issues / stars > 0.05:
        signals.append("high_open_issue_ratio")
    return signals


def _github_tool_maintenance_risk(
    risk_signals: list[str],
) -> Literal["low", "medium", "high", "unknown"]:
    if "repository_archived" in risk_signals or "commit_stale_over_180_days" in risk_signals:
        return "high"
    medium_signals = {
        "license_missing",
        "release_missing",
        "readme_missing",
        "commit_stale_over_90_days",
        "high_open_issue_ratio",
    }
    if any(signal in medium_signals for signal in risk_signals):
        return "medium"
    if "commit_freshness_unknown" in risk_signals:
        return "unknown"
    return "low"


def _github_tool_install_sources(
    *,
    html_url: str | None,
    latest_release_tag: str | None,
    readme_present: bool | None,
) -> list[str]:
    sources: list[str] = []
    if html_url is not None:
        sources.append("repository_url")
    if latest_release_tag is not None:
        sources.append("latest_release")
    if readme_present is True:
        sources.append("readme_metadata")
    return sources


def _github_tool_recommended_use_cases(
    *,
    language: str | None,
    topics: list[str],
    stars: int,
) -> list[str]:
    use_cases: list[str] = []
    normalized_topics = {topic.lower() for topic in topics}
    if "browser-automation" in normalized_topics or "crawler" in normalized_topics:
        use_cases.append("collection_tool_benchmark")
    if "ai-agent" in normalized_topics:
        use_cases.append("agent_browser_workflow_reference")
    if language == "Python":
        use_cases.append("python_collector_stack_reference")
    if stars >= 10000:
        use_cases.append("high_adoption_training_candidate")
    return use_cases or ["manual_review_required"]


def _github_tool_unsuitable_boundaries(
    *,
    risk_signals: list[str],
    license_spdx_id: str | None,
) -> list[str]:
    boundaries = [
        "not_a_license_clearance",
        "not_a_security_audit",
        "not_a_provider_call_or_live_install",
    ]
    if license_spdx_id is None:
        boundaries.append("do_not_redistribute_until_license_reviewed")
    if "repository_archived" in risk_signals:
        boundaries.append("do_not_use_as_new_dependency_without_owner_review")
    if "release_missing" in risk_signals:
        boundaries.append("do_not_assume_stable_release_channel")
    return boundaries


def _github_tool_report_risk_sections(
    repositories: list[AutomationGitHubToolReportRepositoryResponse],
) -> list[dict[str, Any]]:
    risk_counts: dict[str, int] = {"low": 0, "medium": 0, "high": 0, "unknown": 0}
    all_use_cases: set[str] = set()
    all_boundaries: set[str] = set()
    all_install_sources: set[str] = set()
    for repository in repositories:
        risk_counts[repository.maintenance_risk] += 1
        all_use_cases.update(repository.recommended_use_cases)
        all_boundaries.update(repository.unsuitable_boundaries)
        all_install_sources.update(repository.install_sources)
    return [
        {
            "title": "维护风险",
            "items": [f"{risk}={count}" for risk, count in risk_counts.items()],
            "evidence_fields": [
                "archived",
                "license_spdx_id",
                "latest_release_tag",
                "readme_detected",
                "commit_freshness_days",
                "open_issues",
                "stars",
            ],
        },
        {
            "title": "适用采集场景",
            "items": sorted(all_use_cases) or ["manual_review_required"],
        },
        {
            "title": "不适用边界",
            "items": sorted(all_boundaries),
        },
        {
            "title": "安装与溯源入口",
            "items": sorted(all_install_sources) or ["repository_url_missing"],
        },
    ]


def _count_repository_languages(
    repositories: list[AutomationGitHubToolReportRepositoryResponse],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for repository in repositories:
        if repository.language is None:
            continue
        counts[repository.language] = counts.get(repository.language, 0) + 1
    return dict(sorted(counts.items()))


def _count_repository_topics(
    repositories: list[AutomationGitHubToolReportRepositoryResponse],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for repository in repositories:
        for topic in repository.topics:
            counts[topic] = counts.get(topic, 0) + 1
    return dict(sorted(counts.items()))


def _github_tool_report_recommendations(
    top_repositories: list[AutomationGitHubToolReportRepositoryResponse],
    min_stars: int,
) -> list[str]:
    if not top_repositories:
        return ["当前工具数据集没有可生成培训建议的仓库行。"]
    recommendations: list[str] = []
    for repository in top_repositories[:3]:
        threshold_note = (
            f"达到 {min_stars} stars 门槛"
            if repository.stars >= min_stars
            else f"未达到 {min_stars} stars 门槛"
        )
        topics = "、".join(repository.topics[:3]) if repository.topics else "未标注 topic"
        release_note = (
            f"最新 release {repository.latest_release_tag}"
            if repository.latest_release_tag
            else "未发现 latest release"
        )
        license_note = repository.license_spdx_id or "license 未声明"
        readme_note = "README 已识别" if repository.readme_detected is True else "README 未确认"
        issue_note = (
            f"open issues {repository.issue_activity_open_count}"
            if repository.issue_activity_open_count is not None
            else "issue 活跃度未知"
        )
        commit_note = repository.commit_freshness_status or "commit 新鲜度未知"
        risk_note = f"维护风险={repository.maintenance_risk}"
        recommendations.append(
            f"{repository.repo_full_name} 具备 {repository.stars} stars，{threshold_note}；"
            f"{license_note}，{release_note}；"
            f"{readme_note}，{issue_note}，commit {commit_note}；"
            f"{risk_note}；"
            f"可优先用于 {topics} 方向的数据采集工具培训与 SOP 编写。"
        )
    return recommendations


def _render_github_tool_report_asset_content(
    report: AutomationGitHubToolReportResponse,
) -> str:
    top_repository_lines = [
        (
            "| 仓库 | Stars | 语言 | License | Release | README | Issues | "
            "Commit freshness | Risk | Topics | 链接 |"
        ),
        "| --- | ---: | --- | --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for repository in report.top_repositories:
        topics = "、".join(repository.topics[:5]) if repository.topics else "未标注"
        html_url = repository.html_url or ""
        open_issues = (
            repository.issue_activity_open_count
            if repository.issue_activity_open_count is not None
            else repository.open_issues
        )
        open_issues_text = open_issues if open_issues is not None else "-"
        release_tag = repository.latest_release_tag or "-"
        readme = "yes" if repository.readme_detected is True else "unknown"
        commit_freshness = repository.commit_freshness_status or "-"
        top_repository_lines.append(
            "| "
            f"{repository.repo_full_name} | "
            f"{repository.stars} | "
            f"{repository.language or '-'} | "
            f"{repository.license_spdx_id or '-'} | "
            f"{release_tag} | "
            f"{readme} | "
            f"{open_issues_text} | "
            f"{commit_freshness} | "
            f"{repository.maintenance_risk} | "
            f"{topics} | "
            f"{html_url} |"
        )

    recommendation_lines = [
        f"{index}. {recommendation}"
        for index, recommendation in enumerate(report.recommendations, start=1)
    ]
    languages = _format_github_tool_report_counts(report.summary.languages)
    topics = _format_github_tool_report_counts(report.summary.top_topics)
    fields = "、".join(report.version.selected_fields)
    schema = report.version.export_preview.get("schema", {})
    schema_version = schema.get("schema_version") if isinstance(schema, dict) else None
    risk_section_lines = _render_github_tool_risk_section_lines(report.risk_sections)

    sections = [
        f"# GitHub 工具雷达报告 - {report.dataset.name}",
        "",
        "## 报告口径",
        f"- dataset_type: {report.dataset.dataset_type}",
        f"- dataset_id: {report.dataset.id}",
        f"- dataset_version_id: {report.version.id}",
        f"- version_number: {report.version.version_number}",
        f"- schema_version: {schema_version or 'unknown'}",
        f"- selected_fields: {fields}",
        f"- row_count: {report.version.row_count}",
        f"- average_completeness_percent: {report.version.average_completeness_percent}",
        "",
        "## 工具池概览",
        f"- repository_count: {report.summary.repository_count}",
        f"- total_stars: {report.summary.total_stars}",
        f"- high_value_repositories: {report.summary.high_value_repositories}",
        f"- licensed_repositories: {report.summary.licensed_repositories}",
        f"- release_tagged_repositories: {report.summary.release_tagged_repositories}",
        f"- readme_documented_repositories: {report.summary.readme_documented_repositories}",
        f"- issue_active_repositories: {report.summary.issue_active_repositories}",
        f"- fresh_commit_repositories: {report.summary.fresh_commit_repositories}",
        f"- archived_repositories: {report.summary.archived_repositories}",
        f"- fork_repositories: {report.summary.fork_repositories}",
        f"- languages: {languages}",
        f"- top_topics: {topics}",
        "",
        "## Top 仓库",
        *top_repository_lines,
        "",
        "## 维护风险与使用边界",
        *risk_section_lines,
        "",
        "## 培训应用建议",
        *recommendation_lines,
        "",
        "## 证据边界",
        "- 本报告来自已保存的 github_tool_radar DatasetVersion。",
        "- 保存报告不会启动采集、创建通知或发送邮件。",
        "- 若用于培训材料，需要结合最新 drift check 复核字段完整度和新鲜度。",
    ]
    return "\n".join(sections).strip()


def _render_github_tool_risk_section_lines(
    risk_sections: list[dict[str, Any]],
) -> list[str]:
    lines: list[str] = []
    for section in risk_sections:
        title = _string_or_none(section.get("title")) or "未命名风险项"
        lines.append(f"### {title}")
        items = section.get("items")
        if isinstance(items, list) and items:
            lines.extend(f"- {item}" for item in items)
        else:
            lines.append("- 无")
    return lines


def _format_github_tool_report_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "无"
    return "、".join(f"{key}={value}" for key, value in counts.items())


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(float(text))
        except ValueError:
            return None
    return None


def _bool_or_none(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return None


def _int_or_zero(value: object) -> int:
    return _int_or_none(value) or 0


async def _dataset_product_raw_records(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    task_run_ids: list[uuid.UUID],
    max_rows: int,
) -> list[RawRecord]:
    records: list[RawRecord] = []
    for task_run_id in task_run_ids:
        product_records, _reused_deduplicated_records = await _product_records_for_task_run(
            session=session,
            workspace_id=workspace_id,
            task_run_id=task_run_id,
            limit=max_rows,
        )
        records.extend(product_records)
        if len(records) >= max_rows:
            return records[:max_rows]
    return records


async def _dataset_github_tool_raw_records(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    task_run_ids: list[uuid.UUID],
    max_rows: int,
) -> list[RawRecord]:
    records: list[RawRecord] = []
    for task_run_id in task_run_ids:
        github_records = await _github_tool_raw_records_for_task_run(
            session=session,
            workspace_id=workspace_id,
            task_run_id=task_run_id,
            limit=max_rows,
        )
        records.extend(github_records)
        if len(records) >= max_rows:
            return records[:max_rows]
    return records


async def _single_project_id_for_task_runs(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    task_run_ids: list[uuid.UUID],
    max_rows: int,
) -> uuid.UUID:
    raw_records = await _dataset_product_raw_records(
        session,
        workspace_id,
        task_run_ids,
        max_rows,
    )
    if not raw_records:
        raise CollectorError("cleaning_plan_preview_empty")
    project_ids = {raw_record.project_id for raw_record in raw_records}
    if len(project_ids) != 1:
        raise CollectorError("cleaning_plan_project_lineage_ambiguous")
    return next(iter(project_ids))


async def _github_tool_raw_records_for_task_run(
    *,
    session: AsyncSession,
    workspace_id: uuid.UUID,
    task_run_id: uuid.UUID,
    limit: int,
) -> list[RawRecord]:
    raw_records = await list_raw_records(
        session=session,
        workspace_id=workspace_id,
        task_run_id=task_run_id,
        limit=limit,
    )
    return [
        raw_record
        for raw_record in raw_records
        if raw_record.record_type in {"github_topic", "github_repo"}
    ]


async def _product_records_for_task_run(
    *,
    session: AsyncSession,
    workspace_id: uuid.UUID,
    task_run_id: uuid.UUID,
    limit: int,
) -> tuple[list[RawRecord], bool]:
    raw_records = await list_raw_records(
        session=session,
        workspace_id=workspace_id,
        task_run_id=task_run_id,
        limit=limit,
    )
    product_records = _product_page_records(raw_records)
    if product_records:
        return product_records, False

    task_run = await session.get(TaskRun, task_run_id)
    if (
        task_run is None
        or task_run.workspace_id != workspace_id
        or task_run.status not in {"success", "partial_success"}
    ):
        return [], False
    task = await session.get(CollectionTask, task_run.task_id)
    if task is None or task.workspace_id != workspace_id:
        return [], False
    source_records = await list_raw_records(
        session=session,
        workspace_id=workspace_id,
        source_id=task.source_id,
        limit=limit,
    )
    fallback_records = _product_page_records(source_records)
    return fallback_records, bool(fallback_records)


def _product_page_records(raw_records: list[RawRecord]) -> list[RawRecord]:
    return [
        raw_record
        for raw_record in raw_records
        if raw_record.record_type == "ecommerce_product_page"
    ]


async def _lock_workspace_for_dataset_save(session: AsyncSession, workspace_id: uuid.UUID) -> None:
    await session.execute(
        select(Workspace.id).where(Workspace.id == workspace_id).with_for_update()
    )


def _discovery_blocked_reasons(product_candidates: object) -> list[str]:
    if not isinstance(product_candidates, list) or not product_candidates:
        return ["未识别到可进入商品详情页采集的商品 URL。"]
    return []


def _fanout_fields(fields: list[str] | None) -> list[str]:
    requested = fields or list(ECOMMERCE_PRODUCT_FIELDS)
    allowed = set(ECOMMERCE_PRODUCT_FIELDS)
    normalized = [field for field in requested if field in allowed]
    return normalized or list(ECOMMERCE_PRODUCT_FIELDS)


def _candidate_block_reason(
    candidate_url: str | None,
    parent_origin: str,
    seen_urls: set[str],
    ready_count: int,
    max_sources: int,
) -> str | None:
    if candidate_url is None:
        return "candidate_url_invalid"
    if _origin(candidate_url) != parent_origin:
        return "candidate_url_cross_origin"
    if candidate_url in seen_urls:
        return "duplicate_candidate_url"
    if ready_count >= max_sources:
        return "candidate_exceeds_preview_limit"
    return None


def _normalize_candidate_url(value: str) -> str | None:
    cleaned, _fragment = urldefrag(value.strip())
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return cleaned


def _origin(value: str) -> str | None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        return None
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}"


def _fanout_source_name(title: str | None, url: str) -> str:
    display = title.strip() if isinstance(title, str) and title.strip() else urlparse(url).path
    return f"商品页采集：{display[:80]}"


def _fanout_blocked_reasons(
    source_drafts: list[AutomationSourceDraftResponse],
    blocked_count: int,
) -> list[str]:
    blocked: list[str] = []
    if not source_drafts:
        blocked.append("没有可预览的商品页采集源。")
    if blocked_count:
        blocked.append("部分候选 URL 被阻断，请复核后再创建批量任务。")
    blocked.append("当前结果仅为预览，尚未创建真实采集源、任务或采集运行。")
    return blocked


def _draft_url(draft: AutomationSourceDraftResponse) -> str | None:
    value = draft.config.get("url")
    return value if isinstance(value, str) and value.strip() else None
