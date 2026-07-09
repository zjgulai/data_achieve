import { describe, expect, it } from "vitest";

import {
  apiMarketEndpoints,
  buildApiMarketStats,
  findApiMarketEndpointById,
  filterApiMarketEndpoints,
} from "@/lib/api-market-catalog";
import { buildApiMarketPreviewChainInputs } from "@/lib/api-market-preview-chain";
import {
  buildSocialExecutionDryRunRequestBody,
  buildSocialProviderAdapterPlanRequestBody,
} from "@/lib/api/social-provider";

describe("api market catalog", () => {
  it("contains overseas social API marketplace endpoints with no live side effects", () => {
    expect(apiMarketEndpoints.length).toBeGreaterThanOrEqual(14);
    expect(apiMarketEndpoints.every((item) => item.providerCall === false)).toBe(true);
    expect(apiMarketEndpoints.every((item) => item.liveClientCreated === false)).toBe(true);
    expect(apiMarketEndpoints.every((item) => item.productionWriteAllowed === false)).toBe(true);
  });

  it("filters by platform, category, and text query", () => {
    const results = filterApiMarketEndpoints({
      category: "comment_threads",
      executionMode: "all",
      platform: "youtube",
      priority: "all",
      query: "commentThreads",
      stability: "all",
    });

    expect(results.map((item) => item.endpoint)).toContain("commentThreads.list");
    expect(results.every((item) => item.platform === "youtube")).toBe(true);
  });

  it("finds endpoint details by stable id", () => {
    const endpoint = findApiMarketEndpointById("youtube-v3-videos-list");

    expect(endpoint?.providerId).toBe("youtube.v3");
    expect(endpoint?.endpoint).toBe("videos.list");
    expect(endpoint?.request.parameters.some((param) => param.name === "part")).toBe(true);
  });

  it("returns null for unknown endpoint ids", () => {
    expect(findApiMarketEndpointById("missing-endpoint")).toBeNull();
  });

  it("builds marketplace stats from the catalog", () => {
    const stats = buildApiMarketStats(apiMarketEndpoints);

    expect(stats.platformCount).toBe(7);
    expect(stats.providerCallAttempted).toBe(false);
    expect(stats.liveGatedCount).toBeGreaterThan(0);
  });

  it("builds fixture-only preview chain inputs from an API market endpoint", () => {
    const endpoint = findApiMarketEndpointById("youtube-v3-commentthreads-list");
    expect(endpoint).not.toBeNull();

    const inputs = buildApiMarketPreviewChainInputs(endpoint!, { fixtureLimit: 4 });

    expect(inputs.readiness).toEqual({
      platform: "youtube",
      endpoints: ["commentThreads.list"],
    });
    expect(inputs.datasetPreview.datasetName).toBe("YouTube commentThreads.list VOC fixture dataset");
    expect(inputs.sourceTemplate.sourceName).toBe("YouTube commentThreads.list fixture source");
    expect(inputs.taskRunApprovalTemplate.intendedUse).toBe(
      "fixture-only api-market review for youtube commentThreads.list",
    );

    const adapterRequest = buildSocialProviderAdapterPlanRequestBody(inputs.adapterPlan);
    expect(adapterRequest.authorized).toBe(false);
    expect(adapterRequest.fixture_limit).toBe(4);
    expect(adapterRequest.credential_reference).toBeUndefined();

    const dryRunRequest = buildSocialExecutionDryRunRequestBody(inputs.executionDryRun);
    expect(dryRunRequest.authorized).toBe(false);
    expect(dryRunRequest.credentials_ready).toBe(false);
    expect(dryRunRequest.include_live_comparison).toBe(false);
    expect(dryRunRequest.dataset_save_requested).toBe(false);
    expect(dryRunRequest.export_requested).toBe(false);
    expect(dryRunRequest.allow_ai_training).toBe(false);
  });

  it("keeps non-YouTube API market endpoints scoped to their own platform", () => {
    const endpoint = findApiMarketEndpointById("x-v2-tweets-search-recent");
    expect(endpoint).not.toBeNull();

    const inputs = buildApiMarketPreviewChainInputs(endpoint!, { maxRows: 7 });

    expect(inputs.readiness.platform).toBe("x");
    expect(inputs.adapterPlan.endpoints).toEqual(["tweets/search/recent"]);
    expect(inputs.datasetPreview.endpoint).toBe("tweets/search/recent");
    expect(inputs.datasetPreview.maxRows).toBe(7);
    expect(inputs.executionDryRun.endpoint).toBe("tweets/search/recent");
  });
});
