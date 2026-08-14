import { describe, expect, it } from "vitest";

import {
  mapCapabilityImplementationDetail,
  mapCapabilityMatrixResponse,
} from "@/lib/api/capabilities";
import {
  buildImplementationComparison,
  capabilityAccessChannels,
  capabilityOperations,
  capabilityPlatforms,
  capabilityResourceTypes,
  capabilityScoreKeys,
  capabilityStatuses,
  capabilityStatusLabel,
  filterCapabilityImplementations,
  filterCapabilityMatrixCells,
  groupCapabilityScenarios,
  parseCapabilityMarketFilters,
  parseCapabilityMarketView,
  updateCapabilityMarketQuery,
} from "@/lib/capability-market";
import {
  buildMockCapabilityAssertions,
  buildMockCapabilityImplementationDetailDto,
  buildMockCapabilityImplementations,
  buildMockCapabilityMatrixDto,
} from "@/lib/capability-mock";
import type { CapabilityImplementationDetail } from "@/types/capability";

function errorMessage(action: () => void): string {
  try {
    action();
  } catch (error: unknown) {
    if (error instanceof Error) {
      return error.message;
    }
    throw error;
  }
  throw new Error("expected_error");
}

function cloneDetail(
  detail: CapabilityImplementationDetail,
  implementationId: string,
): CapabilityImplementationDetail {
  return {
    ...detail,
    implementation: {
      ...detail.implementation,
      implementationId,
      providerId: implementationId,
    },
    assertions: detail.assertions.map((assertion) => ({ ...assertion })),
    evidence: detail.evidence.map((evidence) => ({ ...evidence })),
  };
}

describe("capability market", () => {
  it("parses matrix and list views and defaults invalid or null views to scenarios", () => {
    expect(parseCapabilityMarketView("matrix")).toBe("matrix");
    expect(parseCapabilityMarketView("list")).toBe("list");
    expect(parseCapabilityMarketView("invalid")).toBe("scenarios");
    expect(parseCapabilityMarketView(null)).toBe("scenarios");
    expect(parseCapabilityMarketView(undefined)).toBe("scenarios");
  });

  it("updates capability query parameters without dropping unrelated state", () => {
    const result = updateCapabilityMarketQuery(
      "project_id=p1&view=list",
      {
        view: "matrix",
        platform: "youtube",
        accessChannel: "official_authorized_api",
        status: "candidate",
      },
    );

    expect(result).toBe(
      "project_id=p1&view=matrix&platform=youtube&access_channel=official_authorized_api&status=candidate",
    );
  });

  it("parses valid filters and omits invalid platform and status values", () => {
    expect(
      parseCapabilityMarketFilters(
        "platform=reddit&access_channel=authorized_browser&resource_type=conversation&operation=list_enumerate&status=candidate&q=%20voc%20",
      ),
    ).toEqual({
      platform: "reddit",
      accessChannel: "authorized_browser",
      resourceType: "conversation",
      operation: "list_enumerate",
      status: "candidate",
      query: "voc",
    });
    expect(
      parseCapabilityMarketFilters(
        "platform=invalid&status=invalid",
      ),
    ).toEqual({});
  });

  it("filters matrix cells while preserving the complete default and explicit unknown status", () => {
    const matrix = mapCapabilityMatrixResponse(buildMockCapabilityMatrixDto());

    expect(filterCapabilityMatrixCells(matrix.cells)).toHaveLength(42);
    expect(
      filterCapabilityMatrixCells(matrix.cells, { platform: "reddit" }),
    ).toHaveLength(6);
    expect(
      filterCapabilityMatrixCells(matrix.cells, { status: "unknown" }),
    ).toHaveLength(35);
  });

  it("builds all eight stable capability scenarios in order", () => {
    const assertions = buildMockCapabilityAssertions();
    const scenarios = groupCapabilityScenarios([
      ...assertions,
      assertions[0]!,
    ]);

    expect(scenarios.map(({ id, label }) => ({ id, label }))).toEqual([
      { id: "market-monitoring", label: "市场监测" },
      { id: "keyword-discovery", label: "关键词发现" },
      { id: "content-detail", label: "内容详情" },
      { id: "conversation-voc", label: "评论与对话" },
      { id: "creator-tracking", label: "创作者" },
      { id: "incremental-monitoring", label: "增量监测" },
      { id: "batch-parsing", label: "批量解析" },
      { id: "export-delivery", label: "导出" },
    ]);
    expect(
      scenarios.every(
        (scenario) =>
          new Set(scenario.assertions.map((item) => item.assertion_id)).size ===
          scenario.assertions.length,
      ),
    ).toBe(true);
  });

  it("filters implementations through owned assertion scope", () => {
    const results = filterCapabilityImplementations(
      buildMockCapabilityImplementations(),
      buildMockCapabilityAssertions(),
      {
        platform: "youtube",
        resourceType: "conversation",
        status: "candidate",
      },
    );

    expect(results.map((item) => item.implementationId)).toEqual(["youtube.v3"]);
  });

  it("keeps total enum orders and exact candidate and unknown labels", () => {
    expect(capabilityPlatforms).toEqual([
      "youtube",
      "reddit",
      "x",
      "instagram",
      "threads",
      "tiktok",
      "linkedin",
    ]);
    expect(capabilityAccessChannels).toEqual([
      "official_authorized_api",
      "licensed_partner_data_service",
      "public_web_feed",
      "authorized_browser",
      "managed_opaque_collector",
      "authorized_export_import",
    ]);
    expect(capabilityResourceTypes).toEqual([
      "content",
      "conversation",
      "creator",
      "topic",
      "metrics",
      "media_live",
      "commerce_ads",
      "relationship_graph",
    ]);
    expect(capabilityOperations).toEqual([
      "resolve_detail",
      "search_discover",
      "list_enumerate",
      "monitor_incremental",
      "backfill_history",
      "batch_parse",
      "export_download",
    ]);
    expect(capabilityStatuses).toEqual([
      "unknown",
      "candidate",
      "verified",
      "partial",
      "blocked",
      "unsupported",
      "deprecated",
    ]);
    expect(capabilityStatusLabel("candidate")).toBe("候选，尚不可执行");
    expect(capabilityStatusLabel("unknown")).toBe("尚无能力事实");
    expect(
      capabilityStatuses.every((status) => capabilityStatusLabel(status).length > 0),
    ).toBe(true);
  });

  it("compares two or three same-platform implementations with shared scope", () => {
    const base = mapCapabilityImplementationDetail(
      buildMockCapabilityImplementationDetailDto("youtube.v3"),
    );
    const second = cloneDetail(base, "youtube.second");
    const third = cloneDetail(base, "youtube.third");
    const comparison = buildImplementationComparison([base, second]);

    expect(comparison.platform).toBe("youtube");
    expect(comparison.sharedResources).toEqual([
      "content",
      "conversation",
      "creator",
      "topic",
      "metrics",
    ]);
    expect(comparison.sharedOperations).toEqual([
      "search_discover",
      "list_enumerate",
      "resolve_detail",
      "monitor_incremental",
      "batch_parse",
    ]);
    expect(comparison.columns.map((column) => column.implementationId)).toEqual([
      "youtube.v3",
      "youtube.second",
    ]);
    expect(capabilityScoreKeys).toEqual([
      "coverage",
      "freshness",
      "history",
      "reliability",
      "schema_stability",
      "cost_efficiency",
      "maintainability",
      "evidence_confidence",
    ]);
    expect(Object.keys(comparison.columns[0]!.scores)).toEqual(capabilityScoreKeys);
    expect(comparison.columns[0]!.scores).toEqual({
      coverage: 3,
      freshness: 3,
      history: 2,
      reliability: 5,
      schema_stability: 5,
      cost_efficiency: 3,
      maintainability: 4,
      evidence_confidence: 3,
    });
    expect(comparison.columns[0]!.constraintCodes.length).toBeGreaterThan(0);
    expect(comparison.columns[0]!.evidence.length).toBeGreaterThan(0);
    expect(
      buildImplementationComparison([base, second, third]).columns,
    ).toHaveLength(3);
    expect(errorMessage(() => buildImplementationComparison([base]))).toBe(
      "capability_comparison_requires_two_or_three",
    );

    const otherPlatform = cloneDetail(base, "reddit.second");
    otherPlatform.implementation.platform = "reddit";
    expect(
      errorMessage(() =>
        buildImplementationComparison([base, otherPlatform]),
      ),
    ).toBe(
      "capability_comparison_requires_same_platform",
    );

    const noSharedScope = cloneDetail(base, "youtube.no-shared-scope");
    noSharedScope.assertions = noSharedScope.assertions.map((assertion) => ({
      ...assertion,
      resource_type: "commerce_ads",
      operation: "export_download",
    }));
    expect(
      errorMessage(() =>
        buildImplementationComparison([base, noSharedScope]),
      ),
    ).toBe(
      "capability_comparison_requires_shared_scope",
    );
  });
});
