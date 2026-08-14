import type {
  CapabilityAccessChannel,
  CapabilityAssertion,
  CapabilityEvidence,
  CapabilityImplementation,
  CapabilityImplementationDetail,
  CapabilityMatrixCell,
  CapabilityOperation,
  CapabilityPlatform,
  CapabilityResourceType,
  CapabilityStatus,
} from "@/types/capability";

export type CapabilityMarketView = "scenarios" | "matrix" | "list";

export type CapabilityMarketFilters = {
  platform?: CapabilityPlatform;
  accessChannel?: CapabilityAccessChannel;
  resourceType?: CapabilityResourceType;
  operation?: CapabilityOperation;
  status?: CapabilityStatus;
  query?: string;
};

export type CapabilityMarketQueryPatch = {
  view?: CapabilityMarketView | null;
  platform?: CapabilityPlatform | null;
  accessChannel?: CapabilityAccessChannel | null;
  resourceType?: CapabilityResourceType | null;
  operation?: CapabilityOperation | null;
  status?: CapabilityStatus | null;
  query?: string | null;
};

export type CapabilityScenario = {
  id: string;
  label: string;
  assertions: CapabilityAssertion[];
};

export const capabilityPlatforms = [
  "youtube",
  "reddit",
  "x",
  "instagram",
  "threads",
  "tiktok",
  "linkedin",
] as const satisfies readonly CapabilityPlatform[];

export const capabilityAccessChannels = [
  "official_authorized_api",
  "licensed_partner_data_service",
  "public_web_feed",
  "authorized_browser",
  "managed_opaque_collector",
  "authorized_export_import",
] as const satisfies readonly CapabilityAccessChannel[];

export const capabilityResourceTypes = [
  "content",
  "conversation",
  "creator",
  "topic",
  "metrics",
  "media_live",
  "commerce_ads",
  "relationship_graph",
] as const satisfies readonly CapabilityResourceType[];

export const capabilityOperations = [
  "resolve_detail",
  "search_discover",
  "list_enumerate",
  "monitor_incremental",
  "backfill_history",
  "batch_parse",
  "export_download",
] as const satisfies readonly CapabilityOperation[];

export const capabilityStatuses = [
  "unknown",
  "candidate",
  "verified",
  "partial",
  "blocked",
  "unsupported",
  "deprecated",
] as const satisfies readonly CapabilityStatus[];

export const capabilityScoreKeys = [
  "coverage",
  "freshness",
  "history",
  "reliability",
  "schema_stability",
  "cost_efficiency",
  "maintainability",
  "evidence_confidence",
] as const;

export type CapabilityScoreKey = (typeof capabilityScoreKeys)[number];

export type CapabilityComparisonColumn = {
  implementationId: string;
  providerId: string;
  scores: Record<CapabilityScoreKey, number | null>;
  constraintCodes: string[];
  evidence: CapabilityEvidence[];
};

export type CapabilityImplementationComparison = {
  platform: CapabilityPlatform;
  sharedResources: CapabilityResourceType[];
  sharedOperations: CapabilityOperation[];
  columns: CapabilityComparisonColumn[];
};

const capabilityStatusLabels: Record<CapabilityStatus, string> = {
  blocked: "已阻断",
  candidate: "候选，尚不可执行",
  deprecated: "已弃用",
  partial: "部分支持",
  unknown: "尚无能力事实",
  unsupported: "不支持",
  verified: "已核验",
};

const capabilityPlatformLabels: Record<CapabilityPlatform, string> = {
  instagram: "Instagram",
  linkedin: "LinkedIn",
  reddit: "Reddit",
  threads: "Threads",
  tiktok: "TikTok",
  x: "X",
  youtube: "YouTube",
};

export function capabilityStatusLabel(status: CapabilityStatus): string {
  return capabilityStatusLabels[status];
}

export function capabilityPlatformLabel(platform: CapabilityPlatform): string {
  return capabilityPlatformLabels[platform];
}

export function parseCapabilityMarketView(
  value: string | null | undefined,
): CapabilityMarketView {
  return value === "matrix" || value === "list" ? value : "scenarios";
}

export function updateCapabilityMarketQuery(
  search: string,
  patch: CapabilityMarketQueryPatch,
): string {
  const query = new URLSearchParams(search);

  updateQueryValue(query, "view", patch.view);
  updateQueryValue(query, "platform", patch.platform);
  updateQueryValue(query, "access_channel", patch.accessChannel);
  updateQueryValue(query, "resource_type", patch.resourceType);
  updateQueryValue(query, "operation", patch.operation);
  updateQueryValue(query, "status", patch.status);
  updateQueryValue(query, "q", patch.query, true);

  return query.toString();
}

export function parseCapabilityMarketFilters(
  search: string,
): CapabilityMarketFilters {
  const queryParameters = new URLSearchParams(search);
  const platform = parseEnum(
    queryParameters.get("platform"),
    capabilityPlatforms,
  );
  const accessChannel = parseEnum(
    queryParameters.get("access_channel"),
    capabilityAccessChannels,
  );
  const resourceType = parseEnum(
    queryParameters.get("resource_type"),
    capabilityResourceTypes,
  );
  const operation = parseEnum(
    queryParameters.get("operation"),
    capabilityOperations,
  );
  const status = parseEnum(
    queryParameters.get("status"),
    capabilityStatuses,
  );
  const query = queryParameters.get("q")?.trim();

  return {
    ...(platform ? { platform } : {}),
    ...(accessChannel ? { accessChannel } : {}),
    ...(resourceType ? { resourceType } : {}),
    ...(operation ? { operation } : {}),
    ...(status ? { status } : {}),
    ...(query ? { query } : {}),
  };
}

export function filterCapabilityMatrixCells(
  cells: CapabilityMatrixCell[],
  filters: CapabilityMarketFilters = {},
): CapabilityMatrixCell[] {
  return cells.filter(
    (cell) =>
      (!filters.platform || cell.platform === filters.platform) &&
      (!filters.accessChannel ||
        cell.accessChannel === filters.accessChannel) &&
      (!filters.status || cell.summaryStatus === filters.status),
  );
}

export function filterCapabilityImplementations(
  implementations: CapabilityImplementation[],
  assertions: CapabilityAssertion[],
  filters: CapabilityMarketFilters = {},
): CapabilityImplementation[] {
  const hasAssertionScope = Boolean(
    filters.resourceType || filters.operation || filters.status,
  );
  const normalizedQuery = filters.query?.trim().toLowerCase();
  const assertionsByImplementation = new Map<string, CapabilityAssertion[]>();

  if (hasAssertionScope) {
    for (const assertion of assertions) {
      const ownedAssertions =
        assertionsByImplementation.get(assertion.implementation_id) ?? [];
      ownedAssertions.push(assertion);
      assertionsByImplementation.set(assertion.implementation_id, ownedAssertions);
    }
  }

  return implementations.filter((implementation) => {
    if (
      filters.platform &&
      implementation.platform !== filters.platform
    ) {
      return false;
    }
    if (
      filters.accessChannel &&
      implementation.accessChannel !== filters.accessChannel
    ) {
      return false;
    }

    if (hasAssertionScope) {
      const hasMatchingAssertion = (
        assertionsByImplementation.get(implementation.implementationId) ?? []
      ).some(
        (assertion) =>
          (!filters.resourceType ||
            assertion.resource_type === filters.resourceType) &&
          (!filters.operation || assertion.operation === filters.operation) &&
          (!filters.status || assertion.support_status === filters.status),
      );
      if (!hasMatchingAssertion) {
        return false;
      }
    }

    if (normalizedQuery) {
      const searchableValues = [
        implementation.implementationId,
        implementation.providerId,
        implementation.platform,
        implementation.deliveryForm,
        ...implementation.resourceGroups,
        ...implementation.dataDomains,
      ];
      if (
        !searchableValues.some((value) =>
          value.toLowerCase().includes(normalizedQuery),
        )
      ) {
        return false;
      }
    }

    return true;
  });
}

export function groupCapabilityScenarios(
  assertions: CapabilityAssertion[],
): CapabilityScenario[] {
  return capabilityScenarioDefinitions.map((definition) => {
    const seenAssertionIds = new Set<string>();
    const scenarioAssertions = assertions.filter((assertion) => {
      if (
        !definition.matches(assertion) ||
        seenAssertionIds.has(assertion.assertion_id)
      ) {
        return false;
      }
      seenAssertionIds.add(assertion.assertion_id);
      return true;
    });

    return {
      id: definition.id,
      label: definition.label,
      assertions: scenarioAssertions,
    };
  });
}

export function buildImplementationComparison(
  details: CapabilityImplementationDetail[],
): CapabilityImplementationComparison {
  if (details.length < 2 || details.length > 3) {
    throw new Error("capability_comparison_requires_two_or_three");
  }

  const firstDetail = details[0]!;
  const platform = firstDetail.implementation.platform;
  if (
    details.some((detail) => detail.implementation.platform !== platform)
  ) {
    throw new Error("capability_comparison_requires_same_platform");
  }

  const sharedResources = intersection(
    details.map((detail) =>
      detail.assertions.map((assertion) => assertion.resource_type),
    ),
  );
  const sharedOperations = intersection(
    details.map((detail) =>
      detail.assertions.map((assertion) => assertion.operation),
    ),
  );

  if (sharedResources.length === 0 && sharedOperations.length === 0) {
    throw new Error("capability_comparison_requires_shared_scope");
  }

  return {
    platform,
    sharedResources,
    sharedOperations,
    columns: details.map((detail) =>
      buildComparisonColumn(detail, sharedResources, sharedOperations),
    ),
  };
}

const capabilityScenarioDefinitions: ReadonlyArray<{
  id: string;
  label: string;
  matches: (assertion: CapabilityAssertion) => boolean;
}> = [
  {
    id: "market-monitoring",
    label: "市场监测",
    matches: (assertion) => assertion.resource_type === "metrics",
  },
  {
    id: "keyword-discovery",
    label: "关键词发现",
    matches: (assertion) =>
      assertion.operation === "search_discover" ||
      assertion.resource_type === "topic",
  },
  {
    id: "content-detail",
    label: "内容详情",
    matches: (assertion) =>
      assertion.operation === "resolve_detail" ||
      assertion.resource_type === "content",
  },
  {
    id: "conversation-voc",
    label: "评论与对话",
    matches: (assertion) => assertion.resource_type === "conversation",
  },
  {
    id: "creator-tracking",
    label: "创作者",
    matches: (assertion) => assertion.resource_type === "creator",
  },
  {
    id: "incremental-monitoring",
    label: "增量监测",
    matches: (assertion) => assertion.operation === "monitor_incremental",
  },
  {
    id: "batch-parsing",
    label: "批量解析",
    matches: (assertion) => assertion.operation === "batch_parse",
  },
  {
    id: "export-delivery",
    label: "导出",
    matches: (assertion) => assertion.operation === "export_download",
  },
];

function updateQueryValue(
  query: URLSearchParams,
  key: string,
  value: string | null | undefined,
  trim = false,
): void {
  if (value === undefined) {
    return;
  }

  const normalizedValue = trim && value !== null ? value.trim() : value;
  if (normalizedValue === null || normalizedValue === "") {
    query.delete(key);
    return;
  }

  query.set(key, normalizedValue);
}

function parseEnum<Value extends string>(
  value: string | null,
  allowedValues: readonly Value[],
): Value | undefined {
  if (value === null || !allowedValues.includes(value as Value)) {
    return undefined;
  }
  return value as Value;
}

function intersection<Value>(values: ReadonlyArray<readonly Value[]>): Value[] {
  const [first = [], ...rest] = values;
  return [...new Set(first)].filter((value) =>
    rest.every((items) => items.includes(value)),
  );
}

function buildComparisonColumn(
  detail: CapabilityImplementationDetail,
  sharedResources: CapabilityResourceType[],
  sharedOperations: CapabilityOperation[],
): CapabilityComparisonColumn {
  const scopedAssertions = detail.assertions.filter(
    (assertion) =>
      sharedResources.includes(assertion.resource_type) ||
      sharedOperations.includes(assertion.operation),
  );
  const constraintCodes = [
    ...new Set(
      scopedAssertions.flatMap((assertion) =>
        assertion.constraints.map((constraint) => constraint.code),
      ),
    ),
  ].sort();
  const referencedEvidenceIds = new Set(
    scopedAssertions.flatMap((assertion) => assertion.evidence_refs),
  );
  const evidenceById = new Map(
    detail.evidence
      .filter((evidence) => referencedEvidenceIds.has(evidence.evidence_id))
      .map((evidence) => [evidence.evidence_id, evidence]),
  );

  return {
    implementationId: detail.implementation.implementationId,
    providerId: detail.implementation.providerId,
    scores: Object.fromEntries(
      capabilityScoreKeys.map((key) => [
        key,
        averageScore(scopedAssertions, key),
      ]),
    ) as Record<CapabilityScoreKey, number | null>,
    constraintCodes,
    evidence: [...evidenceById.values()].sort((left, right) =>
      left.evidence_id.localeCompare(right.evidence_id),
    ),
  };
}

function averageScore(
  assertions: CapabilityAssertion[],
  key: CapabilityScoreKey,
): number | null {
  const values = assertions
    .map((assertion) => assertion.score_profile[key])
    .filter((value): value is number =>
      typeof value === "number" && Number.isFinite(value),
    );
  if (values.length === 0) {
    return null;
  }

  const average = values.reduce((total, value) => total + value, 0) / values.length;
  return Math.round(average * 100) / 100;
}
