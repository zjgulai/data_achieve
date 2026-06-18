import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import {
  getMockAutomationProductFanoutCreate,
  getMockAutomationProductFanoutPreview,
  getMockAutomationProductBatchRun,
  getMockAutomationProductDatasetPreview,
  getMockAutomationProductDatasetSave,
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
  getMockAutomationSiteAnalysis,
} from "@/lib/api/mock";
import type {
  AutomationCleaningStep,
  AutomationFieldCandidate,
  AutomationProductDiscovery,
  AutomationProductDiscoveryInput,
  AutomationProductBatchRun,
  AutomationProductBatchRunInput,
  AutomationProductDatasetPreview,
  AutomationProductDatasetPreviewInput,
  AutomationProductDatasetSave,
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
  AutomationSiteAnalysis,
  AutomationSiteAnalysisInput,
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
  source_draft: {
    type: string;
    config: Record<string, unknown>;
    suggested_name: string;
    schedule_cron: string | null;
  };
  blocked_reasons: string[];
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

export async function analyzeAutomationSite(
  input: AutomationSiteAnalysisInput,
): Promise<AutomationSiteAnalysis> {
  if (mockApiEnabled) {
    return getMockAutomationSiteAnalysis(input.url);
  }
  const response = await apiFetch<AutomationSiteAnalysisResponse>("/api/automation/site-analysis", {
    method: "POST",
    body: JSON.stringify({
      url: input.url,
      authorized: input.authorized,
      target: input.target ?? "ecommerce_product",
      fields: input.fields,
    }),
  });
  return mapAutomationSiteAnalysis(response);
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
      }),
    },
  );
  return mapAutomationProductDatasetSave(response);
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
