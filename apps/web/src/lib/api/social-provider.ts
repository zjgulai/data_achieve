import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import { getSocialProviderUiConfig } from "@/lib/social-provider-config";
import type {
  SocialDatasetPreviewRow,
  SocialDatasetPreviewRowDto,
  SocialExecutionDryRun,
  SocialExecutionDryRunInput,
  SocialExecutionDryRunRequestDto,
  SocialExecutionDryRunResponseDto,
  SocialExecutionDryRunStage,
  SocialExecutionDryRunStageDto,
} from "@/types/social-provider";

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
    rawRecordId: row.raw_record_id,
    evidenceRef: row.evidence_ref,
    sourceSchemaVersion: row.source_schema_version,
    textExcerpt: stringValue(row.payload.text_excerpt),
    providerCall: booleanValue(row.payload.provider_call),
    llmCallAttempted: booleanValue(row.payload.llm_call_attempted),
  };
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function booleanValue(value: unknown): boolean {
  return typeof value === "boolean" ? value : false;
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
        {
          row_id: `social_dataset_row:${providerId}:1`,
          raw_record_id: `fixture:${providerId}:${input.endpoint}:1`,
          evidence_ref: `fixture://${providerId}/${input.endpoint}/1`,
          source_schema_version: "social_voc_item.v1",
          payload: {
            text_excerpt: `${input.platform} fixture review item`,
            provider_call: false,
            llm_call_attempted: false,
          },
        },
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
