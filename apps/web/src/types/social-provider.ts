export type SocialProviderPlatform =
  | "youtube"
  | "reddit"
  | "x"
  | "instagram"
  | "threads"
  | "tiktok"
  | "linkedin";

export type SocialExecutionDryRunInput = {
  platform: SocialProviderPlatform;
  endpoint: string;
  fixtureLimit: number;
  intendedUse: string;
  datasetName?: string;
  sourceName?: string;
  taskName?: string;
  credentialReference?: string;
  maxRequests?: number;
  maxItems?: number;
  maxRows?: number;
};

export type SocialExecutionDryRunRequestDto = {
  platform: SocialProviderPlatform;
  endpoint: string;
  fixture_limit: number;
  intended_use: string;
  dataset_name?: string;
  source_name?: string;
  task_name?: string;
  credential_reference?: string;
  credentials_ready: false;
  authorized: false;
  include_live_comparison: false;
  dataset_save_requested: false;
  export_requested: false;
  allow_ai_training: false;
  max_requests: number;
  max_items: number;
  max_rows: number;
  max_cost_usd: 0;
  retention_hours: 24;
  author_policy: "hashed";
  cleanup_policy: "cleanup_after_evidence";
};

export type SocialProviderCatalogResponseDto = {
  schema_version: "external_provider_catalog.v1";
  evidence_level: string;
  provider_call: boolean;
  generated_at: string;
  providers: SocialProviderCatalogItemDto[];
};

export type SocialProviderCatalogItemDto = {
  provider_id: string;
  platform: string;
  data_domain: string[];
  resource_groups: string[];
  official_docs: string[];
  sdk_selection: SocialProviderSdkSelectionDto | null;
  live_adapter_strategy: string;
  auth_mode: string;
  quota_hint: Record<string, unknown>;
  policy_flags: string[];
  blocked_actions: string[];
  stability: string;
  self_host_priority: string;
  api_version: string;
  required_credentials: string[];
  supported_endpoints: string[];
  endpoint_contracts?: Array<Record<string, unknown>>;
};

export type SocialProviderSdkSelectionDto = {
  package: string;
  import_name: string | null;
  source_url: string;
  status: "selected" | "candidate" | "manual_review" | "blocked";
  reason: string;
};

export type SocialProviderReadinessInput = {
  platform: SocialProviderPlatform;
  endpoints: string[];
};

export type SocialDatasetPreviewInput = {
  platform: SocialProviderPlatform;
  endpoint: string;
  fixtureLimit: number;
  datasetName?: string;
  maxRows?: number;
};

export type SocialProviderSourceTemplateInput = {
  platform: SocialProviderPlatform;
  endpoints: string[];
  sourceName?: string;
  fixtureLimit?: number;
};

export type SocialTaskRunApprovalTemplateInput = {
  platform: SocialProviderPlatform;
  endpoints: string[];
  intendedUse: string;
  sourceName?: string;
  taskName?: string;
  datasetName?: string;
  credentialReference?: string;
  maxRequests?: number;
  maxItems?: number;
  maxRows?: number;
};

export type SocialProviderReadinessRequestDto = {
  platform: SocialProviderPlatform;
  endpoints: string[];
  credentials_ready: false;
  dry_run: true;
  policy_context: {
    allow_ai_training: false;
    allow_private_profile_merge: false;
    allow_login_state_collection: false;
    max_retention_hours: 24;
  };
};

export type SocialDatasetPreviewRequestDto = {
  platform: SocialProviderPlatform;
  endpoint: string;
  fixture_limit: number;
  dataset_name?: string;
  max_rows: number;
  include_live_comparison: false;
  authorized: false;
  author_policy: "hashed";
  save_requested: false;
  export_requested: false;
};

export type SocialProviderSourceTemplateRequestDto = {
  platform: SocialProviderPlatform;
  endpoints: string[];
  source_name?: string;
  authorized: false;
  fixture_limit: number;
  credential_reference?: undefined;
};

export type SocialTaskRunApprovalTemplateRequestDto = {
  platform: SocialProviderPlatform;
  endpoints: string[];
  intended_use: string;
  source_name?: string;
  task_name?: string;
  dataset_name?: string;
  credential_reference?: string;
  authorized: false;
  max_requests: number;
  max_items: number;
  max_rows: number;
  max_cost_usd: 0;
  retention_hours: 24;
  allow_ai_training: false;
  dataset_save_requested: false;
  export_requested: false;
  cleanup_policy: "cleanup_after_evidence";
};

export type SocialProviderReadinessResponseDto = {
  schema_version: "social_provider_readiness.v1";
  platform: string;
  provider_id: string;
  readiness: boolean;
  missing_credentials: string[];
  missing_scope: string[];
  blocked_reasons: string[];
  policy_blockers: string[];
  forbidden_actions: string[];
  rate_limit_profile: SocialProviderRateLimitProfileDto;
  provider_call_allowed: boolean;
  provider_call_attempted: boolean;
  dry_run: boolean;
  checked_at?: string;
};

export type SocialProviderRateLimitProfileDto = {
  provider_id: string;
  requested: Record<string, unknown>;
  catalog_hint: Record<string, unknown>;
  budget_status: string;
  effective_limits: Record<string, unknown>;
  estimated_cost_usd: number | null;
};

export type SocialDatasetPreviewResponseDto = {
  schema_version: "social_dataset_preview.v1";
  platform: string;
  provider_id: string;
  endpoint: string;
  dataset_name: string;
  dataset_type: "social_voc_fixture_preview";
  dataset_schema_version: "social_voc_dataset.v1";
  fixture_only: boolean;
  provider_call_allowed: boolean;
  provider_call_attempted: boolean;
  credential_read_attempted: boolean;
  production_write_allowed: boolean;
  dataset_write_allowed: boolean;
  dataset_created: boolean;
  dataset_version_created: boolean;
  export_created: boolean;
  live_comparison_available: boolean;
  blocked_reasons: string[];
  source_item_count: number;
  row_count: number;
  max_rows: number;
  truncated: boolean;
  rows: SocialDatasetPreviewRowDto[];
  normalized_items: Array<Record<string, unknown>>;
  sdk_selection: SocialProviderSdkSelectionDto | null;
  next_required_authorization: string;
  checked_at?: string;
};

export type SocialProviderSourceTemplateResponseDto = {
  schema_version: "social_provider_source_template.v1";
  platform: string;
  provider_id: string;
  source_type: "manual_json";
  template_strategy: "manual_json_authorized_import";
  fixture_only: boolean;
  source_create_allowed: boolean;
  source_created: boolean;
  task_created: boolean;
  provider_call_attempted: boolean;
  credential_read_attempted: boolean;
  production_write_allowed: boolean;
  source_create_payload: Record<string, unknown> | null;
  blocked_reasons: string[];
  next_required_authorization: string;
  checked_at?: string;
};

export type SocialTaskRunApprovalTemplateResponseDto = {
  schema_version: "social_task_run_approval_template.v1";
  platform: string;
  provider_id: string;
  sdk_selection: SocialProviderSdkSelectionDto | null;
  approval_packet: Record<string, unknown>;
  required_confirmations: string[];
  blocked_reasons: string[];
  provider_call_allowed: boolean;
  provider_call_attempted: boolean;
  credential_read_attempted: boolean;
  source_create_allowed: boolean;
  task_create_allowed: boolean;
  task_run_allowed: boolean;
  dataset_write_allowed: boolean;
  export_allowed: boolean;
  production_write_allowed: boolean;
  next_required_authorization: string;
  checked_at?: string;
};

export type SocialProviderCatalog = {
  schemaVersion: "external_provider_catalog.v1";
  evidenceLevel: string;
  providerCall: boolean;
  generatedAt: string;
  providers: SocialProviderCatalogItem[];
};

export type SocialProviderCatalogItem = {
  providerId: string;
  platform: string;
  dataDomain: string[];
  resourceGroups: string[];
  officialDocs: string[];
  sdkSelection: SocialProviderSdkSelection | null;
  liveAdapterStrategy: string;
  authMode: string;
  quotaHint: Record<string, unknown>;
  policyFlags: string[];
  blockedActions: string[];
  stability: string;
  selfHostPriority: string;
  apiVersion: string;
  requiredCredentials: string[];
  supportedEndpoints: string[];
};

export type SocialProviderSdkSelection = {
  package: string;
  importName: string | null;
  sourceUrl: string;
  status: "selected" | "candidate" | "manual_review" | "blocked";
  reason: string;
};

export type SocialProviderReadiness = {
  schemaVersion: "social_provider_readiness.v1";
  platform: string;
  providerId: string;
  ready: boolean;
  missingCredentials: string[];
  missingScope: string[];
  blockedReasons: string[];
  policyBlockers: string[];
  forbiddenActions: string[];
  rateLimitProfile: SocialProviderRateLimitProfile;
  providerCallAllowed: boolean;
  providerCallAttempted: boolean;
  dryRun: boolean;
};

export type SocialProviderRateLimitProfile = {
  providerId: string;
  requested: Record<string, unknown>;
  catalogHint: Record<string, unknown>;
  budgetStatus: string;
  effectiveLimits: Record<string, unknown>;
  estimatedCostUsd: number | null;
};

export type SocialDatasetPreview = {
  schemaVersion: "social_dataset_preview.v1";
  platform: string;
  providerId: string;
  endpoint: string;
  datasetName: string;
  datasetType: "social_voc_fixture_preview";
  datasetSchemaVersion: "social_voc_dataset.v1";
  fixtureOnly: boolean;
  providerCallAllowed: boolean;
  providerCallAttempted: boolean;
  credentialReadAttempted: boolean;
  productionWriteAllowed: boolean;
  datasetWriteAllowed: boolean;
  datasetCreated: boolean;
  datasetVersionCreated: boolean;
  exportCreated: boolean;
  liveComparisonAvailable: boolean;
  blockedReasons: string[];
  sourceItemCount: number;
  rowCount: number;
  maxRows: number;
  truncated: boolean;
  rows: SocialDatasetPreviewRow[];
  nextRequiredAuthorization: string;
};

export type SocialProviderSourceTemplate = {
  schemaVersion: "social_provider_source_template.v1";
  platform: string;
  providerId: string;
  sourceType: "manual_json";
  templateStrategy: "manual_json_authorized_import";
  fixtureOnly: boolean;
  sourceCreateAllowed: boolean;
  sourceCreated: boolean;
  taskCreated: boolean;
  providerCallAttempted: boolean;
  credentialReadAttempted: boolean;
  productionWriteAllowed: boolean;
  sourceCreatePayload: Record<string, unknown> | null;
  payloadPresent: boolean;
  blockedReasons: string[];
  nextRequiredAuthorization: string;
};

export type SocialTaskRunApprovalTemplate = {
  schemaVersion: "social_task_run_approval_template.v1";
  platform: string;
  providerId: string;
  approvalPacket: Record<string, unknown>;
  requiredConfirmations: string[];
  blockedReasons: string[];
  providerCallAllowed: boolean;
  providerCallAttempted: boolean;
  credentialReadAttempted: boolean;
  sourceCreateAllowed: boolean;
  taskCreateAllowed: boolean;
  taskRunAllowed: boolean;
  datasetWriteAllowed: boolean;
  exportAllowed: boolean;
  productionWriteAllowed: boolean;
  nextRequiredAuthorization: string;
};

export type SocialExecutionStageName =
  | "readiness"
  | "raw_preview"
  | "normalization_preview"
  | "dataset_preview"
  | "source_template"
  | "task_run_approval_template";

export type SocialExecutionDryRunStageDto = {
  stage: SocialExecutionStageName;
  status: "ready" | "blocked" | "previewed";
  blocked_reasons: string[];
  provider_call: boolean;
  credential_read: boolean;
  production_write: boolean;
  details: Record<string, unknown>;
};

export type SocialExecutionDryRunStage = {
  stage: SocialExecutionStageName;
  status: "ready" | "blocked" | "previewed";
  blockedReasons: string[];
  providerCall: boolean;
  credentialRead: boolean;
  productionWrite: boolean;
  details: Record<string, unknown>;
};

export type SocialExecutionDryRunResponseDto = {
  schema_version: "social_execution_dry_run.v1";
  platform: string;
  provider_id: string;
  endpoint: string;
  fixture_only: boolean;
  provider_call_allowed: boolean;
  provider_call_attempted: boolean;
  credential_read_attempted: boolean;
  source_create_allowed: boolean;
  task_create_allowed: boolean;
  task_run_allowed: boolean;
  dataset_write_allowed: boolean;
  export_allowed: boolean;
  production_write_allowed: boolean;
  live_comparison_available: boolean;
  blocked_reasons: string[];
  execution_plan: SocialExecutionDryRunStageDto[];
  readiness: {
    readiness: boolean;
    missing_credentials: string[];
    missing_scope: string[];
    blocked_reasons: string[];
    provider_call_allowed: boolean;
    provider_call_attempted: boolean;
  };
  raw_preview: {
    records: Array<{
      schema_version: string;
      raw_record_id: string;
      evidence_ref: string;
    }>;
  };
  normalization_preview: {
    normalized_items: Array<{
      schema_version: string;
      item_id: string;
      raw_record_id: string;
      evidence_ref: string;
    }>;
  };
  dataset_preview: {
    dataset_name: string;
    row_count: number;
    source_item_count: number;
    truncated: boolean;
    rows: SocialDatasetPreviewRowDto[];
  };
  source_template: {
    source_create_allowed: boolean;
    source_created: boolean;
    task_created: boolean;
    source_create_payload: Record<string, unknown> | null;
  };
  task_run_approval_template: {
    task_run_allowed: boolean;
    dataset_write_allowed: boolean;
    approval_packet: Record<string, unknown>;
  };
  next_required_authorization: string;
};

export type SocialDatasetPreviewRowDto = {
  row_id: string;
  provider_id?: string;
  platform?: string;
  raw_record_id: string;
  evidence_ref: string;
  source_item_id?: string;
  source_schema_version: string;
  author_policy?: "hashed" | "dropped" | "retained_with_approval";
  payload: Record<string, unknown>;
};

export type SocialDatasetPreviewRow = {
  rowId: string;
  providerId: string;
  platform: string;
  rawRecordId: string;
  evidenceRef: string;
  sourceItemId: string;
  sourceSchemaVersion: string;
  authorPolicy: "hashed" | "dropped" | "retained_with_approval";
  textExcerpt: string;
  providerCall: boolean;
  llmCallAttempted: boolean;
};

export type SocialExecutionDryRun = {
  schemaVersion: "social_execution_dry_run.v1";
  platform: string;
  providerId: string;
  endpoint: string;
  fixtureOnly: boolean;
  providerCallAllowed: boolean;
  providerCallAttempted: boolean;
  credentialReadAttempted: boolean;
  sourceCreateAllowed: boolean;
  taskCreateAllowed: boolean;
  taskRunAllowed: boolean;
  datasetWriteAllowed: boolean;
  exportAllowed: boolean;
  productionWriteAllowed: boolean;
  liveComparisonAvailable: boolean;
  blockedReasons: string[];
  executionPlan: SocialExecutionDryRunStage[];
  readiness: {
    ready: boolean;
    missingCredentials: string[];
    missingScope: string[];
    blockedReasons: string[];
    providerCallAllowed: boolean;
    providerCallAttempted: boolean;
  };
  rawRecordCount: number;
  normalizedItemCount: number;
  datasetPreview: {
    datasetName: string;
    rowCount: number;
    sourceItemCount: number;
    truncated: boolean;
    rows: SocialDatasetPreviewRow[];
  };
  sourceTemplate: {
    sourceCreateAllowed: boolean;
    sourceCreated: boolean;
    taskCreated: boolean;
    payloadPresent: boolean;
  };
  taskRunApprovalTemplate: {
    taskRunAllowed: boolean;
    datasetWriteAllowed: boolean;
    approvalPacket: Record<string, unknown>;
  };
  nextRequiredAuthorization: string;
};
