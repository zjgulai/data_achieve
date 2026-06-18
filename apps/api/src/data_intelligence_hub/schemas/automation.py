from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

from data_intelligence_hub.schemas.alert import AlertEventResponse, AlertRuleResponse
from data_intelligence_hub.schemas.notification import NotificationResponse
from data_intelligence_hub.schemas.signal import SignalResponse
from data_intelligence_hub.schemas.source import SourceResponse
from data_intelligence_hub.schemas.task import CollectionTaskResponse, TaskRunResponse


class AutomationSiteAnalysisRequest(BaseModel):
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
