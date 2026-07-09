import { describe, expect, it } from "vitest";

import {
  buildSocialProviderAdapterPlanRequestBody,
  buildSocialDatasetPreviewRequestBody,
  buildSocialProviderReadinessRequestBody,
  buildSocialProviderSourceTemplateRequestBody,
  buildSocialTaskRunApprovalTemplateRequestBody,
  buildSocialExecutionDryRunRequestBody,
  mapSocialProviderAdapterPlanResponse,
  mapSocialDatasetPreviewResponse,
  mapSocialProviderCatalogResponse,
  mapSocialProviderReadinessResponse,
  mapSocialProviderSourceTemplateResponse,
  mapSocialTaskRunApprovalTemplateResponse,
  mapSocialExecutionDryRunResponse,
} from "@/lib/api/social-provider";
import {
  getSocialProviderUiConfig,
  socialProviderUiConfigs,
} from "@/lib/social-provider-config";
import type { SocialExecutionDryRunResponseDto } from "@/types/social-provider";

const catalogResponse = {
  schema_version: "external_provider_catalog.v1",
  evidence_level: "L1-public-or-runtime",
  provider_call: false,
  generated_at: "2026-07-08",
  providers: [
    {
      provider_id: "instagram_graph.v19",
      platform: "instagram",
      data_domain: ["media_feed", "mentions"],
      resource_groups: ["media_feed", "mentions"],
      official_docs: ["https://developers.facebook.com/docs/instagram-api"],
      sdk_selection: {
        package: "facebook-business",
        import_name: "facebook_business",
        source_url: "https://github.com/facebook/facebook-python-business-sdk",
        status: "manual_review",
        reason: "Requires app review and authorized business assets.",
      },
      live_adapter_strategy: "use_meta_business_sdk_or_graph_httpx_for_authorized_business_assets",
      auth_mode: "Meta App Token + Page/Business token + permissions",
      quota_hint: {
        default_requests_per_hour: 200,
        period: "hour",
      },
      policy_flags: ["business_account_required", "no_ai_training"],
      blocked_actions: ["consumer_dm_capture", "login_state_collection"],
      stability: "medium",
      self_host_priority: "p2",
      api_version: "v19",
      required_credentials: ["access_token", "app_secret", "page_access_token"],
      supported_endpoints: ["media", "mentions", "comments"],
      endpoint_contracts: [],
    },
  ],
} as const;

const readinessResponse = {
  schema_version: "social_provider_readiness.v1",
  platform: "instagram",
  provider_id: "instagram_graph.v19",
  readiness: false,
  missing_credentials: ["access_token", "app_secret"],
  missing_scope: [],
  blocked_reasons: ["credential_missing:access_token", "credential_missing:app_secret"],
  policy_blockers: ["policy:no_ai_training"],
  forbidden_actions: ["consumer_dm_capture"],
  rate_limit_profile: {
    provider_id: "instagram_graph.v19",
    requested: {
      requests_per_minute: null,
      requests_per_hour: null,
      requests_per_day: null,
      estimated_cost_usd: null,
    },
    catalog_hint: {
      default_requests_per_hour: 200,
      period: "hour",
    },
    budget_status: "within_default_catalog_hint",
    effective_limits: {
      requests_per_hour: 200,
    },
    estimated_cost_usd: null,
  },
  provider_call_allowed: false,
  provider_call_attempted: false,
  dry_run: true,
} as const;

const adapterPlanResponse = {
  schema_version: "social_provider_adapter_plan.v1",
  platform: "youtube",
  provider_id: "youtube.v3",
  sdk_selection: {
    package: "google-api-python-client",
    import_name: "googleapiclient",
    source_url: "https://github.com/googleapis/google-api-python-client",
    status: "selected",
    reason: "Official Google discovery-based API client after gate approval.",
  },
  adapter_module: "data_intelligence_hub.social_api.youtube.google_api_client",
  dependency_present: false,
  dependency_import_name: "googleapiclient",
  adapter_ready: true,
  provider_call_allowed: false,
  provider_call_attempted: false,
  credential_read_attempted: false,
  live_client_created: false,
  production_write_allowed: false,
  fixture_replay_supported: true,
  planned_operations: [
    {
      operation: "fixture_replay",
      endpoint: "videos.list",
      mode: "fixture",
      provider_call: false,
      credential_read: false,
      production_write: false,
      live_client_created: false,
      fixture_limit: 2,
    },
  ],
  blocked_reasons: ["dependency_not_installed:google-api-python-client"],
  next_required_authorization: "L4_social_provider_live_adapter_authorization_required",
} as const;

const datasetPreviewResponse = {
  schema_version: "social_dataset_preview.v1",
  platform: "reddit",
  provider_id: "reddit.praw",
  endpoint: "comments.new",
  dataset_name: "Reddit comments VOC fixture",
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
  source_item_count: 1,
  row_count: 1,
  max_rows: 20,
  truncated: false,
  rows: [
    {
      row_id: "social_dataset_row:reddit.praw:1",
      provider_id: "reddit.praw",
      platform: "reddit",
      raw_record_id: "fixture:reddit.praw:comments.new:1",
      evidence_ref: "fixture://reddit.praw/comments.new/1",
      source_item_id: "social_voc_item:reddit.praw:1",
      source_schema_version: "social_voc_item.v1",
      author_policy: "hashed",
      payload: {
        raw_record_id: "fixture:reddit.praw:comments.new:1",
        evidence_ref: "fixture://reddit.praw/comments.new/1",
        text_excerpt: "Reddit fixture comment",
        provider_call: false,
        llm_call_attempted: false,
      },
    },
  ],
  normalized_items: [
    {
      schema_version: "social_voc_item.v1",
      item_id: "social_voc_item:reddit.praw:1",
      provider_id: "reddit.praw",
      platform: "reddit",
      raw_record_id: "fixture:reddit.praw:comments.new:1",
      evidence_ref: "fixture://reddit.praw/comments.new/1",
      author_policy: "hashed",
      payload: {
        text_excerpt: "Reddit fixture comment",
      },
    },
  ],
  sdk_selection: null,
  next_required_authorization: "L4_social_dataset_save_authorization_required",
} as const;

const sourceTemplateResponse = {
  schema_version: "social_provider_source_template.v1",
  platform: "reddit",
  provider_id: "reddit.praw",
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
    name: "Reddit comments fixture source",
    type: "manual_json",
    config: {
      json_data: {
        provider_call: false,
      },
    },
  },
  blocked_reasons: ["source_create_requires_separate_l4_authorization"],
  next_required_authorization: "L4_social_source_task_authorization_required",
} as const;

const approvalTemplateResponse = {
  schema_version: "social_task_run_approval_template.v1",
  platform: "reddit",
  provider_id: "reddit.praw",
  sdk_selection: null,
  approval_packet: {
    schema_version: "social_task_run_l4_approval_packet.v1",
    provider_call: false,
    task_run: false,
    dataset_save: false,
    export: false,
    scope: {
      endpoints: ["comments.new"],
    },
  },
  required_confirmations: [
    "confirm_no_provider_call_without_live_gate",
    "confirm_no_ai_training",
  ],
  blocked_reasons: ["provider_call_requires_l4_authorization"],
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
} as const;

const response: SocialExecutionDryRunResponseDto = {
  schema_version: "social_execution_dry_run.v1",
  platform: "reddit",
  provider_id: "reddit.praw",
  endpoint: "comments.new",
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
  blocked_reasons: ["credential_missing:oauth_token"],
  execution_plan: [
    {
      stage: "readiness",
      status: "blocked",
      blocked_reasons: ["credential_missing:oauth_token"],
      provider_call: false,
      credential_read: false,
      production_write: false,
      details: {
        missing_credentials: ["oauth_token"],
      },
    },
    {
      stage: "dataset_preview",
      status: "previewed",
      blocked_reasons: [],
      provider_call: false,
      credential_read: false,
      production_write: false,
      details: {
        row_count: 2,
      },
    },
  ],
  readiness: {
    readiness: false,
    missing_credentials: ["oauth_token"],
    missing_scope: [],
    blocked_reasons: ["credential_missing:oauth_token"],
    provider_call_allowed: false,
    provider_call_attempted: false,
  },
  raw_preview: {
    records: [
      {
        schema_version: "social_raw.v1",
        raw_record_id: "fixture:reddit.praw:comments.new:1",
        evidence_ref: "fixture://reddit.praw/comments.new/1",
      },
    ],
  },
  normalization_preview: {
    normalized_items: [
      {
        schema_version: "social_comment.v1",
        item_id: "social_comment:reddit.praw:1",
        raw_record_id: "fixture:reddit.praw:comments.new:1",
        evidence_ref: "fixture://reddit.praw/comments.new/1",
      },
    ],
  },
  dataset_preview: {
    dataset_name: "Reddit comments VOC fixture",
    row_count: 2,
    source_item_count: 2,
    truncated: false,
    rows: [
      {
        row_id: "social_dataset_row:reddit.praw:1",
        raw_record_id: "fixture:reddit.praw:comments.new:1",
        evidence_ref: "fixture://reddit.praw/comments.new/1",
        source_schema_version: "social_voc_item.v1",
        payload: {
          text_excerpt: "Reddit fixture post 1",
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
      name: "Reddit comments fixture source",
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

describe("mapSocialExecutionDryRunResponse", () => {
  it("maps social execution dry-run response and preserves no-write flags", () => {
    const mapped = mapSocialExecutionDryRunResponse(response);

    expect(mapped.schemaVersion).toBe("social_execution_dry_run.v1");
    expect(mapped.providerId).toBe("reddit.praw");
    expect(mapped.fixtureOnly).toBe(true);
    expect(mapped.providerCallAllowed).toBe(false);
    expect(mapped.providerCallAttempted).toBe(false);
    expect(mapped.credentialReadAttempted).toBe(false);
    expect(mapped.sourceCreateAllowed).toBe(false);
    expect(mapped.taskRunAllowed).toBe(false);
    expect(mapped.datasetWriteAllowed).toBe(false);
    expect(mapped.exportAllowed).toBe(false);
    expect(mapped.productionWriteAllowed).toBe(false);
    expect(mapped.blockedReasons).toEqual(["credential_missing:oauth_token"]);
    expect(mapped.executionPlan.map((stage) => stage.stage)).toEqual([
      "readiness",
      "dataset_preview",
    ]);
    expect(mapped.executionPlan.every((stage) => !stage.providerCall)).toBe(true);
    expect(mapped.datasetPreview.rowCount).toBe(2);
    expect(mapped.datasetPreview.rows[0]?.textExcerpt).toBe("Reddit fixture post 1");
    expect(mapped.taskRunApprovalTemplate.approvalPacket.task_run).toBe(false);
  });
});

describe("social provider UI config", () => {
  it("exposes the full first-batch overseas social platform catalog", () => {
    expect(socialProviderUiConfigs.map((config) => config.platform)).toEqual([
      "youtube",
      "reddit",
      "x",
      "instagram",
      "threads",
      "tiktok",
      "linkedin",
    ]);

    for (const config of socialProviderUiConfigs) {
      expect(config.endpoints.length).toBeGreaterThan(0);
    }
    expect(getSocialProviderUiConfig("x").providerId).toBe("x.v2");
    expect(getSocialProviderUiConfig("tiktok").providerId).toBe("tiktok_research");
    expect(getSocialProviderUiConfig("linkedin").providerId).toBe("linkedin.mcdm");
  });
});

describe("buildSocialExecutionDryRunRequestBody", () => {
  it("keeps non-P0 platform dry-run requests fixture-only and no-write", () => {
    const body = buildSocialExecutionDryRunRequestBody({
      platform: "linkedin",
      endpoint: "ugcPosts",
      fixtureLimit: 3,
      intendedUse: "fixture-only linkedin ugcPosts social review",
      datasetName: "LinkedIn ugcPosts VOC fixture",
      sourceName: "LinkedIn ugcPosts fixture source",
      taskName: "LinkedIn ugcPosts fixture task",
      credentialReference: "vault:overseas-social-readonly",
      maxItems: 20,
      maxRequests: 5,
      maxRows: 20,
    });

    expect(body.platform).toBe("linkedin");
    expect(body.endpoint).toBe("ugcPosts");
    expect(body.credentials_ready).toBe(false);
    expect(body.authorized).toBe(false);
    expect(body.include_live_comparison).toBe(false);
    expect(body.dataset_save_requested).toBe(false);
    expect(body.export_requested).toBe(false);
    expect(body.allow_ai_training).toBe(false);
    expect(body.max_cost_usd).toBe(0);
    expect(body.author_policy).toBe("hashed");
    expect(body.cleanup_policy).toBe("cleanup_after_evidence");
  });
});

describe("social provider catalog and readiness mappers", () => {
  it("maps catalog provider metadata for review-only display", () => {
    const mapped = mapSocialProviderCatalogResponse(catalogResponse);

    expect(mapped.schemaVersion).toBe("external_provider_catalog.v1");
    expect(mapped.providerCall).toBe(false);
    expect(mapped.providers[0]?.providerId).toBe("instagram_graph.v19");
    expect(mapped.providers[0]?.sdkSelection?.status).toBe("manual_review");
    expect(mapped.providers[0]?.policyFlags).toContain("business_account_required");
  });

  it("maps readiness without upgrading provider-call evidence", () => {
    const mapped = mapSocialProviderReadinessResponse(readinessResponse);

    expect(mapped.schemaVersion).toBe("social_provider_readiness.v1");
    expect(mapped.ready).toBe(false);
    expect(mapped.providerCallAllowed).toBe(false);
    expect(mapped.providerCallAttempted).toBe(false);
    expect(mapped.missingCredentials).toEqual(["access_token", "app_secret"]);
    expect(mapped.rateLimitProfile.budgetStatus).toBe("within_default_catalog_hint");
  });
});

describe("social provider adapter plan mapper", () => {
  it("maps adapter plan metadata without creating live clients", () => {
    const mapped = mapSocialProviderAdapterPlanResponse(adapterPlanResponse);

    expect(mapped.schemaVersion).toBe("social_provider_adapter_plan.v1");
    expect(mapped.providerId).toBe("youtube.v3");
    expect(mapped.sdkSelection?.package).toBe("google-api-python-client");
    expect(mapped.dependencyPresent).toBe(false);
    expect(mapped.adapterReady).toBe(true);
    expect(mapped.fixtureReplaySupported).toBe(true);
    expect(mapped.providerCallAttempted).toBe(false);
    expect(mapped.credentialReadAttempted).toBe(false);
    expect(mapped.liveClientCreated).toBe(false);
    expect(mapped.plannedOperations[0]?.providerCall).toBe(false);
  });
});

describe("social preview chain mappers", () => {
  it("maps dataset preview rows without upgrading write evidence", () => {
    const mapped = mapSocialDatasetPreviewResponse(datasetPreviewResponse);

    expect(mapped.schemaVersion).toBe("social_dataset_preview.v1");
    expect(mapped.datasetName).toBe("Reddit comments VOC fixture");
    expect(mapped.datasetWriteAllowed).toBe(false);
    expect(mapped.datasetCreated).toBe(false);
    expect(mapped.exportCreated).toBe(false);
    expect(mapped.rows[0]?.rawRecordId).toBe("fixture:reddit.praw:comments.new:1");
    expect(mapped.rows[0]?.providerCall).toBe(false);
  });

  it("maps source template preview as no-write manual_json candidate", () => {
    const mapped = mapSocialProviderSourceTemplateResponse(sourceTemplateResponse);

    expect(mapped.schemaVersion).toBe("social_provider_source_template.v1");
    expect(mapped.sourceType).toBe("manual_json");
    expect(mapped.sourceCreateAllowed).toBe(false);
    expect(mapped.sourceCreated).toBe(false);
    expect(mapped.taskCreated).toBe(false);
    expect(mapped.payloadPresent).toBe(true);
    expect(mapped.blockedReasons).toContain("source_create_requires_separate_l4_authorization");
  });

  it("maps task approval template without enabling execution", () => {
    const mapped = mapSocialTaskRunApprovalTemplateResponse(approvalTemplateResponse);

    expect(mapped.schemaVersion).toBe("social_task_run_approval_template.v1");
    expect(mapped.taskRunAllowed).toBe(false);
    expect(mapped.datasetWriteAllowed).toBe(false);
    expect(mapped.exportAllowed).toBe(false);
    expect(mapped.productionWriteAllowed).toBe(false);
    expect(mapped.requiredConfirmations).toContain("confirm_no_provider_call_without_live_gate");
    expect(mapped.approvalPacket.task_run).toBe(false);
  });
});

describe("social preview chain request builders", () => {
  it("keeps dataset preview fixture-only and no-write", () => {
    const body = buildSocialDatasetPreviewRequestBody({
      platform: "reddit",
      endpoint: "comments.new",
      fixtureLimit: 2,
      datasetName: "Reddit comments VOC fixture",
      maxRows: 20,
    });

    expect(body.platform).toBe("reddit");
    expect(body.endpoint).toBe("comments.new");
    expect(body.fixture_limit).toBe(2);
    expect(body.include_live_comparison).toBe(false);
    expect(body.authorized).toBe(false);
    expect(body.author_policy).toBe("hashed");
    expect(body.save_requested).toBe(false);
    expect(body.export_requested).toBe(false);
  });

  it("keeps source template preview from creating source or task", () => {
    const body = buildSocialProviderSourceTemplateRequestBody({
      platform: "reddit",
      endpoints: ["comments.new"],
      sourceName: "Reddit comments fixture source",
      fixtureLimit: 2,
    });

    expect(body.platform).toBe("reddit");
    expect(body.endpoints).toEqual(["comments.new"]);
    expect(body.source_name).toBe("Reddit comments fixture source");
    expect(body.authorized).toBe(false);
    expect(body.fixture_limit).toBe(2);
    expect(body.credential_reference).toBeUndefined();
  });

  it("keeps task approval template as a review packet only", () => {
    const body = buildSocialTaskRunApprovalTemplateRequestBody({
      platform: "reddit",
      endpoints: ["comments.new"],
      intendedUse: "fixture-only approval review",
      sourceName: "Reddit comments fixture source",
      taskName: "Reddit comments fixture task",
      datasetName: "Reddit comments VOC fixture",
      credentialReference: "vault:overseas-social-readonly",
      maxRequests: 5,
      maxItems: 20,
      maxRows: 20,
    });

    expect(body.platform).toBe("reddit");
    expect(body.endpoints).toEqual(["comments.new"]);
    expect(body.authorized).toBe(false);
    expect(body.allow_ai_training).toBe(false);
    expect(body.dataset_save_requested).toBe(false);
    expect(body.export_requested).toBe(false);
    expect(body.max_cost_usd).toBe(0);
    expect(body.retention_hours).toBe(24);
    expect(body.cleanup_policy).toBe("cleanup_after_evidence");
  });
});

describe("buildSocialProviderAdapterPlanRequestBody", () => {
  it("keeps adapter planning fixture-only and credential-free", () => {
    const body = buildSocialProviderAdapterPlanRequestBody({
      platform: "youtube",
      endpoints: ["videos.list"],
      fixtureLimit: 2,
    });

    expect(body.platform).toBe("youtube");
    expect(body.endpoints).toEqual(["videos.list"]);
    expect(body.authorized).toBe(false);
    expect(body.fixture_limit).toBe(2);
    expect(body.credential_reference).toBeUndefined();
  });
});

describe("buildSocialProviderReadinessRequestBody", () => {
  it("keeps readiness checks dry-run and policy-gated", () => {
    const body = buildSocialProviderReadinessRequestBody({
      platform: "instagram",
      endpoints: ["media"],
    });

    expect(body.platform).toBe("instagram");
    expect(body.endpoints).toEqual(["media"]);
    expect(body.credentials_ready).toBe(false);
    expect(body.dry_run).toBe(true);
    expect(body.policy_context).toEqual({
      allow_ai_training: false,
      allow_private_profile_merge: false,
      allow_login_state_collection: false,
      max_retention_hours: 24,
    });
  });
});
