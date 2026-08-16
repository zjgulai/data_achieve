// @vitest-environment jsdom

import * as React from "react";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CapabilityGovernanceWorkspace } from "@/components/api-market/capability-governance-workspace";
import {
  mapCapabilityGovernanceCandidateDetail,
  mapCapabilityGovernanceCandidateList,
  mapCapabilityGovernanceImportResponse,
  mapCapabilityGovernancePublicationDetail,
  mapCapabilityGovernancePublicationList,
  mapCapabilityGovernancePublicationResponse,
  mapCapabilityGovernanceReviewResponse,
  mapCapabilityGovernanceVerificationTaskDetail,
  mapCapabilityGovernanceVerificationTaskList,
  type CapabilityGovernanceTransport,
} from "@/lib/api/capability-governance";
import {
  buildMockCapabilityGovernanceCanonicalBundleDto,
  createMockCapabilityGovernanceStore,
  type CapabilityGovernanceMockStore,
} from "@/lib/capability-governance-mock";
import type {
  CapabilityGovernanceCandidate,
  CapabilityGovernancePermissionSet,
  CapabilityGovernancePublicationRevision,
  CapabilityGovernanceVerificationTask,
} from "@/types/capability-governance";

(
  globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }
).IS_REACT_ACT_ENVIRONMENT = true;

beforeEach(() => {
  vi.stubGlobal("React", React);
});

function transportForStore(
  store: CapabilityGovernanceMockStore,
): CapabilityGovernanceTransport {
  return {
    async listCandidates(options = {}) {
      return mapCapabilityGovernanceCandidateList(
        store.listCandidates({
          limit: options.limit ?? 50,
          offset: options.offset ?? 0,
        }),
      );
    },
    async getCandidate(candidateKey) {
      return mapCapabilityGovernanceCandidateDetail(
        store.getCandidate(candidateKey),
      );
    },
    async listVerificationTasks(options = {}) {
      return mapCapabilityGovernanceVerificationTaskList(
        store.listVerificationTasks({
          status: options.status,
          limit: options.limit ?? 50,
          offset: options.offset ?? 0,
        }),
      );
    },
    async getVerificationTask(taskId) {
      return mapCapabilityGovernanceVerificationTaskDetail(
        store.getVerificationTask(taskId),
      );
    },
    async listPublications(options = {}) {
      return mapCapabilityGovernancePublicationList(
        store.listPublications({
          limit: options.limit ?? 50,
          offset: options.offset ?? 0,
        }),
      );
    },
    async getPublication(revisionId) {
      return mapCapabilityGovernancePublicationDetail(
        store.getPublication(revisionId),
      );
    },
    async importCandidates(payload, idempotencyKey) {
      return mapCapabilityGovernanceImportResponse(
        store.importCandidates(payload, idempotencyKey),
      );
    },
    async reviewCandidate(taskId, payload, idempotencyKey) {
      return mapCapabilityGovernanceReviewResponse(
        store.reviewCandidate(taskId, payload, idempotencyKey),
      );
    },
    async publishCatalog(payload, idempotencyKey) {
      return mapCapabilityGovernancePublicationResponse(
        store.publishCatalog(payload, idempotencyKey),
      );
    },
    async rollbackCatalog(payload, idempotencyKey) {
      return mapCapabilityGovernancePublicationResponse(
        store.rollbackCatalog(payload, idempotencyKey),
      );
    },
  };
}

function buttonByName(container: HTMLElement, name: string): HTMLButtonElement {
  const button = [...container.querySelectorAll("button")].find(
    (candidate) => candidate.textContent?.trim() === name,
  );
  if (!(button instanceof HTMLButtonElement)) {
    throw new Error(`button_not_found:${name}`);
  }
  return button;
}

async function settle(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function renderGovernanceWorkspace({
  permissions,
  transport,
}: {
  permissions?: CapabilityGovernancePermissionSet;
  transport?: CapabilityGovernanceTransport;
} = {}): Promise<{
  container: HTMLDivElement;
  root: Root;
  store: CapabilityGovernanceMockStore;
  transport: CapabilityGovernanceTransport;
}> {
  const store = createMockCapabilityGovernanceStore({ permissions });
  const selectedTransport = transport ?? transportForStore(store);
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);

  await act(async () => {
    root.render(
      createElement(CapabilityGovernanceWorkspace, {
        transport: selectedTransport,
        resolveCanonicalBundle: () =>
          buildMockCapabilityGovernanceCanonicalBundleDto(),
      }),
    );
    await Promise.resolve();
    await Promise.resolve();
  });
  await settle();

  return { container, root, store, transport: selectedTransport };
}

afterEach(() => {
  document.body.replaceChildren();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.resetModules();
});

describe("capability governance workspace", () => {
  it("loads every governance page and shows only the latest immutable Candidate version", async () => {
    const store = createMockCapabilityGovernanceStore();
    const base = transportForStore(store);
    const candidateSeed = (await base.listCandidates()).items[0]!;
    const taskSeed = (await base.listVerificationTasks()).items[0]!;
    const candidates: CapabilityGovernanceCandidate[] = Array.from(
      { length: 100 },
      (_, index) => ({
        ...candidateSeed,
        id: `candidate-${index}`,
        candidateKey: `candidate-key-${index}`,
        semanticVersion: index === 0 ? 2 : 1,
      }),
    );
    candidates.push({
      ...candidateSeed,
      id: "candidate-0-older",
      candidateKey: "candidate-key-0",
      semanticVersion: 1,
    });
    const tasks: CapabilityGovernanceVerificationTask[] = Array.from(
      { length: 101 },
      (_, index) => ({
        ...taskSeed,
        id: `task-${index}`,
        candidateVersionId: `candidate-${index}`,
        status: "open",
      }),
    );
    const publications: CapabilityGovernancePublicationRevision[] = Array.from(
      { length: 101 },
      (_, index) => ({
        id: `revision-${index}`,
        revisionNumber: 101 - index,
        parentRevisionId: index === 100 ? null : `revision-${index + 1}`,
        restoredFromRevisionId: null,
        catalogSnapshotId: `snapshot-${index}`,
        publisherUserId: "publisher",
        publishedAt: new Date(Date.UTC(2026, 6, 18, 0, index)).toISOString(),
        reason: `revision ${index}`,
        operations: [],
        isCurrent: index === 0,
      }),
    );
    const candidateOffsets: number[] = [];
    const taskOffsets: number[] = [];
    const publicationOffsets: number[] = [];
    const transport: CapabilityGovernanceTransport = {
      ...base,
      async listCandidates(options = {}) {
        const limit = options.limit ?? 50;
        const offset = options.offset ?? 0;
        candidateOffsets.push(offset);
        const first = await base.listCandidates();
        return {
          ...first,
          items: candidates.slice(offset, offset + limit),
          limit,
          offset,
        };
      },
      async listVerificationTasks(options = {}) {
        const limit = options.limit ?? 50;
        const offset = options.offset ?? 0;
        taskOffsets.push(offset);
        const first = await base.listVerificationTasks();
        return {
          ...first,
          items: tasks.slice(offset, offset + limit),
          limit,
          offset,
        };
      },
      async listPublications(options = {}) {
        const limit = options.limit ?? 50;
        const offset = options.offset ?? 0;
        publicationOffsets.push(offset);
        const first = await base.listPublications();
        return {
          ...first,
          items: publications.slice(offset, offset + limit),
          currentRevisionId: publications[0]!.id,
          limit,
          offset,
        };
      },
    };

    const { container, root } = await renderGovernanceWorkspace({ transport });

    expect(candidateOffsets).toEqual([0, 100]);
    expect(taskOffsets).toEqual([0, 100]);
    expect(publicationOffsets).toEqual([0, 100]);
    expect(
      container.querySelectorAll("[data-governance-candidate-key]"),
    ).toHaveLength(100);
    expect(
      container.querySelectorAll(
        '[data-governance-candidate-key="candidate-key-0"]',
      ),
    ).toHaveLength(1);
    expect(container.textContent).toContain("101 open");
    expect(
      container.querySelectorAll("[data-governance-revision-id]"),
    ).toHaveLength(101);

    act(() => root.unmount());
  });

  it("renders the Candidate inbox and Evidence dossier, then restores focus on Escape", async () => {
    const animationFrames: FrameRequestCallback[] = [];
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      animationFrames.push(callback);
      return animationFrames.length;
    });
    const { container, root } = await renderGovernanceWorkspace();

    expect(container.textContent).toContain("治理审计台");
    expect(container.textContent).toContain("Candidate Inbox");
    expect(container.textContent).toContain("Revision Ledger");
    expect(
      container.querySelectorAll("[data-governance-candidate-key]"),
    ).toHaveLength(7);
    expect(container.textContent).toContain("可审查");
    expect(container.textContent).toContain("可发布");

    const trigger = container.querySelector<HTMLButtonElement>(
      "[data-governance-candidate-key] button",
    );
    expect(trigger).not.toBeNull();
    trigger?.focus();
    act(() => trigger?.click());
    await settle();

    expect(container.querySelector('[role="dialog"]')).not.toBeNull();
    expect(container.textContent).toContain("Evidence Dossier");
    expect(container.textContent).toContain("业务事实");
    expect(container.textContent).toContain("高级契约与指纹");
    expect(
      container.querySelectorAll("[data-governance-evidence-id]").length,
    ).toBeGreaterThan(0);

    act(() =>
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })),
    );
    act(() => animationFrames.shift()?.(0));
    expect(container.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);

    act(() => root.unmount());
  });

  it("reviews a Candidate, publishes its verified decision, and appends Revision history", async () => {
    const { container, root } = await renderGovernanceWorkspace();
    const trigger = container.querySelector<HTMLButtonElement>(
      "[data-governance-candidate-key] button",
    );

    act(() => trigger?.click());
    await settle();
    act(() => buttonByName(container, "核验通过").click());
    await settle();

    expect(container.querySelector('[role="status"]')?.textContent).toContain(
      "核验已记录",
    );
    expect(container.textContent).toContain("已核验");
    act(() => buttonByName(container, "发布到 Catalog").click());
    await settle();

    expect(container.querySelector('[role="status"]')?.textContent).toContain(
      "Revision #1 已发布",
    );
    expect(container.textContent).toContain("Revision #1");
    expect(container.textContent).toContain("当前版本");
    expect(
      container.querySelectorAll("[data-governance-revision-id]"),
    ).toHaveLength(1);

    act(() => root.unmount());
  });

  it("renders explicit read-only and forbidden states without mutation controls", async () => {
    const readOnly = await renderGovernanceWorkspace({
      permissions: { canRead: true, canReview: false, canPublish: false },
    });

    expect(readOnly.container.textContent).toContain("只读访问");
    const trigger = readOnly.container.querySelector<HTMLButtonElement>(
      "[data-governance-candidate-key] button",
    );
    act(() => trigger?.click());
    await settle();
    expect(readOnly.container.textContent).not.toContain("核验通过");
    expect(readOnly.container.textContent).not.toContain("发布到 Catalog");
    act(() => readOnly.root.unmount());

    const forbidden = await renderGovernanceWorkspace({
      permissions: { canRead: false, canReview: false, canPublish: false },
    });
    expect(
      forbidden.container.querySelector('[role="alert"]')?.textContent,
    ).toContain("capability_governance_forbidden");
    expect(
      forbidden.container.querySelectorAll("[data-governance-candidate-key]"),
    ).toHaveLength(0);
    act(() => forbidden.root.unmount());
  });

  it("surfaces a review conflict and reloads authoritative Task and Revision state", async () => {
    const store = createMockCapabilityGovernanceStore();
    const base = transportForStore(store);
    const listTasks = vi.fn(base.listVerificationTasks);
    const listPublications = vi.fn(base.listPublications);
    const transport: CapabilityGovernanceTransport = {
      ...base,
      listVerificationTasks: listTasks,
      listPublications,
      reviewCandidate: vi.fn(async () => {
        throw new Error("verification_task_conflict");
      }),
    };
    const { container, root } = await renderGovernanceWorkspace({ transport });
    const trigger = container.querySelector<HTMLButtonElement>(
      "[data-governance-candidate-key] button",
    );

    act(() => trigger?.click());
    await settle();
    act(() => buttonByName(container, "拒绝 Candidate").click());
    await settle();

    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      "verification_task_conflict",
    );
    expect(container.textContent).toContain("已重新加载权威状态");
    expect(listTasks).toHaveBeenCalledTimes(2);
    expect(listPublications).toHaveBeenCalledTimes(2);

    act(() => root.unmount());
  });

  it("does not reopen a closed dossier when a mutation refresh resolves late", async () => {
    const store = createMockCapabilityGovernanceStore();
    const base = transportForStore(store);
    const initialDetail = await base.getCandidate(
      (await base.listCandidates()).items[0]!.candidateKey,
    );
    let resolveRefresh: ((value: typeof initialDetail) => void) | null = null;
    let detailCalls = 0;
    const transport: CapabilityGovernanceTransport = {
      ...base,
      async getCandidate(candidateKey) {
        detailCalls += 1;
        if (detailCalls === 1) return base.getCandidate(candidateKey);
        return new Promise((resolve) => {
          resolveRefresh = resolve;
        });
      },
    };
    const { container, root } = await renderGovernanceWorkspace({ transport });
    const trigger = container.querySelector<HTMLButtonElement>(
      "[data-governance-candidate-key] button",
    );

    act(() => trigger?.click());
    await settle();
    act(() => buttonByName(container, "拒绝 Candidate").click());
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(detailCalls).toBe(2);
    act(() =>
      container
        .querySelector<HTMLButtonElement>('[aria-label="关闭治理档案"]')
        ?.click(),
    );
    expect(container.querySelector('[role="dialog"]')).toBeNull();

    await act(async () => {
      resolveRefresh?.(initialDetail);
      await Promise.resolve();
      await Promise.resolve();
    });
    await settle();

    expect(container.querySelector('[role="dialog"]')).toBeNull();
    act(() => root.unmount());
  });
});
