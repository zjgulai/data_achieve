import { apiBaseUrl, apiFetch, mockApiEnabled } from "@/lib/api/client";
import {
  getMockAutomationProductFanoutCreate,
  getMockAutomationProductFanoutPreview,
  getMockAutomationProductBatchRun,
  getMockAutomationProductDatasetPreview,
  getMockAutomationGitHubToolDatasetPreview,
  getMockAutomationProductDatasetSave,
  getMockAutomationGitHubToolDatasetSave,
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
  getMockAutomationGitHubToolDriftCheck,
  getMockAutomationProductDriftEvents,
  getMockAutomationProductDriftEventSave,
  getMockAutomationProductScheduleApprove,
  getMockAutomationCapabilityProbes,
  getMockAutomationPlatformPackages,
  getMockAutomationSiteAnalysis,
} from "@/lib/api/mock";
import type {
  AutomationCleaningPlanCreate,
  AutomationCleaningPlanCreateInput,
  AutomationCleaningPlanDryRun,
  AutomationCleaningPlanInput,
  AutomationCleaningRule,
  AutomationBrowserAutomationPlan,
  AutomationBrowserAutomationPlanInput,
  AutomationBrowserDiagnosticJob,
  AutomationBrowserDiagnosticJobCreateInput,
  AutomationBrowserDiagnosticJobList,
  AutomationBrowserExecutorContract,
  AutomationBrowserExecutorContractInput,
  AutomationBrowserExecutorReadinessCheck,
  AutomationBrowserLocalRunnerInput,
  AutomationBrowserLocalRunnerResult,
  AutomationBrowserLocalRunnerResultList,
  AutomationBrowserDiagnosticRun,
  AutomationBrowserDiagnosticRunList,
  AutomationBrowserExecutableSpecCheck,
  AutomationBrowserExecutableSpecDryRun,
  AutomationBrowserExecutableSpecDryRunInput,
  AutomationBrowserExecutableSpecDryRunSummary,
  AutomationCleaningStep,
  AutomationCapabilityProbe,
  AutomationCapabilityProbeList,
  AutomationFieldCandidate,
  AutomationGitHubToolReport,
  AutomationGitHubToolReportAsset,
  AutomationGitHubToolReportAssetInput,
  AutomationGitHubToolReportInput,
  AutomationPublicContentReport,
  AutomationPublicContentReportAsset,
  AutomationPublicContentReportAssetInput,
  AutomationPublicContentReportInput,
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
import type { Report } from "@/types/report";
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
  default_entrypoint: "product-discovery" | "site-analysis" | "sop-import" | "source-create" | "preflight";
  sample_urls: Array<{
    label: string;
    entrypoint: "product-discovery" | "site-analysis" | "sop-import" | "source-create" | "preflight";
    url: string;
    description: string;
  }>;
  cleaning_rules: Array<{
    field: string;
    operation:
      | "strip_text"
      | "parse_decimal"
      | "normalize_url"
      | "uppercase"
      | "normalize_availability"
      | "fill_default";
    value?: string | number | boolean | null;
    description: string;
  }>;
  operator_checklist: string[];
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

type AutomationCapabilityProbeBackendCandidateResponse = {
  backend_id: string;
  label: string;
  priority: number;
  status:
    | "available"
    | "missing_tool"
    | "not_configured"
    | "requires_login"
    | "requires_proxy"
    | "manual_review"
    | "blocked"
    | "unknown";
  credential_mode: "none" | "token" | "cookie" | "browser_profile" | "manual_export" | "unknown";
  requires_login: boolean;
  requires_proxy: boolean;
  evidence_level:
    | "L0-unverified"
    | "L1-repo-or-runtime"
    | "L2-fixture-or-dry-run"
    | "L3-production-read-only"
    | "L4-authorized-live";
  notes: string[];
};

type AutomationAgentReachChannelProbeResponse = {
  schema_version: "agent_reach_channel_probe.v1";
  installed: boolean;
  command_path: string | null;
  doctor_status:
    | "available"
    | "missing_tool"
    | "not_configured"
    | "requires_login"
    | "requires_proxy"
    | "blocked"
    | "unknown";
  active_backend: string | null;
  requires_login: boolean;
  requires_proxy: boolean;
  blocked_reason: string | null;
  platforms: string[];
  read_invoked: boolean;
  search_invoked: boolean;
  raw_summary: Record<string, unknown>;
};

type AutomationCapabilityProbeResponse = {
  schema_version: "capability_probe.v1";
  platform_id: string;
  platform_label: string;
  generated_at: string;
  doctor_status:
    | "available"
    | "missing_tool"
    | "not_configured"
    | "requires_login"
    | "requires_proxy"
    | "manual_review"
    | "blocked"
    | "unknown";
  credential_mode: "none" | "token" | "cookie" | "browser_profile" | "manual_export" | "unknown";
  execution_boundary: "executable" | "read_only_probe" | "import_only" | "sop_only" | "blocked";
  risk_level: "low" | "medium" | "high";
  backend_candidates: AutomationCapabilityProbeBackendCandidateResponse[];
  agent_reach: AutomationAgentReachChannelProbeResponse | null;
  allowed_outputs: string[];
  forbidden_actions: string[];
  next_actions: string[];
  run_started: boolean;
  collection_resources_written: boolean;
};

type AutomationCapabilityProbeListResponse = {
  schema_version: "capability_probe_list.v1";
  generated_at: string;
  items: AutomationCapabilityProbeResponse[];
  total: number;
  run_started: boolean;
  collection_resources_written: boolean;
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

type AutomationBrowserAutomationPlanResponse = {
  site_analysis: AutomationSiteAnalysisHistoryItemResponse;
  extraction_plan: AutomationExtractionPlanResponse;
  browser_diagnostic: AutomationBrowserDiagnosticRunResponse;
  site_analysis_created: boolean;
  extraction_plan_created: boolean;
  browser_diagnostic_created: boolean;
  run_started: boolean;
};

type AutomationBrowserDiagnosticRunResponse = {
  id: string;
  project_id: string;
  site_analysis_id: string | null;
  requested_url: string;
  final_url: string;
  status: string;
  authorization_confirmed: boolean;
  schema_version: string;
  recommended_path: string;
  confidence: number;
  field_stability: string | null;
  evidence_source: string;
  screenshot_path: string | null;
  run_policy: Record<string, unknown>;
  page_summary: Record<string, unknown>;
  network_summary: Record<string, unknown>;
  accessibility_summary: Record<string, unknown>;
  risk_flags: Array<Record<string, unknown>>;
  extraction_strategy: Record<string, unknown>;
  blocked_reasons: string[];
  created_at: string;
  run_started: boolean;
};

type AutomationBrowserDiagnosticRunListResponse = {
  items: AutomationBrowserDiagnosticRunResponse[];
  total: number;
  run_started: boolean;
};

type AutomationBrowserExecutableSpecCheckResponse = {
  key: string;
  label: string;
  status: "passed" | "review" | "blocked";
  message: string;
  evidence: Record<string, unknown>;
};

type AutomationBrowserExecutableSpecDryRunSummaryResponse = {
  status: "ready" | "review" | "blocked";
  total_checks: number;
  passed_checks: number;
  review_checks: number;
  blocked_checks: number;
  selector_count: number;
  wait_condition_count: number;
  api_candidate_count: number;
  manual_review_required: boolean;
  can_dry_run_after_review: boolean;
  write_allowed: boolean;
  run_started: boolean;
};

type AutomationBrowserExecutableSpecDryRunResponse = {
  site_analysis: AutomationSiteAnalysisHistoryItemResponse;
  extraction_plan: AutomationExtractionPlanResponse;
  browser_diagnostic: AutomationBrowserDiagnosticRunResponse | null;
  summary: AutomationBrowserExecutableSpecDryRunSummaryResponse;
  checks: AutomationBrowserExecutableSpecCheckResponse[];
  executable_spec: Record<string, unknown>;
  blocked_reasons: string[];
  audit_events: Array<Record<string, unknown>>;
  run_started: boolean;
};

type AutomationBrowserDiagnosticJobResponse = {
  id: string;
  project_id: string;
  site_analysis_id: string;
  extraction_plan_id: string;
  browser_diagnostic_run_id: string;
  requested_url: string;
  final_url: string;
  status: string;
  authorization_confirmed: boolean;
  runner: string;
  execution_mode: string;
  selector_scope: Array<Record<string, unknown>>;
  wait_policy: Array<Record<string, unknown>>;
  network_observation_policy: Record<string, unknown>;
  artifact_policy: Record<string, unknown>;
  safety_flags: string[];
  dry_run_summary: Record<string, unknown>;
  executable_spec_snapshot: Record<string, unknown>;
  blocked_reasons: string[];
  audit_events: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
  cancelled_at: string | null;
  run_started: boolean;
};

type AutomationBrowserDiagnosticJobListResponse = {
  items: AutomationBrowserDiagnosticJobResponse[];
  total: number;
  run_started: boolean;
};

type AutomationBrowserExecutorReadinessCheckResponse = {
  key: string;
  label: string;
  status: "passed" | "review" | "blocked";
  message: string;
  evidence: Record<string, unknown>;
};

type AutomationBrowserExecutorContractResponse = {
  job: AutomationBrowserDiagnosticJobResponse;
  adapter: Record<string, unknown>;
  runtime_isolation: Record<string, unknown>;
  artifact_retention_policy: Record<string, unknown>;
  allowed_actions: string[];
  denied_actions: string[];
  readiness_checks: AutomationBrowserExecutorReadinessCheckResponse[];
  blocked_reasons: string[];
  audit_events: Array<Record<string, unknown>>;
  run_started: boolean;
  execution_started: boolean;
};

type AutomationBrowserLocalRunnerResultResponse = {
  id: string;
  job: AutomationBrowserDiagnosticJobResponse;
  status: string;
  runner: string;
  run_mode: string;
  contract_snapshot: Record<string, unknown>;
  artifact_manifest: Record<string, unknown>;
  selector_results: Array<Record<string, unknown>>;
  selector_evaluations: Array<Record<string, unknown>>;
  preview_rows: Array<Record<string, unknown>>;
  network_observation_summary: Record<string, unknown>;
  network_metadata_summary: Record<string, unknown>;
  error_summary: Record<string, unknown>;
  promotion_gate: Record<string, unknown>;
  redaction_summary: Record<string, unknown>;
  blocked_reasons: string[];
  audit_events: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
  started_at: string;
  finished_at: string;
  execution_started: boolean;
  browser_started: boolean;
  files_written: boolean;
  collection_resources_written: boolean;
};

type AutomationBrowserLocalRunnerResultListResponse = {
  items: AutomationBrowserLocalRunnerResultResponse[];
  total: number;
  browser_started: boolean;
  files_written: boolean;
  collection_resources_written: boolean;
};

type AutomationProductCandidateResponse = {
  url: string;
  title: string | null;
  source: string;
  confidence: number;
  canonical_url: string;
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
    pagination_url_count: number;
    duplicate_url_count: number;
    skipped_url_count: number;
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
    pagination_urls: string[];
    dedupe_summary: {
      input_url_count: number;
      canonical_candidate_count: number;
      duplicate_url_count: number;
      skipped_url_count: number;
      skipped_reasons: string[];
    };
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
    row_change: "unchanged" | "added" | "removed" | "mixed";
    added_row_count: number;
    removed_row_count: number;
    price_change_percent: number | null;
    freshness_target_hours: number | null;
    stale_hours: number | null;
    issues: string[];
    signal_groups: Record<string, string[]>;
  }>;
  summary: {
    requested_tasks: number;
    checked_tasks: number;
    blocked_tasks: number;
    warning_tasks: number;
    critical_tasks: number;
    stale_tasks: number;
    missing_field_tasks: number;
    added_rows: number;
    removed_rows: number;
    price_changed_tasks: number;
    drift_layers: Record<string, number>;
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

type AutomationGitHubToolReportResponse = {
  generated_at: string;
  authorization_confirmed: boolean;
  dataset: AutomationProductDatasetSaveResponse["dataset"];
  version: AutomationProductDatasetSaveResponse["version"];
  summary: {
    repository_count: number;
    total_stars: number;
    high_value_repositories: number;
    licensed_repositories: number;
    release_tagged_repositories: number;
    readme_documented_repositories: number;
    issue_active_repositories: number;
    fresh_commit_repositories: number;
    archived_repositories: number;
    fork_repositories: number;
    languages: Record<string, number>;
    top_topics: Record<string, number>;
    report_created: boolean;
    run_started: boolean;
  };
  top_repositories: Array<{
    repo_full_name: string;
    html_url: string | null;
    description: string | null;
    stars: number;
    forks: number | null;
    open_issues: number | null;
    watchers: number | null;
    language: string | null;
    topics: string[];
    license_spdx_id: string | null;
    default_branch: string | null;
    latest_release_tag: string | null;
    latest_release_published_at: string | null;
    archived: boolean | null;
    fork: boolean | null;
    updated_at: string | null;
    pushed_at: string | null;
    readme_detected: boolean | null;
    readme_html_url: string | null;
    readme_size: number | null;
    issue_activity_open_count: number | null;
    issue_activity_status: string | null;
    commit_freshness_days: number | null;
    commit_freshness_status: string | null;
    maintenance_risk: "low" | "medium" | "high" | "unknown";
    risk_signals: string[];
    install_sources: string[];
    recommended_use_cases: string[];
    unsuitable_boundaries: string[];
  }>;
  recommendations: string[];
  risk_sections: Array<{
    title: string;
    items: string[];
    evidence_fields?: string[];
  }>;
  audit_events: Array<Record<string, unknown>>;
  blocked_reasons: string[];
};

type ReportResponse = {
  id: string;
  workspace_id: string;
  project_id: string | null;
  report_type: string;
  title: string;
  content: string;
  status: string;
  period_start: string;
  period_end: string;
  created_at: string;
};

type AutomationGitHubToolReportAssetResponse = AutomationGitHubToolReportResponse & {
  report: ReportResponse;
  notification_created: boolean;
};

type AutomationPublicContentReportResponse = {
  generated_at: string;
  authorization_confirmed: boolean;
  dataset: AutomationProductDatasetSaveResponse["dataset"];
  version: AutomationProductDatasetSaveResponse["version"];
  summary: {
    entry_count: number;
    feed_count: number;
    unique_author_count: number;
    tagged_entry_count: number;
    entries_with_summary: number;
    content_hash_count: number;
    report_created: boolean;
    run_started: boolean;
  };
  latest_entries: Array<{
    title: string | null;
    link: string | null;
    feed_url: string | null;
    feed_title: string | null;
    published_at: string | null;
    updated_at: string | null;
    author: string | null;
    tags: string[];
    summary: string | null;
    content_hash: string | null;
  }>;
  recommendations: string[];
  risk_sections: Array<{
    title: string;
    items: string[];
    evidence_fields?: string[];
  }>;
  audit_events: Array<Record<string, unknown>>;
  blocked_reasons: string[];
};

type AutomationPublicContentReportAssetResponse = AutomationPublicContentReportResponse & {
  report: ReportResponse;
  notification_created: boolean;
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

export async function listAutomationCapabilityProbes(input: {
  platformId?: string;
} = {}): Promise<AutomationCapabilityProbeList> {
  if (mockApiEnabled) {
    const list = getMockAutomationCapabilityProbes();
    const items = input.platformId
      ? list.items.filter((item) => item.platformId === input.platformId)
      : list.items;
    return {
      ...list,
      items,
      total: items.length,
    };
  }
  const params = new URLSearchParams();
  if (input.platformId) {
    params.set("platform_id", input.platformId);
  }
  const query = params.toString();
  const response = await apiFetch<AutomationCapabilityProbeListResponse>(
    `/api/automation/capability-probes${query ? `?${query}` : ""}`,
  );
  return {
    schemaVersion: response.schema_version,
    generatedAt: response.generated_at,
    items: response.items.map(mapAutomationCapabilityProbe),
    total: response.total,
    runStarted: response.run_started,
    collectionResourcesWritten: response.collection_resources_written,
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

export async function saveAutomationBrowserAutomationPlan(
  input: AutomationBrowserAutomationPlanInput,
): Promise<AutomationBrowserAutomationPlan> {
  const selectedFields = input.fieldContract.fields
    .filter((field) => field.selected)
    .map((field) => field.key);
  if (mockApiEnabled) {
    const now = new Date().toISOString();
    const planId = `mock-browser-plan-${now}`;
    const siteAnalysisId = `mock-browser-analysis-${now}`;
    const extractionPlan: AutomationExtractionPlan = {
      id: planId,
      siteAnalysisId,
      projectId: input.projectId,
      name: input.name ?? "Browser Automation: mock",
      versionNumber: 1,
      collectorType: "browser_automation",
      selectedFields,
      sourceDraft: {
        type: "browser_automation",
        suggestedName: input.name ?? "Browser Automation: mock",
        scheduleCron: null,
        config: {
          start_url: input.browserDiagnostic.finalUrl,
          requested_url: input.requestedUrl,
          runner: input.runner,
          execution_mode: input.executionMode,
          fields: selectedFields,
          field_contract: input.fieldContract,
          browser_diagnostic: input.browserDiagnostic,
          browser_diagnostic_run_id: "mock-browser-diagnostic-run",
          executable_spec: {
            schema_version: "browser_automation_executable_spec.v1",
            status: "draft",
            run_started: false,
            manual_review_required: input.riskLevel !== "low",
            selector_contract: selectedFields.map((field) => ({ field })),
            wait_conditions: [{ type: "domcontentloaded", timeout_seconds: 15 }],
            pagination_hypothesis: { strategy: "not_configured", review_required: true },
            api_candidates: input.apiCandidates,
            dry_run_limits: { max_pages: 1, max_records: 20, write_allowed: false },
            guardrails: input.guardrails,
          },
          api_candidates: input.apiCandidates,
          guardrails: input.guardrails,
          run_started: false,
        },
      },
      scheduleCron: null,
      status: "draft",
      riskLevel: input.riskLevel,
      auditEvents: [
        {
          event: "browser_automation_plan_saved",
          created_at: now,
          run_started: false,
        },
      ],
      createdAt: now,
      runStarted: false,
    };
    return {
      siteAnalysis: {
        id: siteAnalysisId,
        projectId: input.projectId,
        requestedUrl: input.requestedUrl,
        target: "browser_automation",
        status: "draft",
        platformType: "dynamic_browser_page",
        pageType: "browser_runtime",
        riskLevel: input.riskLevel,
        analyzedAt: now,
        createdAt: now,
        latestPlan: extractionPlan,
      },
      extractionPlan,
      browserDiagnostic: {
        id: "mock-browser-diagnostic-run",
        projectId: input.projectId,
        siteAnalysisId,
        requestedUrl: input.requestedUrl,
        finalUrl: input.browserDiagnostic.finalUrl,
        status: "draft",
        authorizationConfirmed: input.authorized,
        schemaVersion: input.browserDiagnostic.schemaVersion,
        recommendedPath: input.browserDiagnostic.recommendedPath,
        confidence: input.browserDiagnostic.confidence > 1
          ? input.browserDiagnostic.confidence / 100
          : input.browserDiagnostic.confidence,
        fieldStability: input.browserDiagnostic.fieldStability ?? null,
        evidenceSource: input.browserDiagnostic.evidenceSource,
        screenshotPath: input.browserDiagnostic.screenshotPath ?? null,
        runPolicy: { read_only: true, run_started: false },
        pageSummary: {},
        networkSummary: { api_candidate_count: input.apiCandidates.length },
        accessibilitySummary: {},
        riskFlags: [],
        extractionStrategy: { recommended_path: input.browserDiagnostic.recommendedPath },
        blockedReasons: ["浏览器诊断已保存为只读资产，尚未启动采集运行。"],
        createdAt: now,
        runStarted: false,
      },
      siteAnalysisCreated: true,
      extractionPlanCreated: true,
      browserDiagnosticCreated: true,
      runStarted: false,
    };
  }
  const response = await apiFetch<AutomationBrowserAutomationPlanResponse>(
    "/api/automation/browser-automation-plans",
    {
      method: "POST",
      body: JSON.stringify({
        project_id: input.projectId,
        requested_url: input.requestedUrl,
        authorized: input.authorized,
        name: input.name,
        runner: input.runner,
        execution_mode: input.executionMode,
        risk_level: input.riskLevel,
        field_contract: {
          fields: input.fieldContract.fields.map((field) => ({
            key: field.key,
            label: field.label,
            source: field.source,
            required: field.required,
            selected: field.selected,
            selector_hint: field.selectorHint,
          })),
          cleaning_rules: input.fieldContract.cleaningRules.map((rule) => ({
            field: rule.field,
            operation: rule.operation,
            description: rule.description,
          })),
        },
        browser_diagnostic: {
          schema_version: input.browserDiagnostic.schemaVersion,
          final_url: input.browserDiagnostic.finalUrl,
          recommended_path: input.browserDiagnostic.recommendedPath,
          confidence: input.browserDiagnostic.confidence,
          field_stability: input.browserDiagnostic.fieldStability,
          evidence_source: input.browserDiagnostic.evidenceSource,
          screenshot_path: input.browserDiagnostic.screenshotPath,
        },
        diagnostic_payload: input.diagnosticPayload ?? {},
        api_candidates: input.apiCandidates,
        guardrails: input.guardrails,
      }),
    },
  );
  return {
    siteAnalysis: mapAutomationSiteAnalysisHistoryItem(response.site_analysis),
    extractionPlan: mapAutomationExtractionPlan(response.extraction_plan),
    browserDiagnostic: mapAutomationBrowserDiagnosticRun(response.browser_diagnostic),
    siteAnalysisCreated: response.site_analysis_created,
    extractionPlanCreated: response.extraction_plan_created,
    browserDiagnosticCreated: response.browser_diagnostic_created,
    runStarted: response.run_started,
  };
}

export async function listAutomationBrowserDiagnostics(input: {
  projectId?: string;
  siteAnalysisId?: string;
  limit?: number;
} = {}): Promise<AutomationBrowserDiagnosticRunList> {
  const query = new URLSearchParams();
  if (input.projectId) {
    query.set("project_id", input.projectId);
  }
  if (input.siteAnalysisId) {
    query.set("site_analysis_id", input.siteAnalysisId);
  }
  if (input.limit) {
    query.set("limit", String(input.limit));
  }
  if (mockApiEnabled) {
    const now = new Date().toISOString();
    return {
      items: [
        {
          id: "mock-browser-diagnostic-history",
          projectId: input.projectId ?? "project_marketplace_price",
          siteAnalysisId: input.siteAnalysisId ?? "mock-browser-analysis-history",
          requestedUrl: "https://example.com/app",
          finalUrl: "https://example.com/app",
          status: "draft",
          authorizationConfirmed: true,
          schemaVersion: "browser_structure_diagnostic.v1",
          recommendedPath: "browser_automation",
          confidence: 0.82,
          fieldStability: "medium",
          evidenceSource: "browser-harness",
          screenshotPath: null,
          runPolicy: { read_only: true, run_started: false },
          pageSummary: {},
          networkSummary: { api_candidate_count: 1 },
          accessibilitySummary: {},
          riskFlags: [],
          extractionStrategy: { recommended_path: "browser_automation" },
          blockedReasons: ["浏览器诊断已保存为只读资产，尚未启动采集运行。"],
          createdAt: now,
          runStarted: false,
        },
      ],
      total: 1,
      runStarted: false,
    };
  }
  const response = await apiFetch<AutomationBrowserDiagnosticRunListResponse>(
    `/api/automation/browser-diagnostics${query.size ? `?${query}` : ""}`,
  );
  return {
    items: response.items.map(mapAutomationBrowserDiagnosticRun),
    total: response.total,
    runStarted: response.run_started,
  };
}

export async function dryRunAutomationBrowserExecutableSpec(
  input: AutomationBrowserExecutableSpecDryRunInput,
): Promise<AutomationBrowserExecutableSpecDryRun> {
  if (mockApiEnabled) {
    const now = new Date().toISOString();
    const extractionPlan: AutomationExtractionPlan = {
      id: input.extractionPlanId,
      siteAnalysisId: input.siteAnalysisId,
      projectId: "project_marketplace_price",
      name: "Browser Automation: example.com",
      versionNumber: 1,
      collectorType: "browser_automation",
      selectedFields: ["page_title", "canonical_url"],
      sourceDraft: {
        type: "browser_automation",
        suggestedName: "Browser Automation: example.com",
        scheduleCron: null,
        config: {
          executable_spec: {
            schema_version: "browser_automation_executable_spec.v1",
            selector_contract: [{ field: "page_title" }, { field: "canonical_url" }],
            wait_conditions: [{ type: "domcontentloaded", timeout_seconds: 15 }],
            api_candidates: ["https://example.com/api/products"],
            manual_review_required: true,
            run_started: false,
          },
        },
      },
      scheduleCron: null,
      status: "draft",
      riskLevel: "medium",
      auditEvents: [],
      createdAt: now,
      runStarted: false,
    };
    return {
      siteAnalysis: {
        id: input.siteAnalysisId,
        projectId: "project_marketplace_price",
        requestedUrl: "https://example.com/app",
        target: "browser_automation",
        status: "draft",
        platformType: "dynamic_browser_page",
        pageType: "browser_runtime",
        riskLevel: "medium",
        analyzedAt: now,
        createdAt: now,
        latestPlan: extractionPlan,
      },
      extractionPlan,
      browserDiagnostic: null,
      summary: {
        status: "review",
        totalChecks: 11,
        passedChecks: 10,
        reviewChecks: 1,
        blockedChecks: 0,
        selectorCount: 2,
        waitConditionCount: 1,
        apiCandidateCount: 1,
        manualReviewRequired: true,
        canDryRunAfterReview: true,
        writeAllowed: false,
        runStarted: false,
      },
      checks: [
        {
          key: "manual-review",
          label: "人工复核",
          status: "review",
          message: "执行规格标记为需要人工复核。",
          evidence: { manual_review_required: true },
        },
      ],
      executableSpec: {},
      blockedReasons: [],
      auditEvents: [{ event: "browser_automation_spec_dry_run_validated" }],
      runStarted: false,
    };
  }
  const response = await apiFetch<AutomationBrowserExecutableSpecDryRunResponse>(
    "/api/automation/browser-automation-spec-dry-run",
    {
      method: "POST",
      body: JSON.stringify({
        authorized: input.authorized,
        confirm_review: input.confirmReview,
        site_analysis_id: input.siteAnalysisId,
        extraction_plan_id: input.extractionPlanId,
        browser_diagnostic_run_id: input.browserDiagnosticRunId,
      }),
    },
  );
  return mapAutomationBrowserExecutableSpecDryRun(response);
}

export async function createAutomationBrowserDiagnosticJob(
  input: AutomationBrowserDiagnosticJobCreateInput,
): Promise<AutomationBrowserDiagnosticJob> {
  if (mockApiEnabled) {
    const now = new Date().toISOString();
    return {
      id: "mock-browser-diagnostic-job",
      projectId: "project_marketplace_price",
      siteAnalysisId: input.siteAnalysisId,
      extractionPlanId: input.extractionPlanId,
      browserDiagnosticRunId: input.browserDiagnosticRunId ?? "mock-browser-diagnostic-history",
      requestedUrl: "https://example.com/app",
      finalUrl: "https://example.com/app",
      status: "ready_for_manual_execution",
      authorizationConfirmed: input.authorized,
      runner: "browser_harness",
      executionMode: "read_only_browser_harness",
      selectorScope: [{ field: "page_title" }, { field: "canonical_url" }],
      waitPolicy: [{ type: "domcontentloaded", timeout_seconds: 15 }],
      networkObservationPolicy: {
        mode: input.networkObservationMode ?? "metadata_only",
        write_allowed: false,
      },
      artifactPolicy: {
        mode: input.artifactMode ?? "screenshot_reference_only",
        write_files: false,
      },
      safetyFlags: ["read_only", "no_browser_run_started", "no_source_task_taskrun_creation"],
      dryRunSummary: { status: "review", write_allowed: false },
      executableSpecSnapshot: {},
      blockedReasons: ["browser_diagnostic_job_created_no_runner"],
      auditEvents: [{ event: "browser_diagnostic_job_created", run_started: false }],
      createdAt: now,
      updatedAt: now,
      cancelledAt: null,
      runStarted: false,
    };
  }
  const response = await apiFetch<AutomationBrowserDiagnosticJobResponse>(
    "/api/automation/browser-diagnostic-jobs",
    {
      method: "POST",
      body: JSON.stringify({
        authorized: input.authorized,
        confirm_create: input.confirmCreate,
        site_analysis_id: input.siteAnalysisId,
        extraction_plan_id: input.extractionPlanId,
        browser_diagnostic_run_id: input.browserDiagnosticRunId,
        network_observation_mode: input.networkObservationMode ?? "metadata_only",
        artifact_mode: input.artifactMode ?? "screenshot_reference_only",
        note: input.note,
      }),
    },
  );
  return mapAutomationBrowserDiagnosticJob(response);
}

export async function listAutomationBrowserDiagnosticJobs(input: {
  projectId?: string;
  siteAnalysisId?: string;
  extractionPlanId?: string;
  status?: string;
  limit?: number;
} = {}): Promise<AutomationBrowserDiagnosticJobList> {
  const query = new URLSearchParams();
  if (input.projectId) {
    query.set("project_id", input.projectId);
  }
  if (input.siteAnalysisId) {
    query.set("site_analysis_id", input.siteAnalysisId);
  }
  if (input.extractionPlanId) {
    query.set("extraction_plan_id", input.extractionPlanId);
  }
  if (input.status) {
    query.set("status", input.status);
  }
  if (input.limit) {
    query.set("limit", String(input.limit));
  }
  if (mockApiEnabled) {
    const now = new Date().toISOString();
    return {
      items: [
        {
          id: "mock-browser-diagnostic-job",
          projectId: input.projectId ?? "project_marketplace_price",
          siteAnalysisId: input.siteAnalysisId ?? "mock-browser-analysis-history",
          extractionPlanId: input.extractionPlanId ?? "mock-browser-plan-history",
          browserDiagnosticRunId: "mock-browser-diagnostic-history",
          requestedUrl: "https://example.com/app",
          finalUrl: "https://example.com/app",
          status: input.status ?? "ready_for_manual_execution",
          authorizationConfirmed: true,
          runner: "browser_harness",
          executionMode: "read_only_browser_harness",
          selectorScope: [{ field: "page_title" }, { field: "canonical_url" }],
          waitPolicy: [{ type: "domcontentloaded", timeout_seconds: 15 }],
          networkObservationPolicy: { mode: "metadata_only", write_allowed: false },
          artifactPolicy: { mode: "screenshot_reference_only", write_files: false },
          safetyFlags: ["read_only", "no_browser_run_started"],
          dryRunSummary: { status: "review", write_allowed: false },
          executableSpecSnapshot: {},
          blockedReasons: ["browser_diagnostic_job_created_no_runner"],
          auditEvents: [{ event: "browser_diagnostic_job_created", run_started: false }],
          createdAt: now,
          updatedAt: now,
          cancelledAt: null,
          runStarted: false,
        },
      ],
      total: 1,
      runStarted: false,
    };
  }
  const response = await apiFetch<AutomationBrowserDiagnosticJobListResponse>(
    `/api/automation/browser-diagnostic-jobs${query.size ? `?${query}` : ""}`,
  );
  return {
    items: response.items.map(mapAutomationBrowserDiagnosticJob),
    total: response.total,
    runStarted: response.run_started,
  };
}

export async function getAutomationBrowserDiagnosticJob(
  jobId: string,
): Promise<AutomationBrowserDiagnosticJob> {
  if (mockApiEnabled) {
    const list = await listAutomationBrowserDiagnosticJobs();
    return { ...list.items[0], id: jobId };
  }
  const response = await apiFetch<AutomationBrowserDiagnosticJobResponse>(
    `/api/automation/browser-diagnostic-jobs/${jobId}`,
  );
  return mapAutomationBrowserDiagnosticJob(response);
}

export async function cancelAutomationBrowserDiagnosticJob(
  jobId: string,
): Promise<AutomationBrowserDiagnosticJob> {
  if (mockApiEnabled) {
    const now = new Date().toISOString();
    const job = await getAutomationBrowserDiagnosticJob(jobId);
    return {
      ...job,
      status: "cancelled",
      cancelledAt: now,
      updatedAt: now,
      auditEvents: [
        ...job.auditEvents,
        { event: "browser_diagnostic_job_cancelled", run_started: false },
      ],
    };
  }
  const response = await apiFetch<AutomationBrowserDiagnosticJobResponse>(
    `/api/automation/browser-diagnostic-jobs/${jobId}/cancel`,
    { method: "POST" },
  );
  return mapAutomationBrowserDiagnosticJob(response);
}

export async function buildAutomationBrowserExecutorContract(
  jobId: string,
  input: AutomationBrowserExecutorContractInput,
): Promise<AutomationBrowserExecutorContract> {
  if (mockApiEnabled) {
    const job = await getAutomationBrowserDiagnosticJob(jobId);
    return {
      job,
      adapter: {
        schema_version: "browser_executor_adapter_contract.v1",
        adapter_name: "browser_harness_read_only_local",
        adapter_kind: "local_manual_runner",
        execution_policy: {
          manual_operator_required: true,
          automatic_api_worker_start: false,
          production_enabled: false,
          write_allowed: false,
          run_started: false,
        },
      },
      runtimeIsolation: {
        mode: "local_ephemeral_browser_context",
        reuse_user_profile: false,
        cookie_export_allowed: false,
        login_state_allowed: false,
        filesystem_write_allowed: false,
      },
      artifactRetentionPolicy: {
        schema_version: "browser_artifact_retention_policy.v1",
        write_files_now: false,
        retention_days: input.artifactRetentionDays ?? 7,
        max_preview_rows: input.maxPreviewRows ?? 20,
        har_summary: { enabled: input.includeHarSummary ?? true, capture_body: false },
      },
      allowedActions: ["open_authorized_final_url", "evaluate_declared_selectors"],
      deniedActions: ["reuse_user_chrome_profile", "export_cookies", "create_task_run"],
      readinessChecks: [
        {
          key: "job-status",
          label: "任务状态",
          status: "passed",
          message: "诊断任务已审核，等待人工执行。",
          evidence: { status: job.status },
        },
      ],
      blockedReasons: [],
      auditEvents: [{ event: "browser_executor_contract_built", run_started: false }],
      runStarted: false,
      executionStarted: false,
    };
  }
  const response = await apiFetch<AutomationBrowserExecutorContractResponse>(
    `/api/automation/browser-diagnostic-jobs/${jobId}/executor-contract`,
    {
      method: "POST",
      body: JSON.stringify({
        authorized: input.authorized,
        confirm_review: input.confirmReview,
        artifact_retention_days: input.artifactRetentionDays ?? 7,
        max_preview_rows: input.maxPreviewRows ?? 20,
        include_screenshot: input.includeScreenshot ?? true,
        include_trace_summary: input.includeTraceSummary ?? false,
        include_har_summary: input.includeHarSummary ?? true,
        note: input.note,
      }),
    },
  );
  return mapAutomationBrowserExecutorContract(response);
}

export async function runAutomationBrowserDiagnosticJobLocal(
  jobId: string,
  input: AutomationBrowserLocalRunnerInput,
): Promise<AutomationBrowserLocalRunnerResult> {
  if (mockApiEnabled) {
    const now = new Date().toISOString();
    const runMode = input.runMode ?? "diagnostic_snapshot_replay";
    const isHarnessProbe = runMode === "ephemeral_browser_harness_probe";
    const contract = await buildAutomationBrowserExecutorContract(jobId, {
      authorized: input.authorized,
      confirmReview: true,
      artifactRetentionDays: input.artifactRetentionDays ?? 7,
      maxPreviewRows: input.maxPreviewRows ?? 20,
      includeScreenshot: input.includeScreenshot ?? true,
      includeTraceSummary: input.includeTraceSummary ?? false,
      includeHarSummary: input.includeHarSummary ?? true,
      note: input.note,
    });
    return {
      id: isHarnessProbe ? "mock-browser-harness-probe-run" : "mock-browser-local-run",
      job: contract.job,
      status: isHarnessProbe ? "completed_ephemeral_probe" : "completed_snapshot_replay",
      runner: "browser_harness_read_only_local",
      runMode,
      contractSnapshot: contract as unknown as Record<string, unknown>,
      artifactManifest: {
        schema_version: "browser_local_runner_artifact_manifest.v1",
        files_written: false,
        preview_rows_count: 1,
        screenshot: { referenced_path: "/tmp/browser-diagnostic/mock.png" },
        ...(isHarnessProbe
          ? {
              ephemeral_probe: {
                schema_version: "browser_harness_ephemeral_probe.v1",
                status: "completed",
                binary: "mock-browser-harness",
                exit_code: 0,
                files_written: false,
                object_storage_write: false,
                target_tab_closed: true,
              },
            }
          : {}),
      },
      selectorResults: [
        {
          field: "page_title",
          status: "observed_from_diagnostic_snapshot",
          value: "Dynamic Product Grid",
        },
      ],
      selectorEvaluations: [
        {
          schema_version: "browser_selector_evaluation.v1",
          field: "page_title",
          label: "page_title",
          selector_hint: "title",
          required: true,
          status: "observed_from_diagnostic_snapshot",
          match_count: 1,
          sample_text: "Dynamic Product Grid",
          missing_reason: null,
          source: "diagnostic_snapshot_replay",
          browser_started: false,
        },
      ],
      previewRows: [
        {
          row_index: 1,
          source: "diagnostic_snapshot_replay",
          values: { page_title: "Dynamic Product Grid" },
        },
      ],
      networkObservationSummary: {
        mode: "metadata_only",
        browser_started: isHarnessProbe,
        api_candidate_count: 0,
        ...(isHarnessProbe
          ? {
              ephemeral_probe: {
                schema_version: "browser_harness_ephemeral_probe.v1",
                status: "completed",
                target_url: "https://example.com/app",
                page_info: {
                  url: "https://example.com/app",
                  title: "Dynamic Product Grid",
                  w: 1280,
                  h: 720,
                },
                target_tab_closed: true,
                redacted: true,
              },
            }
          : {}),
      },
      networkMetadataSummary: {
        schema_version: "browser_network_metadata_summary.v1",
        mode: "metadata_only",
        same_origin_only: true,
        metadata_only: true,
        capture_headers: false,
        capture_body: false,
        browser_started: isHarnessProbe,
        observed_from_diagnostic_snapshot: true,
        resource_count: 0,
        api_candidate_count: 0,
        api_candidates: [],
        redacted: true,
        ...(isHarnessProbe
          ? {
              ephemeral_probe: {
                schema_version: "browser_harness_ephemeral_probe.v1",
                status: "completed",
                target_url: "https://example.com/app",
                page_info: {
                  url: "https://example.com/app",
                  title: "Dynamic Product Grid",
                  w: 1280,
                  h: 720,
                },
                target_tab_closed: true,
                redacted: true,
              },
            }
          : {}),
      },
      errorSummary: {
        error_count: 0,
        errors: [],
        redacted: true,
        browser_started: isHarnessProbe,
      },
      promotionGate: {
        schema_version: "browser_promotion_gate.v1",
        status: "blocked",
        can_create_collection_resources: false,
        review_required: true,
        reasons: ["m2_read_only_contract_no_direct_promotion"],
        required_missing_fields: [],
        browser_started: isHarnessProbe,
        files_written: false,
        collection_resources_written: false,
      },
      redactionSummary: {
        schema_version: "browser_local_runner_redaction_summary.v1",
        cookies_captured: false,
        headers_captured: false,
        bodies_captured: false,
        query_parameters_retained: false,
        url_query_fragment_removed: true,
        stdout_stderr_tail_redacted: true,
        sample_text_max_chars: 180,
        files_written: false,
        collection_resources_written: false,
      },
      blockedReasons: isHarnessProbe
        ? [
            "browser_harness_ephemeral_probe_only",
            "no_files_written_no_collection_resources_created",
          ]
        : [
            "browser_local_runner_snapshot_replay_only",
            "no_real_browser_started_no_files_written_no_collection_resources_created",
          ],
      auditEvents: [
        {
          event: isHarnessProbe
            ? "browser_harness_ephemeral_probe_completed"
            : "browser_local_runner_snapshot_replay_completed",
          browser_started: isHarnessProbe,
          collection_resources_written: false,
        },
      ],
      createdAt: now,
      updatedAt: now,
      startedAt: now,
      finishedAt: now,
      executionStarted: true,
      browserStarted: isHarnessProbe,
      filesWritten: false,
      collectionResourcesWritten: false,
    };
  }
  const response = await apiFetch<AutomationBrowserLocalRunnerResultResponse>(
    `/api/automation/browser-diagnostic-jobs/${jobId}/local-run`,
    {
      method: "POST",
      body: JSON.stringify({
        authorized: input.authorized,
        confirm_execute: input.confirmExecute,
        run_mode: input.runMode ?? "diagnostic_snapshot_replay",
        confirm_real_browser_probe: input.confirmRealBrowserProbe ?? false,
        browser_harness_binary: input.browserHarnessBinary,
        probe_timeout_seconds: input.probeTimeoutSeconds ?? 15,
        artifact_retention_days: input.artifactRetentionDays ?? 7,
        max_preview_rows: input.maxPreviewRows ?? 20,
        include_screenshot: input.includeScreenshot ?? true,
        include_trace_summary: input.includeTraceSummary ?? false,
        include_har_summary: input.includeHarSummary ?? true,
        note: input.note,
      }),
    },
  );
  return mapAutomationBrowserLocalRunnerResult(response);
}

export async function listAutomationBrowserDiagnosticJobRuns(input: {
  projectId?: string;
  diagnosticJobId?: string;
  status?: string;
  limit?: number;
} = {}): Promise<AutomationBrowserLocalRunnerResultList> {
  const query = new URLSearchParams();
  if (input.projectId) {
    query.set("project_id", input.projectId);
  }
  if (input.diagnosticJobId) {
    query.set("diagnostic_job_id", input.diagnosticJobId);
  }
  if (input.status) {
    query.set("status", input.status);
  }
  if (input.limit) {
    query.set("limit", String(input.limit));
  }
  if (mockApiEnabled) {
    return {
      items: [],
      total: 0,
      browserStarted: false,
      filesWritten: false,
      collectionResourcesWritten: false,
    };
  }
  const response = await apiFetch<AutomationBrowserLocalRunnerResultListResponse>(
    `/api/automation/browser-diagnostic-job-runs${query.size ? `?${query}` : ""}`,
  );
  return {
    items: response.items.map(mapAutomationBrowserLocalRunnerResult),
    total: response.total,
    browserStarted: response.browser_started,
    filesWritten: response.files_written,
    collectionResourcesWritten: response.collection_resources_written,
  };
}

export async function listAutomationSiteAnalyses(
  input: AutomationSiteAnalysisListInput = {},
): Promise<AutomationSiteAnalysisList> {
  if (mockApiEnabled) {
    if (input.target === "browser_automation") {
      const now = new Date().toISOString();
      const siteAnalysisId = "mock-browser-analysis-history";
      const plan: AutomationExtractionPlan = {
        id: "mock-browser-plan-history",
        siteAnalysisId,
        projectId: input.projectId ?? "project_marketplace_price",
        name: "Browser Automation: example.com",
        versionNumber: 1,
        collectorType: "browser_automation",
        selectedFields: ["page_title", "canonical_url"],
        sourceDraft: {
          type: "browser_automation",
          suggestedName: "Browser Automation: example.com",
          scheduleCron: null,
          config: {
            browser_diagnostic_run_id: "mock-browser-diagnostic-history",
            executable_spec: {
              schema_version: "browser_automation_executable_spec.v1",
              selector_contract: [{ field: "page_title" }, { field: "canonical_url" }],
              wait_conditions: [{ type: "domcontentloaded", timeout_seconds: 15 }],
              api_candidates: ["https://example.com/api/products"],
              manual_review_required: true,
              run_started: false,
            },
            run_started: false,
          },
        },
        scheduleCron: null,
        status: "draft",
        riskLevel: "medium",
        auditEvents: [{ event: "browser_automation_plan_saved", run_started: false }],
        createdAt: now,
        runStarted: false,
      };
      return {
        items: [
          {
            id: siteAnalysisId,
            projectId: input.projectId ?? "project_marketplace_price",
            requestedUrl: "https://example.com/app",
            target: "browser_automation",
            status: "draft",
            platformType: "dynamic_browser_page",
            pageType: "browser_runtime",
            riskLevel: "medium",
            analyzedAt: now,
            createdAt: now,
            latestPlan: plan,
          },
        ],
        total: 1,
        runStarted: false,
      };
    }
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

export async function previewAutomationGitHubToolDataset(
  input: AutomationProductDatasetPreviewInput,
): Promise<AutomationProductDatasetPreview> {
  if (mockApiEnabled) {
    return getMockAutomationGitHubToolDatasetPreview(input);
  }
  const response = await apiFetch<AutomationProductDatasetPreviewResponse>(
    "/api/automation/github-tool-dataset-preview",
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
      blockedReasons: ["清洗计划已保存为草案；尚未保存数据集版本或启动采集。"],
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

export async function saveAutomationGitHubToolDataset(
  input: AutomationProductDatasetSaveInput,
): Promise<AutomationProductDatasetSave> {
  if (mockApiEnabled) {
    return getMockAutomationGitHubToolDatasetSave(input);
  }
  const response = await apiFetch<AutomationProductDatasetSaveResponse>(
    "/api/automation/github-tool-dataset-save",
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

export async function checkAutomationGitHubToolDrift(
  input: AutomationProductDriftCheckInput,
): Promise<AutomationProductDriftCheck> {
  if (mockApiEnabled) {
    return getMockAutomationGitHubToolDriftCheck(input);
  }
  const response = await apiFetch<AutomationProductDriftCheckResponse>(
    "/api/automation/github-tool-drift-check",
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

export async function saveAutomationGitHubToolDriftEvent(
  input: AutomationProductDriftEventSaveInput,
): Promise<AutomationProductDriftEvent> {
  if (mockApiEnabled) {
    return getMockAutomationProductDriftEventSave(input);
  }
  const response = await apiFetch<AutomationProductDriftEventResponse>(
    "/api/automation/github-tool-drift-events",
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

export async function generateAutomationGitHubToolReport(
  input: AutomationGitHubToolReportInput,
): Promise<AutomationGitHubToolReport> {
  if (mockApiEnabled) {
    return getMockAutomationGitHubToolReport(input);
  }
  const response = await apiFetch<AutomationGitHubToolReportResponse>(
    "/api/automation/github-tool-report",
    {
      method: "POST",
      body: JSON.stringify({
        authorized: input.authorized,
        dataset_id: input.datasetId,
        dataset_version_id: input.datasetVersionId,
        min_stars: input.minStars ?? 1000,
        top_limit: input.topLimit ?? 10,
      }),
    },
  );
  return mapAutomationGitHubToolReport(response);
}

export async function createAutomationGitHubToolReportAsset(
  input: AutomationGitHubToolReportAssetInput,
): Promise<AutomationGitHubToolReportAsset> {
  if (mockApiEnabled) {
    return getMockAutomationGitHubToolReportAsset(input);
  }
  const response = await apiFetch<AutomationGitHubToolReportAssetResponse>(
    "/api/automation/github-tool-report-assets",
    {
      method: "POST",
      body: JSON.stringify({
        authorized: input.authorized,
        confirm_create: input.confirmCreate,
        dataset_id: input.datasetId,
        dataset_version_id: input.datasetVersionId,
        min_stars: input.minStars ?? 1000,
        top_limit: input.topLimit ?? 10,
      }),
    },
  );
  return mapAutomationGitHubToolReportAsset(response);
}

export async function generateAutomationPublicContentReport(
  input: AutomationPublicContentReportInput,
): Promise<AutomationPublicContentReport> {
  if (mockApiEnabled) {
    return getMockAutomationPublicContentReport(input);
  }
  const response = await apiFetch<AutomationPublicContentReportResponse>(
    "/api/automation/public-content-report",
    {
      method: "POST",
      body: JSON.stringify({
        authorized: input.authorized,
        dataset_id: input.datasetId,
        dataset_version_id: input.datasetVersionId,
        top_limit: input.topLimit ?? 10,
      }),
    },
  );
  return mapAutomationPublicContentReport(response);
}

export async function createAutomationPublicContentReportAsset(
  input: AutomationPublicContentReportAssetInput,
): Promise<AutomationPublicContentReportAsset> {
  if (mockApiEnabled) {
    return getMockAutomationPublicContentReportAsset(input);
  }
  const response = await apiFetch<AutomationPublicContentReportAssetResponse>(
    "/api/automation/public-content-report-assets",
    {
      method: "POST",
      body: JSON.stringify({
        authorized: input.authorized,
        confirm_create: input.confirmCreate,
        dataset_id: input.datasetId,
        dataset_version_id: input.datasetVersionId,
        top_limit: input.topLimit ?? 10,
      }),
    },
  );
  return mapAutomationPublicContentReportAsset(response);
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
    defaultEntrypoint: response.default_entrypoint,
    sampleUrls: response.sample_urls.map((sample) => ({
      label: sample.label,
      entrypoint: sample.entrypoint,
      url: sample.url,
      description: sample.description,
    })),
    cleaningRules: response.cleaning_rules.map((rule) => ({
      field: rule.field,
      operation: rule.operation,
      value: rule.value,
      description: rule.description,
    })),
    operatorChecklist: response.operator_checklist,
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

function mapAutomationCapabilityProbe(
  response: AutomationCapabilityProbeResponse,
): AutomationCapabilityProbe {
  return {
    schemaVersion: response.schema_version,
    platformId: response.platform_id,
    platformLabel: response.platform_label,
    generatedAt: response.generated_at,
    doctorStatus: response.doctor_status,
    credentialMode: response.credential_mode,
    executionBoundary: response.execution_boundary,
    riskLevel: response.risk_level,
    backendCandidates: response.backend_candidates.map((candidate) => ({
      backendId: candidate.backend_id,
      label: candidate.label,
      priority: candidate.priority,
      status: candidate.status,
      credentialMode: candidate.credential_mode,
      requiresLogin: candidate.requires_login,
      requiresProxy: candidate.requires_proxy,
      evidenceLevel: candidate.evidence_level,
      notes: candidate.notes,
    })),
    agentReach: response.agent_reach
      ? {
          schemaVersion: response.agent_reach.schema_version,
          installed: response.agent_reach.installed,
          commandPath: response.agent_reach.command_path,
          doctorStatus: response.agent_reach.doctor_status,
          activeBackend: response.agent_reach.active_backend,
          requiresLogin: response.agent_reach.requires_login,
          requiresProxy: response.agent_reach.requires_proxy,
          blockedReason: response.agent_reach.blocked_reason,
          platforms: response.agent_reach.platforms,
          readInvoked: response.agent_reach.read_invoked,
          searchInvoked: response.agent_reach.search_invoked,
          rawSummary: response.agent_reach.raw_summary,
        }
      : null,
    allowedOutputs: response.allowed_outputs,
    forbiddenActions: response.forbidden_actions,
    nextActions: response.next_actions,
    runStarted: response.run_started,
    collectionResourcesWritten: response.collection_resources_written,
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

function mapAutomationBrowserDiagnosticRun(
  response: AutomationBrowserDiagnosticRunResponse,
): AutomationBrowserDiagnosticRun {
  return {
    id: response.id,
    projectId: response.project_id,
    siteAnalysisId: response.site_analysis_id,
    requestedUrl: response.requested_url,
    finalUrl: response.final_url,
    status: response.status,
    authorizationConfirmed: response.authorization_confirmed,
    schemaVersion: response.schema_version,
    recommendedPath: response.recommended_path,
    confidence: response.confidence,
    fieldStability: response.field_stability,
    evidenceSource: response.evidence_source,
    screenshotPath: response.screenshot_path,
    runPolicy: response.run_policy,
    pageSummary: response.page_summary,
    networkSummary: response.network_summary,
    accessibilitySummary: response.accessibility_summary,
    riskFlags: response.risk_flags,
    extractionStrategy: response.extraction_strategy,
    blockedReasons: response.blocked_reasons,
    createdAt: response.created_at,
    runStarted: response.run_started,
  };
}

function mapAutomationBrowserExecutableSpecDryRun(
  response: AutomationBrowserExecutableSpecDryRunResponse,
): AutomationBrowserExecutableSpecDryRun {
  return {
    siteAnalysis: mapAutomationSiteAnalysisHistoryItem(response.site_analysis),
    extractionPlan: mapAutomationExtractionPlan(response.extraction_plan),
    browserDiagnostic: response.browser_diagnostic
      ? mapAutomationBrowserDiagnosticRun(response.browser_diagnostic)
      : null,
    summary: mapAutomationBrowserExecutableSpecSummary(response.summary),
    checks: response.checks.map(mapAutomationBrowserExecutableSpecCheck),
    executableSpec: response.executable_spec,
    blockedReasons: response.blocked_reasons,
    auditEvents: response.audit_events,
    runStarted: response.run_started,
  };
}

function mapAutomationBrowserDiagnosticJob(
  response: AutomationBrowserDiagnosticJobResponse,
): AutomationBrowserDiagnosticJob {
  return {
    id: response.id,
    projectId: response.project_id,
    siteAnalysisId: response.site_analysis_id,
    extractionPlanId: response.extraction_plan_id,
    browserDiagnosticRunId: response.browser_diagnostic_run_id,
    requestedUrl: response.requested_url,
    finalUrl: response.final_url,
    status: response.status,
    authorizationConfirmed: response.authorization_confirmed,
    runner: response.runner,
    executionMode: response.execution_mode,
    selectorScope: response.selector_scope,
    waitPolicy: response.wait_policy,
    networkObservationPolicy: response.network_observation_policy,
    artifactPolicy: response.artifact_policy,
    safetyFlags: response.safety_flags,
    dryRunSummary: response.dry_run_summary,
    executableSpecSnapshot: response.executable_spec_snapshot,
    blockedReasons: response.blocked_reasons,
    auditEvents: response.audit_events,
    createdAt: response.created_at,
    updatedAt: response.updated_at,
    cancelledAt: response.cancelled_at,
    runStarted: response.run_started,
  };
}

function mapAutomationBrowserExecutorContract(
  response: AutomationBrowserExecutorContractResponse,
): AutomationBrowserExecutorContract {
  return {
    job: mapAutomationBrowserDiagnosticJob(response.job),
    adapter: response.adapter,
    runtimeIsolation: response.runtime_isolation,
    artifactRetentionPolicy: response.artifact_retention_policy,
    allowedActions: response.allowed_actions,
    deniedActions: response.denied_actions,
    readinessChecks: response.readiness_checks.map(mapAutomationBrowserExecutorCheck),
    blockedReasons: response.blocked_reasons,
    auditEvents: response.audit_events,
    runStarted: response.run_started,
    executionStarted: response.execution_started,
  };
}

function mapAutomationBrowserExecutorCheck(
  response: AutomationBrowserExecutorReadinessCheckResponse,
): AutomationBrowserExecutorReadinessCheck {
  return {
    key: response.key,
    label: response.label,
    status: response.status,
    message: response.message,
    evidence: response.evidence,
  };
}

function mapAutomationBrowserLocalRunnerResult(
  response: AutomationBrowserLocalRunnerResultResponse,
): AutomationBrowserLocalRunnerResult {
  return {
    id: response.id,
    job: mapAutomationBrowserDiagnosticJob(response.job),
    status: response.status,
    runner: response.runner,
    runMode: response.run_mode,
    contractSnapshot: response.contract_snapshot,
    artifactManifest: response.artifact_manifest,
    selectorResults: response.selector_results,
    selectorEvaluations: response.selector_evaluations,
    previewRows: response.preview_rows,
    networkObservationSummary: response.network_observation_summary,
    networkMetadataSummary: response.network_metadata_summary,
    errorSummary: response.error_summary,
    promotionGate: response.promotion_gate,
    redactionSummary: response.redaction_summary,
    blockedReasons: response.blocked_reasons,
    auditEvents: response.audit_events,
    createdAt: response.created_at,
    updatedAt: response.updated_at,
    startedAt: response.started_at,
    finishedAt: response.finished_at,
    executionStarted: response.execution_started,
    browserStarted: response.browser_started,
    filesWritten: response.files_written,
    collectionResourcesWritten: response.collection_resources_written,
  };
}

function mapAutomationBrowserExecutableSpecSummary(
  response: AutomationBrowserExecutableSpecDryRunSummaryResponse,
): AutomationBrowserExecutableSpecDryRunSummary {
  return {
    status: response.status,
    totalChecks: response.total_checks,
    passedChecks: response.passed_checks,
    reviewChecks: response.review_checks,
    blockedChecks: response.blocked_checks,
    selectorCount: response.selector_count,
    waitConditionCount: response.wait_condition_count,
    apiCandidateCount: response.api_candidate_count,
    manualReviewRequired: response.manual_review_required,
    canDryRunAfterReview: response.can_dry_run_after_review,
    writeAllowed: response.write_allowed,
    runStarted: response.run_started,
  };
}

function mapAutomationBrowserExecutableSpecCheck(
  response: AutomationBrowserExecutableSpecCheckResponse,
): AutomationBrowserExecutableSpecCheck {
  return {
    key: response.key,
    label: response.label,
    status: response.status,
    message: response.message,
    evidence: response.evidence,
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
      paginationUrlCount: response.page_structure.pagination_url_count,
      duplicateUrlCount: response.page_structure.duplicate_url_count,
      skippedUrlCount: response.page_structure.skipped_url_count,
      scriptCount: response.page_structure.script_count,
      textSample: response.page_structure.text_sample,
    },
    productCandidates: response.product_candidates.map((candidate) => ({
      url: candidate.url,
      title: candidate.title,
      source: candidate.source,
      confidence: candidate.confidence,
      canonicalUrl: candidate.canonical_url,
    })),
    toolRecommendations: response.tool_recommendations.map(mapToolRecommendation),
    discoveryPlan: {
      nextCollectorType: response.discovery_plan.next_collector_type,
      candidateCount: response.discovery_plan.candidate_count,
      maxProducts: response.discovery_plan.max_products,
      fanOutRequiresReview: response.discovery_plan.fan_out_requires_review,
      paginationUrls: response.discovery_plan.pagination_urls,
      dedupeSummary: {
        inputUrlCount: response.discovery_plan.dedupe_summary.input_url_count,
        canonicalCandidateCount: response.discovery_plan.dedupe_summary.canonical_candidate_count,
        duplicateUrlCount: response.discovery_plan.dedupe_summary.duplicate_url_count,
        skippedUrlCount: response.discovery_plan.dedupe_summary.skipped_url_count,
        skippedReasons: response.discovery_plan.dedupe_summary.skipped_reasons,
      },
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
    blockedReasons: ["清洗规则试跑只转换样本行，不会保存数据集版本。"],
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
      rowChange: item.row_change,
      addedRowCount: item.added_row_count,
      removedRowCount: item.removed_row_count,
      priceChangePercent: item.price_change_percent,
      freshnessTargetHours: item.freshness_target_hours,
      staleHours: item.stale_hours,
      issues: item.issues,
      signalGroups: item.signal_groups ?? {},
    })),
    summary: {
      requestedTasks: response.summary.requested_tasks,
      checkedTasks: response.summary.checked_tasks,
      blockedTasks: response.summary.blocked_tasks,
      warningTasks: response.summary.warning_tasks,
      criticalTasks: response.summary.critical_tasks,
      staleTasks: response.summary.stale_tasks,
      missingFieldTasks: response.summary.missing_field_tasks,
      addedRows: response.summary.added_rows,
      removedRows: response.summary.removed_rows,
      priceChangedTasks: response.summary.price_changed_tasks,
      driftLayers: response.summary.drift_layers,
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
      addedRows: response.summary.added_rows,
      removedRows: response.summary.removed_rows,
      priceChangedTasks: response.summary.price_changed_tasks,
      driftLayers: response.summary.drift_layers,
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
      rowChange: item.row_change,
      addedRowCount: item.added_row_count,
      removedRowCount: item.removed_row_count,
      priceChangePercent: item.price_change_percent,
      freshnessTargetHours: item.freshness_target_hours,
      staleHours: item.stale_hours,
      issues: item.issues,
      signalGroups: item.signal_groups ?? {},
    })),
    auditEvents: response.audit_events,
    note: response.note,
    runStarted: response.run_started,
    alertCreated: response.alert_created,
  };
}

function mapAutomationGitHubToolReport(
  response: AutomationGitHubToolReportResponse,
): AutomationGitHubToolReport {
  return {
    generatedAt: response.generated_at,
    authorizationConfirmed: response.authorization_confirmed,
    dataset: mapAutomationDataset(response.dataset),
    version: mapAutomationDatasetVersion(response.version),
    summary: {
      repositoryCount: response.summary.repository_count,
      totalStars: response.summary.total_stars,
      highValueRepositories: response.summary.high_value_repositories,
      licensedRepositories: response.summary.licensed_repositories,
      releaseTaggedRepositories: response.summary.release_tagged_repositories,
      readmeDocumentedRepositories: response.summary.readme_documented_repositories,
      issueActiveRepositories: response.summary.issue_active_repositories,
      freshCommitRepositories: response.summary.fresh_commit_repositories,
      archivedRepositories: response.summary.archived_repositories,
      forkRepositories: response.summary.fork_repositories,
      languages: response.summary.languages,
      topTopics: response.summary.top_topics,
      reportCreated: response.summary.report_created,
      runStarted: response.summary.run_started,
    },
    topRepositories: response.top_repositories.map((repository) => ({
      repoFullName: repository.repo_full_name,
      htmlUrl: repository.html_url,
      description: repository.description,
      stars: repository.stars,
      forks: repository.forks,
      openIssues: repository.open_issues,
      watchers: repository.watchers,
      language: repository.language,
      topics: repository.topics,
      licenseSpdxId: repository.license_spdx_id,
      defaultBranch: repository.default_branch,
      latestReleaseTag: repository.latest_release_tag,
      latestReleasePublishedAt: repository.latest_release_published_at,
      archived: repository.archived,
      fork: repository.fork,
      updatedAt: repository.updated_at,
      pushedAt: repository.pushed_at,
      readmeDetected: repository.readme_detected,
      readmeHtmlUrl: repository.readme_html_url,
      readmeSize: repository.readme_size,
      issueActivityOpenCount: repository.issue_activity_open_count,
      issueActivityStatus: repository.issue_activity_status,
      commitFreshnessDays: repository.commit_freshness_days,
      commitFreshnessStatus: repository.commit_freshness_status,
      maintenanceRisk: repository.maintenance_risk ?? "unknown",
      riskSignals: repository.risk_signals ?? [],
      installSources: repository.install_sources ?? [],
      recommendedUseCases: repository.recommended_use_cases ?? [],
      unsuitableBoundaries: repository.unsuitable_boundaries ?? [],
    })),
    recommendations: response.recommendations,
    riskSections: response.risk_sections ?? [],
    auditEvents: response.audit_events,
    blockedReasons: response.blocked_reasons,
  };
}

function mapAutomationGitHubToolReportAsset(
  response: AutomationGitHubToolReportAssetResponse,
): AutomationGitHubToolReportAsset {
  return {
    ...mapAutomationGitHubToolReport(response),
    report: mapReport(response.report),
    notificationCreated: response.notification_created,
  };
}

function mapAutomationPublicContentReport(
  response: AutomationPublicContentReportResponse,
): AutomationPublicContentReport {
  return {
    generatedAt: response.generated_at,
    authorizationConfirmed: response.authorization_confirmed,
    dataset: mapAutomationDataset(response.dataset),
    version: mapAutomationDatasetVersion(response.version),
    summary: {
      entryCount: response.summary.entry_count,
      feedCount: response.summary.feed_count,
      uniqueAuthorCount: response.summary.unique_author_count,
      taggedEntryCount: response.summary.tagged_entry_count,
      entriesWithSummary: response.summary.entries_with_summary,
      contentHashCount: response.summary.content_hash_count,
      reportCreated: response.summary.report_created,
      runStarted: response.summary.run_started,
    },
    latestEntries: response.latest_entries.map((entry) => ({
      title: entry.title,
      link: entry.link,
      feedUrl: entry.feed_url,
      feedTitle: entry.feed_title,
      publishedAt: entry.published_at,
      updatedAt: entry.updated_at,
      author: entry.author,
      tags: entry.tags ?? [],
      summary: entry.summary,
      contentHash: entry.content_hash,
    })),
    recommendations: response.recommendations,
    riskSections: response.risk_sections ?? [],
    auditEvents: response.audit_events,
    blockedReasons: response.blocked_reasons,
  };
}

function mapAutomationPublicContentReportAsset(
  response: AutomationPublicContentReportAssetResponse,
): AutomationPublicContentReportAsset {
  return {
    ...mapAutomationPublicContentReport(response),
    report: mapReport(response.report),
    notificationCreated: response.notification_created,
  };
}

function mapReport(response: ReportResponse): Report {
  return {
    id: response.id,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    reportType: response.report_type,
    title: response.title,
    content: response.content,
    status: response.status,
    periodStart: response.period_start,
    periodEnd: response.period_end,
    createdAt: response.created_at,
  };
}

function getMockAutomationGitHubToolReport(
  input: AutomationGitHubToolReportInput,
): AutomationGitHubToolReport {
  const now = new Date().toISOString();
  return {
    generatedAt: now,
    authorizationConfirmed: input.authorized,
    dataset: {
      id: input.datasetId,
      projectId: "project_marketplace_price",
      name: "GitHub Tool Radar mock",
      datasetType: "github_tool_radar",
      status: "active",
      description: "Mock GitHub tool radar dataset.",
    },
    version: {
      id: input.datasetVersionId,
      datasetId: input.datasetId,
      cleaningPlanId: null,
      versionNumber: 1,
      sourceTaskRunIds: [],
      selectedFields: [
        "repo_full_name",
        "stars",
        "html_url",
        "language",
        "topics",
        "license_spdx_id",
        "default_branch",
        "latest_release_tag",
        "updated_at",
      ],
      cleaningScript: [],
      rowCount: 2,
      averageCompletenessPercent: 100,
      status: "saved",
      createdAt: now,
      exportPreview: {},
    },
    summary: {
      repositoryCount: 2,
      totalStars: 128000,
      highValueRepositories: 2,
      licensedRepositories: 2,
      releaseTaggedRepositories: 2,
      readmeDocumentedRepositories: 2,
      issueActiveRepositories: 2,
      freshCommitRepositories: 2,
      archivedRepositories: 0,
      forkRepositories: 0,
      languages: { Python: 2 },
      topTopics: {
        "ai-agent": 1,
        "browser-automation": 1,
        crawler: 1,
        scraping: 1,
      },
      reportCreated: false,
      runStarted: false,
    },
    topRepositories: [
      {
        repoFullName: "browser-use/browser-use",
        htmlUrl: "https://github.com/browser-use/browser-use",
        description: "Make websites accessible for AI agents",
        stars: 72000,
        forks: 8400,
        openIssues: 120,
        watchers: 72000,
        language: "Python",
        topics: ["browser-automation", "ai-agent"],
        licenseSpdxId: "MIT",
        defaultBranch: "main",
        latestReleaseTag: "v0.4.0",
        latestReleasePublishedAt: now,
        archived: false,
        fork: false,
        updatedAt: now,
        pushedAt: now,
        readmeDetected: true,
        readmeHtmlUrl: "https://github.com/browser-use/browser-use/blob/main/README.md",
        readmeSize: 12000,
        issueActivityOpenCount: 120,
        issueActivityStatus: "active",
        commitFreshnessDays: 0,
        commitFreshnessStatus: "fresh",
        maintenanceRisk: "low",
        riskSignals: [],
        installSources: ["repository_url", "latest_release", "readme_metadata"],
        recommendedUseCases: [
          "collection_tool_benchmark",
          "agent_browser_workflow_reference",
          "python_collector_stack_reference",
          "high_adoption_training_candidate",
        ],
        unsuitableBoundaries: [
          "not_a_license_clearance",
          "not_a_security_audit",
          "not_a_provider_call_or_live_install",
        ],
      },
    ],
    recommendations: [
      "browser-use/browser-use 具备 72000 stars，MIT，最新 release v0.4.0；维护风险=low；可优先用于 AI 浏览器自动化培训与 SOP 编写。",
    ],
    riskSections: [
      {
        title: "维护风险",
        items: ["low=2", "medium=0", "high=0", "unknown=0"],
        evidenceFields: [
          "archived",
          "license_spdx_id",
          "latest_release_tag",
          "readme_detected",
          "commit_freshness_days",
        ],
      },
      {
        title: "适用采集场景",
        items: ["collection_tool_benchmark", "agent_browser_workflow_reference"],
      },
      {
        title: "不适用边界",
        items: [
          "not_a_license_clearance",
          "not_a_security_audit",
          "not_a_provider_call_or_live_install",
        ],
      },
    ],
    auditEvents: [],
    blockedReasons: ["Mock 报告不会启动采集、创建报告资产或发送通知。"],
  };
}

function getMockAutomationGitHubToolReportAsset(
  input: AutomationGitHubToolReportAssetInput,
): AutomationGitHubToolReportAsset {
  const report = getMockAutomationGitHubToolReport(input);
  const now = new Date().toISOString();
  return {
    ...report,
    generatedAt: now,
    summary: {
      ...report.summary,
      reportCreated: input.confirmCreate,
      runStarted: false,
    },
    auditEvents: [
      ...report.auditEvents,
      {
        event: "github_tool_report_asset_created",
        report_created: input.confirmCreate,
        run_started: false,
        notification_created: false,
      },
    ],
    blockedReasons: ["Mock 报告资产已保存；不会启动采集、创建通知或发送邮件。"],
    report: {
      id: "report_github_tool_radar_mock",
      workspaceId: "workspace_demo",
      projectId: "project_marketplace_price",
      reportType: "github_tool_radar",
      title: "GitHub 工具雷达报告 - GitHub Tool Radar mock v1",
      content: "github_tool_radar\nschema_version: github_tool_radar.v2\n## 维护风险与使用边界\nbrowser-use/browser-use",
      status: "generated",
      periodStart: now,
      periodEnd: now,
      createdAt: now,
    },
    notificationCreated: false,
  };
}

function getMockAutomationPublicContentReport(
  input: AutomationPublicContentReportInput,
): AutomationPublicContentReport {
  const now = new Date().toISOString();
  return {
    generatedAt: now,
    authorizationConfirmed: input.authorized,
    dataset: {
      id: input.datasetId,
      projectId: "project_public_content",
      name: "Public Content Updates mock",
      datasetType: "public_content_update",
      status: "active",
      description: "Mock public feed dataset.",
    },
    version: {
      id: input.datasetVersionId,
      datasetId: input.datasetId,
      cleaningPlanId: null,
      versionNumber: 1,
      sourceTaskRunIds: [],
      selectedFields: [
        "title",
        "link",
        "published_at",
        "author",
        "summary",
        "content_hash",
      ],
      cleaningScript: [],
      rowCount: 2,
      averageCompletenessPercent: 90,
      status: "saved",
      createdAt: now,
      exportPreview: {},
    },
    summary: {
      entryCount: 2,
      feedCount: 1,
      uniqueAuthorCount: 1,
      taggedEntryCount: 1,
      entriesWithSummary: 2,
      contentHashCount: 2,
      reportCreated: false,
      runStarted: false,
    },
    latestEntries: [
      {
        title: "Launch notes",
        link: "https://example.com/blog/launch",
        feedUrl: "https://example.com/feed.xml",
        feedTitle: "Example updates",
        publishedAt: now,
        updatedAt: now,
        author: "Docs Team",
        tags: ["release"],
        summary: "A public content update.",
        contentHash: "hash-launch-v1",
      },
    ],
    recommendations: [
      "继续使用 RSS/Atom 作为低风险公开内容入口，并用 content_hash 监控内容变化。",
    ],
    riskSections: [
      {
        title: "内容主键与漂移信号",
        items: ["drift_signal=content_hash", "dedupe_key=link"],
        evidenceFields: ["link", "content_hash"],
      },
    ],
    auditEvents: [],
    blockedReasons: ["Mock 公开内容报告不会启动采集、创建报告资产或发送通知。"],
  };
}

function getMockAutomationPublicContentReportAsset(
  input: AutomationPublicContentReportAssetInput,
): AutomationPublicContentReportAsset {
  const report = getMockAutomationPublicContentReport(input);
  const now = new Date().toISOString();
  return {
    ...report,
    generatedAt: now,
    summary: {
      ...report.summary,
      reportCreated: input.confirmCreate,
      runStarted: false,
    },
    auditEvents: [
      ...report.auditEvents,
      {
        event: "public_content_report_asset_created",
        report_created: input.confirmCreate,
        run_started: false,
        notification_created: false,
      },
    ],
    blockedReasons: [
      "Mock 公开内容报告资产已保存；不会启动采集、创建通知、发送邮件或写出导出文件。",
    ],
    report: {
      id: "report_public_content_update_mock",
      workspaceId: "workspace_demo",
      projectId: "project_public_content",
      reportType: "public_content_update",
      title: "公开内容更新报告 - Public Content Updates mock v1",
      content: "public_content_update\nschema_version: public_content_update.v1\n## 内容风险与边界\nLaunch notes",
      status: "generated",
      periodStart: now,
      periodEnd: now,
      createdAt: now,
    },
    notificationCreated: false,
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
