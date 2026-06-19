import { apiBaseUrl, apiFetch, mockApiEnabled } from "@/lib/api/client";
import {
  getMockAutomationProductFanoutCreate,
  getMockAutomationProductFanoutPreview,
  getMockAutomationProductBatchRun,
  getMockAutomationProductDatasetPreview,
  getMockAutomationProductDatasetSave,
  getMockAutomationProductDatasetExportCreate,
  getMockAutomationProductDatasetExports,
  getMockAutomationProductDatasets,
  getMockAutomationProductDatasetVersions,
  getMockAutomationProductDiscovery,
  getMockAutomationProductDriftAlertPreview,
  getMockAutomationProductDriftAlertEventCreate,
  getMockAutomationProductDriftAlertNotificationSend,
  getMockAutomationProductDriftAlertEmailSend,
  getMockAutomationProductDriftAlertRuleCreate,
  getMockAutomationProductDriftCheck,
  getMockAutomationProductDriftEvents,
  getMockAutomationProductDriftEventSave,
  getMockAutomationProductScheduleApprove,
  getMockAutomationPlatformPackages,
  getMockAutomationSiteAnalysis,
} from "@/lib/api/mock";
import type {
  AutomationCleaningPlanCreate,
  AutomationCleaningPlanCreateInput,
  AutomationCleaningPlanDryRun,
  AutomationCleaningPlanInput,
  AutomationCleaningRule,
  AutomationCleaningStep,
  AutomationFieldCandidate,
  AutomationProductDiscovery,
  AutomationProductDiscoveryInput,
  AutomationProductBatchRun,
  AutomationProductBatchRunInput,
  AutomationProductDatasetPreview,
  AutomationProductDatasetPreviewInput,
  AutomationProductDatasetSave,
  AutomationProductDatasetExportCreateInput,
  AutomationProductDatasetExportJob,
  AutomationProductDatasetExportList,
  AutomationProductDatasetExportListInput,
  AutomationProductDatasetSaveInput,
  AutomationProductDatasetList,
  AutomationProductDatasetListInput,
  AutomationProductDatasetVersionList,
  AutomationProductDatasetVersionListInput,
  AutomationProductDriftCheck,
  AutomationProductDriftCheckInput,
  AutomationProductDriftAlertPreview,
  AutomationProductDriftAlertPreviewInput,
  AutomationProductDriftAlertEventCreate,
  AutomationProductDriftAlertEventCreateInput,
  AutomationProductDriftAlertNotificationSend,
  AutomationProductDriftAlertNotificationSendInput,
  AutomationProductDriftAlertEmailSend,
  AutomationProductDriftAlertEmailSendInput,
  AutomationProductDriftAlertRuleCreate,
  AutomationProductDriftAlertRuleCreateInput,
  AutomationProductDriftEvent,
  AutomationProductDriftEventList,
  AutomationProductDriftEventListInput,
  AutomationProductDriftEventSaveInput,
  AutomationProductFanoutCreate,
  AutomationProductFanoutCreateInput,
  AutomationProductFanoutPreview,
  AutomationProductFanoutPreviewInput,
  AutomationProductScheduleApprove,
  AutomationProductScheduleApproveInput,
  AutomationExtractionPlan,
  AutomationPlatformPackage,
  AutomationPlatformPackageList,
  AutomationSiteAnalysis,
  AutomationSiteAnalysisHistoryItem,
  AutomationSiteAnalysisInput,
  AutomationSiteAnalysisList,
  AutomationSiteAnalysisListInput,
  AutomationToolRecommendation,
} from "@/types/automation";
import type { AlertEvent } from "@/types/alert";
import type { NotificationItem } from "@/types/notification";
import type { Signal } from "@/types/signal";

type AutomationFieldCandidateResponse = {
  key: string;
  label: string;
  value: string | number | boolean | null;
  data_type: string;
  source: string;
  confidence: number;
  selected: boolean;
  cleaning_rule: string;
};

type AutomationToolRecommendationResponse = {
  tool: string;
  collector_type: string;
  fit: string;
  risk_level: string;
  reason: string;
};

type AutomationCleaningStepResponse = {
  field: string;
  operation: string;
  description: string;
};

type AutomationSourceDraftResponse = {
  type: string;
  config: Record<string, unknown>;
  suggested_name: string;
  schedule_cron: string | null;
};

type AutomationPlatformPackageResponse = {
  id: string;
  name: string;
  category: string;
  summary: string;
  supported_targets: string[];
  collector_types: string[];
  field_schema: Array<{
    key: string;
    label: string;
    data_type: string;
    required: boolean;
    source: string;
    cleaning_rule: string;
  }>;
  strategy_matrix: Array<{
    id: string;
    label: string;
    entrypoint: string;
    collector_type: string;
    fit: "high" | "medium" | "low";
    can_start_from_automation: boolean;
    review_required: boolean;
    description: string;
  }>;
  risk_boundaries: Array<{
    condition: string;
    severity: "info" | "warning" | "blocked";
    guidance: string;
  }>;
  sop_links: Array<{
    label: string;
    href: string;
  }>;
  sample_fixture: {
    fixture_type: string;
    available: boolean;
    description: string;
  };
  execution_boundary: "executable" | "sop_import_only" | "blocked";
  run_started: boolean;
};

type AutomationPlatformPackageListResponse = {
  items: AutomationPlatformPackageResponse[];
  total: number;
  run_started: boolean;
};

type AutomationExtractionPlanResponse = {
  id: string;
  site_analysis_id: string;
  project_id: string;
  name: string;
  version_number: number;
  collector_type: string;
  selected_fields: string[];
  source_draft: AutomationSourceDraftResponse;
  schedule_cron: string | null;
  status: string;
  risk_level: string;
  audit_events: Array<Record<string, unknown>>;
  created_at: string;
  run_started: boolean;
};

type AutomationSiteAnalysisHistoryItemResponse = {
  id: string;
  project_id: string;
  requested_url: string;
  target: string;
  status: string;
  platform_type: string;
  page_type: string;
  risk_level: string;
  analyzed_at: string;
  created_at: string;
  latest_plan: AutomationExtractionPlanResponse | null;
};

type AutomationSiteAnalysisListResponse = {
  items: AutomationSiteAnalysisHistoryItemResponse[];
  total: number;
  run_started: boolean;
};

type AutomationSiteAnalysisResponse = {
  requested_url: string;
  analyzed_at: string;
  authorization_confirmed: boolean;
  platform_profile: {
    platform_type: string;
    confidence: number;
    indicators: string[];
    risk_level: string;
  };
  page_structure: {
    page_type: string;
    title: string | null;
    canonical_url: string | null;
    script_count: number;
    form_count: number;
    image_count: number;
    product_schema_count: number;
    same_origin_link_count: number;
    text_sample: string;
  };
  field_candidates: AutomationFieldCandidateResponse[];
  tool_recommendations: AutomationToolRecommendationResponse[];
  cleaning_plan: AutomationCleaningStepResponse[];
  source_draft: AutomationSourceDraftResponse;
  blocked_reasons: string[];
  site_analysis: AutomationSiteAnalysisHistoryItemResponse | null;
  extraction_plan: AutomationExtractionPlanResponse | null;
  site_analysis_created: boolean;
  extraction_plan_created: boolean;
  run_started: boolean;
};

type AutomationProductCandidateResponse = {
  url: string;
  title: string | null;
  source: string;
  confidence: number;
};

type AutomationProductDiscoveryResponse = {
  requested_url: string;
  analyzed_at: string;
  authorization_confirmed: boolean;
  platform_profile: {
    platform_type: string;
    confidence: number;
    indicators: string[];
    risk_level: string;
  };
  page_structure: {
    page_type: string;
    title: string | null;
    canonical_url: string | null;
    link_count: number;
    product_link_count: number;
    jsonld_url_count: number;
    sitemap_url_count: number;
    script_count: number;
    text_sample: string;
  };
  product_candidates: AutomationProductCandidateResponse[];
  tool_recommendations: AutomationToolRecommendationResponse[];
  discovery_plan: {
    next_collector_type: string;
    candidate_count: number;
    max_products: number;
    fan_out_requires_review: boolean;
  };
  source_draft: {
    type: string;
    config: Record<string, unknown>;
    suggested_name: string;
    schedule_cron: string | null;
  };
  blocked_reasons: string[];
};

type AutomationFanoutCandidateStatusResponse = {
  url: string;
  title: string | null;
  source: string | null;
  confidence: number | null;
  status: "ready" | "blocked";
  reason: string | null;
};

type AutomationProductFanoutPreviewResponse = {
  requested_parent_url: string;
  analyzed_at: string;
  authorization_confirmed: boolean;
  candidate_statuses: AutomationFanoutCandidateStatusResponse[];
  source_drafts: Array<{
    type: string;
    config: Record<string, unknown>;
    suggested_name: string;
    schedule_cron: string | null;
  }>;
  batch_plan: {
    run_mode: "preview_only";
    next_collector_type: string;
    ready_count: number;
    blocked_count: number;
    max_sources: number;
    fields: string[];
    manual_review_required: boolean;
    execution_boundary: string;
  };
  blocked_reasons: string[];
};

type AutomationProductFanoutCreateResponse = {
  requested_parent_url: string;
  created_at: string;
  authorization_confirmed: boolean;
  persisted_sources: Array<{
    url: string;
    action: "created" | "reused";
    source: {
      id: string;
      project_id: string;
      name: string;
      type: string;
      url: string | null;
      enabled: boolean;
      config: Record<string, unknown>;
      schedule_cron: string | null;
      created_at: string;
      updated_at: string;
    };
    task: {
      id: string;
      source_id: string;
      collector_type: string;
      name: string;
      status: string;
      schedule_cron: string | null;
    } | null;
  }>;
  candidate_statuses: AutomationFanoutCandidateStatusResponse[];
  summary: {
    created_sources: number;
    reused_sources: number;
    enabled_tasks: number;
    blocked_candidates: number;
    run_started: boolean;
  };
  audit_events: Array<Record<string, unknown>>;
  blocked_reasons: string[];
};

type AutomationProductBatchRunResponse = {
  created_at: string;
  authorization_confirmed: boolean;
  items: Array<{
    task_id: string;
    task_name: string | null;
    source_id: string | null;
    source_url: string | null;
    status: "run_completed" | "run_failed" | "blocked";
    blocked_reason: string | null;
    run: {
      id: string;
      task_id: string;
      status: string;
      records_count: number;
      entities_count: number;
      error_message: string | null;
      started_at: string | null;
      finished_at: string | null;
    } | null;
    records_count: number;
    entities_count: number;
    field_completeness: {
      configured_fields: string[];
      extracted_fields: string[];
      missing_fields: string[];
      field_values: Record<string, unknown>;
      completeness_ratio: number;
      completeness_percent: number;
    } | null;
    error_message: string | null;
  }>;
  summary: {
    requested_tasks: number;
    run_tasks: number;
    blocked_tasks: number;
    successful_runs: number;
    failed_runs: number;
    records_count: number;
    entities_count: number;
    average_completeness_percent: number;
    run_started: boolean;
  };
  audit_events: Array<Record<string, unknown>>;
  blocked_reasons: string[];
};

type AutomationProductDatasetPreviewResponse = {
  created_at: string;
  authorization_confirmed: boolean;
  rows: Array<{
    row_id: string;
    task_run_id: string;
    raw_record_id: string;
    source_url: string | null;
    values: Record<string, unknown>;
    missing_fields: string[];
    completeness_percent: number;
  }>;
  summary: {
    requested_runs: number;
    matched_runs: number;
    rows_count: number;
    selected_fields: string[];
    average_completeness_percent: number;
    export_format: "json";
    export_ready: boolean;
  };
  cleaning_script_draft: string[];
  export_preview: Record<string, unknown>;
  audit_events: Array<Record<string, unknown>>;
  blocked_reasons: string[];
};

type AutomationCleaningPlanDryRunResponse = {
  created_at: string;
  authorization_confirmed: boolean;
  rows: Array<{
    row_id: string;
    task_run_id: string;
    raw_record_id: string;
    source_url: string | null;
    before_values: Record<string, unknown>;
    after_values: Record<string, unknown>;
    missing_fields_before: string[];
    missing_fields_after: string[];
    changed_fields: string[];
  }>;
  summary: {
    rows_count: number;
    rows_changed: number;
    rules_count: number;
    selected_fields: string[];
    dataset_version_created: boolean;
    cleaning_plan_created: boolean;
    run_started: boolean;
  };
  cleaning_script: string[];
  export_preview: Record<string, unknown>;
  audit_events: Array<Record<string, unknown>>;
  blocked_reasons: string[];
};

type AutomationCleaningPlanResponse = {
  id: string;
  project_id: string;
  name: string;
  version_number: number;
  target: string;
  selected_fields: string[];
  source_task_run_ids: string[];
  rules: Array<Record<string, unknown>>;
  cleaning_script: string[];
  dry_run_preview: Record<string, unknown>;
  status: string;
  created_at: string;
};

type AutomationCleaningPlanCreateResponse = {
  saved_at: string;
  authorization_confirmed: boolean;
  cleaning_plan: AutomationCleaningPlanResponse;
  dry_run: AutomationCleaningPlanDryRunResponse;
  cleaning_plan_created: boolean;
  dataset_version_created: boolean;
  run_started: boolean;
  audit_events: Array<Record<string, unknown>>;
  blocked_reasons: string[];
};

type AutomationProductDatasetSaveResponse = {
  saved_at: string;
  authorization_confirmed: boolean;
  dataset: {
    id: string;
    project_id: string;
    name: string;
    dataset_type: string;
    status: string;
    description: string | null;
  };
  version: {
    id: string;
    dataset_id: string;
    cleaning_plan_id: string | null;
    version_number: number;
    source_task_run_ids: string[];
    selected_fields: string[];
    cleaning_script: string[];
    row_count: number;
    average_completeness_percent: number;
    status: string;
    created_at: string;
    export_preview: Record<string, unknown>;
  };
  audit_events: Array<Record<string, unknown>>;
  blocked_reasons: string[];
};

type AutomationProductDatasetExportJobResponse = {
  id: string;
  dataset: AutomationProductDatasetSaveResponse["dataset"];
  version: AutomationProductDatasetSaveResponse["version"];
  export_format: "csv" | "json" | "jsonl";
  status: string;
  filename: string;
  content_type: string;
  artifact_size_bytes: number;
  row_count: number;
  checksum_sha256: string;
  error_message: string | null;
  created_at: string;
  finished_at: string | null;
  download_url: string | null;
  audit_events: Array<Record<string, unknown>>;
  blocked_reasons: string[];
};

type AutomationProductDatasetExportListResponse = {
  items: AutomationProductDatasetExportJobResponse[];
  total: number;
  export_created: boolean;
  run_started: boolean;
};

type AutomationProductScheduleApproveResponse = {
  approved_at: string;
  authorization_confirmed: boolean;
  dataset: AutomationProductDatasetSaveResponse["dataset"];
  version: AutomationProductDatasetSaveResponse["version"];
  approved_tasks: Array<{
    task_id: string;
    task_name: string;
    status: string;
    schedule_cron: string | null;
    schedule_policy: string;
    freshness_target_hours: number;
    dataset_id: string;
    dataset_version_id: string;
    approved_at: string;
  }>;
  blocked_tasks: Array<{
    task_id: string;
    reason: string;
  }>;
  summary: {
    requested_tasks: number;
    approved_tasks: number;
    blocked_tasks: number;
    run_started: boolean;
  };
  audit_events: Array<Record<string, unknown>>;
  blocked_reasons: string[];
};

type AutomationProductDriftCheckResponse = {
  checked_at: string;
  authorization_confirmed: boolean;
  dataset: AutomationProductDatasetSaveResponse["dataset"];
  version: AutomationProductDatasetSaveResponse["version"];
  items: Array<{
    task_id: string;
    task_name: string | null;
    source_url: string | null;
    status: "ok" | "warning" | "critical" | "blocked";
    blocked_reason: string | null;
    latest_run_id: string | null;
    latest_run_status: string | null;
    dataset_version_completeness_percent: number;
    latest_completeness_percent: number | null;
    completeness_drop_percent: number | null;
    missing_fields: string[];
    new_missing_fields: string[];
    freshness_target_hours: number | null;
    stale_hours: number | null;
    issues: string[];
  }>;
  summary: {
    requested_tasks: number;
    checked_tasks: number;
    blocked_tasks: number;
    warning_tasks: number;
    critical_tasks: number;
    stale_tasks: number;
    missing_field_tasks: number;
    run_started: boolean;
    alert_created: boolean;
  };
  audit_events: Array<Record<string, unknown>>;
  blocked_reasons: string[];
};

type AutomationProductDriftEventResponse = {
  id: string;
  created_at: string;
  dataset: AutomationProductDatasetSaveResponse["dataset"];
  version: AutomationProductDatasetSaveResponse["version"];
  event_type: string;
  status: "ok" | "warning" | "critical" | "blocked";
  thresholds: Record<string, unknown>;
  summary: AutomationProductDriftCheckResponse["summary"];
  items: AutomationProductDriftCheckResponse["items"];
  audit_events: Array<Record<string, unknown>>;
  note: string | null;
  run_started: boolean;
  alert_created: boolean;
};

type AutomationProductDriftEventListResponse = {
  items: AutomationProductDriftEventResponse[];
  total: number;
  run_started: boolean;
  alert_created: boolean;
};

type AutomationProductDatasetListResponse = {
  items: Array<{
    dataset: AutomationProductDatasetSaveResponse["dataset"];
    latest_version: AutomationProductDatasetSaveResponse["version"] | null;
    version_count: number;
    latest_drift_event: AutomationProductDriftEventResponse | null;
    drift_event_count: number;
  }>;
  total: number;
  run_started: boolean;
  alert_created: boolean;
};

type AutomationProductDatasetVersionListResponse = {
  dataset: AutomationProductDatasetSaveResponse["dataset"];
  versions: AutomationProductDatasetSaveResponse["version"][];
  total: number;
  run_started: boolean;
  alert_created: boolean;
};

type AutomationProductDriftAlertRuleDraftResponse = {
  name: string;
  project_id: string;
  signal_type: "dataset_drift";
  condition: Record<string, unknown>;
  channel: "in_app" | "email" | "both";
  enabled: boolean;
};

type AutomationProductDriftAlertSummaryResponse = {
  matched_events: number;
  critical_events: number;
  warning_events: number;
  alert_rule_created: boolean;
  signal_created: boolean;
  alert_event_created: boolean;
  notification_created: boolean;
  run_started: boolean;
};

type AutomationProductDriftAlertPreviewResponse = {
  generated_at: string;
  authorization_confirmed: boolean;
  dataset: AutomationProductDatasetSaveResponse["dataset"];
  latest_version: AutomationProductDatasetSaveResponse["version"] | null;
  rule_draft: AutomationProductDriftAlertRuleDraftResponse;
  matched_events: AutomationProductDriftEventResponse[];
  summary: AutomationProductDriftAlertSummaryResponse;
  blocked_reasons: string[];
};

type AutomationProductDriftAlertRuleCreateResponse =
  AutomationProductDriftAlertPreviewResponse & {
    alert_rule: {
      id: string;
      workspace_id: string;
      project_id: string | null;
      name: string;
      signal_type: string;
      condition: Record<string, unknown>;
      channel: string;
      enabled: boolean;
      created_at: string;
    };
  };

type SignalResponse = {
  id: string;
  workspace_id: string;
  project_id: string;
  entity_id: string;
  signal_type: string;
  previous_snapshot_id: string;
  current_snapshot_id: string;
  current_value: number | null;
  previous_value: number | null;
  delta: number | null;
  delta_ratio: number | null;
  confidence: number;
  severity: string;
  metadata: Record<string, unknown>;
  detected_at: string;
};

type AlertEventResponse = {
  id: string;
  rule_id: string;
  signal_id: string;
  status: string;
  payload: Record<string, unknown>;
  triggered_at: string;
  sent_at: string | null;
};

type AutomationProductDriftAlertEventCreateResponse = {
  generated_at: string;
  authorization_confirmed: boolean;
  dataset: AutomationProductDatasetSaveResponse["dataset"];
  version: AutomationProductDatasetSaveResponse["version"];
  drift_event: AutomationProductDriftEventResponse;
  signal: SignalResponse;
  alert_events: AlertEventResponse[];
  summary: AutomationProductDriftAlertSummaryResponse;
  blocked_reasons: string[];
};

type NotificationResponse = {
  id: string;
  user_id: string;
  title: string;
  body: string;
  notification_type: string;
  reference_type: string;
  reference_id: string;
  is_read: boolean;
  created_at: string;
};

type AutomationProductDriftAlertNotificationSendResponse = {
  generated_at: string;
  authorization_confirmed: boolean;
  dataset: AutomationProductDatasetSaveResponse["dataset"];
  version: AutomationProductDatasetSaveResponse["version"];
  drift_event: AutomationProductDriftEventResponse;
  alert_events: AlertEventResponse[];
  notifications: NotificationResponse[];
  summary: AutomationProductDriftAlertSummaryResponse;
  blocked_reasons: string[];
};

type AutomationProductDriftAlertEmailDeliveryResponse = {
  alert_event_id: string;
  recipient_email: string;
  delivered: boolean;
  delivered_at: string | null;
  reason: string | null;
};

type AutomationProductDriftAlertEmailSendResponse = {
  generated_at: string;
  authorization_confirmed: boolean;
  dataset: AutomationProductDatasetSaveResponse["dataset"];
  version: AutomationProductDatasetSaveResponse["version"];
  drift_event: AutomationProductDriftEventResponse;
  alert_events: AlertEventResponse[];
  email_deliveries: AutomationProductDriftAlertEmailDeliveryResponse[];
  summary: AutomationProductDriftAlertSummaryResponse;
  blocked_reasons: string[];
};

export async function listAutomationPlatformPackages(): Promise<AutomationPlatformPackageList> {
  if (mockApiEnabled) {
    const items = getMockAutomationPlatformPackages();
    return {
      items,
      total: items.length,
      runStarted: false,
    };
  }
  const response = await apiFetch<AutomationPlatformPackageListResponse>(
    "/api/automation/platform-packages",
  );
  return {
    items: response.items.map(mapAutomationPlatformPackage),
    total: response.total,
    runStarted: response.run_started,
  };
}

export async function analyzeAutomationSite(
  input: AutomationSiteAnalysisInput,
): Promise<AutomationSiteAnalysis> {
  if (mockApiEnabled) {
    return getMockAutomationSiteAnalysis(input.url);
  }
  const response = await apiFetch<AutomationSiteAnalysisResponse>("/api/automation/site-analysis", {
    method: "POST",
    body: JSON.stringify({
      project_id: input.projectId,
      url: input.url,
      authorized: input.authorized,
      target: input.target ?? "ecommerce_product",
      fields: input.fields,
    }),
  });
  return mapAutomationSiteAnalysis(response);
}

export async function listAutomationSiteAnalyses(
  input: AutomationSiteAnalysisListInput = {},
): Promise<AutomationSiteAnalysisList> {
  if (mockApiEnabled) {
    const analysis = getMockAutomationSiteAnalysis("https://shop.example/products/demo-bag");
    return {
      items: [
        {
          id: "site_analysis_mock",
          projectId: input.projectId ?? "project_marketplace_price",
          requestedUrl: analysis.requestedUrl,
          target: "ecommerce_product",
          status: "analyzed",
          platformType: analysis.platformProfile.platformType,
          pageType: analysis.pageStructure.pageType,
          riskLevel: analysis.platformProfile.riskLevel,
          analyzedAt: analysis.analyzedAt,
          createdAt: analysis.analyzedAt,
          latestPlan: null,
        },
      ],
      total: 1,
      runStarted: false,
    };
  }
  const params = new URLSearchParams();
  if (input.projectId) {
    params.set("project_id", input.projectId);
  }
  if (input.target) {
    params.set("target", input.target);
  }
  if (input.limit) {
    params.set("limit", String(input.limit));
  }
  const query = params.toString();
  const response = await apiFetch<AutomationSiteAnalysisListResponse>(
    `/api/automation/site-analyses${query ? `?${query}` : ""}`,
  );
  return {
    items: response.items.map(mapAutomationSiteAnalysisHistoryItem),
    total: response.total,
    runStarted: response.run_started,
  };
}

export async function discoverAutomationProducts(
  input: AutomationProductDiscoveryInput,
): Promise<AutomationProductDiscovery> {
  if (mockApiEnabled) {
    return getMockAutomationProductDiscovery(input.url);
  }
  const response = await apiFetch<AutomationProductDiscoveryResponse>(
    "/api/automation/product-discovery",
    {
      method: "POST",
      body: JSON.stringify({
        url: input.url,
        authorized: input.authorized,
        max_products: input.maxProducts ?? 50,
      }),
    },
  );
  return mapAutomationProductDiscovery(response);
}

export async function previewAutomationProductFanout(
  input: AutomationProductFanoutPreviewInput,
): Promise<AutomationProductFanoutPreview> {
  if (mockApiEnabled) {
    return getMockAutomationProductFanoutPreview(input);
  }
  const response = await apiFetch<AutomationProductFanoutPreviewResponse>(
    "/api/automation/product-fanout-preview",
    {
      method: "POST",
      body: JSON.stringify({
        parent_url: input.parentUrl,
        authorized: input.authorized,
        candidates: input.candidates,
        fields: input.fields,
        max_sources: input.maxSources ?? 20,
      }),
    },
  );
  return mapAutomationProductFanoutPreview(response);
}

export async function createAutomationProductFanout(
  input: AutomationProductFanoutCreateInput,
): Promise<AutomationProductFanoutCreate> {
  if (mockApiEnabled) {
    return getMockAutomationProductFanoutCreate(input);
  }
  const response = await apiFetch<AutomationProductFanoutCreateResponse>(
    "/api/automation/product-fanout-create",
    {
      method: "POST",
      body: JSON.stringify({
        project_id: input.projectId,
        parent_url: input.parentUrl,
        authorized: input.authorized,
        candidates: input.candidates,
        fields: input.fields,
        max_sources: input.maxSources ?? 20,
        enable_tasks: input.enableTasks ?? true,
      }),
    },
  );
  return mapAutomationProductFanoutCreate(response);
}

export async function runAutomationProductBatch(
  input: AutomationProductBatchRunInput,
): Promise<AutomationProductBatchRun> {
  if (mockApiEnabled) {
    return getMockAutomationProductBatchRun(input);
  }
  const response = await apiFetch<AutomationProductBatchRunResponse>(
    "/api/automation/product-batch-run",
    {
      method: "POST",
      body: JSON.stringify({
        authorized: input.authorized,
        task_ids: input.taskIds,
        max_tasks: input.maxTasks ?? 5,
      }),
    },
  );
  return mapAutomationProductBatchRun(response);
}

export async function previewAutomationProductDataset(
  input: AutomationProductDatasetPreviewInput,
): Promise<AutomationProductDatasetPreview> {
  if (mockApiEnabled) {
    return getMockAutomationProductDatasetPreview(input);
  }
  const response = await apiFetch<AutomationProductDatasetPreviewResponse>(
    "/api/automation/product-dataset-preview",
    {
      method: "POST",
      body: JSON.stringify({
        authorized: input.authorized,
        task_run_ids: input.taskRunIds,
        fields: input.fields,
        max_rows: input.maxRows ?? 100,
      }),
    },
  );
  return mapAutomationProductDatasetPreview(response);
}

export async function dryRunAutomationCleaningPlan(
  input: AutomationCleaningPlanInput,
): Promise<AutomationCleaningPlanDryRun> {
  if (mockApiEnabled) {
    return getMockAutomationCleaningPlanDryRun(input);
  }
  const response = await apiFetch<AutomationCleaningPlanDryRunResponse>(
    "/api/automation/cleaning-plan-dry-run",
    {
      method: "POST",
      body: JSON.stringify({
        authorized: input.authorized,
        task_run_ids: input.taskRunIds,
        fields: input.fields,
        rules: input.rules.map(mapCleaningRuleRequest),
        max_rows: input.maxRows ?? 100,
      }),
    },
  );
  return mapAutomationCleaningPlanDryRun(response);
}

export async function createAutomationCleaningPlan(
  input: AutomationCleaningPlanCreateInput,
): Promise<AutomationCleaningPlanCreate> {
  if (mockApiEnabled) {
    const dryRun = getMockAutomationCleaningPlanDryRun(input);
    return {
      savedAt: new Date().toISOString(),
      authorizationConfirmed: input.authorized,
      cleaningPlan: {
        id: "mock-cleaning-plan-1",
        projectId: "mock-project-1",
        name: input.name,
        versionNumber: 1,
        target: "ecommerce_product",
        selectedFields: dryRun.summary.selectedFields,
        sourceTaskRunIds: input.taskRunIds,
        rules: input.rules as unknown as Array<Record<string, unknown>>,
        cleaningScript: dryRun.cleaningScript,
        dryRunPreview: dryRun.exportPreview,
        status: "draft",
        createdAt: new Date().toISOString(),
      },
      dryRun,
      cleaningPlanCreated: true,
      datasetVersionCreated: false,
      runStarted: false,
      auditEvents: [{ event: "mock_cleaning_plan_created" }],
      blockedReasons: ["CleaningPlan 已保存为草案；尚未保存 DatasetVersion 或启动采集。"],
    };
  }
  const response = await apiFetch<AutomationCleaningPlanCreateResponse>(
    "/api/automation/cleaning-plans",
    {
      method: "POST",
      body: JSON.stringify({
        authorized: input.authorized,
        name: input.name,
        task_run_ids: input.taskRunIds,
        fields: input.fields,
        rules: input.rules.map(mapCleaningRuleRequest),
        max_rows: input.maxRows ?? 100,
      }),
    },
  );
  return mapAutomationCleaningPlanCreate(response);
}

export async function saveAutomationProductDataset(
  input: AutomationProductDatasetSaveInput,
): Promise<AutomationProductDatasetSave> {
  if (mockApiEnabled) {
    return getMockAutomationProductDatasetSave(input);
  }
  const response = await apiFetch<AutomationProductDatasetSaveResponse>(
    "/api/automation/product-dataset-save",
    {
      method: "POST",
      body: JSON.stringify({
        authorized: input.authorized,
        name: input.name,
        description: input.description,
        task_run_ids: input.taskRunIds,
        fields: input.fields,
        max_rows: input.maxRows ?? 100,
        cleaning_plan_id: input.cleaningPlanId,
      }),
    },
  );
  return mapAutomationProductDatasetSave(response);
}

export async function createAutomationProductDatasetExport(
  input: AutomationProductDatasetExportCreateInput,
): Promise<AutomationProductDatasetExportJob> {
  if (mockApiEnabled) {
    return getMockAutomationProductDatasetExportCreate(input);
  }
  const response = await apiFetch<AutomationProductDatasetExportJobResponse>(
    "/api/automation/product-dataset-exports",
    {
      method: "POST",
      body: JSON.stringify({
        authorized: input.authorized,
        confirm_create: input.confirmCreate,
        dataset_id: input.datasetId,
        dataset_version_id: input.datasetVersionId,
        export_format: input.exportFormat,
      }),
    },
  );
  return mapAutomationProductDatasetExportJob(response);
}

export async function approveAutomationProductSchedule(
  input: AutomationProductScheduleApproveInput,
): Promise<AutomationProductScheduleApprove> {
  if (mockApiEnabled) {
    return getMockAutomationProductScheduleApprove(input);
  }
  const response = await apiFetch<AutomationProductScheduleApproveResponse>(
    "/api/automation/product-schedule-approve",
    {
      method: "POST",
      body: JSON.stringify({
        authorized: input.authorized,
        dataset_id: input.datasetId,
        dataset_version_id: input.datasetVersionId,
        task_ids: input.taskIds,
        schedule_policy: input.schedulePolicy ?? "auto_freshness",
        schedule_cron: input.scheduleCron?.trim() || null,
        freshness_target_hours: input.freshnessTargetHours ?? 24,
        minimum_completeness_percent: input.minimumCompletenessPercent ?? 80,
        note: input.note,
      }),
    },
  );
  return mapAutomationProductScheduleApprove(response);
}

export async function checkAutomationProductDrift(
  input: AutomationProductDriftCheckInput,
): Promise<AutomationProductDriftCheck> {
  if (mockApiEnabled) {
    return getMockAutomationProductDriftCheck(input);
  }
  const response = await apiFetch<AutomationProductDriftCheckResponse>(
    "/api/automation/product-drift-check",
    {
      method: "POST",
      body: JSON.stringify({
        authorized: input.authorized,
        dataset_id: input.datasetId,
        dataset_version_id: input.datasetVersionId,
        task_ids: input.taskIds,
        completeness_drop_threshold_percent: input.completenessDropThresholdPercent ?? 10,
        freshness_grace_hours: input.freshnessGraceHours ?? 0,
      }),
    },
  );
  return mapAutomationProductDriftCheck(response);
}

export async function saveAutomationProductDriftEvent(
  input: AutomationProductDriftEventSaveInput,
): Promise<AutomationProductDriftEvent> {
  if (mockApiEnabled) {
    return getMockAutomationProductDriftEventSave(input);
  }
  const response = await apiFetch<AutomationProductDriftEventResponse>(
    "/api/automation/product-drift-events",
    {
      method: "POST",
      body: JSON.stringify({
        authorized: input.authorized,
        dataset_id: input.datasetId,
        dataset_version_id: input.datasetVersionId,
        task_ids: input.taskIds,
        completeness_drop_threshold_percent: input.completenessDropThresholdPercent ?? 10,
        freshness_grace_hours: input.freshnessGraceHours ?? 0,
        note: input.note,
      }),
    },
  );
  return mapAutomationProductDriftEvent(response);
}

export async function listAutomationProductDriftEvents(
  input: AutomationProductDriftEventListInput = {},
): Promise<AutomationProductDriftEventList> {
  if (mockApiEnabled) {
    return getMockAutomationProductDriftEvents(input);
  }
  const params = new URLSearchParams();
  if (input.datasetId) {
    params.set("dataset_id", input.datasetId);
  }
  if (input.datasetVersionId) {
    params.set("dataset_version_id", input.datasetVersionId);
  }
  if (input.limit) {
    params.set("limit", String(input.limit));
  }
  const query = params.toString();
  const response = await apiFetch<AutomationProductDriftEventListResponse>(
    `/api/automation/product-drift-events${query ? `?${query}` : ""}`,
  );
  return {
    items: response.items.map(mapAutomationProductDriftEvent),
    total: response.total,
    runStarted: response.run_started,
    alertCreated: response.alert_created,
  };
}

export async function listAutomationProductDatasets(
  input: AutomationProductDatasetListInput = {},
): Promise<AutomationProductDatasetList> {
  if (mockApiEnabled) {
    return getMockAutomationProductDatasets(input);
  }
  const params = new URLSearchParams();
  if (input.projectId) {
    params.set("project_id", input.projectId);
  }
  if (input.limit) {
    params.set("limit", String(input.limit));
  }
  const query = params.toString();
  const response = await apiFetch<AutomationProductDatasetListResponse>(
    `/api/automation/product-datasets${query ? `?${query}` : ""}`,
  );
  return {
    items: response.items.map((item) => ({
      dataset: mapAutomationDataset(item.dataset),
      latestVersion: item.latest_version
        ? mapAutomationDatasetVersion(item.latest_version)
        : null,
      versionCount: item.version_count,
      latestDriftEvent: item.latest_drift_event
        ? mapAutomationProductDriftEvent(item.latest_drift_event)
        : null,
      driftEventCount: item.drift_event_count,
    })),
    total: response.total,
    runStarted: response.run_started,
    alertCreated: response.alert_created,
  };
}

export async function listAutomationProductDatasetVersions(
  input: AutomationProductDatasetVersionListInput,
): Promise<AutomationProductDatasetVersionList> {
  if (mockApiEnabled) {
    return getMockAutomationProductDatasetVersions(input);
  }
  const params = new URLSearchParams();
  if (input.limit) {
    params.set("limit", String(input.limit));
  }
  const query = params.toString();
  const response = await apiFetch<AutomationProductDatasetVersionListResponse>(
    `/api/automation/product-datasets/${input.datasetId}/versions${query ? `?${query}` : ""}`,
  );
  return {
    dataset: mapAutomationDataset(response.dataset),
    versions: response.versions.map(mapAutomationDatasetVersion),
    total: response.total,
    runStarted: response.run_started,
    alertCreated: response.alert_created,
  };
}

export async function listAutomationProductDatasetExports(
  input: AutomationProductDatasetExportListInput,
): Promise<AutomationProductDatasetExportList> {
  if (mockApiEnabled) {
    return getMockAutomationProductDatasetExports(input);
  }
  const params = new URLSearchParams();
  if (input.datasetVersionId) {
    params.set("dataset_version_id", input.datasetVersionId);
  }
  if (input.limit) {
    params.set("limit", String(input.limit));
  }
  const query = params.toString();
  const response = await apiFetch<AutomationProductDatasetExportListResponse>(
    `/api/automation/product-datasets/${input.datasetId}/exports${query ? `?${query}` : ""}`,
  );
  return {
    items: response.items.map(mapAutomationProductDatasetExportJob),
    total: response.total,
    exportCreated: response.export_created,
    runStarted: response.run_started,
  };
}

export function datasetExportDownloadHref(downloadUrl: string) {
  return `${apiBaseUrl}${downloadUrl}`;
}

export async function previewAutomationProductDriftAlertRule(
  input: AutomationProductDriftAlertPreviewInput,
): Promise<AutomationProductDriftAlertPreview> {
  if (mockApiEnabled) {
    return getMockAutomationProductDriftAlertPreview(input);
  }
  const response = await apiFetch<AutomationProductDriftAlertPreviewResponse>(
    "/api/automation/product-drift-alert-preview",
    {
      method: "POST",
      body: JSON.stringify(driftAlertPayload(input)),
    },
  );
  return mapAutomationProductDriftAlertPreview(response);
}

export async function createAutomationProductDriftAlertRule(
  input: AutomationProductDriftAlertRuleCreateInput,
): Promise<AutomationProductDriftAlertRuleCreate> {
  if (mockApiEnabled) {
    return getMockAutomationProductDriftAlertRuleCreate(input);
  }
  const response = await apiFetch<AutomationProductDriftAlertRuleCreateResponse>(
    "/api/automation/product-drift-alert-rules",
    {
      method: "POST",
      body: JSON.stringify({
        ...driftAlertPayload(input),
        confirm_create: input.confirmCreate,
      }),
    },
  );
  return {
    ...mapAutomationProductDriftAlertPreview(response),
    alertRule: {
      id: response.alert_rule.id,
      workspaceId: response.alert_rule.workspace_id,
      projectId: response.alert_rule.project_id,
      name: response.alert_rule.name,
      signalType: response.alert_rule.signal_type,
      condition: response.alert_rule.condition,
      channel: response.alert_rule.channel,
      enabled: response.alert_rule.enabled,
      createdAt: response.alert_rule.created_at,
    },
  };
}

export async function createAutomationProductDriftAlertEvents(
  input: AutomationProductDriftAlertEventCreateInput,
): Promise<AutomationProductDriftAlertEventCreate> {
  if (mockApiEnabled) {
    return getMockAutomationProductDriftAlertEventCreate(input);
  }
  const response = await apiFetch<AutomationProductDriftAlertEventCreateResponse>(
    "/api/automation/product-drift-alert-events",
    {
      method: "POST",
      body: JSON.stringify({
        authorized: input.authorized,
        confirm_create: input.confirmCreate,
        dataset_id: input.datasetId,
        dataset_version_id: input.datasetVersionId,
        drift_event_id: input.driftEventId,
      }),
    },
  );
  return {
    generatedAt: response.generated_at,
    authorizationConfirmed: response.authorization_confirmed,
    dataset: mapAutomationDataset(response.dataset),
    version: mapAutomationDatasetVersion(response.version),
    driftEvent: mapAutomationProductDriftEvent(response.drift_event),
    signal: mapAutomationSignal(response.signal),
    alertEvents: response.alert_events.map(mapAutomationAlertEvent),
    summary: mapAutomationDriftAlertSummary(response.summary),
    blockedReasons: response.blocked_reasons,
  };
}

export async function sendAutomationProductDriftAlertNotifications(
  input: AutomationProductDriftAlertNotificationSendInput,
): Promise<AutomationProductDriftAlertNotificationSend> {
  if (mockApiEnabled) {
    return getMockAutomationProductDriftAlertNotificationSend(input);
  }
  const response = await apiFetch<AutomationProductDriftAlertNotificationSendResponse>(
    "/api/automation/product-drift-alert-notifications",
    {
      method: "POST",
      body: JSON.stringify({
        authorized: input.authorized,
        confirm_send: input.confirmSend,
        dataset_id: input.datasetId,
        dataset_version_id: input.datasetVersionId,
        drift_event_id: input.driftEventId,
        alert_event_ids: input.alertEventIds,
      }),
    },
  );
  return {
    generatedAt: response.generated_at,
    authorizationConfirmed: response.authorization_confirmed,
    dataset: mapAutomationDataset(response.dataset),
    version: mapAutomationDatasetVersion(response.version),
    driftEvent: mapAutomationProductDriftEvent(response.drift_event),
    alertEvents: response.alert_events.map(mapAutomationAlertEvent),
    notifications: response.notifications.map(mapAutomationNotification),
    summary: mapAutomationDriftAlertSummary(response.summary),
    blockedReasons: response.blocked_reasons,
  };
}

export async function sendAutomationProductDriftAlertEmails(
  input: AutomationProductDriftAlertEmailSendInput,
): Promise<AutomationProductDriftAlertEmailSend> {
  if (mockApiEnabled) {
    return getMockAutomationProductDriftAlertEmailSend(input);
  }
  const response = await apiFetch<AutomationProductDriftAlertEmailSendResponse>(
    "/api/automation/product-drift-alert-emails",
    {
      method: "POST",
      body: JSON.stringify({
        authorized: input.authorized,
        confirm_send: input.confirmSend,
        dataset_id: input.datasetId,
        dataset_version_id: input.datasetVersionId,
        drift_event_id: input.driftEventId,
        alert_event_ids: input.alertEventIds,
        recipient_email: input.recipientEmail ?? null,
      }),
    },
  );
  return {
    generatedAt: response.generated_at,
    authorizationConfirmed: response.authorization_confirmed,
    dataset: mapAutomationDataset(response.dataset),
    version: mapAutomationDatasetVersion(response.version),
    driftEvent: mapAutomationProductDriftEvent(response.drift_event),
    alertEvents: response.alert_events.map(mapAutomationAlertEvent),
    emailDeliveries: response.email_deliveries.map((delivery) => ({
      alertEventId: delivery.alert_event_id,
      recipientEmail: delivery.recipient_email,
      delivered: delivery.delivered,
      deliveredAt: delivery.delivered_at,
      reason: delivery.reason,
    })),
    summary: mapAutomationDriftAlertSummary(response.summary),
    blockedReasons: response.blocked_reasons,
  };
}

function driftAlertPayload(input: AutomationProductDriftAlertPreviewInput) {
  return {
    authorized: input.authorized,
    dataset_id: input.datasetId,
    dataset_version_id: input.datasetVersionId ?? null,
    min_status: input.minStatus ?? "critical",
    channel: input.channel ?? "in_app",
    enabled: input.enabled ?? true,
    name: input.name ?? null,
    limit: input.limit ?? 20,
  };
}

function mapAutomationProductDriftAlertPreview(
  response: AutomationProductDriftAlertPreviewResponse,
): AutomationProductDriftAlertPreview {
  return {
    generatedAt: response.generated_at,
    authorizationConfirmed: response.authorization_confirmed,
    dataset: mapAutomationDataset(response.dataset),
    latestVersion: response.latest_version
      ? mapAutomationDatasetVersion(response.latest_version)
      : null,
    ruleDraft: {
      name: response.rule_draft.name,
      projectId: response.rule_draft.project_id,
      signalType: response.rule_draft.signal_type,
      condition: response.rule_draft.condition,
      channel: response.rule_draft.channel,
      enabled: response.rule_draft.enabled,
    },
    matchedEvents: response.matched_events.map(mapAutomationProductDriftEvent),
    summary: mapAutomationDriftAlertSummary(response.summary),
    blockedReasons: response.blocked_reasons,
  };
}

function mapAutomationDriftAlertSummary(response: AutomationProductDriftAlertSummaryResponse) {
  return {
    matchedEvents: response.matched_events,
    criticalEvents: response.critical_events,
    warningEvents: response.warning_events,
    alertRuleCreated: response.alert_rule_created,
    signalCreated: response.signal_created,
    alertEventCreated: response.alert_event_created,
    notificationCreated: response.notification_created,
    runStarted: response.run_started,
  };
}

function mapAutomationSignal(response: SignalResponse): Signal {
  return {
    id: response.id,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    entityId: response.entity_id,
    signalType: response.signal_type,
    previousSnapshotId: response.previous_snapshot_id,
    currentSnapshotId: response.current_snapshot_id,
    currentValue: response.current_value,
    previousValue: response.previous_value,
    delta: response.delta,
    deltaRatio: response.delta_ratio,
    confidence: response.confidence,
    severity: response.severity,
    metadata: response.metadata,
    detectedAt: response.detected_at,
  };
}

function mapAutomationAlertEvent(response: AlertEventResponse): AlertEvent {
  return {
    id: response.id,
    ruleId: response.rule_id,
    signalId: response.signal_id,
    status: response.status,
    payload: response.payload,
    triggeredAt: response.triggered_at,
    sentAt: response.sent_at,
  };
}

function mapAutomationNotification(response: NotificationResponse): NotificationItem {
  return {
    id: response.id,
    userId: response.user_id,
    title: response.title,
    body: response.body,
    notificationType: response.notification_type,
    referenceType: response.reference_type,
    referenceId: response.reference_id,
    isRead: response.is_read,
    createdAt: response.created_at,
  };
}

function mapAutomationPlatformPackage(
  response: AutomationPlatformPackageResponse,
): AutomationPlatformPackage {
  return {
    id: response.id,
    name: response.name,
    category: response.category,
    summary: response.summary,
    supportedTargets: response.supported_targets,
    collectorTypes: response.collector_types,
    fieldSchema: response.field_schema.map((field) => ({
      key: field.key,
      label: field.label,
      dataType: field.data_type,
      required: field.required,
      source: field.source,
      cleaningRule: field.cleaning_rule,
    })),
    strategyMatrix: response.strategy_matrix.map((strategy) => ({
      id: strategy.id,
      label: strategy.label,
      entrypoint: strategy.entrypoint,
      collectorType: strategy.collector_type,
      fit: strategy.fit,
      canStartFromAutomation: strategy.can_start_from_automation,
      reviewRequired: strategy.review_required,
      description: strategy.description,
    })),
    riskBoundaries: response.risk_boundaries.map((boundary) => ({
      condition: boundary.condition,
      severity: boundary.severity,
      guidance: boundary.guidance,
    })),
    sopLinks: response.sop_links.map((link) => ({
      label: link.label,
      href: link.href,
    })),
    sampleFixture: {
      fixtureType: response.sample_fixture.fixture_type,
      available: response.sample_fixture.available,
      description: response.sample_fixture.description,
    },
    executionBoundary: response.execution_boundary,
    runStarted: response.run_started,
  };
}

function mapAutomationSiteAnalysis(response: AutomationSiteAnalysisResponse): AutomationSiteAnalysis {
  return {
    requestedUrl: response.requested_url,
    analyzedAt: response.analyzed_at,
    authorizationConfirmed: response.authorization_confirmed,
    platformProfile: {
      platformType: response.platform_profile.platform_type,
      confidence: response.platform_profile.confidence,
      indicators: response.platform_profile.indicators,
      riskLevel: response.platform_profile.risk_level,
    },
    pageStructure: {
      pageType: response.page_structure.page_type,
      title: response.page_structure.title,
      canonicalUrl: response.page_structure.canonical_url,
      scriptCount: response.page_structure.script_count,
      formCount: response.page_structure.form_count,
      imageCount: response.page_structure.image_count,
      productSchemaCount: response.page_structure.product_schema_count,
      sameOriginLinkCount: response.page_structure.same_origin_link_count,
      textSample: response.page_structure.text_sample,
    },
    fieldCandidates: response.field_candidates.map(mapFieldCandidate),
    toolRecommendations: response.tool_recommendations.map(mapToolRecommendation),
    cleaningPlan: response.cleaning_plan.map(mapCleaningStep),
    sourceDraft: {
      type: response.source_draft.type,
      config: response.source_draft.config,
      suggestedName: response.source_draft.suggested_name,
      scheduleCron: response.source_draft.schedule_cron,
    },
    blockedReasons: response.blocked_reasons,
    siteAnalysis: response.site_analysis
      ? mapAutomationSiteAnalysisHistoryItem(response.site_analysis)
      : null,
    extractionPlan: response.extraction_plan
      ? mapAutomationExtractionPlan(response.extraction_plan)
      : null,
    siteAnalysisCreated: response.site_analysis_created,
    extractionPlanCreated: response.extraction_plan_created,
    runStarted: response.run_started,
  };
}

function mapAutomationExtractionPlan(
  response: AutomationExtractionPlanResponse,
): AutomationExtractionPlan {
  return {
    id: response.id,
    siteAnalysisId: response.site_analysis_id,
    projectId: response.project_id,
    name: response.name,
    versionNumber: response.version_number,
    collectorType: response.collector_type,
    selectedFields: response.selected_fields,
    sourceDraft: {
      type: response.source_draft.type,
      config: response.source_draft.config,
      suggestedName: response.source_draft.suggested_name,
      scheduleCron: response.source_draft.schedule_cron,
    },
    scheduleCron: response.schedule_cron,
    status: response.status,
    riskLevel: response.risk_level,
    auditEvents: response.audit_events,
    createdAt: response.created_at,
    runStarted: response.run_started,
  };
}

function mapAutomationSiteAnalysisHistoryItem(
  response: AutomationSiteAnalysisHistoryItemResponse,
): AutomationSiteAnalysisHistoryItem {
  return {
    id: response.id,
    projectId: response.project_id,
    requestedUrl: response.requested_url,
    target: response.target,
    status: response.status,
    platformType: response.platform_type,
    pageType: response.page_type,
    riskLevel: response.risk_level,
    analyzedAt: response.analyzed_at,
    createdAt: response.created_at,
    latestPlan: response.latest_plan ? mapAutomationExtractionPlan(response.latest_plan) : null,
  };
}

function mapAutomationProductDiscovery(
  response: AutomationProductDiscoveryResponse,
): AutomationProductDiscovery {
  return {
    requestedUrl: response.requested_url,
    analyzedAt: response.analyzed_at,
    authorizationConfirmed: response.authorization_confirmed,
    platformProfile: {
      platformType: response.platform_profile.platform_type,
      confidence: response.platform_profile.confidence,
      indicators: response.platform_profile.indicators,
      riskLevel: response.platform_profile.risk_level,
    },
    pageStructure: {
      pageType: response.page_structure.page_type,
      title: response.page_structure.title,
      canonicalUrl: response.page_structure.canonical_url,
      linkCount: response.page_structure.link_count,
      productLinkCount: response.page_structure.product_link_count,
      jsonldUrlCount: response.page_structure.jsonld_url_count,
      sitemapUrlCount: response.page_structure.sitemap_url_count,
      scriptCount: response.page_structure.script_count,
      textSample: response.page_structure.text_sample,
    },
    productCandidates: response.product_candidates.map((candidate) => ({
      url: candidate.url,
      title: candidate.title,
      source: candidate.source,
      confidence: candidate.confidence,
    })),
    toolRecommendations: response.tool_recommendations.map(mapToolRecommendation),
    discoveryPlan: {
      nextCollectorType: response.discovery_plan.next_collector_type,
      candidateCount: response.discovery_plan.candidate_count,
      maxProducts: response.discovery_plan.max_products,
      fanOutRequiresReview: response.discovery_plan.fan_out_requires_review,
    },
    sourceDraft: {
      type: response.source_draft.type,
      config: response.source_draft.config,
      suggestedName: response.source_draft.suggested_name,
      scheduleCron: response.source_draft.schedule_cron,
    },
    blockedReasons: response.blocked_reasons,
  };
}

function mapAutomationProductFanoutPreview(
  response: AutomationProductFanoutPreviewResponse,
): AutomationProductFanoutPreview {
  return {
    requestedParentUrl: response.requested_parent_url,
    analyzedAt: response.analyzed_at,
    authorizationConfirmed: response.authorization_confirmed,
    candidateStatuses: response.candidate_statuses.map((candidate) => ({
      url: candidate.url,
      title: candidate.title,
      source: candidate.source,
      confidence: candidate.confidence,
      status: candidate.status,
      reason: candidate.reason,
    })),
    sourceDrafts: response.source_drafts.map((draft) => ({
      type: draft.type,
      config: draft.config,
      suggestedName: draft.suggested_name,
      scheduleCron: draft.schedule_cron,
    })),
    batchPlan: {
      runMode: response.batch_plan.run_mode,
      nextCollectorType: response.batch_plan.next_collector_type,
      readyCount: response.batch_plan.ready_count,
      blockedCount: response.batch_plan.blocked_count,
      maxSources: response.batch_plan.max_sources,
      fields: response.batch_plan.fields,
      manualReviewRequired: response.batch_plan.manual_review_required,
      executionBoundary: response.batch_plan.execution_boundary,
    },
    blockedReasons: response.blocked_reasons,
  };
}

function mapAutomationProductFanoutCreate(
  response: AutomationProductFanoutCreateResponse,
): AutomationProductFanoutCreate {
  return {
    requestedParentUrl: response.requested_parent_url,
    createdAt: response.created_at,
    authorizationConfirmed: response.authorization_confirmed,
    persistedSources: response.persisted_sources.map((item) => ({
      url: item.url,
      action: item.action,
      source: {
        id: item.source.id,
        projectId: item.source.project_id,
        name: item.source.name,
        type: item.source.type,
        url: item.source.url,
        enabled: item.source.enabled,
        config: item.source.config,
        scheduleCron: item.source.schedule_cron,
        createdAt: item.source.created_at,
        updatedAt: item.source.updated_at,
      },
      task: item.task
        ? {
            id: item.task.id,
            sourceId: item.task.source_id,
            collectorType: item.task.collector_type,
            name: item.task.name,
            status: item.task.status,
            scheduleCron: item.task.schedule_cron,
          }
        : null,
    })),
    candidateStatuses: response.candidate_statuses.map((candidate) => ({
      url: candidate.url,
      title: candidate.title,
      source: candidate.source,
      confidence: candidate.confidence,
      status: candidate.status,
      reason: candidate.reason,
    })),
    summary: {
      createdSources: response.summary.created_sources,
      reusedSources: response.summary.reused_sources,
      enabledTasks: response.summary.enabled_tasks,
      blockedCandidates: response.summary.blocked_candidates,
      runStarted: response.summary.run_started,
    },
    auditEvents: response.audit_events,
    blockedReasons: response.blocked_reasons,
  };
}

function mapAutomationProductBatchRun(
  response: AutomationProductBatchRunResponse,
): AutomationProductBatchRun {
  return {
    createdAt: response.created_at,
    authorizationConfirmed: response.authorization_confirmed,
    items: response.items.map((item) => ({
      taskId: item.task_id,
      taskName: item.task_name,
      sourceId: item.source_id,
      sourceUrl: item.source_url,
      status: item.status,
      blockedReason: item.blocked_reason,
      run: item.run
        ? {
            id: item.run.id,
            taskId: item.run.task_id,
            status: item.run.status,
            recordsCount: item.run.records_count,
            entitiesCount: item.run.entities_count,
            errorMessage: item.run.error_message,
            startedAt: item.run.started_at,
            finishedAt: item.run.finished_at,
          }
        : null,
      recordsCount: item.records_count,
      entitiesCount: item.entities_count,
      fieldCompleteness: item.field_completeness
        ? {
            configuredFields: item.field_completeness.configured_fields,
            extractedFields: item.field_completeness.extracted_fields,
            missingFields: item.field_completeness.missing_fields,
            fieldValues: item.field_completeness.field_values,
            completenessRatio: item.field_completeness.completeness_ratio,
            completenessPercent: item.field_completeness.completeness_percent,
          }
        : null,
      errorMessage: item.error_message,
    })),
    summary: {
      requestedTasks: response.summary.requested_tasks,
      runTasks: response.summary.run_tasks,
      blockedTasks: response.summary.blocked_tasks,
      successfulRuns: response.summary.successful_runs,
      failedRuns: response.summary.failed_runs,
      recordsCount: response.summary.records_count,
      entitiesCount: response.summary.entities_count,
      averageCompletenessPercent: response.summary.average_completeness_percent,
      runStarted: response.summary.run_started,
    },
    auditEvents: response.audit_events,
    blockedReasons: response.blocked_reasons,
  };
}

function mapCleaningRuleRequest(rule: AutomationCleaningRule) {
  return {
    field: rule.field,
    operation: rule.operation,
    value: rule.value,
    description: rule.description,
  };
}

function getMockAutomationCleaningPlanDryRun(
  input: AutomationCleaningPlanInput,
): AutomationCleaningPlanDryRun {
  const selectedFields = input.fields?.length
    ? input.fields
    : ["title", "price", "sku", "canonical_url"];
  const beforeRows = [
    {
      rowId: "mock-run-1:mock-record-1",
      taskRunId: input.taskRunIds[0] ?? "mock-run-1",
      rawRecordId: "mock-record-1",
      sourceUrl: "https://shop.example/products/demo-bag",
      values: {
        title: "Demo Carry Bag",
        price: 129.9,
        sku: "BAG-001",
        canonical_url: "https://shop.example/products/demo-bag",
      },
    },
    {
      rowId: "mock-run-2:mock-record-2",
      taskRunId: input.taskRunIds[1] ?? input.taskRunIds[0] ?? "mock-run-2",
      rawRecordId: "mock-record-2",
      sourceUrl: "https://shop.example/products/weekend-tote",
      values: {
        title: "Weekend Tote",
        price: null,
        sku: null,
        canonical_url: "https://shop.example/products/weekend-tote",
      },
    },
  ];
  const rows = beforeRows.map((row) => {
    const beforeValues = Object.fromEntries(
      selectedFields.map((field) => [field, row.values[field as keyof typeof row.values] ?? null]),
    );
    const afterValues: Record<string, unknown> = { ...beforeValues };
    for (const rule of input.rules) {
      if (rule.operation === "fill_default" && !afterValues[rule.field]) {
        afterValues[rule.field] = rule.value ?? null;
      }
      if (rule.operation === "strip_text" && typeof afterValues[rule.field] === "string") {
        afterValues[rule.field] = String(afterValues[rule.field]).trim().replace(/\s+/g, " ");
      }
    }
    const changedFields = selectedFields.filter((field) => beforeValues[field] !== afterValues[field]);
    return {
      rowId: row.rowId,
      taskRunId: row.taskRunId,
      rawRecordId: row.rawRecordId,
      sourceUrl: row.sourceUrl,
      beforeValues,
      afterValues,
      missingFieldsBefore: selectedFields.filter((field) => !beforeValues[field]),
      missingFieldsAfter: selectedFields.filter((field) => !afterValues[field]),
      changedFields,
    };
  });
  return {
    createdAt: new Date().toISOString(),
    authorizationConfirmed: input.authorized,
    rows,
    summary: {
      rowsCount: rows.length,
      rowsChanged: rows.filter((row) => row.changedFields.length > 0).length,
      rulesCount: input.rules.length,
      selectedFields,
      datasetVersionCreated: false,
      cleaningPlanCreated: false,
      runStarted: false,
    },
    cleaningScript: input.rules.map((rule) =>
      rule.operation === "fill_default"
        ? `fill ${rule.field} with default value ${rule.value}`
        : `${rule.operation} ${rule.field}`,
    ),
    exportPreview: {
      format: "json",
      schema: { fields: selectedFields, primary_key: "canonical_url" },
      rows: rows.map((row) => row.afterValues),
    },
    auditEvents: [{ event: "mock_cleaning_plan_dry-run_requested" }],
    blockedReasons: ["CleaningPlan dry-run 只转换样本行，不会保存 DatasetVersion。"],
  };
}

function mapAutomationProductDatasetPreview(
  response: AutomationProductDatasetPreviewResponse,
): AutomationProductDatasetPreview {
  return {
    createdAt: response.created_at,
    authorizationConfirmed: response.authorization_confirmed,
    rows: response.rows.map((row) => ({
      rowId: row.row_id,
      taskRunId: row.task_run_id,
      rawRecordId: row.raw_record_id,
      sourceUrl: row.source_url,
      values: row.values,
      missingFields: row.missing_fields,
      completenessPercent: row.completeness_percent,
    })),
    summary: {
      requestedRuns: response.summary.requested_runs,
      matchedRuns: response.summary.matched_runs,
      rowsCount: response.summary.rows_count,
      selectedFields: response.summary.selected_fields,
      averageCompletenessPercent: response.summary.average_completeness_percent,
      exportFormat: response.summary.export_format,
      exportReady: response.summary.export_ready,
    },
    cleaningScriptDraft: response.cleaning_script_draft,
    exportPreview: response.export_preview,
    auditEvents: response.audit_events,
    blockedReasons: response.blocked_reasons,
  };
}

function mapAutomationCleaningPlanDryRun(
  response: AutomationCleaningPlanDryRunResponse,
): AutomationCleaningPlanDryRun {
  return {
    createdAt: response.created_at,
    authorizationConfirmed: response.authorization_confirmed,
    rows: response.rows.map((row) => ({
      rowId: row.row_id,
      taskRunId: row.task_run_id,
      rawRecordId: row.raw_record_id,
      sourceUrl: row.source_url,
      beforeValues: row.before_values,
      afterValues: row.after_values,
      missingFieldsBefore: row.missing_fields_before,
      missingFieldsAfter: row.missing_fields_after,
      changedFields: row.changed_fields,
    })),
    summary: {
      rowsCount: response.summary.rows_count,
      rowsChanged: response.summary.rows_changed,
      rulesCount: response.summary.rules_count,
      selectedFields: response.summary.selected_fields,
      datasetVersionCreated: response.summary.dataset_version_created,
      cleaningPlanCreated: response.summary.cleaning_plan_created,
      runStarted: response.summary.run_started,
    },
    cleaningScript: response.cleaning_script,
    exportPreview: response.export_preview,
    auditEvents: response.audit_events,
    blockedReasons: response.blocked_reasons,
  };
}

function mapAutomationCleaningPlan(
  response: AutomationCleaningPlanResponse,
): AutomationCleaningPlanCreate["cleaningPlan"] {
  return {
    id: response.id,
    projectId: response.project_id,
    name: response.name,
    versionNumber: response.version_number,
    target: response.target,
    selectedFields: response.selected_fields,
    sourceTaskRunIds: response.source_task_run_ids,
    rules: response.rules,
    cleaningScript: response.cleaning_script,
    dryRunPreview: response.dry_run_preview,
    status: response.status,
    createdAt: response.created_at,
  };
}

function mapAutomationCleaningPlanCreate(
  response: AutomationCleaningPlanCreateResponse,
): AutomationCleaningPlanCreate {
  return {
    savedAt: response.saved_at,
    authorizationConfirmed: response.authorization_confirmed,
    cleaningPlan: mapAutomationCleaningPlan(response.cleaning_plan),
    dryRun: mapAutomationCleaningPlanDryRun(response.dry_run),
    cleaningPlanCreated: response.cleaning_plan_created,
    datasetVersionCreated: response.dataset_version_created,
    runStarted: response.run_started,
    auditEvents: response.audit_events,
    blockedReasons: response.blocked_reasons,
  };
}

function mapAutomationProductDatasetSave(
  response: AutomationProductDatasetSaveResponse,
): AutomationProductDatasetSave {
  return {
    savedAt: response.saved_at,
    authorizationConfirmed: response.authorization_confirmed,
    dataset: {
      id: response.dataset.id,
      projectId: response.dataset.project_id,
      name: response.dataset.name,
      datasetType: response.dataset.dataset_type,
      status: response.dataset.status,
      description: response.dataset.description,
    },
    version: {
      id: response.version.id,
      datasetId: response.version.dataset_id,
      cleaningPlanId: response.version.cleaning_plan_id,
      versionNumber: response.version.version_number,
      sourceTaskRunIds: response.version.source_task_run_ids,
      selectedFields: response.version.selected_fields,
      cleaningScript: response.version.cleaning_script,
      rowCount: response.version.row_count,
      averageCompletenessPercent: response.version.average_completeness_percent,
      status: response.version.status,
      createdAt: response.version.created_at,
      exportPreview: response.version.export_preview,
    },
    auditEvents: response.audit_events,
    blockedReasons: response.blocked_reasons,
  };
}

function mapAutomationProductScheduleApprove(
  response: AutomationProductScheduleApproveResponse,
): AutomationProductScheduleApprove {
  return {
    approvedAt: response.approved_at,
    authorizationConfirmed: response.authorization_confirmed,
    dataset: {
      id: response.dataset.id,
      projectId: response.dataset.project_id,
      name: response.dataset.name,
      datasetType: response.dataset.dataset_type,
      status: response.dataset.status,
      description: response.dataset.description,
    },
    version: {
      id: response.version.id,
      datasetId: response.version.dataset_id,
      cleaningPlanId: response.version.cleaning_plan_id,
      versionNumber: response.version.version_number,
      sourceTaskRunIds: response.version.source_task_run_ids,
      selectedFields: response.version.selected_fields,
      cleaningScript: response.version.cleaning_script,
      rowCount: response.version.row_count,
      averageCompletenessPercent: response.version.average_completeness_percent,
      status: response.version.status,
      createdAt: response.version.created_at,
      exportPreview: response.version.export_preview,
    },
    approvedTasks: response.approved_tasks.map((task) => ({
      taskId: task.task_id,
      taskName: task.task_name,
      status: task.status,
      scheduleCron: task.schedule_cron,
      schedulePolicy: task.schedule_policy,
      freshnessTargetHours: task.freshness_target_hours,
      datasetId: task.dataset_id,
      datasetVersionId: task.dataset_version_id,
      approvedAt: task.approved_at,
    })),
    blockedTasks: response.blocked_tasks.map((task) => ({
      taskId: task.task_id,
      reason: task.reason,
    })),
    summary: {
      requestedTasks: response.summary.requested_tasks,
      approvedTasks: response.summary.approved_tasks,
      blockedTasks: response.summary.blocked_tasks,
      runStarted: response.summary.run_started,
    },
    auditEvents: response.audit_events,
    blockedReasons: response.blocked_reasons,
  };
}

function mapAutomationProductDriftCheck(
  response: AutomationProductDriftCheckResponse,
): AutomationProductDriftCheck {
  return {
    checkedAt: response.checked_at,
    authorizationConfirmed: response.authorization_confirmed,
    dataset: {
      id: response.dataset.id,
      projectId: response.dataset.project_id,
      name: response.dataset.name,
      datasetType: response.dataset.dataset_type,
      status: response.dataset.status,
      description: response.dataset.description,
    },
    version: {
      id: response.version.id,
      datasetId: response.version.dataset_id,
      cleaningPlanId: response.version.cleaning_plan_id,
      versionNumber: response.version.version_number,
      sourceTaskRunIds: response.version.source_task_run_ids,
      selectedFields: response.version.selected_fields,
      cleaningScript: response.version.cleaning_script,
      rowCount: response.version.row_count,
      averageCompletenessPercent: response.version.average_completeness_percent,
      status: response.version.status,
      createdAt: response.version.created_at,
      exportPreview: response.version.export_preview,
    },
    items: response.items.map((item) => ({
      taskId: item.task_id,
      taskName: item.task_name,
      sourceUrl: item.source_url,
      status: item.status,
      blockedReason: item.blocked_reason,
      latestRunId: item.latest_run_id,
      latestRunStatus: item.latest_run_status,
      datasetVersionCompletenessPercent: item.dataset_version_completeness_percent,
      latestCompletenessPercent: item.latest_completeness_percent,
      completenessDropPercent: item.completeness_drop_percent,
      missingFields: item.missing_fields,
      newMissingFields: item.new_missing_fields,
      freshnessTargetHours: item.freshness_target_hours,
      staleHours: item.stale_hours,
      issues: item.issues,
    })),
    summary: {
      requestedTasks: response.summary.requested_tasks,
      checkedTasks: response.summary.checked_tasks,
      blockedTasks: response.summary.blocked_tasks,
      warningTasks: response.summary.warning_tasks,
      criticalTasks: response.summary.critical_tasks,
      staleTasks: response.summary.stale_tasks,
      missingFieldTasks: response.summary.missing_field_tasks,
      runStarted: response.summary.run_started,
      alertCreated: response.summary.alert_created,
    },
    auditEvents: response.audit_events,
    blockedReasons: response.blocked_reasons,
  };
}

function mapAutomationProductDriftEvent(
  response: AutomationProductDriftEventResponse,
): AutomationProductDriftEvent {
  return {
    id: response.id,
    createdAt: response.created_at,
    dataset: {
      id: response.dataset.id,
      projectId: response.dataset.project_id,
      name: response.dataset.name,
      datasetType: response.dataset.dataset_type,
      status: response.dataset.status,
      description: response.dataset.description,
    },
    version: {
      id: response.version.id,
      datasetId: response.version.dataset_id,
      cleaningPlanId: response.version.cleaning_plan_id,
      versionNumber: response.version.version_number,
      sourceTaskRunIds: response.version.source_task_run_ids,
      selectedFields: response.version.selected_fields,
      cleaningScript: response.version.cleaning_script,
      rowCount: response.version.row_count,
      averageCompletenessPercent: response.version.average_completeness_percent,
      status: response.version.status,
      createdAt: response.version.created_at,
      exportPreview: response.version.export_preview,
    },
    eventType: response.event_type,
    status: response.status,
    thresholds: response.thresholds,
    summary: {
      requestedTasks: response.summary.requested_tasks,
      checkedTasks: response.summary.checked_tasks,
      blockedTasks: response.summary.blocked_tasks,
      warningTasks: response.summary.warning_tasks,
      criticalTasks: response.summary.critical_tasks,
      staleTasks: response.summary.stale_tasks,
      missingFieldTasks: response.summary.missing_field_tasks,
      runStarted: response.summary.run_started,
      alertCreated: response.summary.alert_created,
    },
    items: response.items.map((item) => ({
      taskId: item.task_id,
      taskName: item.task_name,
      sourceUrl: item.source_url,
      status: item.status,
      blockedReason: item.blocked_reason,
      latestRunId: item.latest_run_id,
      latestRunStatus: item.latest_run_status,
      datasetVersionCompletenessPercent: item.dataset_version_completeness_percent,
      latestCompletenessPercent: item.latest_completeness_percent,
      completenessDropPercent: item.completeness_drop_percent,
      missingFields: item.missing_fields,
      newMissingFields: item.new_missing_fields,
      freshnessTargetHours: item.freshness_target_hours,
      staleHours: item.stale_hours,
      issues: item.issues,
    })),
    auditEvents: response.audit_events,
    note: response.note,
    runStarted: response.run_started,
    alertCreated: response.alert_created,
  };
}

function mapAutomationDataset(
  response: AutomationProductDatasetSaveResponse["dataset"],
) {
  return {
    id: response.id,
    projectId: response.project_id,
    name: response.name,
    datasetType: response.dataset_type,
    status: response.status,
    description: response.description,
  };
}

function mapAutomationDatasetVersion(
  response: AutomationProductDatasetSaveResponse["version"],
) {
  return {
    id: response.id,
    datasetId: response.dataset_id,
    cleaningPlanId: response.cleaning_plan_id,
    versionNumber: response.version_number,
    sourceTaskRunIds: response.source_task_run_ids,
    selectedFields: response.selected_fields,
    cleaningScript: response.cleaning_script,
    rowCount: response.row_count,
    averageCompletenessPercent: response.average_completeness_percent,
    status: response.status,
    createdAt: response.created_at,
    exportPreview: response.export_preview,
  };
}

function mapAutomationProductDatasetExportJob(
  response: AutomationProductDatasetExportJobResponse,
): AutomationProductDatasetExportJob {
  return {
    id: response.id,
    dataset: mapAutomationDataset(response.dataset),
    version: mapAutomationDatasetVersion(response.version),
    exportFormat: response.export_format,
    status: response.status,
    filename: response.filename,
    contentType: response.content_type,
    artifactSizeBytes: response.artifact_size_bytes,
    rowCount: response.row_count,
    checksumSha256: response.checksum_sha256,
    errorMessage: response.error_message,
    createdAt: response.created_at,
    finishedAt: response.finished_at,
    downloadUrl: response.download_url,
    auditEvents: response.audit_events,
    blockedReasons: response.blocked_reasons,
  };
}

function mapFieldCandidate(
  response: AutomationFieldCandidateResponse,
): AutomationFieldCandidate {
  return {
    key: response.key,
    label: response.label,
    value: response.value,
    dataType: response.data_type,
    source: response.source,
    confidence: response.confidence,
    selected: response.selected,
    cleaningRule: response.cleaning_rule,
  };
}

function mapToolRecommendation(
  response: AutomationToolRecommendationResponse,
): AutomationToolRecommendation {
  return {
    tool: response.tool,
    collectorType: response.collector_type,
    fit: response.fit,
    riskLevel: response.risk_level,
    reason: response.reason,
  };
}

function mapCleaningStep(response: AutomationCleaningStepResponse): AutomationCleaningStep {
  return {
    field: response.field,
    operation: response.operation,
    description: response.description,
  };
}
