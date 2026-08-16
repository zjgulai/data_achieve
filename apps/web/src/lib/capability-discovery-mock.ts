import type {
  CapabilityDiscoveryAccessChannel,
  CapabilityDiscoveryConstraintDto,
  CapabilityDiscoveryDeliveryForm,
  CapabilityDiscoveryDeploymentMode,
  CapabilityDiscoveryFixtureId,
  CapabilityDiscoveryOperation,
  CapabilityDiscoveryParserId,
  CapabilityDiscoveryPlatform,
  CapabilityDiscoveryPreviewResponseDto,
  CapabilityDiscoveryResourceType,
} from "@/types/capability-discovery";

const OBSERVED_AT = "2026-07-14T08:00:00Z";
const MOCK_PREVIEW_FINGERPRINT = `sha256:${"d".repeat(64)}`;

type CandidateDefinition = {
  resourceType: CapabilityDiscoveryResourceType;
  operation: CapabilityDiscoveryOperation;
  claimRef: string;
  requiredFields: string[];
  optionalFields: string[];
  constraint: CapabilityDiscoveryConstraintDto;
  purposeScope: string[];
  regionScope: string[];
  authScope: string[];
};

type SourceDefinition = {
  fixtureId: CapabilityDiscoveryFixtureId;
  sourceKind: "public_market" | "official_doc";
  sourceName: string;
  sourceUrl: string;
  sourceVersion: string;
  parserId: CapabilityDiscoveryParserId;
  contentHash: string;
  providerId: string;
  platform: CapabilityDiscoveryPlatform;
  accessChannel: CapabilityDiscoveryAccessChannel;
  deliveryForm: CapabilityDiscoveryDeliveryForm;
  deploymentMode: CapabilityDiscoveryDeploymentMode;
  authMode: string;
  requiredCredentials: string[];
  limitations: string[];
  candidates: CandidateDefinition[];
  warningClaimRef?: string;
};

const sourceDefinitions: SourceDefinition[] = [
  {
    fixtureId: "apify-reddit-market-v1",
    sourceKind: "public_market",
    sourceName: "Apify Reddit Scraper public Actor page",
    sourceUrl: "https://apify.com/prodiger/reddit-scraper",
    sourceVersion: "published-2026-04-18",
    parserId: "apify_public_market.v1",
    contentHash:
      "9302c771424147797290712cb2228300b9350cc271b4d0b7afe4083509ebc8e4",
    providerId: "apify.prodiger-reddit-scraper.v1",
    platform: "reddit",
    accessChannel: "managed_opaque_collector",
    deliveryForm: "actor",
    deploymentMode: "managed_saas",
    authMode: "apify_console_or_api_token",
    requiredCredentials: ["apify_account_or_api_token_for_run"],
    limitations: [
      "actor_run_required",
      "market_claims_require_independent_verification",
      "public_html_only",
    ],
    candidates: [
      {
        resourceType: "content",
        operation: "search_discover",
        claimRef: "claim:apify:reddit-search",
        requiredFields: ["reddit_url_or_search_query"],
        optionalFields: ["post_id", "title", "self_text", "score"],
        constraint: {
          constraint_type: "policy",
          severity: "blocking",
          code: "public_reddit_pages_only",
          details: { private_subreddits: false },
        },
        purposeScope: ["public_discussion_research"],
        regionScope: ["source_page_not_region_scoped"],
        authScope: ["apify_account_or_api_token_claimed"],
      },
      {
        resourceType: "conversation",
        operation: "list_enumerate",
        claimRef: "claim:apify:reddit-comments",
        requiredFields: ["public_post_url"],
        optionalFields: ["comment_id", "body", "depth", "parent_id"],
        constraint: {
          constraint_type: "policy",
          severity: "major",
          code: "comment_depth_completeness_claim",
          details: { deep_collapsed_threads_fetched: false },
        },
        purposeScope: ["public_comment_research"],
        regionScope: ["source_page_not_region_scoped"],
        authScope: ["apify_account_or_api_token_claimed"],
      },
    ],
    warningClaimRef: "claim:apify:user-profile",
  },
  {
    fixtureId: "reddit-data-api-doc-v1",
    sourceKind: "official_doc",
    sourceName: "Reddit Data API GET search official documentation",
    sourceUrl: "https://www.reddit.com/dev/api/#GET_search",
    sourceVersion: "live-api-doc-observed-2026-07-14",
    parserId: "reddit_official_doc.v1",
    contentHash:
      "71683c5de9cdbabce31cda75c9fd18cb7495113c3caa5c1426504d9011e5edec",
    providerId: "reddit.data-api.v1",
    platform: "reddit",
    accessChannel: "official_authorized_api",
    deliveryForm: "endpoint",
    deploymentMode: "official_cloud",
    authMode: "oauth2_read_scope",
    requiredCredentials: ["registered_reddit_oauth_token"],
    limitations: [
      "registered_oauth_token_required",
      "search_result_limit_maximum_100",
    ],
    candidates: [
      {
        resourceType: "content",
        operation: "search_discover",
        claimRef: "claim:reddit:search",
        requiredFields: ["q"],
        optionalFields: ["subreddit", "after", "limit", "sort"],
        constraint: {
          constraint_type: "policy",
          severity: "blocking",
          code: "oauth_read_scope",
          details: { oauth_scope: "read" },
        },
        purposeScope: ["link_search"],
        regionScope: ["source_page_not_region_scoped"],
        authScope: ["oauth2_read"],
      },
    ],
  },
  {
    fixtureId: "tikhub-youtube-market-v1",
    sourceKind: "public_market",
    sourceName: "TikHub YouTube API public page",
    sourceUrl: "https://tikhub.io/youtube-api",
    sourceVersion: "published-2026-06-20",
    parserId: "tikhub_public_market.v1",
    contentHash:
      "537bc5351ffd49472880fa5e9bcfa5927fd512cadc4bee0a3186699f951ff40d",
    providerId: "tikhub.youtube.v1",
    platform: "youtube",
    accessChannel: "managed_opaque_collector",
    deliveryForm: "endpoint",
    deploymentMode: "managed_saas",
    authMode: "authorization_header_api_key",
    requiredCredentials: ["tikhub_api_key"],
    limitations: [
      "market_claims_require_independent_verification",
      "public_content_only",
    ],
    candidates: [
      {
        resourceType: "content",
        operation: "resolve_detail",
        claimRef: "claim:tikhub:video-detail",
        requiredFields: ["video_id_or_public_url"],
        optionalFields: ["video_metadata", "video_statistics", "available_subtitles"],
        constraint: {
          constraint_type: "policy",
          severity: "blocking",
          code: "public_content_only",
          details: { private_or_unlisted_content: false },
        },
        purposeScope: ["public_content_research"],
        regionScope: ["source_page_not_region_scoped"],
        authScope: ["api_key_claimed"],
      },
      {
        resourceType: "content",
        operation: "search_discover",
        claimRef: "claim:tikhub:video-search",
        requiredFields: ["search_query"],
        optionalFields: ["search_results", "shorts", "continuation_token"],
        constraint: {
          constraint_type: "quota",
          severity: "major",
          code: "continuation_token_pagination",
          details: { pagination: "continuation_token" },
        },
        purposeScope: ["public_content_research"],
        regionScope: ["source_page_not_region_scoped"],
        authScope: ["api_key_claimed"],
      },
      {
        resourceType: "conversation",
        operation: "list_enumerate",
        claimRef: "claim:tikhub:comment-list",
        requiredFields: ["video_id_or_public_url"],
        optionalFields: ["public_comments", "continuation_token"],
        constraint: {
          constraint_type: "quota",
          severity: "major",
          code: "continuation_token_pagination",
          details: { pagination: "continuation_token" },
        },
        purposeScope: ["public_comment_research"],
        regionScope: ["source_page_not_region_scoped"],
        authScope: ["api_key_claimed"],
      },
    ],
    warningClaimRef: "claim:tikhub:channel-profile",
  },
  {
    fixtureId: "youtube-data-api-doc-v1",
    sourceKind: "official_doc",
    sourceName: "YouTube Data API videos.list official documentation",
    sourceUrl: "https://developers.google.com/youtube/v3/docs/videos/list",
    sourceVersion: "last-updated-2026-07-08",
    parserId: "youtube_official_doc.v1",
    contentHash:
      "02e3b6d9760becddc64f1cb8145ea21596f0fd0eba76c74cf273b7429d27cabe",
    providerId: "youtube.data-api.v3",
    platform: "youtube",
    accessChannel: "official_authorized_api",
    deliveryForm: "endpoint",
    deploymentMode: "official_cloud",
    authMode: "api_key_or_oauth2_by_request_scope",
    requiredCredentials: ["google_api_key_or_oauth2_token"],
    limitations: ["exactly_one_filter_required", "quota_cost_applies"],
    candidates: [
      {
        resourceType: "content",
        operation: "resolve_detail",
        claimRef: "claim:youtube:videos-list",
        requiredFields: ["part"],
        optionalFields: ["chart", "id", "myRating", "pageToken", "items"],
        constraint: {
          constraint_type: "quota",
          severity: "major",
          code: "videos_list_quota_cost",
          details: { quota_units_per_call: 1 },
        },
        purposeScope: ["video_resource_lookup"],
        regionScope: ["region_code_optional_for_chart"],
        authScope: ["api_key_for_public_data_or_oauth2_for_authorized_parts"],
      },
    ],
  },
];

function candidateFingerprint(index: number): string {
  return `sha256:${index.toString(16).repeat(64).slice(0, 64)}`;
}

export function buildMockCapabilityDiscoveryPreviewDto(): CapabilityDiscoveryPreviewResponseDto {
  const evidence = sourceDefinitions.map((source) => ({
    schema_version: "capability_evidence.v1" as const,
    evidence_id: `evidence:${source.fixtureId}`,
    evidence_type: source.sourceKind,
    source_url: source.sourceUrl,
    source_version: source.sourceVersion,
    observed_at: OBSERVED_AT,
    content_hash: source.contentHash,
    hash_scope: "retrieved_content" as const,
    evidence_grade: "L2-fixture-or-dry-run" as const,
    provider_call_attempted: false as const,
    credential_read_attempted: false as const,
    live_client_created: false as const,
    production_write_attempted: false as const,
  }));
  let candidateIndex = 0;
  const candidateAssertions = sourceDefinitions.flatMap((source) =>
    source.candidates.map((candidate) => {
      candidateIndex += 1;
      return {
        schema_version: "capability_candidate_assertion_preview.v1" as const,
        candidate_id: `candidate:${source.providerId}:${candidate.resourceType}:${candidate.operation}`,
        proposed_implementation_id: `proposed:${source.providerId}`,
        platform: source.platform,
        access_channel: source.accessChannel,
        resource_type: candidate.resourceType,
        operation: candidate.operation,
        support_status: "candidate" as const,
        verification_status: "unverified" as const,
        executable: false as const,
        publishable: false as const,
        claimed_field_contract: {
          required: [...candidate.requiredFields],
          optional: [...candidate.optionalFields],
        },
        claimed_constraints: [
          {
            ...candidate.constraint,
            details: { ...candidate.constraint.details },
          },
        ],
        region_scope: [...candidate.regionScope],
        purpose_scope: [...candidate.purposeScope],
        auth_scope: [...candidate.authScope],
        source_claim_refs: [candidate.claimRef],
        evidence_refs: [`evidence:${source.fixtureId}`],
        parser_id: source.parserId,
        candidate_fingerprint: candidateFingerprint(candidateIndex),
      };
    }),
  );
  const diagnostics = [
    ...sourceDefinitions.flatMap((source) =>
      source.candidates.map((candidate) => ({
        schema_version: "capability_discovery_diagnostic.v1" as const,
        fixture_id: source.fixtureId,
        severity: "info" as const,
        code: "source_claim_mapped",
        message: "Source claim mapped to a candidate assertion.",
        source_claim_ref: candidate.claimRef,
      })),
    ),
    ...sourceDefinitions.flatMap((source) =>
      source.warningClaimRef
        ? [
            {
              schema_version: "capability_discovery_diagnostic.v1" as const,
              fixture_id: source.fixtureId,
              severity: "warning" as const,
              code: "source_claim_not_mapped",
              message:
                "Source claim was retained as a warning and did not create a candidate assertion.",
              source_claim_ref: source.warningClaimRef,
            },
          ]
        : [],
    ),
  ];

  return {
    schema_version: "capability_discovery_preview.v1",
    evidence_grade: "L2-fixture-or-dry-run",
    preview_mode: "fixture_replay",
    preview_fingerprint: MOCK_PREVIEW_FINGERPRINT,
    generated_from_observed_at: OBSERVED_AT,
    source_snapshots: sourceDefinitions.map((source) => ({
      schema_version: "capability_source_snapshot_preview.v1",
      fixture_id: source.fixtureId,
      source_kind: source.sourceKind,
      source_name: source.sourceName,
      source_url: source.sourceUrl,
      source_version: source.sourceVersion,
      observed_at: OBSERVED_AT,
      parser_id: source.parserId,
      content_hash: source.contentHash,
    })),
    proposed_implementations: sourceDefinitions.map((source) => ({
      schema_version: "capability_proposed_implementation_preview.v1",
      proposed_implementation_id: `proposed:${source.providerId}`,
      provider_id: source.providerId,
      platform: source.platform,
      access_channel: source.accessChannel,
      delivery_form: source.deliveryForm,
      deployment_mode: source.deploymentMode,
      source_label: source.sourceName,
      claimed_auth_mode: source.authMode,
      claimed_required_credentials: [...source.requiredCredentials],
      claimed_limitations: [...source.limitations],
      evidence_refs: [`evidence:${source.fixtureId}`],
    })),
    candidate_assertions: candidateAssertions,
    evidence,
    diagnostics,
    summary: {
      source_count: 4,
      market_source_count: 2,
      official_doc_source_count: 2,
      proposed_implementation_count: 4,
      candidate_assertion_count: 7,
      evidence_count: 4,
      warning_count: 2,
      error_count: 0,
    },
    provider_call: false,
    provider_call_attempted: false,
    actor_run: false,
    browser_run: false,
    llm_call: false,
    credential_read_attempted: false,
    database_write: false,
    database_migration: false,
    workflow_run_created: false,
    candidate_publish_allowed: false,
    production_write_allowed: false,
  };
}
