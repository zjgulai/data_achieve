import { describe, expect, it } from "vitest";

import {
  apiMarketEndpoints,
  buildApiMarketStats,
  findApiMarketEndpointById,
  filterApiMarketEndpoints,
} from "@/lib/api-market-catalog";

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
});
