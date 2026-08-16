import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  apiMarketEndpointPresentations,
  assertApiMarketPresentationParity,
  buildApiMarketStats,
  composeApiMarketEndpoints,
  filterApiMarketEndpoints,
  findApiMarketEndpointById,
  findApiMarketPresentationById,
  listApiMarketPresentationsByProviderId,
} from "@/lib/api-market-catalog";
import { buildApiMarketPreviewChainInputs } from "@/lib/api-market-preview-chain";
import {
  buildSocialExecutionDryRunRequestBody,
  buildSocialProviderAdapterPlanRequestBody,
} from "@/lib/api/social-provider";
import { mapCapabilityImplementation } from "@/lib/api/capabilities";
import {
  buildMockCapabilityAssertions,
  buildMockCapabilityImplementations,
} from "@/lib/capability-mock";
import { capabilityStatusLabel } from "@/lib/capability-market";
import type { CapabilityImplementationDto } from "@/types/capability";

function readCanonicalCapabilityImplementations() {
  const fixturePath = resolve(
    process.cwd(),
    "../api/src/data_intelligence_hub/services/fixtures/capability_catalog_overseas_v2.json",
  );
  const fixture = JSON.parse(readFileSync(fixturePath, "utf8")) as {
    implementations: CapabilityImplementationDto[];
  };

  return fixture.implementations.map(mapCapabilityImplementation);
}

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

describe("api market catalog", () => {
  const mockImplementations = buildMockCapabilityImplementations();
  const mockAssertions = buildMockCapabilityAssertions();
  const composedEndpoints = composeApiMarketEndpoints(
    apiMarketEndpointPresentations,
    mockImplementations,
    mockAssertions,
  );

  it("contains overseas social API marketplace endpoints with no live side effects", () => {
    expect(composedEndpoints.length).toBeGreaterThanOrEqual(14);
    for (const endpoint of composedEndpoints) {
      expect(endpoint.providerCall).toBe(false);
      expect(endpoint.providerCallAttempted).toBe(false);
      expect(endpoint.credentialReadAttempted).toBe(false);
      expect(endpoint.liveClientCreated).toBe(false);
      expect(endpoint.productionWriteAllowed).toBe(false);
    }
  });

  it("filters by platform, category, and text query", () => {
    const results = filterApiMarketEndpoints(composedEndpoints, {
      accessChannel: "all",
      category: "comment_threads",
      platform: "youtube",
      priority: "all",
      query: "commentThreads",
      status: "all",
    });

    expect(results.map((item) => item.endpoint)).toContain("commentThreads.list");
    expect(results.every((item) => item.platform === "youtube")).toBe(true);
  });

  it("finds composed endpoint details by stable id", () => {
    const endpoint = findApiMarketEndpointById(
      composedEndpoints,
      "youtube-v3-videos-list",
    );

    expect(endpoint?.providerId).toBe("youtube.v3");
    expect(endpoint?.endpoint).toBe("videos.list");
    expect(endpoint?.request?.parameters.some((param) => param.name === "part")).toBe(
      true,
    );
  });

  it("finds presentation-only details by stable id", () => {
    const presentation = findApiMarketPresentationById("youtube-v3-videos-list");

    expect(presentation?.providerId).toBe("youtube.v3");
    expect(presentation?.endpointId).toBe("videos.list");

    const youtubePresentations = listApiMarketPresentationsByProviderId("youtube.v3");
    expect(youtubePresentations).toHaveLength(4);
    expect(
      youtubePresentations.every(
        (youtubePresentation) => youtubePresentation.providerId === "youtube.v3",
      ),
    ).toBe(true);
  });

  it("returns null for unknown endpoint ids", () => {
    expect(
      findApiMarketEndpointById(composedEndpoints, "missing-endpoint"),
    ).toBeNull();
  });

  it("builds marketplace stats from the composed catalog", () => {
    const stats = buildApiMarketStats(composedEndpoints);

    expect(stats.platformCount).toBe(7);
    expect(stats.providerCallAttempted).toBe(false);
    expect(stats.candidateCount).toBeGreaterThan(0);
  });

  it("builds fixture-only preview chain inputs from an enhanced endpoint", () => {
    const endpoint = findApiMarketEndpointById(
      composedEndpoints,
      "youtube-v3-commentthreads-list",
    );
    expect(endpoint?.presentationMode).toBe("enhanced");
    if (endpoint?.presentationMode !== "enhanced") {
      throw new Error("expected_enhanced_endpoint");
    }

    const inputs = buildApiMarketPreviewChainInputs(endpoint, { fixtureLimit: 4 });

    expect(inputs.readiness).toEqual({
      platform: "youtube",
      endpoints: ["commentThreads.list"],
    });
    expect(inputs.datasetPreview.datasetName).toBe(
      "YouTube commentThreads.list VOC fixture dataset",
    );
    expect(inputs.sourceTemplate.sourceName).toBe(
      "YouTube commentThreads.list fixture source",
    );
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

  it("keeps non-YouTube enhanced endpoints scoped to their own platform", () => {
    const endpoint = findApiMarketEndpointById(
      composedEndpoints,
      "x-v2-tweets-search-recent",
    );
    expect(endpoint?.presentationMode).toBe("enhanced");
    if (endpoint?.presentationMode !== "enhanced") {
      throw new Error("expected_enhanced_endpoint");
    }

    const inputs = buildApiMarketPreviewChainInputs(endpoint, { maxRows: 7 });

    expect(inputs.readiness.platform).toBe("x");
    expect(inputs.adapterPlan.endpoints).toEqual(["tweets/search/recent"]);
    expect(inputs.datasetPreview.endpoint).toBe("tweets/search/recent");
    expect(inputs.datasetPreview.maxRows).toBe(7);
    expect(inputs.executionDryRun.endpoint).toBe("tweets/search/recent");
  });

  it("accepts the mock capability catalog presentation parity", () => {
    expect(() =>
      assertApiMarketPresentationParity(
        apiMarketEndpointPresentations,
        mockImplementations,
      ),
    ).not.toThrow();
  });

  it("composes all canonical fixture endpoints with strict parity", () => {
    const canonicalImplementations = readCanonicalCapabilityImplementations();
    const expectedEndpointCount = canonicalImplementations.reduce(
      (total, implementation) => total + implementation.supportedEndpoints.length,
      0,
    );

    expect(expectedEndpointCount).toBe(38);
    expect(() =>
      assertApiMarketPresentationParity(
        apiMarketEndpointPresentations,
        canonicalImplementations,
      ),
    ).not.toThrow();

    const canonicalEndpoints = composeApiMarketEndpoints(
      apiMarketEndpointPresentations,
      canonicalImplementations,
      mockAssertions,
    );
    expect(canonicalEndpoints).toHaveLength(expectedEndpointCount);
    expect(
      canonicalEndpoints.filter(
        (endpoint) => endpoint.presentationMode === "enhanced",
      ),
    ).toHaveLength(18);
    expect(
      canonicalEndpoints.filter(
        (endpoint) => endpoint.presentationMode === "generic",
      ),
    ).toHaveLength(20);
  });

  it("rejects a presentation endpoint absent from the capability catalog", () => {
    const invalidPresentation = {
      ...apiMarketEndpointPresentations[0],
      id: "invalid-extra-presentation",
      endpointId: "missing.endpoint",
    };

    expect(
      errorMessage(() =>
        assertApiMarketPresentationParity(
          [...apiMarketEndpointPresentations, invalidPresentation],
          mockImplementations,
        ),
      ),
    ).toBe("api_market_presentation_endpoint_not_in_catalog");
  });

  it("rejects duplicate implementation providers with an exact error", () => {
    const firstImplementation = mockImplementations[0];
    if (!firstImplementation) {
      throw new Error("expected_mock_implementation");
    }

    expect(
      errorMessage(() =>
        assertApiMarketPresentationParity(apiMarketEndpointPresentations, [
          ...mockImplementations,
          {
            ...firstImplementation,
            implementationId: "duplicate.youtube.v3",
          },
        ]),
      ),
    ).toBe("api_market_duplicate_provider_id");
  });

  it("rejects duplicate presentation keys with an exact error", () => {
    const firstPresentation = apiMarketEndpointPresentations[0];
    if (!firstPresentation) {
      throw new Error("expected_api_market_presentation");
    }

    expect(
      errorMessage(() =>
        assertApiMarketPresentationParity(
          [
            ...apiMarketEndpointPresentations,
            { ...firstPresentation, id: "duplicate-presentation" },
          ],
          mockImplementations,
        ),
      ),
    ).toBe("api_market_duplicate_presentation_key");
  });

  it("rejects presentations without an implementation with an exact error", () => {
    const firstPresentation = apiMarketEndpointPresentations[0];
    if (!firstPresentation) {
      throw new Error("expected_api_market_presentation");
    }

    expect(
      errorMessage(() =>
        assertApiMarketPresentationParity(
          [
            ...apiMarketEndpointPresentations,
            {
              ...firstPresentation,
              id: "missing-implementation-presentation",
              providerId: "missing.provider",
            },
          ],
          mockImplementations,
        ),
      ),
    ).toBe("api_market_presentation_implementation_not_found");
  });

  it("composes YouTube commentThreads facts from its capability implementation", () => {
    const endpoint = findApiMarketEndpointById(
      composedEndpoints,
      "youtube-v3-commentthreads-list",
    );

    expect(endpoint?.providerId).toBe("youtube.v3");
    expect(endpoint?.accessChannel).toBe("official_authorized_api");
    expect(endpoint?.supportStatus).toBe("candidate");
    expect(endpoint?.providerCall).toBe(false);
    expect(endpoint?.providerCallAttempted).toBe(false);
    expect(endpoint?.productionWriteAllowed).toBe(false);
  });

  it("keeps backend-only YouTube videos.insert generic and blocked", () => {
    const canonicalEndpoints = composeApiMarketEndpoints(
      apiMarketEndpointPresentations,
      readCanonicalCapabilityImplementations(),
      mockAssertions,
    );
    const endpoint = findApiMarketEndpointById(
      canonicalEndpoints,
      "generic:youtube.v3:videos.insert",
    );

    expect(endpoint?.presentationMode).toBe("generic");
    expect(endpoint?.presentation).toBeNull();
    expect(endpoint?.title).toBe("videos.insert");
    expect(endpoint?.blockedActions).toContain("unauthorized_video_download");
  });

  it("uses exact total capability status labels", () => {
    expect(capabilityStatusLabel("candidate")).toBe("候选，尚不可执行");
    expect(capabilityStatusLabel("unknown")).toBe("尚无能力事实");
    expect(capabilityStatusLabel("verified")).toBe("已核验");
  });

  it("links to Discovery as a secondary surface without creating a fourth Catalog tab", () => {
    const workspaceSource = readFileSync(
      resolve(
        process.cwd(),
        "src/components/api-market/api-market-workspace.tsx",
      ),
      "utf8",
    );
    const discoveryPageSource = readFileSync(
      resolve(process.cwd(), "src/app/api-market/discovery/page.tsx"),
      "utf8",
    );

    expect(workspaceSource).toContain('href="/api-market/discovery"');
    expect(workspaceSource).toContain("打开能力发现 Preview");
    expect(workspaceSource.match(/value: \"(scenarios|matrix|list)\"/g)).toHaveLength(
      3,
    );
    expect(discoveryPageSource).toContain("CapabilityDiscoveryWorkspace");
  });
});
