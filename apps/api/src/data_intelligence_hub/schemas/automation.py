from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

from data_intelligence_hub.schemas.alert import AlertEventResponse, AlertRuleResponse
from data_intelligence_hub.schemas.notification import NotificationResponse
from data_intelligence_hub.schemas.report import ReportResponse
from data_intelligence_hub.schemas.signal import SignalResponse
from data_intelligence_hub.schemas.source import SourceResponse
from data_intelligence_hub.schemas.task import CollectionTaskResponse, TaskRunResponse


class AutomationSiteAnalysisRequest(BaseModel):
    project_id: uuid.UUID | None = None
    url: str = Field(min_length=1, max_length=5000)
    authorized: bool
    target: Literal["ecommerce_product"] = "ecommerce_product"
    fields: list[str] | None = None


class AutomationProductDiscoveryRequest(BaseModel):
    url: str = Field(min_length=1, max_length=5000)
    authorized: bool
    max_products: int = Field(default=50, ge=1, le=200)


class AutomationFanoutCandidateInput(BaseModel):
    url: str = Field(min_length=1, max_length=5000)
    title: str | None = None
    source: str | None = None
    confidence: float | None = None


class AutomationProductFanoutPreviewRequest(BaseModel):
    parent_url: str = Field(min_length=1, max_length=5000)
    authorized: bool
    candidates: list[AutomationFanoutCandidateInput] = Field(min_length=1, max_length=50)
    fields: list[str] | None = None
    max_sources: int = Field(default=20, ge=1, le=50)


class AutomationProductFanoutCreateRequest(BaseModel):
    project_id: uuid.UUID
    parent_url: str = Field(min_length=1, max_length=5000)
    authorized: bool
    candidates: list[AutomationFanoutCandidateInput] = Field(min_length=1, max_length=50)
    fields: list[str] | None = None
    max_sources: int = Field(default=20, ge=1, le=50)
    enable_tasks: bool = True


class AutomationProductBatchRunRequest(BaseModel):
    authorized: bool
    task_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)
    max_tasks: int = Field(default=5, ge=1, le=20)


class AutomationProductDatasetPreviewRequest(BaseModel):
    authorized: bool
    task_run_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    fields: list[str] | None = None
    max_rows: int = Field(default=100, ge=1, le=500)


class AutomationProductDatasetSaveRequest(AutomationProductDatasetPreviewRequest):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    cleaning_plan_id: uuid.UUID | None = None


class AutomationGitHubToolDatasetPreviewRequest(AutomationProductDatasetPreviewRequest):
    pass


class AutomationGitHubToolDatasetSaveRequest(AutomationGitHubToolDatasetPreviewRequest):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)


class AutomationCleaningRuleInput(BaseModel):
    field: str = Field(min_length=1, max_length=80)
    operation: Literal[
        "strip_text",
        "parse_decimal",
        "parse_integer",
        "normalize_url",
        "normalize_tags",
        "uppercase",
        "normalize_availability",
        "fill_default",
    ]
    value: str | int | float | bool | None = None
    description: str | None = Field(default=None, max_length=500)


class AutomationCleaningPlanDryRunRequest(BaseModel):
    authorized: bool
    task_run_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    fields: list[str] | None = None
    rules: list[AutomationCleaningRuleInput] = Field(min_length=1, max_length=50)
    max_rows: int = Field(default=100, ge=1, le=500)


class AutomationCleaningPlanCreateRequest(AutomationCleaningPlanDryRunRequest):
    name: str = Field(min_length=1, max_length=200)


class AutomationProductDatasetExportCreateRequest(BaseModel):
    authorized: bool
    confirm_create: bool
    dataset_id: uuid.UUID
    dataset_version_id: uuid.UUID
    export_format: Literal["csv", "json", "jsonl"] = "csv"


class AutomationProductScheduleApproveRequest(BaseModel):
    authorized: bool
    dataset_id: uuid.UUID
    dataset_version_id: uuid.UUID
    task_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)
    schedule_policy: Literal["auto_freshness", "manual_refresh_only"] = "auto_freshness"
    schedule_cron: str | None = Field(default=None, max_length=50)
    freshness_target_hours: int = Field(default=24, ge=1, le=720)
    minimum_completeness_percent: int = Field(default=80, ge=0, le=100)
    note: str | None = Field(default=None, max_length=500)


class AutomationProductDriftCheckRequest(BaseModel):
    authorized: bool
    dataset_id: uuid.UUID
    dataset_version_id: uuid.UUID
    task_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)
    completeness_drop_threshold_percent: int = Field(default=10, ge=0, le=100)
    freshness_grace_hours: int = Field(default=0, ge=0, le=168)


class AutomationProductDriftEventSaveRequest(AutomationProductDriftCheckRequest):
    note: str | None = Field(default=None, max_length=500)


class AutomationGitHubToolDriftCheckRequest(AutomationProductDriftCheckRequest):
    pass


class AutomationGitHubToolDriftEventSaveRequest(AutomationGitHubToolDriftCheckRequest):
    note: str | None = Field(default=None, max_length=500)


class AutomationGitHubToolReportRequest(BaseModel):
    authorized: bool
    dataset_id: uuid.UUID
    dataset_version_id: uuid.UUID
    min_stars: int = Field(default=1000, ge=0)
    top_limit: int = Field(default=10, ge=1, le=50)


class AutomationGitHubToolReportAssetCreateRequest(AutomationGitHubToolReportRequest):
    confirm_create: bool


class AutomationProductDriftAlertPreviewRequest(BaseModel):
    authorized: bool
    dataset_id: uuid.UUID
    dataset_version_id: uuid.UUID | None = None
    min_status: Literal["warning", "critical"] = "critical"
    channel: Literal["in_app", "email", "both"] = "in_app"
    enabled: bool = True
    name: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=20, ge=1, le=100)


class AutomationProductDriftAlertRuleCreateRequest(AutomationProductDriftAlertPreviewRequest):
    confirm_create: bool


class AutomationProductDriftAlertEventCreateRequest(BaseModel):
    authorized: bool
    confirm_create: bool
    dataset_id: uuid.UUID
    dataset_version_id: uuid.UUID
    drift_event_id: uuid.UUID


class AutomationProductDriftAlertNotificationSendRequest(BaseModel):
    authorized: bool
    confirm_send: bool
    dataset_id: uuid.UUID
    dataset_version_id: uuid.UUID
    drift_event_id: uuid.UUID
    alert_event_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)


class AutomationProductDriftAlertEmailSendRequest(BaseModel):
    authorized: bool
    confirm_send: bool
    dataset_id: uuid.UUID
    dataset_version_id: uuid.UUID
    drift_event_id: uuid.UUID
    alert_event_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)
    recipient_email: EmailStr | None = None


class AutomationPlatformProfileResponse(BaseModel):
    platform_type: str
    confidence: float
    indicators: list[str]
    risk_level: str


class AutomationPageStructureResponse(BaseModel):
    page_type: str
    title: str | None
    canonical_url: str | None
    script_count: int
    form_count: int
    image_count: int
    product_schema_count: int
    same_origin_link_count: int
    text_sample: str


class AutomationFieldCandidateResponse(BaseModel):
    key: str
    label: str
    value: str | int | float | bool | None
    data_type: str
    source: str
    confidence: float
    selected: bool
    cleaning_rule: str


class AutomationToolRecommendationResponse(BaseModel):
    tool: str
    collector_type: str
    fit: str
    risk_level: str
    reason: str


class AutomationCleaningStepResponse(BaseModel):
    field: str
    operation: str
    description: str


class AutomationSourceDraftResponse(BaseModel):
    type: str
    config: dict[str, Any]
    suggested_name: str
    schedule_cron: str | None


class AutomationPlatformPackageFieldResponse(BaseModel):
    key: str
    label: str
    data_type: str
    required: bool
    source: str
    cleaning_rule: str


class AutomationPlatformPackageSampleUrlResponse(BaseModel):
    label: str
    entrypoint: Literal[
        "product-discovery",
        "site-analysis",
        "sop-import",
        "source-create",
        "preflight",
    ]
    url: str
    description: str


class AutomationPlatformPackageCleaningRuleResponse(BaseModel):
    field: str
    operation: Literal[
        "strip_text",
        "parse_decimal",
        "normalize_url",
        "uppercase",
        "normalize_availability",
        "fill_default",
    ]
    value: str | int | float | bool | None = None
    description: str


class AutomationPlatformPackageStrategyResponse(BaseModel):
    id: str
    label: str
    entrypoint: str
    collector_type: str
    fit: Literal["high", "medium", "low"]
    can_start_from_automation: bool
    review_required: bool
    description: str


class AutomationPlatformPackageRiskBoundaryResponse(BaseModel):
    condition: str
    severity: Literal["info", "warning", "blocked"]
    guidance: str


class AutomationPlatformPackageSopLinkResponse(BaseModel):
    label: str
    href: str


class AutomationPlatformPackageFixtureResponse(BaseModel):
    fixture_type: str
    available: bool
    description: str


class AutomationPlatformPackageResponse(BaseModel):
    id: str
    name: str
    category: str
    summary: str
    supported_targets: list[str]
    collector_types: list[str]
    field_schema: list[AutomationPlatformPackageFieldResponse]
    default_entrypoint: Literal[
        "product-discovery",
        "site-analysis",
        "sop-import",
        "source-create",
        "preflight",
    ]
    sample_urls: list[AutomationPlatformPackageSampleUrlResponse]
    cleaning_rules: list[AutomationPlatformPackageCleaningRuleResponse]
    operator_checklist: list[str]
    strategy_matrix: list[AutomationPlatformPackageStrategyResponse]
    risk_boundaries: list[AutomationPlatformPackageRiskBoundaryResponse]
    sop_links: list[AutomationPlatformPackageSopLinkResponse]
    sample_fixture: AutomationPlatformPackageFixtureResponse
    execution_boundary: Literal["executable", "sop_import_only", "blocked"]
    run_started: bool


class AutomationPlatformPackageListResponse(BaseModel):
    items: list[AutomationPlatformPackageResponse]
    total: int
    run_started: bool


class AutomationCapabilityProbeBackendCandidateResponse(BaseModel):
    backend_id: str
    label: str
    priority: int
    status: Literal[
        "available",
        "missing_tool",
        "not_configured",
        "requires_login",
        "requires_proxy",
        "manual_review",
        "blocked",
        "unknown",
    ]
    credential_mode: Literal[
        "none",
        "token",
        "cookie",
        "browser_profile",
        "manual_export",
        "unknown",
    ]
    requires_login: bool
    requires_proxy: bool
    evidence_level: Literal[
        "L0-unverified",
        "L1-repo-or-runtime",
        "L2-fixture-or-dry-run",
        "L3-production-read-only",
        "L4-authorized-live",
    ]
    notes: list[str]


class AutomationAgentReachChannelProbeResponse(BaseModel):
    schema_version: Literal["agent_reach_channel_probe.v1"] = (
        "agent_reach_channel_probe.v1"
    )
    installed: bool
    command_path: str | None
    doctor_status: Literal[
        "available",
        "missing_tool",
        "not_configured",
        "requires_login",
        "requires_proxy",
        "blocked",
        "unknown",
    ]
    active_backend: str | None
    requires_login: bool
    requires_proxy: bool
    blocked_reason: str | None
    platforms: list[str]
    read_invoked: bool
    search_invoked: bool
    raw_summary: dict[str, Any]


class AutomationCapabilityProbeResponse(BaseModel):
    schema_version: Literal["capability_probe.v1"] = "capability_probe.v1"
    platform_id: str
    platform_label: str
    generated_at: str
    doctor_status: Literal[
        "available",
        "missing_tool",
        "not_configured",
        "requires_login",
        "requires_proxy",
        "manual_review",
        "blocked",
        "unknown",
    ]
    credential_mode: Literal[
        "none",
        "token",
        "cookie",
        "browser_profile",
        "manual_export",
        "unknown",
    ]
    execution_boundary: Literal[
        "executable",
        "read_only_probe",
        "import_only",
        "sop_only",
        "blocked",
    ]
    risk_level: Literal["low", "medium", "high"]
    backend_candidates: list[AutomationCapabilityProbeBackendCandidateResponse]
    agent_reach: AutomationAgentReachChannelProbeResponse | None = None
    allowed_outputs: list[str]
    forbidden_actions: list[str]
    next_actions: list[str]
    run_started: bool
    collection_resources_written: bool


class AutomationCapabilityProbeListResponse(BaseModel):
    schema_version: Literal["capability_probe_list.v1"] = "capability_probe_list.v1"
    generated_at: str
    items: list[AutomationCapabilityProbeResponse]
    total: int
    run_started: bool
    collection_resources_written: bool


class AutomationExtractionPlanCreateRequest(BaseModel):
    authorized: bool
    name: str | None = Field(default=None, max_length=200)
    fields: list[str] | None = None
    schedule_cron: str | None = Field(default=None, max_length=50)


class AutomationBrowserFieldContractFieldRequest(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=200)
    required: bool = False
    selected: bool = True
    selector_hint: str | None = Field(default=None, max_length=1000)


class AutomationBrowserCleaningRuleRequest(BaseModel):
    field: str = Field(min_length=1, max_length=120)
    operation: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)


class AutomationBrowserFieldContractRequest(BaseModel):
    fields: list[AutomationBrowserFieldContractFieldRequest] = Field(
        min_length=1,
        max_length=50,
    )
    cleaning_rules: list[AutomationBrowserCleaningRuleRequest] = Field(
        default_factory=list,
        max_length=50,
    )


class AutomationBrowserDiagnosticEvidenceRequest(BaseModel):
    schema_version: Literal["browser_structure_diagnostic.v1"] = (
        "browser_structure_diagnostic.v1"
    )
    final_url: str = Field(min_length=1, max_length=5000)
    recommended_path: str = Field(min_length=1, max_length=80)
    confidence: float = Field(default=0, ge=0, le=100)
    field_stability: Literal["high", "medium", "low"] | None = None
    evidence_source: str = Field(default="browser-harness", max_length=120)
    screenshot_path: str | None = Field(default=None, max_length=1000)


class AutomationBrowserAutomationPlanRequest(BaseModel):
    project_id: uuid.UUID
    requested_url: str = Field(min_length=1, max_length=5000)
    authorized: bool
    name: str | None = Field(default=None, max_length=200)
    runner: Literal["browser_harness"] = "browser_harness"
    execution_mode: Literal["read_only_browser_harness"] = "read_only_browser_harness"
    risk_level: Literal["low", "medium", "high"] = "medium"
    field_contract: AutomationBrowserFieldContractRequest
    browser_diagnostic: AutomationBrowserDiagnosticEvidenceRequest
    diagnostic_payload: dict[str, Any] = Field(default_factory=dict)
    api_candidates: list[str] = Field(default_factory=list, max_length=20)
    guardrails: list[str] = Field(default_factory=list, max_length=20)


class AutomationBrowserDiagnosticRunResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    site_analysis_id: uuid.UUID | None
    requested_url: str
    final_url: str
    status: str
    authorization_confirmed: bool
    schema_version: str
    recommended_path: str
    confidence: float
    field_stability: str | None
    evidence_source: str
    screenshot_path: str | None
    run_policy: dict[str, Any]
    page_summary: dict[str, Any]
    network_summary: dict[str, Any]
    accessibility_summary: dict[str, Any]
    risk_flags: list[dict[str, Any]]
    extraction_strategy: dict[str, Any]
    blocked_reasons: list[str]
    created_at: datetime
    run_started: bool = False


class AutomationBrowserDiagnosticRunListResponse(BaseModel):
    items: list[AutomationBrowserDiagnosticRunResponse]
    total: int
    run_started: bool = False


class AutomationBrowserExecutableSpecDryRunRequest(BaseModel):
    authorized: bool
    confirm_review: bool
    site_analysis_id: uuid.UUID
    extraction_plan_id: uuid.UUID
    browser_diagnostic_run_id: uuid.UUID | None = None


class AutomationBrowserDiagnosticJobCreateRequest(BaseModel):
    authorized: bool
    confirm_create: bool
    site_analysis_id: uuid.UUID
    extraction_plan_id: uuid.UUID
    browser_diagnostic_run_id: uuid.UUID | None = None
    network_observation_mode: Literal[
        "metadata_only",
        "same_origin_api_candidates",
    ] = "metadata_only"
    artifact_mode: Literal[
        "none",
        "screenshot_reference_only",
        "diagnostic_json_reference",
    ] = "screenshot_reference_only"
    note: str | None = Field(default=None, max_length=500)


class AutomationBrowserExecutableSpecCheckResponse(BaseModel):
    key: str
    label: str
    status: Literal["passed", "review", "blocked"]
    message: str
    evidence: dict[str, Any]


class AutomationBrowserExecutableSpecDryRunSummaryResponse(BaseModel):
    status: Literal["ready", "review", "blocked"]
    total_checks: int
    passed_checks: int
    review_checks: int
    blocked_checks: int
    selector_count: int
    wait_condition_count: int
    api_candidate_count: int
    manual_review_required: bool
    can_dry_run_after_review: bool
    write_allowed: bool = False
    run_started: bool = False


class AutomationExtractionPlanResponse(BaseModel):
    id: uuid.UUID
    site_analysis_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    version_number: int
    collector_type: str
    selected_fields: list[str]
    source_draft: AutomationSourceDraftResponse
    schedule_cron: str | None
    status: str
    risk_level: str
    audit_events: list[dict[str, Any]]
    created_at: datetime
    run_started: bool = False


class AutomationSiteAnalysisHistoryItemResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    requested_url: str
    target: str
    status: str
    platform_type: str
    page_type: str
    risk_level: str
    analyzed_at: datetime
    created_at: datetime
    latest_plan: AutomationExtractionPlanResponse | None = None


class AutomationSiteAnalysisListResponse(BaseModel):
    items: list[AutomationSiteAnalysisHistoryItemResponse]
    total: int
    run_started: bool = False


class AutomationBrowserAutomationPlanResponse(BaseModel):
    site_analysis: AutomationSiteAnalysisHistoryItemResponse
    extraction_plan: AutomationExtractionPlanResponse
    browser_diagnostic: AutomationBrowserDiagnosticRunResponse
    site_analysis_created: bool
    extraction_plan_created: bool
    browser_diagnostic_created: bool
    run_started: bool = False


class AutomationBrowserExecutableSpecDryRunResponse(BaseModel):
    site_analysis: AutomationSiteAnalysisHistoryItemResponse
    extraction_plan: AutomationExtractionPlanResponse
    browser_diagnostic: AutomationBrowserDiagnosticRunResponse | None
    summary: AutomationBrowserExecutableSpecDryRunSummaryResponse
    checks: list[AutomationBrowserExecutableSpecCheckResponse]
    executable_spec: dict[str, Any]
    blocked_reasons: list[str]
    audit_events: list[dict[str, Any]]
    run_started: bool = False


class AutomationBrowserDiagnosticJobResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    site_analysis_id: uuid.UUID
    extraction_plan_id: uuid.UUID
    browser_diagnostic_run_id: uuid.UUID
    requested_url: str
    final_url: str
    status: str
    authorization_confirmed: bool
    runner: str
    execution_mode: str
    selector_scope: list[dict[str, Any]]
    wait_policy: list[dict[str, Any]]
    network_observation_policy: dict[str, Any]
    artifact_policy: dict[str, Any]
    safety_flags: list[str]
    dry_run_summary: dict[str, Any]
    executable_spec_snapshot: dict[str, Any]
    blocked_reasons: list[str]
    audit_events: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    cancelled_at: datetime | None
    run_started: bool = False


class AutomationBrowserDiagnosticJobListResponse(BaseModel):
    items: list[AutomationBrowserDiagnosticJobResponse]
    total: int
    run_started: bool = False


class AutomationBrowserExecutorContractRequest(BaseModel):
    authorized: bool
    confirm_review: bool
    artifact_retention_days: int = Field(default=7, ge=1, le=30)
    max_preview_rows: int = Field(default=20, ge=1, le=100)
    include_screenshot: bool = True
    include_trace_summary: bool = False
    include_har_summary: bool = True
    note: str | None = Field(default=None, max_length=500)


class AutomationBrowserExecutorReadinessCheckResponse(BaseModel):
    key: str
    label: str
    status: Literal["passed", "review", "blocked"]
    message: str
    evidence: dict[str, Any]


class AutomationBrowserExecutorContractResponse(BaseModel):
    job: AutomationBrowserDiagnosticJobResponse
    adapter: dict[str, Any]
    runtime_isolation: dict[str, Any]
    artifact_retention_policy: dict[str, Any]
    allowed_actions: list[str]
    denied_actions: list[str]
    readiness_checks: list[AutomationBrowserExecutorReadinessCheckResponse]
    blocked_reasons: list[str]
    audit_events: list[dict[str, Any]]
    run_started: bool = False
    execution_started: bool = False


class AutomationBrowserLocalRunnerRequest(BaseModel):
    authorized: bool
    confirm_execute: bool
    run_mode: Literal[
        "diagnostic_snapshot_replay",
        "ephemeral_browser_harness_probe",
    ] = "diagnostic_snapshot_replay"
    confirm_real_browser_probe: bool = False
    browser_harness_binary: str | None = Field(default=None, max_length=500)
    probe_timeout_seconds: int = Field(default=15, ge=3, le=45)
    artifact_retention_days: int = Field(default=7, ge=1, le=30)
    max_preview_rows: int = Field(default=20, ge=1, le=100)
    include_screenshot: bool = True
    include_trace_summary: bool = False
    include_har_summary: bool = True
    note: str | None = Field(default=None, max_length=500)


class AutomationBrowserLocalRunnerResultResponse(BaseModel):
    id: uuid.UUID
    job: AutomationBrowserDiagnosticJobResponse
    status: str
    runner: str
    run_mode: str
    contract_snapshot: dict[str, Any]
    artifact_manifest: dict[str, Any]
    selector_results: list[dict[str, Any]]
    selector_evaluations: list[dict[str, Any]]
    preview_rows: list[dict[str, Any]]
    network_observation_summary: dict[str, Any]
    network_metadata_summary: dict[str, Any]
    error_summary: dict[str, Any]
    promotion_gate: dict[str, Any]
    redaction_summary: dict[str, Any]
    blocked_reasons: list[str]
    audit_events: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    started_at: datetime
    finished_at: datetime
    execution_started: bool
    browser_started: bool
    files_written: bool
    collection_resources_written: bool


class AutomationBrowserLocalRunnerResultListResponse(BaseModel):
    items: list[AutomationBrowserLocalRunnerResultResponse]
    total: int
    browser_started: bool = False
    files_written: bool = False
    collection_resources_written: bool = False


class AutomationSiteAnalysisDetailResponse(BaseModel):
    site_analysis: AutomationSiteAnalysisHistoryItemResponse
    platform_profile: AutomationPlatformProfileResponse
    page_structure: AutomationPageStructureResponse
    field_candidates: list[AutomationFieldCandidateResponse]
    tool_recommendations: list[AutomationToolRecommendationResponse]
    cleaning_plan: list[AutomationCleaningStepResponse]
    source_draft: AutomationSourceDraftResponse
    extraction_plans: list[AutomationExtractionPlanResponse]
    blocked_reasons: list[str]
    run_started: bool = False


class AutomationProductCandidateResponse(BaseModel):
    url: str
    title: str | None
    source: str
    confidence: float


class AutomationDiscoveryPageStructureResponse(BaseModel):
    page_type: str
    title: str | None
    canonical_url: str | None
    link_count: int
    product_link_count: int
    jsonld_url_count: int
    sitemap_url_count: int
    script_count: int
    text_sample: str


class AutomationDiscoveryPlanResponse(BaseModel):
    next_collector_type: str
    candidate_count: int
    max_products: int
    fan_out_requires_review: bool


class AutomationFanoutCandidateStatusResponse(BaseModel):
    url: str
    title: str | None
    source: str | None
    confidence: float | None
    status: Literal["ready", "blocked"]
    reason: str | None


class AutomationFanoutBatchPlanResponse(BaseModel):
    run_mode: Literal["preview_only"]
    next_collector_type: str
    ready_count: int
    blocked_count: int
    max_sources: int
    fields: list[str]
    manual_review_required: bool
    execution_boundary: str


class AutomationSiteAnalysisResponse(BaseModel):
    requested_url: str
    analyzed_at: datetime
    authorization_confirmed: bool
    platform_profile: AutomationPlatformProfileResponse
    page_structure: AutomationPageStructureResponse
    field_candidates: list[AutomationFieldCandidateResponse]
    tool_recommendations: list[AutomationToolRecommendationResponse]
    cleaning_plan: list[AutomationCleaningStepResponse]
    source_draft: AutomationSourceDraftResponse
    blocked_reasons: list[str]
    site_analysis: AutomationSiteAnalysisHistoryItemResponse | None = None
    extraction_plan: AutomationExtractionPlanResponse | None = None
    site_analysis_created: bool = False
    extraction_plan_created: bool = False
    run_started: bool = False


class AutomationProductDiscoveryResponse(BaseModel):
    requested_url: str
    analyzed_at: datetime
    authorization_confirmed: bool
    platform_profile: AutomationPlatformProfileResponse
    page_structure: AutomationDiscoveryPageStructureResponse
    product_candidates: list[AutomationProductCandidateResponse]
    tool_recommendations: list[AutomationToolRecommendationResponse]
    discovery_plan: AutomationDiscoveryPlanResponse
    source_draft: AutomationSourceDraftResponse
    blocked_reasons: list[str]


class AutomationProductFanoutPreviewResponse(BaseModel):
    requested_parent_url: str
    analyzed_at: datetime
    authorization_confirmed: bool
    candidate_statuses: list[AutomationFanoutCandidateStatusResponse]
    source_drafts: list[AutomationSourceDraftResponse]
    batch_plan: AutomationFanoutBatchPlanResponse
    blocked_reasons: list[str]


class AutomationFanoutPersistedSourceResponse(BaseModel):
    url: str
    action: Literal["created", "reused"]
    source: SourceResponse
    task: CollectionTaskResponse | None


class AutomationFanoutCreateSummaryResponse(BaseModel):
    created_sources: int
    reused_sources: int
    enabled_tasks: int
    blocked_candidates: int
    run_started: bool


class AutomationProductFanoutCreateResponse(BaseModel):
    requested_parent_url: str
    created_at: datetime
    authorization_confirmed: bool
    persisted_sources: list[AutomationFanoutPersistedSourceResponse]
    candidate_statuses: list[AutomationFanoutCandidateStatusResponse]
    summary: AutomationFanoutCreateSummaryResponse
    audit_events: list[dict[str, Any]]
    blocked_reasons: list[str]


class AutomationProductBatchFieldCompletenessResponse(BaseModel):
    configured_fields: list[str]
    extracted_fields: list[str]
    missing_fields: list[str]
    field_values: dict[str, Any]
    completeness_ratio: float
    completeness_percent: int


class AutomationProductBatchRunItemResponse(BaseModel):
    task_id: uuid.UUID
    task_name: str | None
    source_id: uuid.UUID | None
    source_url: str | None
    status: Literal["run_completed", "run_failed", "blocked"]
    blocked_reason: str | None
    run: TaskRunResponse | None
    records_count: int
    entities_count: int
    field_completeness: AutomationProductBatchFieldCompletenessResponse | None
    error_message: str | None


class AutomationProductBatchRunSummaryResponse(BaseModel):
    requested_tasks: int
    run_tasks: int
    blocked_tasks: int
    successful_runs: int
    failed_runs: int
    records_count: int
    entities_count: int
    average_completeness_percent: int
    run_started: bool


class AutomationProductBatchRunResponse(BaseModel):
    created_at: datetime
    authorization_confirmed: bool
    items: list[AutomationProductBatchRunItemResponse]
    summary: AutomationProductBatchRunSummaryResponse
    audit_events: list[dict[str, Any]]
    blocked_reasons: list[str]


class AutomationProductDatasetRowResponse(BaseModel):
    row_id: str
    task_run_id: uuid.UUID
    raw_record_id: uuid.UUID
    source_url: str | None
    values: dict[str, Any]
    missing_fields: list[str]
    completeness_percent: int


class AutomationProductDatasetSummaryResponse(BaseModel):
    requested_runs: int
    matched_runs: int
    rows_count: int
    selected_fields: list[str]
    average_completeness_percent: int
    export_format: Literal["json"]
    export_ready: bool


class AutomationProductDatasetPreviewResponse(BaseModel):
    created_at: datetime
    authorization_confirmed: bool
    rows: list[AutomationProductDatasetRowResponse]
    summary: AutomationProductDatasetSummaryResponse
    cleaning_script_draft: list[str]
    export_preview: dict[str, Any]
    audit_events: list[dict[str, Any]]
    blocked_reasons: list[str]


class AutomationCleaningPlanDryRunRowResponse(BaseModel):
    row_id: str
    task_run_id: uuid.UUID
    raw_record_id: uuid.UUID
    source_url: str | None
    before_values: dict[str, Any]
    after_values: dict[str, Any]
    missing_fields_before: list[str]
    missing_fields_after: list[str]
    changed_fields: list[str]


class AutomationCleaningPlanDryRunSummaryResponse(BaseModel):
    rows_count: int
    rows_changed: int
    rules_count: int
    selected_fields: list[str]
    dataset_version_created: bool
    cleaning_plan_created: bool
    run_started: bool


class AutomationCleaningPlanDryRunResponse(BaseModel):
    created_at: datetime
    authorization_confirmed: bool
    rows: list[AutomationCleaningPlanDryRunRowResponse]
    summary: AutomationCleaningPlanDryRunSummaryResponse
    cleaning_script: list[str]
    export_preview: dict[str, Any]
    audit_events: list[dict[str, Any]]
    blocked_reasons: list[str]


class AutomationCleaningPlanResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    version_number: int
    target: str
    selected_fields: list[str]
    source_task_run_ids: list[str]
    rules: list[dict[str, Any]]
    cleaning_script: list[str]
    dry_run_preview: dict[str, Any]
    status: str
    created_at: datetime


class AutomationCleaningPlanCreateResponse(BaseModel):
    saved_at: datetime
    authorization_confirmed: bool
    cleaning_plan: AutomationCleaningPlanResponse
    dry_run: AutomationCleaningPlanDryRunResponse
    cleaning_plan_created: bool
    dataset_version_created: bool
    run_started: bool
    audit_events: list[dict[str, Any]]
    blocked_reasons: list[str]


class AutomationCleaningPlanListResponse(BaseModel):
    items: list[AutomationCleaningPlanResponse]
    total: int
    dataset_version_created: bool
    run_started: bool


class AutomationDatasetResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    dataset_type: str
    status: str
    description: str | None


class AutomationDatasetVersionResponse(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    cleaning_plan_id: uuid.UUID | None = None
    version_number: int
    source_task_run_ids: list[str]
    selected_fields: list[str]
    cleaning_script: list[str]
    row_count: int
    average_completeness_percent: int
    status: str
    created_at: datetime
    export_preview: dict[str, Any]


class AutomationProductDatasetSaveResponse(BaseModel):
    saved_at: datetime
    authorization_confirmed: bool
    dataset: AutomationDatasetResponse
    version: AutomationDatasetVersionResponse
    audit_events: list[dict[str, Any]]
    blocked_reasons: list[str]


class AutomationScheduleApprovedTaskResponse(BaseModel):
    task_id: uuid.UUID
    task_name: str
    status: str
    schedule_cron: str | None
    schedule_policy: str
    freshness_target_hours: int
    dataset_id: uuid.UUID
    dataset_version_id: uuid.UUID
    approved_at: datetime


class AutomationScheduleBlockedTaskResponse(BaseModel):
    task_id: uuid.UUID
    reason: str


class AutomationProductScheduleApproveSummaryResponse(BaseModel):
    requested_tasks: int
    approved_tasks: int
    blocked_tasks: int
    run_started: bool


class AutomationProductScheduleApproveResponse(BaseModel):
    approved_at: datetime
    authorization_confirmed: bool
    dataset: AutomationDatasetResponse
    version: AutomationDatasetVersionResponse
    approved_tasks: list[AutomationScheduleApprovedTaskResponse]
    blocked_tasks: list[AutomationScheduleBlockedTaskResponse]
    summary: AutomationProductScheduleApproveSummaryResponse
    audit_events: list[dict[str, Any]]
    blocked_reasons: list[str]


class AutomationProductDriftItemResponse(BaseModel):
    task_id: uuid.UUID
    task_name: str | None
    source_url: str | None
    status: Literal["ok", "warning", "critical", "blocked"]
    blocked_reason: str | None
    latest_run_id: uuid.UUID | None
    latest_run_status: str | None
    dataset_version_completeness_percent: int
    latest_completeness_percent: int | None
    completeness_drop_percent: int | None
    missing_fields: list[str]
    new_missing_fields: list[str]
    freshness_target_hours: int | None
    stale_hours: float | None
    issues: list[str]


class AutomationProductDriftSummaryResponse(BaseModel):
    requested_tasks: int
    checked_tasks: int
    blocked_tasks: int
    warning_tasks: int
    critical_tasks: int
    stale_tasks: int
    missing_field_tasks: int
    run_started: bool
    alert_created: bool


class AutomationProductDriftCheckResponse(BaseModel):
    checked_at: datetime
    authorization_confirmed: bool
    dataset: AutomationDatasetResponse
    version: AutomationDatasetVersionResponse
    items: list[AutomationProductDriftItemResponse]
    summary: AutomationProductDriftSummaryResponse
    audit_events: list[dict[str, Any]]
    blocked_reasons: list[str]


class AutomationProductDriftEventResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    dataset: AutomationDatasetResponse
    version: AutomationDatasetVersionResponse
    event_type: str
    status: Literal["ok", "warning", "critical", "blocked"]
    thresholds: dict[str, Any]
    summary: AutomationProductDriftSummaryResponse
    items: list[AutomationProductDriftItemResponse]
    audit_events: list[dict[str, Any]]
    note: str | None
    run_started: bool
    alert_created: bool


class AutomationProductDriftEventListResponse(BaseModel):
    items: list[AutomationProductDriftEventResponse]
    total: int
    run_started: bool
    alert_created: bool


class AutomationGitHubToolReportRepositoryResponse(BaseModel):
    repo_full_name: str
    html_url: str | None
    description: str | None
    stars: int
    forks: int | None
    open_issues: int | None
    watchers: int | None
    language: str | None
    topics: list[str]
    license_spdx_id: str | None
    default_branch: str | None
    latest_release_tag: str | None
    latest_release_published_at: str | None
    archived: bool | None
    fork: bool | None
    updated_at: str | None
    pushed_at: str | None


class AutomationGitHubToolReportSummaryResponse(BaseModel):
    repository_count: int
    total_stars: int
    high_value_repositories: int
    licensed_repositories: int
    release_tagged_repositories: int
    archived_repositories: int
    fork_repositories: int
    languages: dict[str, int]
    top_topics: dict[str, int]
    report_created: bool
    run_started: bool


class AutomationGitHubToolReportResponse(BaseModel):
    generated_at: datetime
    authorization_confirmed: bool
    dataset: AutomationDatasetResponse
    version: AutomationDatasetVersionResponse
    summary: AutomationGitHubToolReportSummaryResponse
    top_repositories: list[AutomationGitHubToolReportRepositoryResponse]
    recommendations: list[str]
    audit_events: list[dict[str, Any]]
    blocked_reasons: list[str]


class AutomationGitHubToolReportAssetResponse(AutomationGitHubToolReportResponse):
    report: ReportResponse
    notification_created: bool


class AutomationProductDatasetListItemResponse(BaseModel):
    dataset: AutomationDatasetResponse
    latest_version: AutomationDatasetVersionResponse | None
    version_count: int
    latest_drift_event: AutomationProductDriftEventResponse | None
    drift_event_count: int


class AutomationProductDatasetListResponse(BaseModel):
    items: list[AutomationProductDatasetListItemResponse]
    total: int
    run_started: bool
    alert_created: bool


class AutomationProductDatasetVersionListResponse(BaseModel):
    dataset: AutomationDatasetResponse
    versions: list[AutomationDatasetVersionResponse]
    total: int
    run_started: bool
    alert_created: bool


class AutomationProductDatasetExportJobResponse(BaseModel):
    id: uuid.UUID
    dataset: AutomationDatasetResponse
    version: AutomationDatasetVersionResponse
    export_format: Literal["csv", "json", "jsonl"]
    status: str
    filename: str
    content_type: str
    artifact_size_bytes: int
    row_count: int
    checksum_sha256: str
    error_message: str | None
    created_at: datetime
    finished_at: datetime | None
    download_url: str | None
    audit_events: list[dict[str, Any]]
    blocked_reasons: list[str]


class AutomationProductDatasetExportListResponse(BaseModel):
    items: list[AutomationProductDatasetExportJobResponse]
    total: int
    export_created: bool
    run_started: bool


class AutomationProductDriftAlertRuleDraftResponse(BaseModel):
    name: str
    project_id: uuid.UUID
    signal_type: Literal["dataset_drift"]
    condition: dict[str, Any]
    channel: Literal["in_app", "email", "both"]
    enabled: bool


class AutomationProductDriftAlertSummaryResponse(BaseModel):
    matched_events: int
    critical_events: int
    warning_events: int
    alert_rule_created: bool
    signal_created: bool
    alert_event_created: bool
    notification_created: bool
    run_started: bool


class AutomationProductDriftAlertPreviewResponse(BaseModel):
    generated_at: datetime
    authorization_confirmed: bool
    dataset: AutomationDatasetResponse
    latest_version: AutomationDatasetVersionResponse | None
    rule_draft: AutomationProductDriftAlertRuleDraftResponse
    matched_events: list[AutomationProductDriftEventResponse]
    summary: AutomationProductDriftAlertSummaryResponse
    blocked_reasons: list[str]


class AutomationProductDriftAlertRuleCreateResponse(AutomationProductDriftAlertPreviewResponse):
    alert_rule: AlertRuleResponse


class AutomationProductDriftAlertEventCreateResponse(BaseModel):
    generated_at: datetime
    authorization_confirmed: bool
    dataset: AutomationDatasetResponse
    version: AutomationDatasetVersionResponse
    drift_event: AutomationProductDriftEventResponse
    signal: SignalResponse
    alert_events: list[AlertEventResponse]
    summary: AutomationProductDriftAlertSummaryResponse
    blocked_reasons: list[str]


class AutomationProductDriftAlertNotificationSendResponse(BaseModel):
    generated_at: datetime
    authorization_confirmed: bool
    dataset: AutomationDatasetResponse
    version: AutomationDatasetVersionResponse
    drift_event: AutomationProductDriftEventResponse
    alert_events: list[AlertEventResponse]
    notifications: list[NotificationResponse]
    summary: AutomationProductDriftAlertSummaryResponse
    blocked_reasons: list[str]


class AutomationProductDriftAlertEmailDeliveryResponse(BaseModel):
    alert_event_id: uuid.UUID
    recipient_email: str
    delivered: bool
    delivered_at: datetime | None = None
    reason: str | None = None


class AutomationProductDriftAlertEmailSendResponse(BaseModel):
    generated_at: datetime
    authorization_confirmed: bool
    dataset: AutomationDatasetResponse
    version: AutomationDatasetVersionResponse
    drift_event: AutomationProductDriftEventResponse
    alert_events: list[AlertEventResponse]
    email_deliveries: list[AutomationProductDriftAlertEmailDeliveryResponse]
    summary: AutomationProductDriftAlertSummaryResponse
    blocked_reasons: list[str]
