// @vitest-environment jsdom

import * as React from "react";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CapabilityDiscoveryWorkspace } from "@/components/api-market/capability-discovery-workspace";
import {
  buildCapabilityDiscoveryPreviewRequest,
  mapCapabilityDiscoveryPreview,
} from "@/lib/api/capability-discovery";
import { buildMockCapabilityDiscoveryPreviewDto } from "@/lib/capability-discovery-mock";
import type { CapabilityDiscoveryPreviewResponseDto } from "@/types/capability-discovery";

(
  globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }
).IS_REACT_ACT_ENVIRONMENT = true;

beforeEach(() => {
  vi.stubGlobal("React", React);
});

function buttonByName(container: HTMLElement, name: string): HTMLButtonElement {
  const button = [...container.querySelectorAll("button")].find(
    (candidate) => candidate.textContent?.trim() === name,
  );
  if (!(button instanceof HTMLButtonElement)) {
    throw new Error(`button_not_found:${name}`);
  }
  return button;
}

async function renderDiscoveryWorkspace({
  loadPreview = async () =>
    mapCapabilityDiscoveryPreview(buildMockCapabilityDiscoveryPreviewDto()),
}: {
  loadPreview?: React.ComponentProps<
    typeof CapabilityDiscoveryWorkspace
  >["loadPreview"];
} = {}): Promise<{ container: HTMLDivElement; root: Root }> {
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);

  await act(async () => {
    root.render(createElement(CapabilityDiscoveryWorkspace, { loadPreview }));
    await Promise.resolve();
    await Promise.resolve();
  });

  return { container, root };
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.resetModules();
});

describe("capability discovery contracts", () => {
  it("maps nested snake_case DTO fields without weakening candidate boundaries", () => {
    const dto: CapabilityDiscoveryPreviewResponseDto =
      buildMockCapabilityDiscoveryPreviewDto();
    const preview = mapCapabilityDiscoveryPreview(dto);

    expect(preview.schemaVersion).toBe("capability_discovery_preview.v1");
    expect(preview.previewFingerprint).toMatch(/^sha256:[0-9a-f]{64}$/);
    expect(preview.generatedFromObservedAt).toBe(dto.generated_from_observed_at);
    expect(preview.sourceSnapshots[0]).toMatchObject({
      fixtureId: dto.source_snapshots[0]?.fixture_id,
      sourceKind: dto.source_snapshots[0]?.source_kind,
      sourceUrl: dto.source_snapshots[0]?.source_url,
      parserId: dto.source_snapshots[0]?.parser_id,
      contentHash: dto.source_snapshots[0]?.content_hash,
    });
    expect(preview.proposedImplementations[0]).toMatchObject({
      proposedImplementationId:
        dto.proposed_implementations[0]?.proposed_implementation_id,
      accessChannel: dto.proposed_implementations[0]?.access_channel,
      claimedRequiredCredentials:
        dto.proposed_implementations[0]?.claimed_required_credentials,
      evidenceRefs: dto.proposed_implementations[0]?.evidence_refs,
    });
    expect(preview.candidateAssertions[0]).toMatchObject({
      candidateId: dto.candidate_assertions[0]?.candidate_id,
      proposedImplementationId:
        dto.candidate_assertions[0]?.proposed_implementation_id,
      supportStatus: "candidate",
      verificationStatus: "unverified",
      executable: false,
      publishable: false,
      sourceClaimRefs: dto.candidate_assertions[0]?.source_claim_refs,
      evidenceRefs: dto.candidate_assertions[0]?.evidence_refs,
      candidateFingerprint:
        dto.candidate_assertions[0]?.candidate_fingerprint,
    });
    expect(preview.candidateAssertions[0]?.claimedConstraints[0]).toMatchObject({
      constraintType:
        dto.candidate_assertions[0]?.claimed_constraints[0]?.constraint_type,
      severity: dto.candidate_assertions[0]?.claimed_constraints[0]?.severity,
    });
    expect(preview.evidence[0]).toMatchObject({
      evidenceId: dto.evidence[0]?.evidence_id,
      sourceVersion: dto.evidence[0]?.source_version,
      observedAt: dto.evidence[0]?.observed_at,
      hashScope: "retrieved_content",
      providerCallAttempted: false,
      credentialReadAttempted: false,
      liveClientCreated: false,
      productionWriteAttempted: false,
    });
    expect(preview.diagnostics.at(-1)).toMatchObject({
      severity: "warning",
      sourceClaimRef: expect.any(String),
    });
    expect(preview.summary).toEqual({
      sourceCount: 4,
      marketSourceCount: 2,
      officialDocSourceCount: 2,
      proposedImplementationCount: 4,
      candidateAssertionCount: 7,
      evidenceCount: 4,
      warningCount: 2,
      errorCount: 0,
    });
    expect(preview.providerCall).toBe(false);
    expect(preview.providerCallAttempted).toBe(false);
    expect(preview.actorRun).toBe(false);
    expect(preview.browserRun).toBe(false);
    expect(preview.llmCall).toBe(false);
    expect(preview.credentialReadAttempted).toBe(false);
    expect(preview.databaseWrite).toBe(false);
    expect(preview.databaseMigration).toBe(false);
    expect(preview.workflowRunCreated).toBe(false);
    expect(preview.candidatePublishAllowed).toBe(false);
    expect(preview.productionWriteAllowed).toBe(false);
  });

  it("builds the bounded default four-fixture request", () => {
    expect(buildCapabilityDiscoveryPreviewRequest()).toEqual({
      schema_version: "capability_discovery_preview_request.v1",
      preview_mode: "fixture_replay",
      fixture_ids: [
        "tikhub-youtube-market-v1",
        "apify-reddit-market-v1",
        "youtube-data-api-doc-v1",
        "reddit-data-api-doc-v1",
      ],
    });
  });

  it("returns a deterministic fresh DTO-shaped mock", () => {
    const first = buildMockCapabilityDiscoveryPreviewDto();
    const second = buildMockCapabilityDiscoveryPreviewDto();

    expect(JSON.stringify(first)).toBe(JSON.stringify(second));
    expect(first).not.toBe(second);
    expect(first.source_snapshots).not.toBe(second.source_snapshots);
    first.diagnostics.length = 0;
    expect(second.diagnostics).toHaveLength(9);
  });

  it("uses only the real preview POST path and body when mock mode is disabled", async () => {
    vi.stubEnv("NEXT_PUBLIC_MOCK_API", "false");
    const responseDto = buildMockCapabilityDiscoveryPreviewDto();
    const fetchMock = vi.fn<typeof fetch>(async () =>
      new Response(JSON.stringify(responseDto), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { previewCapabilityDiscovery } = await import(
      "@/lib/api/capability-discovery"
    );

    const preview = await previewCapabilityDiscovery();

    expect(preview.summary.candidateAssertionCount).toBe(7);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(url).toBe(
      "http://localhost:8000/api/capabilities/discovery/preview",
    );
    expect(init).toMatchObject({
      method: "POST",
      credentials: "include",
    });
    expect(JSON.parse(String(init?.body))).toEqual(
      buildCapabilityDiscoveryPreviewRequest(),
    );
  });

  it("propagates real API failure without falling back to the mock", async () => {
    vi.stubEnv("NEXT_PUBLIC_MOCK_API", "false");
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({ detail: "capability_discovery_fixture_invalid" }),
        {
          status: 503,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { previewCapabilityDiscovery } = await import(
      "@/lib/api/capability-discovery"
    );

    await expect(previewCapabilityDiscovery()).rejects.toMatchObject({
      name: "ApiRequestError",
      status: 503,
      message: "capability_discovery_fixture_invalid",
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("uses the deterministic mock without making a request in mock mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_MOCK_API", "true");
    const fetchMock = vi.fn(async () => {
      throw new Error("fetch must not be called in mock mode");
    });
    vi.stubGlobal("fetch", fetchMock);
    const { previewCapabilityDiscovery } = await import(
      "@/lib/api/capability-discovery"
    );

    const preview = await previewCapabilityDiscovery();

    expect(preview.summary.sourceCount).toBe(4);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("capability discovery workspace", () => {
  it("renders the bounded four-source pipeline, candidates, evidence summary, and warnings", async () => {
    const { container, root } = await renderDiscoveryWorkspace();

    expect(container.textContent).toContain("离线快照边界");
    expect(container.textContent).toContain("Source → Parser → Candidate → Evidence → 待核验");
    expect(container.textContent).toContain("不可执行");
    expect(container.textContent).toContain("不可发布");
    expect(container.textContent).toContain("provider_call=false");
    expect(container.textContent).toContain("browser_run=false");
    expect(container.querySelectorAll("[data-discovery-source-id]")).toHaveLength(4);
    expect(container.querySelectorAll("[data-discovery-candidate-id]")).toHaveLength(7);
    expect(container.querySelectorAll("[data-discovery-warning]")).toHaveLength(2);
    expect(container.textContent).toContain("4 个 Evidence");

    const forbiddenButton = [...container.querySelectorAll("button")].find(
      (button) =>
        /^(核验|发布|执行|运行|激活|重试 Provider|刷新 Web|浏览器抓取)$/.test(
          button.textContent?.trim() ?? "",
        ),
    );
    expect(forbiddenButton).toBeUndefined();

    act(() => root.unmount());
  });

  it("drills from a source to a candidate and evidence, then restores trigger focus on close", async () => {
    const animationFrames: FrameRequestCallback[] = [];
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      animationFrames.push(callback);
      return animationFrames.length;
    });
    const { container, root } = await renderDiscoveryWorkspace();

    act(() => buttonByName(container, "查看 TikHub YouTube API public page 的 Candidate").click());
    expect(container.querySelectorAll("[data-discovery-candidate-id]")).toHaveLength(3);

    const candidateTrigger = container.querySelector<HTMLButtonElement>(
      "[data-discovery-candidate-id] button",
    );
    expect(candidateTrigger).not.toBeNull();
    candidateTrigger?.focus();
    act(() => candidateTrigger?.click());

    expect(container.querySelector('[role="dialog"]')).not.toBeNull();
    expect(container.textContent).toContain("Candidate 详情");
    const evidenceButton = [...container.querySelectorAll("button")].find(
      (button) => button.textContent?.includes("查看 Evidence"),
    );
    expect(evidenceButton).toBeDefined();
    act(() => evidenceButton?.click());
    expect(container.textContent).toContain("Evidence 详情");
    expect(container.textContent).toContain("L2-fixture-or-dry-run");

    act(() => buttonByName(container, "关闭 Candidate 详情").click());
    act(() => animationFrames.shift()?.(0));
    expect(document.activeElement).toBe(candidateTrigger);

    act(() => root.unmount());
  });

  it("surfaces real Preview failure without rendering fixture facts as fallback", async () => {
    const { container, root } = await renderDiscoveryWorkspace({
      loadPreview: async () => {
        throw new Error("capability_discovery_fixture_invalid");
      },
    });

    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      "capability_discovery_fixture_invalid",
    );
    expect(container.textContent).toContain("未使用 mock 回退");
    expect(container.querySelectorAll("[data-discovery-candidate-id]")).toHaveLength(0);

    act(() => root.unmount());
  });
});
