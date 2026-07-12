import type {
  CapabilityAccessChannel,
  CapabilityAssertionDto,
  CapabilityEvidenceDto,
  CapabilityImplementation,
  CapabilityImplementationDetailDto,
  CapabilityImplementationDto,
  CapabilityMatrixResponseDto,
  CapabilityOperation,
  CapabilityPlatform,
  CapabilityResourceType,
} from "@/types/capability";

const MOCK_GENERATED_AT = "2026-07-10T00:00:00Z";

const mockPlatforms: CapabilityPlatform[] = [
  "youtube",
  "reddit",
  "x",
  "instagram",
  "threads",
  "tiktok",
  "linkedin",
];

const mockChannels: CapabilityAccessChannel[] = [
  "official_authorized_api",
  "licensed_partner_data_service",
  "public_web_feed",
  "authorized_browser",
  "managed_opaque_collector",
  "authorized_export_import",
];

const mockAssertionScopes: Array<{
  resourceType: CapabilityResourceType;
  operation: CapabilityOperation;
}> = [
  { resourceType: "content", operation: "search_discover" },
  { resourceType: "conversation", operation: "list_enumerate" },
  { resourceType: "creator", operation: "resolve_detail" },
  { resourceType: "topic", operation: "monitor_incremental" },
  { resourceType: "metrics", operation: "batch_parse" },
];

const mockImplementationDefinitions: Array<{
  implementationId: string;
  platform: CapabilityPlatform;
  supportedEndpoints: string[];
}> = [
  {
    implementationId: "youtube.v3",
    platform: "youtube",
    supportedEndpoints: [
      "search.list",
      "videos.list",
      "videos.insert",
      "commentThreads.list",
      "videos.getRating",
      "channels.list",
      "channels.update",
    ],
  },
  {
    implementationId: "reddit.praw",
    platform: "reddit",
    supportedEndpoints: [
      "hot.list",
      "new.list",
      "comments.new",
      "search",
      "r/{subreddit}/about",
      "user.profile",
    ],
  },
  {
    implementationId: "x.v2",
    platform: "x",
    supportedEndpoints: [
      "tweets/search/recent",
      "tweets/search/all",
      "tweets",
      "users/me",
      "users/by/username/:id",
    ],
  },
  {
    implementationId: "instagram_graph.v19",
    platform: "instagram",
    supportedEndpoints: [
      "media",
      "user_media",
      "mentions",
      "comments",
      "insights",
    ],
  },
  {
    implementationId: "threads.graph.v1",
    platform: "threads",
    supportedEndpoints: ["threads", "users", "mentions", "media", "replies"],
  },
  {
    implementationId: "tiktok_research",
    platform: "tiktok",
    supportedEndpoints: [
      "video.search",
      "video.list",
      "comment.list",
      "user.info",
      "vce.batch_status",
    ],
  },
  {
    implementationId: "linkedin.mcdm",
    platform: "linkedin",
    supportedEndpoints: [
      "ugcPosts",
      "network_sizes",
      "organizations",
      "shares",
      "socialActions",
    ],
  },
];

export function buildMockCapabilityMatrixDto(): CapabilityMatrixResponseDto {
  const implementationIdByPlatform = new Map(
    mockImplementationDefinitions.map((definition) => [
      definition.platform,
      definition.implementationId,
    ]),
  );
  const resourceTypes = mockAssertionScopes.map((scope) => scope.resourceType);
  const operations = mockAssertionScopes.map((scope) => scope.operation);

  return {
    schema_version: "capability_matrix.v1",
    generated_at: MOCK_GENERATED_AT,
    evidence_level: "L2-fixture",
    provider_call: false,
    production_write_allowed: false,
    platforms: [...mockPlatforms],
    access_channels: [...mockChannels],
    cells: mockPlatforms.flatMap((platform) =>
      mockChannels.map((accessChannel) => {
        const implementationId = implementationIdByPlatform.get(platform);
        if (
          accessChannel === "official_authorized_api" &&
          implementationId
        ) {
          return {
            platform,
            access_channel: accessChannel,
            summary_status: "candidate" as const,
            status_counts: { candidate: 5 },
            implementation_ids: [implementationId],
            assertion_ids: mockAssertionScopes.map(
              (_, index) => `${implementationId}:mock:${index + 1}`,
            ),
            resource_types: [...resourceTypes],
            operations: [...operations],
            constraint_codes: ["fixture_only"],
            evidence_count: 2,
            last_verified_at: MOCK_GENERATED_AT,
          };
        }

        return {
          platform,
          access_channel: accessChannel,
          summary_status: "unknown" as const,
          status_counts: { unknown: 1 },
          implementation_ids: [],
          assertion_ids: [],
          resource_types: [],
          operations: [],
          constraint_codes: [],
          evidence_count: 0,
          last_verified_at: null,
        };
      }),
    ),
    summary: {
      cell_count: 42,
      populated_cell_count: 7,
      unknown_cell_count: 35,
      implementation_count: 7,
      assertion_count: 35,
      evidence_count: 14,
    },
  };
}

export function buildMockCapabilityImplementations(): CapabilityImplementation[] {
  return mockImplementationDefinitions.map((definition) => ({
    implementationId: definition.implementationId,
    providerId: definition.implementationId,
    platform: definition.platform,
    accessChannel: "official_authorized_api",
    deliveryForm: "authorized_api",
    deploymentMode: "fixture_only",
    dataDomains: ["social_content"],
    resourceGroups: mockAssertionScopes.map((scope) => scope.resourceType),
    officialDocs: [`https://example.invalid/${definition.platform}/official-docs`],
    sdkSelection: {
      package: `${definition.platform}-sdk-candidate`,
      import_name: null,
      source_url: `https://example.invalid/${definition.platform}/sdk`,
      status: "candidate",
      reason: "fixture-only UI contract",
    },
    authMode:
      definition.platform === "youtube" ? "api_key" : "oauth_access_token",
    quotaHint: { mode: "fixture", requests: 0 },
    costHint: { currency: "none", provider_call: false },
    policyFlags: ["fixture_only", "manual_review"],
    blockedActions: ["provider_live_call", "production_write"],
    stability: "medium",
    apiVersion: "fixture-v1",
    requiredCredentials:
      definition.platform === "youtube" ? ["api_key"] : ["access_token"],
    supportedEndpoints: [...definition.supportedEndpoints],
    lifecycleStatus: "active",
  }));
}

export function buildMockCapabilityAssertions(): CapabilityAssertionDto[] {
  return buildMockCapabilityImplementations().flatMap((implementation) => {
    const evidenceRefs = [
      `${implementation.implementationId}:evidence:contract`,
      `${implementation.implementationId}:evidence:boundary`,
    ];

    return mockAssertionScopes.map((scope, index) => ({
      schema_version: "capability_assertion.v1",
      assertion_id: `${implementation.implementationId}:mock:${index + 1}`,
      implementation_id: implementation.implementationId,
      resource_type: scope.resourceType,
      operation: scope.operation,
      support_status: "candidate",
      source_resource_group: scope.resourceType,
      region_scope: ["global"],
      purpose_scope: ["market_research"],
      auth_scope: ["fixture_only"],
      field_contract: {},
      constraints: [
        {
          constraint_type: "execution_boundary",
          severity: "blocking",
          code: "fixture_only",
          details: { provider_call: false },
        },
      ],
      score_profile: {
        coverage: 3,
        freshness: 3,
        history: 2,
        reliability: 5,
        schema_stability: 5,
        cost_efficiency: 3,
        maintainability: 4,
        evidence_confidence: 3,
      },
      evidence_refs: [...evidenceRefs],
      last_verified_at: MOCK_GENERATED_AT,
    }));
  });
}

export function buildMockCapabilityEvidence(): CapabilityEvidenceDto[] {
  return mockImplementationDefinitions.flatMap((definition, implementationIndex) =>
    (["contract", "boundary"] as const).map((kind, kindIndex) => ({
      schema_version: "capability_evidence.v1",
      evidence_id: `${definition.implementationId}:evidence:${kind}`,
      evidence_type: kind,
      source_url: `https://example.invalid/${definition.platform}/${kind}`,
      source_version: "fixture-v1",
      observed_at: MOCK_GENERATED_AT,
      content_hash: `${(implementationIndex + 1).toString(16)}${(
        kindIndex + 1
      ).toString(16)}`.padStart(64, "0"),
      hash_scope: "source_reference_only",
      evidence_grade: "L2-fixture",
      provider_call_attempted: false,
      credential_read_attempted: false,
      live_client_created: false,
      production_write_attempted: false,
    })),
  );
}

export function buildMockCapabilityImplementationDetailDto(
  implementationId: string,
): CapabilityImplementationDetailDto {
  const implementation = buildMockCapabilityImplementations().find(
    (item) => item.implementationId === implementationId,
  );
  if (!implementation) {
    throw new Error("mock_capability_implementation_not_found");
  }

  const assertions = buildMockCapabilityAssertions().filter(
    (assertion) => assertion.implementation_id === implementationId,
  );
  const referencedEvidenceIds = new Set(
    assertions.flatMap((assertion) => assertion.evidence_refs),
  );

  return {
    schema_version: "capability_implementation_detail.v1",
    implementation: implementationToDto(implementation),
    assertions,
    evidence: buildMockCapabilityEvidence().filter((evidence) =>
      referencedEvidenceIds.has(evidence.evidence_id),
    ),
  };
}

function implementationToDto(
  implementation: CapabilityImplementation,
): CapabilityImplementationDto {
  return {
    schema_version: "capability_implementation.v1",
    implementation_id: implementation.implementationId,
    provider_id: implementation.providerId,
    platform: implementation.platform,
    access_channel: implementation.accessChannel,
    delivery_form: implementation.deliveryForm,
    deployment_mode: implementation.deploymentMode,
    data_domains: implementation.dataDomains,
    resource_groups: implementation.resourceGroups,
    official_docs: implementation.officialDocs,
    sdk_selection: implementation.sdkSelection,
    live_adapter_strategy: "not_enabled",
    auth_mode: implementation.authMode,
    quota_hint: implementation.quotaHint,
    cost_hint: implementation.costHint,
    policy_flags: implementation.policyFlags,
    blocked_actions: implementation.blockedActions,
    stability: implementation.stability,
    self_host_priority: "not_in_scope",
    api_version: implementation.apiVersion,
    required_credentials: implementation.requiredCredentials,
    supported_endpoints: implementation.supportedEndpoints,
    lifecycle_status: implementation.lifecycleStatus,
  };
}
