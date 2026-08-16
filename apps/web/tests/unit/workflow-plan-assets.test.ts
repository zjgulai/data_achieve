// @vitest-environment jsdom

import * as React from "react";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SavedWorkflowPlansWorkspace } from "@/components/workflow-planner/saved-workflow-plans-workspace";
import { WorkflowPlanDetailWorkspace } from "@/components/workflow-planner/workflow-plan-detail-workspace";
import {
  cloneWorkflowPlan,
  compareWorkflowPlanVersions,
  copyMonitoringScopeTemplate,
  getWorkflowPlan,
  listMonitoringScopes,
  listWorkflowPlans,
  listWorkflowPlanVersions,
} from "@/lib/api/workflow-plan-persistence";
import { ApiRequestError } from "@/lib/api/client";
import type {
  MonitoringScope,
  MonitoringScopeListResult,
  WorkflowPlan,
  WorkflowPlanDetail,
  WorkflowPlanListResult,
  WorkflowPlanVersionCompare,
  WorkflowVersion,
  WorkflowVersionListResult,
  WorkflowVersionSummary,
} from "@/types/workflow-plan-persistence";
import type {
  PlanningInput,
  WorkflowPlanPreview,
} from "@/types/workflow-planner";

const projectSelection = vi.hoisted(() => ({
  current: {
    loading: false,
    projectListError: null as string | null,
    selectedProject: {
      id: "project-a",
      name: "Project A",
      status: "active" as const,
    },
  } as {
    loading: boolean;
    projectListError: string | null;
    selectedProject: {
      id: string;
      name: string;
      status: "active";
    } | null;
  },
  clear: vi.fn(),
  mark: vi.fn(),
}));

vi.mock("@/components/layout/project-selection-provider", () => ({
  useProjectSelection: () => ({
    ...projectSelection.current,
    clearProjectFilterApplied: projectSelection.clear,
    markProjectFilterApplied: projectSelection.mark,
  }),
}));

vi.mock("@/lib/api/workflow-plan-persistence", async (importOriginal) => {
  const original =
    await importOriginal<
      typeof import("@/lib/api/workflow-plan-persistence")
    >();
  return {
    ...original,
    cloneWorkflowPlan: vi.fn(),
    compareWorkflowPlanVersions: vi.fn(),
    copyMonitoringScopeTemplate: vi.fn(),
    getWorkflowPlan: vi.fn(),
    listMonitoringScopes: vi.fn(),
    listWorkflowPlans: vi.fn(),
    listWorkflowPlanVersions: vi.fn(),
  };
});

vi.mock("@/components/workflow-planner/workflow-plan-preview", () => ({
  WorkflowPlanPreview: ({ preview }: { preview: WorkflowPlanPreview }) =>
    React.createElement(
      "div",
      { "data-testid": "workflow-planner-preview" },
      preview.previewFingerprint,
    ),
}));

const compareMock = vi.mocked(compareWorkflowPlanVersions);
const cloneMock = vi.mocked(cloneWorkflowPlan);
const copyScopeMock = vi.mocked(copyMonitoringScopeTemplate);
const getPlanMock = vi.mocked(getWorkflowPlan);
const listScopesMock = vi.mocked(listMonitoringScopes);
const listPlansMock = vi.mocked(listWorkflowPlans);
const listVersionsMock = vi.mocked(listWorkflowPlanVersions);

vi.stubGlobal("React", React);
(
  globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }
).IS_REACT_ACT_ENVIRONMENT = true;

const readBoundary = {
  databaseWrite: false,
  planChanged: false,
  providerCall: false,
  actorRun: false,
  browserRun: false,
  llmCall: false,
  workflowRunCreated: false,
  executionAuthorized: false,
} as const;

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
};

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function makePlan(
  projectId = "project-a",
  planId = "plan-a",
  versionNumber = 3,
  name = "Competitor monitoring",
): WorkflowPlan {
  return {
    id: planId,
    workspaceId: "workspace-a",
    projectId,
    createdByUserId: "user-creator",
    name,
    flowMode: "batch_research",
    status: "previewed",
    currentVersionId: `version-${versionNumber}`,
    currentVersionNumber: versionNumber,
    planningStatus: "resolved",
    scopeCount: 2,
    queryTermCount: 5,
    createdAt: "2026-07-13T00:00:00.000Z",
    updatedAt: "2026-07-13T01:00:00.000Z",
  };
}

function makeSummary(
  versionNumber: number,
  projectId = "project-a",
  planId = "plan-a",
): WorkflowVersionSummary {
  return {
    id: `version-${versionNumber}`,
    workspaceId: "workspace-a",
    projectId,
    workflowPlanId: planId,
    createdByUserId: "user-creator",
    versionNumber,
    planningStatus: "resolved",
    plannerContractVersion: "workflow_planner.v1",
    catalogSnapshotId: "catalog-a",
    policyVersion: "policy-a",
    modeTemplateVersion: "template-a",
    queryVersions: { reddit: "query-a" },
    previewFingerprint: `sha256:version-${versionNumber}`,
    createdAt: `2026-07-13T0${Math.min(versionNumber, 9)}:00:00.000Z`,
  };
}

function makeVersion(
  versionNumber: number,
  projectId = "project-a",
  planId = "plan-a",
): WorkflowVersion {
  return {
    ...makeSummary(versionNumber, projectId, planId),
    editableInput: {
      flowMode: "batch_research",
    } as PlanningInput,
    preview: {
      previewFingerprint: `sha256:version-${versionNumber}`,
    } as WorkflowPlanPreview,
  };
}

function makePlanList(
  projectId: string,
  plans: WorkflowPlan[],
  options: { total?: number; limit?: number; offset?: number } = {},
): WorkflowPlanListResult {
  return {
    ...readBoundary,
    projectStatus: "active",
    items: plans,
    total: options.total ?? plans.length,
    limit: options.limit ?? 20,
    offset: options.offset ?? 0,
  };
}

function makeDetail(
  projectStatus: "active" | "archived" = "active",
  versionNumber = 3,
  projectId = "project-a",
  planId = "plan-a",
  name = "Competitor monitoring",
): WorkflowPlanDetail {
  const plan = makePlan(projectId, planId, versionNumber, name);
  return {
    ...readBoundary,
    projectStatus,
    plan,
    currentVersion: makeVersion(plan.currentVersionNumber, projectId, planId),
  };
}

function makeVersionList(
  versions: WorkflowVersionSummary[],
  projectStatus: "active" | "archived" = "active",
  options: { total?: number; limit?: number; offset?: number } = {},
): WorkflowVersionListResult {
  return {
    ...readBoundary,
    projectStatus,
    items: versions,
    total: options.total ?? versions.length,
    limit: options.limit ?? 50,
    offset: options.offset ?? 0,
  };
}

function makeScopeList(
  projectStatus: "active" | "archived" = "active",
  items: MonitoringScope[] = [],
): MonitoringScopeListResult {
  return {
    ...readBoundary,
    projectStatus,
    items,
    total: items.length,
    limit: 100,
    offset: 0,
  };
}

function makeScope(overrides: Partial<MonitoringScope> = {}): MonitoringScope {
  return {
    id: "scope-a",
    workspaceId: "workspace-a",
    projectId: "project-a",
    createdByUserId: "user-creator",
    scopeKey: "scope-key-a",
    scopeType: "brand",
    canonicalTerm: "Example",
    aliases: [],
    includeTerms: [],
    excludeTerms: [],
    officialAccounts: [],
    seedUrls: [],
    effectiveLanguages: ["en"],
    effectiveRegions: ["US"],
    effectivePlatforms: ["reddit"],
    matchMode: "exact",
    createdAt: "2026-07-13T00:00:00.000Z",
    ...overrides,
  };
}

function makeCompare(
  baseVersion: WorkflowVersionSummary,
  targetVersion: WorkflowVersionSummary,
  options: Partial<WorkflowPlanVersionCompare> = {},
): WorkflowPlanVersionCompare {
  return {
    ...readBoundary,
    projectStatus: "active",
    plan: makePlan(),
    baseVersion,
    targetVersion,
    sameVersion: baseVersion.id === targetVersion.id,
    sections: [],
    ...options,
  };
}

function renderNode(node: React.ReactNode): {
  container: HTMLDivElement;
  root: Root;
} {
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  act(() => root.render(node));
  return { container, root };
}

async function flushEffects(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

beforeEach(() => {
  projectSelection.current = {
    loading: false,
    projectListError: null,
    selectedProject: {
      id: "project-a",
      name: "Project A",
      status: "active",
    },
  };
  projectSelection.clear.mockReset();
  projectSelection.mark.mockReset();
  compareMock.mockReset();
  cloneMock.mockReset();
  copyScopeMock.mockReset();
  getPlanMock.mockReset();
  listScopesMock.mockReset();
  listScopesMock.mockResolvedValue(makeScopeList());
  listPlansMock.mockReset();
  listVersionsMock.mockReset();
});

afterEach(() => {
  document.body.replaceChildren();
});

describe("saved WorkflowPlan assets", () => {
  it("renders Project-scoped summary facts and an explicit detail link", async () => {
    const plan = makePlan();
    listPlansMock.mockResolvedValueOnce(makePlanList("project-a", [plan]));
    const { container, root } = renderNode(
      createElement(SavedWorkflowPlansWorkspace),
    );

    await flushEffects();

    expect(container.textContent).toContain(plan.name);
    expect(container.textContent).toContain("规划状态");
    expect(container.textContent).toContain("v3");
    expect(container.textContent).toContain("Scope");
    expect(container.textContent).toContain("QueryTerm");
    expect(container.textContent).toContain(plan.updatedAt);
    expect(container.textContent).toContain("创建者 ID");
    expect(container.textContent).toContain("user-creator");
    expect(
      container.querySelector(
        `a[href="/automation/projects/project-a/plans/plan-a"]`,
      ),
    ).not.toBeNull();
    expect(projectSelection.mark).toHaveBeenCalledWith("project-a");
    const actionText = Array.from(
      container.querySelectorAll("button, a"),
      (element) => element.textContent ?? "",
    ).join(" ");
    expect(actionText).not.toMatch(
      /\b(?:Activate|Run|Schedule|Provider)\b|激活|运行|调度|供应商/i,
    );

    act(() => root.unmount());
  });

  it("renders honest loading and empty states for the selected Project", async () => {
    const request = deferred<WorkflowPlanListResult>();
    listPlansMock.mockReturnValueOnce(request.promise);
    const { container, root } = renderNode(
      createElement(SavedWorkflowPlansWorkspace),
    );

    expect(container.textContent).toContain("正在加载已保存计划");
    expect(projectSelection.mark).not.toHaveBeenCalled();

    request.resolve(makePlanList("project-a", []));
    await flushEffects();

    expect(container.textContent).toContain("当前项目还没有已保存计划");
    expect(projectSelection.mark).toHaveBeenCalledWith("project-a");

    act(() => root.unmount());
  });

  it("ignores a late Project A response after switching to Project B", async () => {
    const projectA = deferred<WorkflowPlanListResult>();
    const projectB = deferred<WorkflowPlanListResult>();
    listPlansMock
      .mockReturnValueOnce(projectA.promise)
      .mockReturnValueOnce(projectB.promise);
    const rendered = renderNode(createElement(SavedWorkflowPlansWorkspace));
    await flushEffects();

    projectSelection.current = {
      loading: false,
      projectListError: null,
      selectedProject: {
        id: "project-b",
        name: "Project B",
        status: "active",
      },
    };
    act(() => rendered.root.render(createElement(SavedWorkflowPlansWorkspace)));
    await flushEffects();
    projectB.resolve(
      makePlanList("project-b", [makePlan("project-b", "plan-b", 1, "Plan B")]),
    );
    await flushEffects();
    projectA.resolve(makePlanList("project-a", [makePlan()]));
    await flushEffects();

    expect(rendered.container.textContent).toContain("Plan B");
    expect(rendered.container.textContent).not.toContain(
      "Competitor monitoring",
    );
    expect(projectSelection.mark).toHaveBeenCalledWith("project-b");
    expect(projectSelection.mark).not.toHaveBeenCalledWith("project-a");

    act(() => rendered.root.unmount());
  });

  it("ignores a late Project A rejection after switching to Project B", async () => {
    const projectA = deferred<WorkflowPlanListResult>();
    listPlansMock
      .mockReturnValueOnce(projectA.promise)
      .mockResolvedValueOnce(
        makePlanList("project-b", [
          makePlan("project-b", "plan-b", 1, "Plan B"),
        ]),
      );
    const rendered = renderNode(createElement(SavedWorkflowPlansWorkspace));
    await flushEffects();

    projectSelection.current = {
      loading: false,
      projectListError: null,
      selectedProject: {
        id: "project-b",
        name: "Project B",
        status: "active",
      },
    };
    act(() => rendered.root.render(createElement(SavedWorkflowPlansWorkspace)));
    await flushEffects();
    projectA.reject(new Error("stale Project A failure"));
    await flushEffects();

    expect(rendered.container.textContent).toContain("Plan B");
    expect(rendered.container.textContent).not.toContain(
      "stale Project A failure",
    );
    expect(projectSelection.mark).toHaveBeenCalledWith("project-b");
    expect(projectSelection.mark).not.toHaveBeenCalledWith("project-a");

    act(() => rendered.root.unmount());
  });

  it("does not request without a Project and exposes error retry plus backend pagination", async () => {
    projectSelection.current = {
      loading: false,
      projectListError: null,
      selectedProject: null,
    };
    const rendered = renderNode(createElement(SavedWorkflowPlansWorkspace));
    await flushEffects();
    expect(rendered.container.textContent).toContain("请先在顶部选择");
    expect(listPlansMock).not.toHaveBeenCalled();

    projectSelection.current = {
      loading: false,
      projectListError: null,
      selectedProject: {
        id: "project-a",
        name: "Project A",
        status: "active",
      },
    };
    listPlansMock
      .mockRejectedValueOnce(new Error("list unavailable"))
      .mockResolvedValueOnce(
        makePlanList("project-a", [makePlan()], { total: 21 }),
      )
      .mockResolvedValueOnce(
        makePlanList(
          "project-a",
          [makePlan("project-a", "plan-last", 1, "Last plan")],
          { total: 21, offset: 20 },
        ),
      );
    act(() => rendered.root.render(createElement(SavedWorkflowPlansWorkspace)));
    await flushEffects();
    expect(rendered.container.textContent).toContain("list unavailable");

    const retry = Array.from(
      rendered.container.querySelectorAll("button"),
    ).find((button) => button.textContent === "重新加载");
    expect(retry).toBeDefined();
    act(() => retry!.click());
    await flushEffects();
    const next = Array.from(rendered.container.querySelectorAll("button")).find(
      (button) => button.textContent === "下一页",
    );
    expect(next).toBeDefined();
    act(() => next!.click());
    await flushEffects();

    expect(listPlansMock).toHaveBeenLastCalledWith(
      "project-a",
      expect.objectContaining({ limit: 20, offset: 20 }),
    );
    expect(rendered.container.textContent).toContain("Last plan");

    act(() => rendered.root.unmount());
  });

  it("fails closed when a list item belongs to another Project", async () => {
    listPlansMock.mockResolvedValueOnce(
      makePlanList("project-a", [makePlan("project-b")]),
    );
    const { container, root } = renderNode(
      createElement(SavedWorkflowPlansWorkspace),
    );
    await flushEffects();

    expect(container.textContent).toContain(
      "WorkflowPlan list response context mismatch",
    );
    expect(projectSelection.mark).not.toHaveBeenCalled();

    act(() => root.unmount());
  });

  it("fails closed when list pagination facts claim hidden rows on an empty page", async () => {
    listPlansMock.mockResolvedValueOnce(
      makePlanList("project-a", [], { total: 1 }),
    );
    const { container, root } = renderNode(
      createElement(SavedWorkflowPlansWorkspace),
    );
    await flushEffects();

    expect(container.textContent).toContain(
      "WorkflowPlan list response context mismatch",
    );
    expect(container.textContent).not.toContain("当前项目还没有已保存计划");
    expect(projectSelection.mark).not.toHaveBeenCalled();

    act(() => root.unmount());
  });

  it("loads current Preview and history in parallel and defaults to adjacent Compare", async () => {
    const detail = makeDetail();
    const versions = [makeSummary(3), makeSummary(2), makeSummary(1)];
    getPlanMock.mockResolvedValueOnce(detail);
    listVersionsMock.mockResolvedValueOnce(makeVersionList(versions));
    compareMock.mockResolvedValueOnce(makeCompare(versions[1]!, versions[0]!));
    const { container, root } = renderNode(
      createElement(WorkflowPlanDetailWorkspace, {
        projectId: "project-a",
        planId: "plan-a",
      }),
    );

    expect(getPlanMock).toHaveBeenCalledTimes(1);
    expect(listVersionsMock).toHaveBeenCalledTimes(1);
    await flushEffects();

    expect(
      container.querySelector('[data-testid="workflow-planner-preview"]')
        ?.textContent,
    ).toBe("sha256:version-3");
    expect(container.textContent).toContain("Version History");
    expect(container.textContent).toContain("创建时间");
    expect(container.textContent).toContain("创建者 ID");
    expect(container.textContent).toContain("Planner Contract");
    expect(container.textContent).toContain("Catalog Snapshot");
    expect(container.textContent?.indexOf("v3")).toBeLessThan(
      container.textContent?.indexOf("v2") ?? Number.MAX_SAFE_INTEGER,
    );
    expect(
      container
        .querySelector('a[href*="source_version_id=version-1"]')
        ?.getAttribute("href"),
    ).toBe(
      "/automation/planner?mode=batch_research&project_id=project-a&plan_id=plan-a&source_version_id=version-1",
    );
    expect(compareMock).toHaveBeenCalledWith(
      "project-a",
      "plan-a",
      "version-2",
      "version-3",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );

    act(() => root.unmount());
  });

  it("loads later Scope pages before filtering the current Version", async () => {
    const detail = makeDetail();
    const versions = [makeSummary(3), makeSummary(2)];
    detail.currentVersion.preview = {
      ...detail.currentVersion.preview,
      normalizedInput: {
        scopes: [{ scopeKey: "scope-key-old" }],
      },
    } as WorkflowPlanPreview;
    const firstPage = Array.from({ length: 100 }, (_, index) =>
      makeScope({
        id: `scope-new-${index}`,
        scopeKey: `scope-key-new-${index}`,
      }),
    );
    const oldScope = makeScope({ id: "scope-old", scopeKey: "scope-key-old" });
    getPlanMock.mockResolvedValueOnce(detail);
    listVersionsMock.mockResolvedValueOnce(makeVersionList(versions));
    listScopesMock
      .mockResolvedValueOnce({
        ...makeScopeList("active", firstPage),
        total: 101,
      })
      .mockResolvedValueOnce({
        ...makeScopeList("active", [oldScope]),
        total: 101,
        offset: 100,
      });
    compareMock.mockResolvedValueOnce(makeCompare(versions[1]!, versions[0]!));

    const { container, root } = renderNode(
      createElement(WorkflowPlanDetailWorkspace, {
        projectId: "project-a",
        planId: "plan-a",
      }),
    );
    await flushEffects();

    expect(listScopesMock).toHaveBeenNthCalledWith(
      2,
      "project-a",
      expect.objectContaining({ limit: 100, offset: 100 }),
    );
    expect(container.textContent).toContain("scope-key-old");
    expect(
      container.querySelector('[data-testid="workflow-scope-template-copy-panel"]'),
    ).not.toBeNull();

    act(() => root.unmount());
  });

  it("fails closed when detail objects cross a Workspace boundary", async () => {
    const detail = makeDetail();
    const versions = [makeSummary(3), makeSummary(2)];
    detail.currentVersion = {
      ...detail.currentVersion,
      workspaceId: "workspace-b",
    };
    getPlanMock.mockResolvedValueOnce(detail);
    listVersionsMock.mockResolvedValueOnce(makeVersionList(versions));
    compareMock.mockResolvedValueOnce(makeCompare(versions[1]!, versions[0]!));
    const { container, root } = renderNode(
      createElement(WorkflowPlanDetailWorkspace, {
        projectId: "project-a",
        planId: "plan-a",
      }),
    );

    await flushEffects();

    expect(container.textContent).toContain(
      "WorkflowPlan detail response context mismatch",
    );
    expect(compareMock).not.toHaveBeenCalled();

    act(() => root.unmount());
  });

  it("fails closed when Version history crosses a Workspace boundary", async () => {
    const versions = [
      { ...makeSummary(3), workspaceId: "workspace-b" },
      makeSummary(2),
    ];
    getPlanMock.mockResolvedValueOnce(makeDetail());
    listVersionsMock.mockResolvedValueOnce(makeVersionList(versions));
    compareMock.mockResolvedValueOnce(makeCompare(versions[1]!, versions[0]!));
    const { container, root } = renderNode(
      createElement(WorkflowPlanDetailWorkspace, {
        projectId: "project-a",
        planId: "plan-a",
      }),
    );

    await flushEffects();

    expect(container.textContent).toContain(
      "WorkflowVersion history context mismatch",
    );
    expect(compareMock).not.toHaveBeenCalled();

    act(() => root.unmount());
  });

  it("fails closed when detail and Version history disagree on the current snapshot", async () => {
    getPlanMock.mockResolvedValueOnce(makeDetail());
    listVersionsMock.mockResolvedValueOnce(
      makeVersionList([makeSummary(2), makeSummary(1)]),
    );
    const { container, root } = renderNode(
      createElement(WorkflowPlanDetailWorkspace, {
        projectId: "project-a",
        planId: "plan-a",
      }),
    );

    await flushEffects();

    expect(container.textContent).toContain(
      "WorkflowPlan current Version history mismatch",
    );
    expect(compareMock).not.toHaveBeenCalled();

    act(() => root.unmount());
  });

  it("renders a generic not-found fact without leaking backend tenant detail", async () => {
    getPlanMock.mockRejectedValueOnce(
      new ApiRequestError(404, "secret tenant lookup detail"),
    );
    listVersionsMock.mockResolvedValueOnce(
      makeVersionList([makeSummary(3), makeSummary(2)]),
    );
    const { container, root } = renderNode(
      createElement(WorkflowPlanDetailWorkspace, {
        projectId: "project-a",
        planId: "missing-plan",
      }),
    );

    await flushEffects();

    expect(container.textContent).toContain("资源不存在或无权访问");
    expect(container.textContent).not.toContain("secret tenant lookup detail");
    expect(compareMock).not.toHaveBeenCalled();
    expect(getPlanMock).toHaveBeenCalledWith(
      "project-a",
      "missing-plan",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(listVersionsMock).toHaveBeenCalledWith(
      "project-a",
      "missing-plan",
      expect.objectContaining({ limit: 50, offset: 0 }),
    );

    act(() => root.unmount());
  });

  it("keeps archived Project detail readable and labels Planner links read-only", async () => {
    const versions = [makeSummary(3), makeSummary(2)];
    getPlanMock.mockResolvedValueOnce(makeDetail("archived"));
    listVersionsMock.mockResolvedValueOnce(
      makeVersionList(versions, "archived"),
    );
    listScopesMock.mockResolvedValueOnce(makeScopeList("archived"));
    compareMock.mockResolvedValueOnce(
      makeCompare(versions[1]!, versions[0]!, { projectStatus: "archived" }),
    );
    const { container, root } = renderNode(
      createElement(WorkflowPlanDetailWorkspace, {
        projectId: "project-a",
        planId: "plan-a",
      }),
    );

    await flushEffects();

    expect(container.textContent).toContain("Archived Project");
    expect(container.textContent).toContain("只读");
    expect(container.textContent).not.toMatch(/激活|运行/);

    act(() => root.unmount());
  });

  it("exposes Plan clone as a separate action from the historical Planner draft link", async () => {
    const detail = makeDetail("active");
    const versions = [makeSummary(3), makeSummary(2)];
    const clonePlan = {
      ...detail.plan,
      id: "plan-clone",
      name: "Competitor monitoring copy",
      sourcePlanId: detail.plan.id,
      sourceVersionId: detail.plan.currentVersionId,
      currentVersionId: "version-clone",
      currentVersionNumber: 1,
    };
    cloneMock.mockResolvedValueOnce({
      ...readBoundary,
      databaseWrite: true,
      planChanged: true,
      outcome: "created",
      idempotentReplay: false,
      sourcePlanId: detail.plan.id,
      sourceVersionId: detail.plan.currentVersionId,
      plan: clonePlan,
      version: {
        ...detail.currentVersion,
        id: "version-clone",
        workflowPlanId: "plan-clone",
        versionNumber: 1,
      },
    });
    getPlanMock.mockResolvedValueOnce(detail);
    listVersionsMock.mockResolvedValueOnce(makeVersionList(versions));
    compareMock.mockResolvedValue(makeCompare(versions[1]!, versions[0]!));

    const { container, root } = renderNode(
      createElement(WorkflowPlanDetailWorkspace, {
        projectId: "project-a",
        planId: "plan-a",
      }),
    );
    await flushEffects();

    const cloneButton = container.querySelector<HTMLButtonElement>(
      '[data-testid="workflow-plan-clone"]',
    );
    expect(cloneButton).not.toBeNull();
    act(() => cloneButton!.click());
    await flushEffects();

    expect(cloneMock).toHaveBeenCalledWith(
      "project-a",
      "plan-a",
      expect.objectContaining({
        name: "Competitor monitoring copy",
        sourceVersionId: "version-3",
        idempotencyKey: expect.any(String),
      }),
    );
    expect(container.textContent).toContain("已创建独立 Plan/v1");
    expect(
      container.querySelector(
        'a[href="/automation/projects/project-a/plans/plan-clone"]',
      ),
    ).not.toBeNull();
    expect(container.textContent).toContain("从 v3 在 Planner 中继续");

    act(() => root.unmount());
  });

  it("reuses clone and Scope-copy idempotency keys after an uncertain failure", async () => {
    const scope = makeScope();
    const detail = makeDetail("active");
    detail.currentVersion.preview = {
      ...detail.currentVersion.preview,
      normalizedInput: { scopes: [{ scopeKey: scope.scopeKey }] },
    } as WorkflowPlanPreview;
    const versions = [makeSummary(3), makeSummary(2)];
    const cloneResult = {
      ...readBoundary,
      databaseWrite: false,
      planChanged: false,
      outcome: "created" as const,
      idempotentReplay: true,
      sourcePlanId: detail.plan.id,
      sourceVersionId: detail.plan.currentVersionId,
      plan: {
        ...detail.plan,
        id: "plan-clone-retry",
        currentVersionId: "version-clone-retry",
        currentVersionNumber: 1,
      },
      version: {
        ...detail.currentVersion,
        id: "version-clone-retry",
        workflowPlanId: "plan-clone-retry",
        versionNumber: 1,
      },
    };
    const copyResult = {
      ...readBoundary,
      databaseWrite: false,
      idempotentReplay: true,
      template: {
        ...readBoundary,
        id: "scope-template-a",
        workspaceId: scope.workspaceId,
        projectId: scope.projectId,
        createdByUserId: scope.createdByUserId,
        sourceScopeId: scope.id,
        sourcePlanId: detail.plan.id,
        sourceVersionId: detail.plan.currentVersionId,
        scopeKey: scope.scopeKey,
        scopeType: scope.scopeType,
        canonicalTerm: scope.canonicalTerm,
        aliases: scope.aliases,
        includeTerms: scope.includeTerms,
        excludeTerms: scope.excludeTerms,
        officialAccounts: scope.officialAccounts,
        seedUrls: scope.seedUrls,
        effectiveLanguages: scope.effectiveLanguages,
        effectiveRegions: scope.effectiveRegions,
        effectivePlatforms: scope.effectivePlatforms,
        matchMode: scope.matchMode,
        createdAt: scope.createdAt,
      },
    };
    cloneMock
      .mockRejectedValueOnce(new Error("response_lost"))
      .mockResolvedValueOnce(cloneResult);
    copyScopeMock
      .mockRejectedValueOnce(new Error("response_lost"))
      .mockResolvedValueOnce(copyResult);
    getPlanMock.mockResolvedValueOnce(detail);
    listVersionsMock.mockResolvedValueOnce(makeVersionList(versions));
    listScopesMock.mockResolvedValueOnce(makeScopeList("active", [scope]));
    compareMock.mockResolvedValue(makeCompare(versions[1]!, versions[0]!));

    const { container, root } = renderNode(
      createElement(WorkflowPlanDetailWorkspace, {
        projectId: "project-a",
        planId: "plan-a",
      }),
    );
    await flushEffects();

    const cloneButton = container.querySelector<HTMLButtonElement>(
      '[data-testid="workflow-plan-clone"]',
    )!;
    act(() => cloneButton.click());
    await flushEffects();
    act(() => cloneButton.click());
    await flushEffects();

    const cloneKeys = cloneMock.mock.calls.map(
      ([, , input]) => input.idempotencyKey,
    );
    expect(cloneKeys).toHaveLength(2);
    expect(new Set(cloneKeys).size).toBe(1);

    const copyButton = [...container.querySelectorAll("button")].find(
      (button) => button.textContent === "复制 Scope 模板",
    )!;
    act(() => copyButton.click());
    await flushEffects();
    act(() => copyButton.click());
    await flushEffects();

    const copyKeys = copyScopeMock.mock.calls.map(
      ([, , input]) => input.idempotencyKey,
    );
    expect(copyKeys).toHaveLength(2);
    expect(new Set(copyKeys).size).toBe(1);

    act(() => root.unmount());
  });

  it("renders nested server Compare facts structurally without raw JSON", async () => {
    const versions = [makeSummary(3), makeSummary(2)];
    getPlanMock.mockResolvedValueOnce(makeDetail());
    listVersionsMock.mockResolvedValueOnce(makeVersionList(versions));
    compareMock.mockResolvedValueOnce(
      makeCompare(versions[1]!, versions[0]!, {
        sections: [
          {
            key: "unknown_section",
            changes: [
              {
                field: "nested_fact",
                before: { policy: { regions: ["US", "GB"] } },
                after: { policy: { regions: ["JP"], enabled: true } },
              },
            ],
          },
        ],
      }),
    );
    const { container, root } = renderNode(
      createElement(WorkflowPlanDetailWorkspace, {
        projectId: "project-a",
        planId: "plan-a",
      }),
    );

    await flushEffects();

    const compareRegion = container.querySelector(
      '[data-testid="workflow-plan-version-compare"]',
    );
    expect(compareRegion?.textContent).toContain("unknown_section");
    expect(compareRegion?.textContent).toContain("nested_fact");
    expect(compareRegion?.textContent).toContain("regions");
    expect(compareRegion?.textContent).toContain("JP");
    expect(compareRegion?.querySelector("pre")).toBeNull();
    expect(compareRegion?.textContent).not.toContain('[{"');
    expect(compareRegion?.textContent).not.toContain("[object Object]");

    act(() => root.unmount());
  });

  it("loads more than 100 Versions cumulatively and preserves an arbitrary directional Compare", async () => {
    const versions = Array.from({ length: 101 }, (_, index) =>
      makeSummary(101 - index),
    );
    const versionById = new Map(
      versions.map((version) => [version.id, version]),
    );
    getPlanMock.mockResolvedValueOnce(makeDetail("active", 101));
    listVersionsMock
      .mockResolvedValueOnce(
        makeVersionList(versions.slice(0, 50), "active", {
          total: 101,
          limit: 50,
          offset: 0,
        }),
      )
      .mockResolvedValueOnce(
        makeVersionList(versions.slice(50, 100), "active", {
          total: 101,
          limit: 50,
          offset: 50,
        }),
      )
      .mockResolvedValueOnce(
        makeVersionList(versions.slice(100), "active", {
          total: 101,
          limit: 50,
          offset: 100,
        }),
      );
    compareMock.mockImplementation(
      async (_projectId, _planId, baseId, targetId) =>
        makeCompare(versionById.get(baseId)!, versionById.get(targetId)!, {
          plan: makePlan("project-a", "plan-a", 101),
        }),
    );
    const { container, root } = renderNode(
      createElement(WorkflowPlanDetailWorkspace, {
        projectId: "project-a",
        planId: "plan-a",
      }),
    );
    await flushEffects();

    expect(compareMock).toHaveBeenCalledWith(
      "project-a",
      "plan-a",
      "version-100",
      "version-101",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(listVersionsMock).toHaveBeenNthCalledWith(
      1,
      "project-a",
      "plan-a",
      expect.objectContaining({ limit: 50, offset: 0 }),
    );
    for (let page = 0; page < 2; page += 1) {
      const loadMore = Array.from(container.querySelectorAll("button")).find(
        (button) => button.textContent === "加载更多 Version",
      );
      expect(loadMore).toBeDefined();
      act(() => loadMore!.click());
      await flushEffects();
      expect(listVersionsMock).toHaveBeenNthCalledWith(
        page + 2,
        "project-a",
        "plan-a",
        expect.objectContaining({ limit: 50, offset: (page + 1) * 50 }),
      );
    }

    const base = container.querySelector<HTMLSelectElement>(
      'select[aria-label="Base Version"]',
    );
    const target = container.querySelector<HTMLSelectElement>(
      'select[aria-label="Target Version"]',
    );
    expect(base).not.toBeNull();
    expect(target).not.toBeNull();
    expect(
      Array.from(base!.options).some((option) => option.value === "version-1"),
    ).toBe(true);
    expect(
      Array.from(target!.options).some(
        (option) => option.value === "version-101",
      ),
    ).toBe(true);
    expect(target!.value).toBe("version-101");
    act(() => {
      base!.value = "version-1";
      base!.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await flushEffects();

    expect(compareMock).toHaveBeenLastCalledWith(
      "project-a",
      "plan-a",
      "version-1",
      "version-101",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );

    act(() => {
      base!.value = "version-101";
      base!.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await flushEffects();
    act(() => {
      target!.value = "version-1";
      target!.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await flushEffects();

    expect(compareMock).toHaveBeenLastCalledWith(
      "project-a",
      "plan-a",
      "version-101",
      "version-1",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );

    act(() => root.unmount());
  });

  it.each(["resolve", "reject"] as const)(
    "ignores a late history %s after the detail context changes",
    async (outcome) => {
      const projectAVersions = [makeSummary(3), makeSummary(2)];
      const projectBVersions = [
        makeSummary(2, "project-b", "plan-b"),
        makeSummary(1, "project-b", "plan-b"),
      ];
      const latePage = deferred<WorkflowVersionListResult>();
      getPlanMock
        .mockResolvedValueOnce(makeDetail())
        .mockResolvedValueOnce(
          makeDetail("active", 2, "project-b", "plan-b", "Plan B"),
        );
      listVersionsMock
        .mockResolvedValueOnce(
          makeVersionList(projectAVersions, "active", { total: 3 }),
        )
        .mockReturnValueOnce(latePage.promise)
        .mockResolvedValueOnce(makeVersionList(projectBVersions));
      compareMock.mockImplementation(
        async (projectId, planId, baseVersionId, targetVersionId) => {
          const sourceVersions =
            projectId === "project-b" ? projectBVersions : projectAVersions;
          const byId = new Map(
            sourceVersions.map((version) => [version.id, version]),
          );
          return makeCompare(
            byId.get(baseVersionId)!,
            byId.get(targetVersionId)!,
            {
              plan:
                projectId === "project-b"
                  ? makePlan("project-b", planId, 2, "Plan B")
                  : makePlan(),
            },
          );
        },
      );
      const rendered = renderNode(
        createElement(WorkflowPlanDetailWorkspace, {
          projectId: "project-a",
          planId: "plan-a",
        }),
      );
      await flushEffects();

      const loadMore = Array.from(
        rendered.container.querySelectorAll("button"),
      ).find((button) => button.textContent === "加载更多 Version");
      expect(loadMore).toBeDefined();
      act(() => loadMore!.click());
      await flushEffects();
      act(() =>
        rendered.root.render(
          createElement(WorkflowPlanDetailWorkspace, {
            projectId: "project-b",
            planId: "plan-b",
          }),
        ),
      );
      await flushEffects();

      if (outcome === "resolve") {
        latePage.resolve(
          makeVersionList([makeSummary(1)], "active", {
            total: 3,
            offset: 2,
          }),
        );
      } else {
        latePage.reject(new Error("stale history failure"));
      }
      await flushEffects();

      expect(rendered.container.textContent).toContain("Plan B");
      expect(compareMock).toHaveBeenCalledTimes(2);
      expect(compareMock).toHaveBeenLastCalledWith(
        "project-b",
        "plan-b",
        "version-1",
        "version-2",
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      );
      expect(rendered.container.textContent).not.toContain(
        "Competitor monitoring",
      );
      expect(rendered.container.textContent).not.toContain(
        "stale history failure",
      );

      act(() => rendered.root.unmount());
    },
  );

  it("fails closed when Version history total drifts while loading more", async () => {
    const versions = [makeSummary(3), makeSummary(2), makeSummary(1)];
    getPlanMock.mockResolvedValueOnce(makeDetail());
    listVersionsMock
      .mockResolvedValueOnce(
        makeVersionList(versions.slice(0, 2), "active", { total: 3 }),
      )
      .mockResolvedValueOnce(
        makeVersionList(versions.slice(2), "active", {
          total: 4,
          offset: 2,
        }),
      );
    compareMock.mockResolvedValueOnce(makeCompare(versions[1]!, versions[0]!));
    const { container, root } = renderNode(
      createElement(WorkflowPlanDetailWorkspace, {
        projectId: "project-a",
        planId: "plan-a",
      }),
    );
    await flushEffects();

    const loadMore = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent === "加载更多 Version",
    );
    act(() => loadMore!.click());
    await flushEffects();

    expect(container.textContent).toContain(
      "WorkflowVersion history total changed during paging",
    );
    expect(container.textContent).toContain("已加载 2 / 3");

    act(() => root.unmount());
  });

  it("calls backend Compare for the same Version and renders its empty fact", async () => {
    const versions = [makeSummary(3), makeSummary(2)];
    const versionById = new Map(
      versions.map((version) => [version.id, version]),
    );
    getPlanMock.mockResolvedValueOnce(makeDetail());
    listVersionsMock.mockResolvedValueOnce(makeVersionList(versions));
    compareMock.mockImplementation(
      async (_projectId, _planId, baseId, targetId) =>
        makeCompare(versionById.get(baseId)!, versionById.get(targetId)!),
    );
    const { container, root } = renderNode(
      createElement(WorkflowPlanDetailWorkspace, {
        projectId: "project-a",
        planId: "plan-a",
      }),
    );
    await flushEffects();

    const base = container.querySelector<HTMLSelectElement>(
      'select[aria-label="Base Version"]',
    );
    expect(base).not.toBeNull();
    act(() => {
      base!.value = "version-3";
      base!.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await flushEffects();

    expect(compareMock).toHaveBeenLastCalledWith(
      "project-a",
      "plan-a",
      "version-3",
      "version-3",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(container.textContent).toContain("同一 Version");
    expect(container.textContent).toContain("无差异");

    act(() => root.unmount());
  });

  it("fails closed when same-Version Compare carries non-empty sections", async () => {
    const versions = [makeSummary(3), makeSummary(2)];
    getPlanMock.mockResolvedValueOnce(makeDetail());
    listVersionsMock.mockResolvedValueOnce(makeVersionList(versions));
    compareMock
      .mockResolvedValueOnce(makeCompare(versions[1]!, versions[0]!))
      .mockResolvedValueOnce(
        makeCompare(versions[0]!, versions[0]!, {
          sections: [
            {
              key: "contradictory",
              changes: [{ field: "should_not_exist", before: 1, after: 2 }],
            },
          ],
        }),
      );
    const { container, root } = renderNode(
      createElement(WorkflowPlanDetailWorkspace, {
        projectId: "project-a",
        planId: "plan-a",
      }),
    );
    await flushEffects();

    const base = container.querySelector<HTMLSelectElement>(
      'select[aria-label="Base Version"]',
    );
    act(() => {
      base!.value = "version-3";
      base!.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await flushEffects();

    expect(container.textContent).toContain(
      "WorkflowPlan Compare response context mismatch",
    );
    expect(container.textContent).not.toContain("同一 Version，无差异");

    act(() => root.unmount());
  });

  it("fails closed when Compare crosses a Workspace boundary", async () => {
    const versions = [makeSummary(3), makeSummary(2)];
    getPlanMock.mockResolvedValueOnce(makeDetail());
    listVersionsMock.mockResolvedValueOnce(makeVersionList(versions));
    compareMock.mockResolvedValueOnce(
      makeCompare(versions[1]!, versions[0]!, {
        baseVersion: { ...versions[1]!, workspaceId: "workspace-b" },
      }),
    );
    const { container, root } = renderNode(
      createElement(WorkflowPlanDetailWorkspace, {
        projectId: "project-a",
        planId: "plan-a",
      }),
    );
    await flushEffects();

    expect(container.textContent).toContain(
      "WorkflowPlan Compare response context mismatch",
    );
    expect(container.textContent).not.toContain("服务端未返回结构化差异");

    act(() => root.unmount());
  });

  it("ignores a late Compare response after the selected pair changes", async () => {
    const versions = [makeSummary(3), makeSummary(2), makeSummary(1)];
    const first = deferred<WorkflowPlanVersionCompare>();
    const second = deferred<WorkflowPlanVersionCompare>();
    getPlanMock.mockResolvedValueOnce(makeDetail());
    listVersionsMock.mockResolvedValueOnce(makeVersionList(versions));
    compareMock
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);
    const { container, root } = renderNode(
      createElement(WorkflowPlanDetailWorkspace, {
        projectId: "project-a",
        planId: "plan-a",
      }),
    );
    await flushEffects();

    const base = container.querySelector<HTMLSelectElement>(
      'select[aria-label="Base Version"]',
    );
    act(() => {
      base!.value = "version-1";
      base!.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await flushEffects();
    second.resolve(
      makeCompare(versions[2]!, versions[0]!, {
        sections: [
          {
            key: "new_pair",
            changes: [{ field: "new_selection", before: 1, after: 2 }],
          },
        ],
      }),
    );
    await flushEffects();
    first.resolve(
      makeCompare(versions[1]!, versions[0]!, {
        sections: [
          {
            key: "stale_pair",
            changes: [{ field: "stale_selection", before: 1, after: 2 }],
          },
        ],
      }),
    );
    await flushEffects();

    expect(container.textContent).toContain("new_selection");
    expect(container.textContent).not.toContain("stale_selection");

    act(() => root.unmount());
  });

  it("ignores a late Compare rejection after the selected pair changes", async () => {
    const versions = [makeSummary(3), makeSummary(2), makeSummary(1)];
    const first = deferred<WorkflowPlanVersionCompare>();
    getPlanMock.mockResolvedValueOnce(makeDetail());
    listVersionsMock.mockResolvedValueOnce(makeVersionList(versions));
    compareMock.mockReturnValueOnce(first.promise).mockResolvedValueOnce(
      makeCompare(versions[2]!, versions[0]!, {
        sections: [
          {
            key: "new_pair",
            changes: [{ field: "new_selection", before: 1, after: 2 }],
          },
        ],
      }),
    );
    const { container, root } = renderNode(
      createElement(WorkflowPlanDetailWorkspace, {
        projectId: "project-a",
        planId: "plan-a",
      }),
    );
    await flushEffects();

    const base = container.querySelector<HTMLSelectElement>(
      'select[aria-label="Base Version"]',
    );
    act(() => {
      base!.value = "version-1";
      base!.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await flushEffects();
    first.reject(new Error("stale Compare failure"));
    await flushEffects();

    expect(container.textContent).toContain("new_selection");
    expect(container.textContent).not.toContain("stale Compare failure");

    act(() => root.unmount());
  });

  it("does not call Compare when only one Version exists", async () => {
    const versions = [makeSummary(1)];
    getPlanMock.mockResolvedValueOnce(makeDetail("active", 1));
    listVersionsMock.mockResolvedValueOnce(makeVersionList(versions));
    const { container, root } = renderNode(
      createElement(WorkflowPlanDetailWorkspace, {
        projectId: "project-a",
        planId: "plan-a",
      }),
    );
    await flushEffects();

    expect(compareMock).not.toHaveBeenCalled();
    expect(container.textContent).toContain("至少需要 2 个 Version");

    act(() => root.unmount());
  });
});
