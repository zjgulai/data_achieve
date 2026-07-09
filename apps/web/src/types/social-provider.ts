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
  raw_record_id: string;
  evidence_ref: string;
  source_schema_version: string;
  payload: Record<string, unknown>;
};

export type SocialDatasetPreviewRow = {
  rowId: string;
  rawRecordId: string;
  evidenceRef: string;
  sourceSchemaVersion: string;
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
