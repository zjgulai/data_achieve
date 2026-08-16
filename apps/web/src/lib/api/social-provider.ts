import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import { getSocialProviderUiConfig } from "@/lib/social-provider-config";
import type {
  SocialDatasetPreview,
  SocialDatasetPreviewInput,
  SocialDatasetPreviewRequestDto,
  SocialDatasetPreviewResponseDto,
  SocialDatasetPreviewRow,
  SocialDatasetPreviewRowDto,
  SocialExecutionDryRun,
  SocialExecutionDryRunInput,
  SocialExecutionDryRunRequestDto,
  SocialExecutionDryRunResponseDto,
  SocialExecutionDryRunStage,
  SocialExecutionDryRunStageDto,
  SocialProviderAdapterPlan,
  SocialProviderAdapterPlanInput,
  SocialProviderAdapterPlanRequestDto,
  SocialProviderAdapterPlanResponseDto,
  SocialProviderCatalog,
  SocialProviderCatalogItem,
  SocialProviderCatalogItemDto,
  SocialProviderCatalogResponseDto,
  SocialProviderPlatform,
  SocialProviderPlannedOperation,
  SocialProviderPlannedOperationDto,
  SocialProviderReadiness,
  SocialProviderReadinessInput,
  SocialProviderReadinessRequestDto,
  SocialProviderReadinessResponseDto,
  SocialProviderSdkSelection,
  SocialProviderSdkSelectionDto,
  SocialProviderSourceTemplate,
  SocialProviderSourceTemplateInput,
  SocialProviderSourceTemplateRequestDto,
  SocialProviderSourceTemplateResponseDto,
  SocialTaskRunApprovalTemplate,
  SocialTaskRunApprovalTemplateInput,
  SocialTaskRunApprovalTemplateRequestDto,
  SocialTaskRunApprovalTemplateResponseDto,
} from "@/types/social-provider";

export async function getSocialProviderCatalog(
  platform: SocialProviderPlatform,
): Promise<SocialProviderCatalog> {
  if (mockApiEnabled) {
    return mapSocialProviderCatalogResponse(mockSocialProviderCatalogResponse(platform));
  }

  const query = new URLSearchParams({ platform });
  const response = await apiFetch<SocialProviderCatalogResponseDto>(
    `/api/automation/social-provider-catalog?${query}`,
  );
  return mapSocialProviderCatalogResponse(response);
}

export async function checkSocialProviderReadiness(
  input: SocialProviderReadinessInput,
): Promise<SocialProviderReadiness> {
  if (mockApiEnabled) {
    return mapSocialProviderReadinessResponse(mockSocialProviderReadinessResponse(input));
  }

  const response = await apiFetch<SocialProviderReadinessResponseDto>(
    "/api/automation/social-provider-readiness",
    {
      body: JSON.stringify(buildSocialProviderReadinessRequestBody(input)),
      method: "POST",
    },
  );
  return mapSocialProviderReadinessResponse(response);
}

export async function previewSocialProviderAdapterPlan(
  input: SocialProviderAdapterPlanInput,
): Promise<SocialProviderAdapterPlan> {
  if (mockApiEnabled) {
    return mapSocialProviderAdapterPlanResponse(mockSocialProviderAdapterPlanResponse(input));
  }

  const response = await apiFetch<SocialProviderAdapterPlanResponseDto>(
    "/api/automation/social-provider-adapter-plan",
    {
      body: JSON.stringify(buildSocialProviderAdapterPlanRequestBody(input)),
      method: "POST",
    },
  );
  return mapSocialProviderAdapterPlanResponse(response);
}

export async function previewSocialDataset(
  input: SocialDatasetPreviewInput,
): Promise<SocialDatasetPreview> {
  if (mockApiEnabled) {
    return mapSocialDatasetPreviewResponse(mockSocialDatasetPreviewResponse(input));
  }

  const response = await apiFetch<SocialDatasetPreviewResponseDto>(
    "/api/automation/social-dataset-preview",
    {
      body: JSON.stringify(buildSocialDatasetPreviewRequestBody(input)),
      method: "POST",
    },
  );
  return mapSocialDatasetPreviewResponse(response);
}

export async function previewSocialProviderSourceTemplate(
  input: SocialProviderSourceTemplateInput,
): Promise<SocialProviderSourceTemplate> {
  if (mockApiEnabled) {
    return mapSocialProviderSourceTemplateResponse(mockSocialProviderSourceTemplateResponse(input));
  }

  const response = await apiFetch<SocialProviderSourceTemplateResponseDto>(
    "/api/automation/social-provider-source-template",
    {
      body: JSON.stringify(buildSocialProviderSourceTemplateRequestBody(input)),
      method: "POST",
    },
  );
  return mapSocialProviderSourceTemplateResponse(response);
}

export async function previewSocialTaskRunApprovalTemplate(
  input: SocialTaskRunApprovalTemplateInput,
): Promise<SocialTaskRunApprovalTemplate> {
  if (mockApiEnabled) {
    return mapSocialTaskRunApprovalTemplateResponse(
      mockSocialTaskRunApprovalTemplateResponse(input),
    );
  }

  const response = await apiFetch<SocialTaskRunApprovalTemplateResponseDto>(
    "/api/automation/social-task-run-approval-template",
    {
      body: JSON.stringify(buildSocialTaskRunApprovalTemplateRequestBody(input)),
      method: "POST",
    },
  );
  return mapSocialTaskRunApprovalTemplateResponse(response);
}

export async function runSocialExecutionDryRun(
  input: SocialExecutionDryRunInput,
): Promise<SocialExecutionDryRun> {
  if (mockApiEnabled) {
    return mapSocialExecutionDryRunResponse(mockSocialExecutionDryRunResponse(input));
  }

  const response = await apiFetch<SocialExecutionDryRunResponseDto>(
    "/api/automation/social-execution-dry-run",
    {
      body: JSON.stringify(buildSocialExecutionDryRunRequestBody(input)),
      method: "POST",
    },
  );

  return mapSocialExecutionDryRunResponse(response);
}

export function buildSocialProviderReadinessRequestBody(
  input: SocialProviderReadinessInput,
): SocialProviderReadinessRequestDto {
  return {
    platform: input.platform,
    endpoints: input.endpoints,
    credentials_ready: false,
    dry_run: true,
    policy_context: {
      allow_ai_training: false,
      allow_private_profile_merge: false,
      allow_login_state_collection: false,
      max_retention_hours: 24,
    },
  };
}

export function buildSocialProviderAdapterPlanRequestBody(
  input: SocialProviderAdapterPlanInput,
): SocialProviderAdapterPlanRequestDto {
  return {
    platform: input.platform,
    endpoints: input.endpoints,
    mode: "fixture_replay",
    authorized: false,
    max_requests: input.maxRequests ?? 5,
    fixture_limit: input.fixtureLimit ?? 3,
  };
}

export function buildSocialDatasetPreviewRequestBody(
  input: SocialDatasetPreviewInput,
): SocialDatasetPreviewRequestDto {
  return {
    platform: input.platform,
    endpoint: input.endpoint,
    fixture_limit: input.fixtureLimit,
    dataset_name: input.datasetName,
    max_rows: input.maxRows ?? 20,
    include_live_comparison: false,
    authorized: false,
    author_policy: "hashed",
    save_requested: false,
    export_requested: false,
  };
}

export function buildSocialProviderSourceTemplateRequestBody(
  input: SocialProviderSourceTemplateInput,
): SocialProviderSourceTemplateRequestDto {
  return {
    platform: input.platform,
    endpoints: input.endpoints,
    source_name: input.sourceName,
    authorized: false,
    fixture_limit: input.fixtureLimit ?? 3,
  };
}

export function buildSocialTaskRunApprovalTemplateRequestBody(
  input: SocialTaskRunApprovalTemplateInput,
): SocialTaskRunApprovalTemplateRequestDto {
  return {
    platform: input.platform,
    endpoints: input.endpoints,
    intended_use: input.intendedUse,
    source_name: input.sourceName,
    task_name: input.taskName,
    dataset_name: input.datasetName,
    credential_reference: input.credentialReference,
    authorized: false,
    max_requests: input.maxRequests ?? 5,
    max_items: input.maxItems ?? 20,
    max_rows: input.maxRows ?? 20,
    max_cost_usd: 0,
    retention_hours: 24,
    allow_ai_training: false,
    dataset_save_requested: false,
    export_requested: false,
    cleanup_policy: "cleanup_after_evidence",
  };
}

export function buildSocialExecutionDryRunRequestBody(
  input: SocialExecutionDryRunInput,
): SocialExecutionDryRunRequestDto {
  return {
    platform: input.platform,
    endpoint: input.endpoint,
    fixture_limit: input.fixtureLimit,
    intended_use: input.intendedUse,
    dataset_name: input.datasetName,
    source_name: input.sourceName,
    task_name: input.taskName,
    credential_reference: input.credentialReference,
    credentials_ready: false,
    authorized: false,
    include_live_comparison: false,
    dataset_save_requested: false,
    export_requested: false,
    allow_ai_training: false,
    max_requests: input.maxRequests ?? 5,
    max_items: input.maxItems ?? 20,
    max_rows: input.maxRows ?? 20,
    max_cost_usd: 0,
    retention_hours: 24,
    author_policy: "hashed",
    cleanup_policy: "cleanup_after_evidence",
  };
}

export function mapSocialProviderAdapterPlanResponse(
  response: SocialProviderAdapterPlanResponseDto,
): SocialProviderAdapterPlan {
  return {
    schemaVersion: response.schema_version,
    platform: response.platform,
    providerId: response.provider_id,
    sdkSelection: response.sdk_selection ? mapSdkSelection(response.sdk_selection) : null,
    adapterModule: response.adapter_module,
    dependencyPresent: response.dependency_present,
    dependencyImportName: response.dependency_import_name,
    adapterReady: response.adapter_ready,
    providerCallAllowed: response.provider_call_allowed,
    providerCallAttempted: response.provider_call_attempted,
    credentialReadAttempted: response.credential_read_attempted,
    liveClientCreated: response.live_client_created,
    productionWriteAllowed: response.production_write_allowed,
    fixtureReplaySupported: response.fixture_replay_supported,
    plannedOperations: response.planned_operations.map(mapPlannedOperation),
    blockedReasons: response.blocked_reasons,
    nextRequiredAuthorization: response.next_required_authorization,
  };
}

export function mapSocialDatasetPreviewResponse(
  response: SocialDatasetPreviewResponseDto,
): SocialDatasetPreview {
  return {
    schemaVersion: response.schema_version,
    platform: response.platform,
    providerId: response.provider_id,
    endpoint: response.endpoint,
    datasetName: response.dataset_name,
    datasetType: response.dataset_type,
    datasetSchemaVersion: response.dataset_schema_version,
    fixtureOnly: response.fixture_only,
    providerCallAllowed: response.provider_call_allowed,
    providerCallAttempted: response.provider_call_attempted,
    credentialReadAttempted: response.credential_read_attempted,
    productionWriteAllowed: response.production_write_allowed,
    datasetWriteAllowed: response.dataset_write_allowed,
    datasetCreated: response.dataset_created,
    datasetVersionCreated: response.dataset_version_created,
    exportCreated: response.export_created,
    liveComparisonAvailable: response.live_comparison_available,
    blockedReasons: response.blocked_reasons,
    sourceItemCount: response.source_item_count,
    rowCount: response.row_count,
    maxRows: response.max_rows,
    truncated: response.truncated,
    rows: response.rows.map(mapDatasetRow),
    nextRequiredAuthorization: response.next_required_authorization,
  };
}

export function mapSocialProviderSourceTemplateResponse(
  response: SocialProviderSourceTemplateResponseDto,
): SocialProviderSourceTemplate {
  return {
    schemaVersion: response.schema_version,
    platform: response.platform,
    providerId: response.provider_id,
    sourceType: response.source_type,
    templateStrategy: response.template_strategy,
    fixtureOnly: response.fixture_only,
    sourceCreateAllowed: response.source_create_allowed,
    sourceCreated: response.source_created,
    taskCreated: response.task_created,
    providerCallAttempted: response.provider_call_attempted,
    credentialReadAttempted: response.credential_read_attempted,
    productionWriteAllowed: response.production_write_allowed,
    sourceCreatePayload: response.source_create_payload,
    payloadPresent: response.source_create_payload !== null,
    blockedReasons: response.blocked_reasons,
    nextRequiredAuthorization: response.next_required_authorization,
  };
}

export function mapSocialTaskRunApprovalTemplateResponse(
  response: SocialTaskRunApprovalTemplateResponseDto,
): SocialTaskRunApprovalTemplate {
  return {
    schemaVersion: response.schema_version,
    platform: response.platform,
    providerId: response.provider_id,
    approvalPacket: response.approval_packet,
    requiredConfirmations: response.required_confirmations,
    blockedReasons: response.blocked_reasons,
    providerCallAllowed: response.provider_call_allowed,
    providerCallAttempted: response.provider_call_attempted,
    credentialReadAttempted: response.credential_read_attempted,
    sourceCreateAllowed: response.source_create_allowed,
    taskCreateAllowed: response.task_create_allowed,
    taskRunAllowed: response.task_run_allowed,
    datasetWriteAllowed: response.dataset_write_allowed,
    exportAllowed: response.export_allowed,
    productionWriteAllowed: response.production_write_allowed,
    nextRequiredAuthorization: response.next_required_authorization,
  };
}

export function mapSocialProviderCatalogResponse(
  response: SocialProviderCatalogResponseDto,
): SocialProviderCatalog {
  return {
    schemaVersion: response.schema_version,
    evidenceLevel: response.evidence_level,
    providerCall: response.provider_call,
    generatedAt: response.generated_at,
    providers: response.providers.map(mapCatalogItem),
  };
}

export function mapSocialProviderReadinessResponse(
  response: SocialProviderReadinessResponseDto,
): SocialProviderReadiness {
  return {
    schemaVersion: response.schema_version,
    platform: response.platform,
    providerId: response.provider_id,
    ready: response.readiness,
    declaredReadiness: response.declared_readiness,
    readinessBasis: response.readiness_basis,
    executionEnabled: response.execution_enabled,
    missingCredentials: response.missing_credentials,
    missingScope: response.missing_scope,
    blockedReasons: response.blocked_reasons,
    policyBlockers: response.policy_blockers,
    forbiddenActions: response.forbidden_actions,
    rateLimitProfile: {
      providerId: response.rate_limit_profile.provider_id,
      requested: response.rate_limit_profile.requested,
      catalogHint: response.rate_limit_profile.catalog_hint,
      budgetStatus: response.rate_limit_profile.budget_status,
      effectiveLimits: response.rate_limit_profile.effective_limits,
      estimatedCostUsd: response.rate_limit_profile.estimated_cost_usd,
    },
    providerCallAllowed: response.provider_call_allowed,
    providerCallAttempted: response.provider_call_attempted,
    dryRun: response.dry_run,
  };
}

export function mapSocialExecutionDryRunResponse(
  response: SocialExecutionDryRunResponseDto,
): SocialExecutionDryRun {
  return {
    schemaVersion: response.schema_version,
    platform: response.platform,
    providerId: response.provider_id,
    endpoint: response.endpoint,
    fixtureOnly: response.fixture_only,
    providerCallAllowed: response.provider_call_allowed,
    providerCallAttempted: response.provider_call_attempted,
    credentialReadAttempted: response.credential_read_attempted,
    sourceCreateAllowed: response.source_create_allowed,
    taskCreateAllowed: response.task_create_allowed,
    taskRunAllowed: response.task_run_allowed,
    datasetWriteAllowed: response.dataset_write_allowed,
    exportAllowed: response.export_allowed,
    productionWriteAllowed: response.production_write_allowed,
    liveComparisonAvailable: response.live_comparison_available,
    blockedReasons: response.blocked_reasons,
    executionPlan: response.execution_plan.map(mapStage),
    readiness: {
      ready: response.readiness.readiness,
      missingCredentials: response.readiness.missing_credentials,
      missingScope: response.readiness.missing_scope,
      blockedReasons: response.readiness.blocked_reasons,
      providerCallAllowed: response.readiness.provider_call_allowed,
      providerCallAttempted: response.readiness.provider_call_attempted,
    },
    rawRecordCount: response.raw_preview.records.length,
    normalizedItemCount: response.normalization_preview.normalized_items.length,
    datasetPreview: {
      datasetName: response.dataset_preview.dataset_name,
      rowCount: response.dataset_preview.row_count,
      sourceItemCount: response.dataset_preview.source_item_count,
      truncated: response.dataset_preview.truncated,
      rows: response.dataset_preview.rows.map(mapDatasetRow),
    },
    sourceTemplate: {
      sourceCreateAllowed: response.source_template.source_create_allowed,
      sourceCreated: response.source_template.source_created,
      taskCreated: response.source_template.task_created,
      payloadPresent: response.source_template.source_create_payload !== null,
    },
    taskRunApprovalTemplate: {
      taskRunAllowed: response.task_run_approval_template.task_run_allowed,
      datasetWriteAllowed: response.task_run_approval_template.dataset_write_allowed,
      approvalPacket: response.task_run_approval_template.approval_packet,
    },
    nextRequiredAuthorization: response.next_required_authorization,
  };
}

function mapCatalogItem(item: SocialProviderCatalogItemDto): SocialProviderCatalogItem {
  return {
    providerId: item.provider_id,
    platform: item.platform,
    dataDomain: item.data_domain,
    resourceGroups: item.resource_groups,
    officialDocs: item.official_docs,
    sdkSelection: item.sdk_selection ? mapSdkSelection(item.sdk_selection) : null,
    liveAdapterStrategy: item.live_adapter_strategy,
    authMode: item.auth_mode,
    quotaHint: item.quota_hint,
    policyFlags: item.policy_flags,
    blockedActions: item.blocked_actions,
    stability: item.stability,
    selfHostPriority: item.self_host_priority,
    apiVersion: item.api_version,
    requiredCredentials: item.required_credentials,
    supportedEndpoints: item.supported_endpoints,
  };
}

function mapSdkSelection(selection: SocialProviderSdkSelectionDto): SocialProviderSdkSelection {
  return {
    package: selection.package,
    importName: selection.import_name,
    sourceUrl: selection.source_url,
    status: selection.status,
    reason: selection.reason,
  };
}

function mapStage(stage: SocialExecutionDryRunStageDto): SocialExecutionDryRunStage {
  return {
    stage: stage.stage,
    status: stage.status,
    blockedReasons: stage.blocked_reasons,
    providerCall: stage.provider_call,
    credentialRead: stage.credential_read,
    productionWrite: stage.production_write,
    details: stage.details,
  };
}

function mapDatasetRow(row: SocialDatasetPreviewRowDto): SocialDatasetPreviewRow {
  return {
    rowId: row.row_id,
    providerId: row.provider_id ?? "",
    platform: row.platform ?? "",
    rawRecordId: row.raw_record_id,
    evidenceRef: row.evidence_ref,
    sourceItemId: row.source_item_id ?? "",
    sourceSchemaVersion: row.source_schema_version,
    authorPolicy: row.author_policy ?? "hashed",
    textExcerpt: stringValue(row.payload.text_excerpt),
    providerCall: booleanValue(row.payload.provider_call),
    llmCallAttempted: booleanValue(row.payload.llm_call_attempted),
  };
}

function mapPlannedOperation(
  operation: SocialProviderPlannedOperationDto,
): SocialProviderPlannedOperation {
  return {
    operation: stringValue(operation.operation),
    endpoint: stringValue(operation.endpoint),
    mode: stringValue(operation.mode),
    providerCall: booleanValue(operation.provider_call),
    credentialRead: booleanValue(operation.credential_read),
    productionWrite: booleanValue(operation.production_write),
    liveClientCreated: booleanValue(operation.live_client_created),
    fixtureLimit: numberValue(operation.fixture_limit),
  };
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function numberValue(value: unknown): number {
  return typeof value === "number" ? value : 0;
}

function booleanValue(value: unknown): boolean {
  return typeof value === "boolean" ? value : false;
}

function mockSocialProviderCatalogResponse(
  platform: SocialProviderPlatform,
): SocialProviderCatalogResponseDto {
  return {
    schema_version: "external_provider_catalog.v1",
    evidence_level: "L1-public-or-runtime",
    provider_call: false,
    generated_at: "2026-07-08",
    providers: [mockCatalogItem(platform)],
  };
}

function mockCatalogItem(platform: SocialProviderPlatform): SocialProviderCatalogItemDto {
  const config = getSocialProviderUiConfig(platform);
  const metadata = mockProviderMetadata[platform];
  return {
    provider_id: config.providerId,
    platform,
    data_domain: metadata.dataDomain,
    resource_groups: metadata.resourceGroups,
    official_docs: metadata.officialDocs,
    sdk_selection: metadata.sdkSelection,
    live_adapter_strategy: metadata.liveAdapterStrategy,
    auth_mode: metadata.authMode,
    quota_hint: metadata.quotaHint,
    policy_flags: metadata.policyFlags,
    blocked_actions: metadata.blockedActions,
    stability: metadata.stability,
    self_host_priority: metadata.selfHostPriority,
    api_version: metadata.apiVersion,
    required_credentials: metadata.requiredCredentials,
    supported_endpoints: config.endpoints.map((endpoint) => endpoint.value),
    endpoint_contracts: [],
  };
}

function mockSocialProviderReadinessResponse(
  input: SocialProviderReadinessInput,
): SocialProviderReadinessResponseDto {
  const catalogItem = mockCatalogItem(input.platform);
  return {
    schema_version: "social_provider_readiness.v2",
    platform: input.platform,
    provider_id: catalogItem.provider_id,
    readiness: false,
    declared_readiness: false,
    readiness_basis: "caller_declared",
    execution_enabled: false,
    missing_credentials: catalogItem.required_credentials,
    missing_scope: input.endpoints.filter(
      (endpoint) => !catalogItem.supported_endpoints.includes(endpoint),
    ),
    blocked_reasons: catalogItem.required_credentials.map(
      (credential) => `credential_missing:${credential}`,
    ),
    policy_blockers: catalogItem.policy_flags.includes("no_ai_training")
      ? ["policy:no_ai_training"]
      : [],
    forbidden_actions: catalogItem.blocked_actions,
    rate_limit_profile: {
      provider_id: catalogItem.provider_id,
      requested: {},
      catalog_hint: catalogItem.quota_hint,
      budget_status: "within_default_catalog_hint",
      effective_limits: catalogItem.quota_hint,
      estimated_cost_usd: null,
    },
    provider_call_allowed: false,
    provider_call_attempted: false,
    dry_run: true,
  };
}

function mockSocialProviderAdapterPlanResponse(
  input: SocialProviderAdapterPlanInput,
): SocialProviderAdapterPlanResponseDto {
  const catalogItem = mockCatalogItem(input.platform);
  const fixtureLimit = input.fixtureLimit ?? 3;
  const dependencyImportName = catalogItem.sdk_selection?.import_name ?? null;
  return {
    schema_version: "social_provider_adapter_plan.v1",
    platform: input.platform,
    provider_id: catalogItem.provider_id,
    sdk_selection: catalogItem.sdk_selection,
    adapter_module: adapterModuleForPlatform(input.platform),
    dependency_present: false,
    dependency_import_name: dependencyImportName,
    adapter_ready: Boolean(catalogItem.sdk_selection),
    provider_call_allowed: false,
    provider_call_attempted: false,
    credential_read_attempted: false,
    live_client_created: false,
    production_write_allowed: false,
    fixture_replay_supported: true,
    planned_operations: input.endpoints.map((endpoint) => ({
      operation: "fixture_replay",
      endpoint,
      mode: "fixture",
      provider_call: false,
      credential_read: false,
      production_write: false,
      live_client_created: false,
      fixture_limit: fixtureLimit,
    })),
    blocked_reasons: catalogItem.sdk_selection
      ? [`dependency_not_installed:${catalogItem.sdk_selection.package}`]
      : ["adapter_metadata_missing"],
    next_required_authorization: "L4_social_provider_live_adapter_authorization_required",
  };
}

function mockSocialDatasetPreviewResponse(
  input: SocialDatasetPreviewInput,
): SocialDatasetPreviewResponseDto {
  const providerId = getSocialProviderUiConfig(input.platform).providerId;
  const rowCount = Math.min(input.fixtureLimit, input.maxRows ?? 20);
  const rows = Array.from({ length: rowCount }, (_, index) =>
    mockDatasetRow(input.platform, providerId, input.endpoint, index + 1),
  );
  return {
    schema_version: "social_dataset_preview.v1",
    platform: input.platform,
    provider_id: providerId,
    endpoint: input.endpoint,
    dataset_name: input.datasetName ?? `${input.platform} social VOC fixture dataset`,
    dataset_type: "social_voc_fixture_preview",
    dataset_schema_version: "social_voc_dataset.v1",
    fixture_only: true,
    provider_call_allowed: false,
    provider_call_attempted: false,
    credential_read_attempted: false,
    production_write_allowed: false,
    dataset_write_allowed: false,
    dataset_created: false,
    dataset_version_created: false,
    export_created: false,
    live_comparison_available: false,
    blocked_reasons: [],
    source_item_count: rowCount,
    row_count: rowCount,
    max_rows: input.maxRows ?? 20,
    truncated: input.fixtureLimit > (input.maxRows ?? 20),
    rows,
    normalized_items: rows.map((row) => ({
      schema_version: "social_voc_item.v1",
      item_id: row.source_item_id ?? row.row_id,
      provider_id: providerId,
      platform: input.platform,
      raw_record_id: row.raw_record_id,
      evidence_ref: row.evidence_ref,
      author_policy: "hashed",
      payload: {
        text_excerpt: row.payload.text_excerpt,
      },
    })),
    sdk_selection: null,
    next_required_authorization: "L4_social_dataset_save_authorization_required",
  };
}

function mockSocialProviderSourceTemplateResponse(
  input: SocialProviderSourceTemplateInput,
): SocialProviderSourceTemplateResponseDto {
  const providerId = getSocialProviderUiConfig(input.platform).providerId;
  return {
    schema_version: "social_provider_source_template.v1",
    platform: input.platform,
    provider_id: providerId,
    source_type: "manual_json",
    template_strategy: "manual_json_authorized_import",
    fixture_only: true,
    source_create_allowed: false,
    source_created: false,
    task_created: false,
    provider_call_attempted: false,
    credential_read_attempted: false,
    production_write_allowed: false,
    source_create_payload: {
      name: input.sourceName ?? `${input.platform} social fixture source`,
      type: "manual_json",
      config: {
        json_data: {
          schema_version: "social_provider_source_template_payload.v1",
          provider_id: providerId,
          platform: input.platform,
          endpoints: input.endpoints,
          provider_call: false,
          credential_read: false,
          production_write: false,
        },
      },
    },
    blocked_reasons: ["source_create_requires_separate_l4_authorization"],
    next_required_authorization: "L4_social_source_task_authorization_required",
  };
}

function mockSocialTaskRunApprovalTemplateResponse(
  input: SocialTaskRunApprovalTemplateInput,
): SocialTaskRunApprovalTemplateResponseDto {
  const providerId = getSocialProviderUiConfig(input.platform).providerId;
  const blockedReasons = ["provider_call_requires_l4_authorization"];
  if (!input.credentialReference) {
    blockedReasons.push("credential_reference_required_for_l4_approval");
  }
  return {
    schema_version: "social_task_run_approval_template.v1",
    platform: input.platform,
    provider_id: providerId,
    sdk_selection: null,
    approval_packet: {
      schema_version: "social_task_run_l4_approval_packet.v1",
      provider_call: false,
      source_create: false,
      task_create: false,
      task_run: false,
      dataset_save: false,
      export: false,
      allow_ai_training: false,
      scope: {
        platform: input.platform,
        provider_id: providerId,
        endpoints: input.endpoints,
        max_requests: input.maxRequests ?? 5,
        max_items: input.maxItems ?? 20,
        max_rows: input.maxRows ?? 20,
      },
      retention: {
        hours: 24,
        cleanup_policy: "cleanup_after_evidence",
      },
    },
    required_confirmations: [
      "confirm_no_provider_call_without_live_gate",
      "confirm_no_ai_training",
      "confirm_retention_and_cleanup_policy",
      "confirm_scope_and_budget",
    ],
    blocked_reasons: blockedReasons,
    provider_call_allowed: false,
    provider_call_attempted: false,
    credential_read_attempted: false,
    source_create_allowed: false,
    task_create_allowed: false,
    task_run_allowed: false,
    dataset_write_allowed: false,
    export_allowed: false,
    production_write_allowed: false,
    next_required_authorization: "L4_social_execution_authorization_required",
  };
}

function mockSocialExecutionDryRunResponse(
  input: SocialExecutionDryRunInput,
): SocialExecutionDryRunResponseDto {
  const providerId = getSocialProviderUiConfig(input.platform).providerId;
  const datasetName = input.datasetName ?? `${input.platform} social VOC fixture dataset`;
  return {
    schema_version: "social_execution_dry_run.v1",
    platform: input.platform,
    provider_id: providerId,
    endpoint: input.endpoint,
    fixture_only: true,
    provider_call_allowed: false,
    provider_call_attempted: false,
    credential_read_attempted: false,
    source_create_allowed: false,
    task_create_allowed: false,
    task_run_allowed: false,
    dataset_write_allowed: false,
    export_allowed: false,
    production_write_allowed: false,
    live_comparison_available: false,
    blocked_reasons: ["credential_missing:fixture_only_mock"],
    execution_plan: [
      mockStage("readiness", "blocked", ["credential_missing:fixture_only_mock"]),
      mockStage("raw_preview", "previewed"),
      mockStage("normalization_preview", "previewed"),
      mockStage("dataset_preview", "previewed", [], { row_count: 1 }),
      mockStage("source_template", "previewed"),
      mockStage("task_run_approval_template", "previewed"),
    ],
    readiness: {
      readiness: false,
      missing_credentials: ["fixture_only_mock"],
      missing_scope: [],
      blocked_reasons: ["credential_missing:fixture_only_mock"],
      provider_call_allowed: false,
      provider_call_attempted: false,
    },
    raw_preview: {
      records: [
        {
          schema_version: "social_raw.v1",
          raw_record_id: `fixture:${providerId}:${input.endpoint}:1`,
          evidence_ref: `fixture://${providerId}/${input.endpoint}/1`,
        },
      ],
    },
    normalization_preview: {
      normalized_items: [
        {
          schema_version: input.endpoint.includes("comment")
            ? "social_comment.v1"
            : "social_post.v1",
          item_id: `social_fixture:${providerId}:1`,
          raw_record_id: `fixture:${providerId}:${input.endpoint}:1`,
          evidence_ref: `fixture://${providerId}/${input.endpoint}/1`,
        },
      ],
    },
    dataset_preview: {
      dataset_name: datasetName,
      row_count: 1,
      source_item_count: 1,
      truncated: false,
      rows: [
        mockDatasetRow(input.platform, providerId, input.endpoint, 1),
      ],
    },
    source_template: {
      source_create_allowed: false,
      source_created: false,
      task_created: false,
      source_create_payload: {
        name: input.sourceName ?? `${input.platform} social fixture source`,
        type: "manual_json",
      },
    },
    task_run_approval_template: {
      task_run_allowed: false,
      dataset_write_allowed: false,
      approval_packet: {
        schema_version: "social_task_run_l4_approval_packet.v1",
        provider_call: false,
        task_run: false,
        dataset_save: false,
      },
    },
    next_required_authorization: "L4_social_execution_authorization_required",
  };
}

function mockDatasetRow(
  platform: SocialProviderPlatform,
  providerId: string,
  endpoint: string,
  index: number,
): SocialDatasetPreviewRowDto {
  return {
    row_id: `social_dataset_row:${providerId}:${index}`,
    provider_id: providerId,
    platform,
    raw_record_id: `fixture:${providerId}:${endpoint}:${index}`,
    evidence_ref: `fixture://${providerId}/${endpoint}/${index}`,
    source_item_id: `social_voc_item:${providerId}:${index}`,
    source_schema_version: "social_voc_item.v1",
    author_policy: "hashed",
    payload: {
      raw_record_id: `fixture:${providerId}:${endpoint}:${index}`,
      evidence_ref: `fixture://${providerId}/${endpoint}/${index}`,
      text_excerpt: `${platform} fixture review item ${index}`,
      provider_call: false,
      llm_call_attempted: false,
    },
  };
}

function mockStage(
  stage: SocialExecutionDryRunStageDto["stage"],
  status: SocialExecutionDryRunStageDto["status"],
  blockedReasons: string[] = [],
  details: Record<string, unknown> = {},
): SocialExecutionDryRunStageDto {
  return {
    stage,
    status,
    blocked_reasons: blockedReasons,
    provider_call: false,
    credential_read: false,
    production_write: false,
    details,
  };
}

function adapterModuleForPlatform(platform: SocialProviderPlatform): string | null {
  if (platform === "youtube") {
    return "data_intelligence_hub.social_api.youtube.google_api_client";
  }
  if (platform === "reddit") {
    return "data_intelligence_hub.social_api.reddit.asyncpraw";
  }
  return null;
}

const mockProviderMetadata: Record<
  SocialProviderPlatform,
  {
    dataDomain: string[];
    resourceGroups: string[];
    officialDocs: string[];
    sdkSelection: SocialProviderSdkSelectionDto;
    liveAdapterStrategy: string;
    authMode: string;
    quotaHint: Record<string, unknown>;
    policyFlags: string[];
    blockedActions: string[];
    stability: string;
    selfHostPriority: string;
    apiVersion: string;
    requiredCredentials: string[];
  }
> = {
  youtube: {
    dataDomain: ["content_search", "video_detail", "comment_threads"],
    resourceGroups: ["content_search", "video_detail", "comment_threads"],
    officialDocs: ["https://developers.google.com/youtube/v3/docs"],
    sdkSelection: {
      package: "google-api-python-client",
      import_name: "googleapiclient",
      source_url: "https://github.com/googleapis/google-api-python-client",
      status: "selected",
      reason: "Official Google discovery-based API client after gate approval.",
    },
    liveAdapterStrategy: "use_google_api_python_client_after_l4_gate",
    authMode: "Google OAuth2 / API Key",
    quotaHint: { default_daily_requests: 10000, period: "day" },
    policyFlags: ["no_login_state", "no_ai_training_from_raw_source_without_governance"],
    blockedActions: ["private_message", "login_cookie_capture", "unauthorized_video_download"],
    stability: "high",
    selfHostPriority: "p0",
    apiVersion: "v3",
    requiredCredentials: ["api_key"],
  },
  reddit: {
    dataDomain: ["post_search", "subreddit_snapshot", "comment_snapshot"],
    resourceGroups: ["post_search", "subreddit_snapshot", "comment_snapshot"],
    officialDocs: ["https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki"],
    sdkSelection: {
      package: "asyncpraw",
      import_name: "asyncpraw",
      source_url: "https://github.com/praw-dev/asyncpraw",
      status: "selected",
      reason: "Mature async Reddit API wrapper after policy gate approval.",
    },
    liveAdapterStrategy: "use_asyncpraw_after_l4_gate_with_policy_gate",
    authMode: "OAuth2 Bearer + User-Agent + App credentials",
    quotaHint: { default_requests_per_minute: 100, period: "minute" },
    policyFlags: ["no_ai_training", "compliance_contract_required"],
    blockedActions: ["private_data_scrape", "login_state_capture", "captcha_bypass"],
    stability: "medium",
    selfHostPriority: "p1",
    apiVersion: "OAuth2",
    requiredCredentials: ["oauth_token", "client_id", "client_secret"],
  },
  x: {
    dataDomain: ["post_search", "user_profile", "post_lookup"],
    resourceGroups: ["post_search", "user_profile", "post_lookup"],
    officialDocs: ["https://docs.x.com/x-api/introduction"],
    sdkSelection: {
      package: "tweepy[async]",
      import_name: "tweepy",
      source_url: "https://github.com/tweepy/tweepy",
      status: "candidate",
      reason: "Enable only after paid tier and max_cost_usd gate are approved.",
    },
    liveAdapterStrategy: "use_tweepy_recent_search_only_after_cost_gate",
    authMode: "OAuth2 Bearer / Paid product key",
    quotaHint: { default_requests_per_minute: 300, period: "minute" },
    policyFlags: ["commercial_use_requires_paywall_terms", "no_ai_training"],
    blockedActions: ["private_message", "dm", "login_cookie_capture"],
    stability: "medium",
    selfHostPriority: "p2",
    apiVersion: "v2",
    requiredCredentials: ["bearer_token", "app_id", "app_secret"],
  },
  instagram: {
    dataDomain: ["media_feed", "mentions", "comments"],
    resourceGroups: ["media_feed", "mentions", "comments"],
    officialDocs: ["https://developers.facebook.com/docs/instagram-api"],
    sdkSelection: {
      package: "facebook-business",
      import_name: "facebook_business",
      source_url: "https://github.com/facebook/facebook-python-business-sdk",
      status: "candidate",
      reason: "Requires app review and authorized business assets.",
    },
    liveAdapterStrategy: "use_meta_business_sdk_or_graph_httpx_for_authorized_business_assets",
    authMode: "Meta App Token + Page/Business token + permissions",
    quotaHint: { default_requests_per_hour: 200, period: "hour" },
    policyFlags: ["business_account_required", "page_level_authorization", "no_ai_training"],
    blockedActions: ["consumer_dm_capture", "private_profile_deep_scrape", "login_state_collection"],
    stability: "medium",
    selfHostPriority: "p2",
    apiVersion: "v19",
    requiredCredentials: ["access_token", "app_secret", "page_access_token"],
  },
  threads: {
    dataDomain: ["thread_feed", "mentions", "replies"],
    resourceGroups: ["thread_feed", "mentions", "replies"],
    officialDocs: ["https://developers.facebook.com/docs/threads"],
    sdkSelection: {
      package: "httpx",
      import_name: "httpx",
      source_url: "https://www.python-httpx.org/",
      status: "selected",
      reason: "Reuse existing HTTP client after authorized Threads app review.",
    },
    liveAdapterStrategy: "use_existing_httpx_graph_adapter_for_authorized_threads_assets",
    authMode: "Meta threads scope + app review",
    quotaHint: { default_requests_per_hour: 120, period: "hour" },
    policyFlags: ["strict_permissions_required", "no_ai_training"],
    blockedActions: ["login_state_capture", "private_account_enumeration"],
    stability: "low",
    selfHostPriority: "p3",
    apiVersion: "threads",
    requiredCredentials: ["app_id", "app_secret", "access_token", "scope"],
  },
  tiktok: {
    dataDomain: ["video_snapshot", "video_comment", "search"],
    resourceGroups: ["video_snapshot", "video_comment", "search"],
    officialDocs: ["https://developers.tiktok.com/doc/research-api-get-started"],
    sdkSelection: {
      package: "TikTokResearchApi",
      import_name: "tiktok_research_api",
      source_url: "https://github.com/tiktok/tiktok-research-api-wrapper",
      status: "manual_review",
      reason: "Qualification, region, purpose, and release maturity must be reviewed first.",
    },
    liveAdapterStrategy: "research_wrapper_test_only_after_qualification",
    authMode: "OAuth2 Bearer + VCE qualification",
    quotaHint: { default_requests_per_day: 1000, period: "day" },
    policyFlags: ["research_only", "no_ai_training"],
    blockedActions: ["private_message", "login_state_capture", "captcha_bypass"],
    stability: "low",
    selfHostPriority: "p3",
    apiVersion: "research",
    requiredCredentials: ["access_token", "app_id", "app_secret"],
  },
  linkedin: {
    dataDomain: ["company_updates", "ugc_posts", "social_actions"],
    resourceGroups: ["company_updates", "ugc_posts", "social_actions"],
    officialDocs: ["https://developer.linkedin.com/product-catalog"],
    sdkSelection: {
      package: "linkedin-api-client",
      import_name: "linkedin_api_client",
      source_url: "https://github.com/linkedin-developers/linkedin-api-python-client",
      status: "manual_review",
      reason: "Official Rest.li client is beta and tier review is required.",
    },
    liveAdapterStrategy: "official_restli_client_after_tier_review",
    authMode: "LinkedIn MDP/MCM OAuth + app tier",
    quotaHint: { default_requests_per_day: 50000, period: "day" },
    policyFlags: ["official_api_only", "version_tier_review_required", "no_ai_training"],
    blockedActions: ["private_message", "contact_graph_expansion", "member_profile_broad_scan"],
    stability: "medium",
    selfHostPriority: "p3",
    apiVersion: "v2",
    requiredCredentials: ["client_id", "client_secret", "access_token"],
  },
};
