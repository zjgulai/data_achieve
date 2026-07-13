// @vitest-environment jsdom

import * as React from "react";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PlannerConstraintsStep } from "@/components/workflow-planner/planner-constraints-step";
import { PlannerScopeStep } from "@/components/workflow-planner/planner-scope-step";
import { WorkflowPlanAdvancedView } from "@/components/workflow-planner/workflow-plan-advanced-view";
import { WorkflowPlanPreview as WorkflowPlanPreviewPanel } from "@/components/workflow-planner/workflow-plan-preview";
import { WorkflowPlanSimpleView } from "@/components/workflow-planner/workflow-plan-simple-view";
import { WorkflowPlannerWorkspace } from "@/components/workflow-planner/workflow-planner-workspace";
import { useUnsavedWorkflowPlannerGuard } from "@/components/workflow-planner/use-unsaved-workflow-planner-guard";
import { ApiRequestError } from "@/lib/api/client";
import {
  createWorkflowPlan,
  createWorkflowVersion,
  getWorkflowPlan,
  getWorkflowVersion,
} from "@/lib/api/workflow-plan-persistence";
import {
  mapPlanningInputToDto,
  previewWorkflowPlan,
} from "@/lib/api/workflow-plans";
import { buildMockWorkflowPlanPreview } from "@/lib/workflow-planner-mock";
import {
  addScopeDraft,
  buildPlanningInput,
  createPreviewErrorState,
  createScopeDraft,
  createWorkflowPlannerDraft,
  invalidatePreviewRequest,
  isPreviewSnapshotCurrent,
  parseWorkflowPlannerRouteQuery,
  removeScopeDraft,
  parseWorkflowPlannerMode,
  shouldAcceptPreviewResponse,
  validatePlannerStep,
  workflowPlannerDraftFromEditableInput,
  workflowPlannerDraftSemanticKey,
  type PreviewRequestState,
  type PreviewSnapshot,
} from "@/lib/workflow-planner";
import type { CapabilityPlatform } from "@/types/capability";
import type { Project } from "@/types/project";
import type {
  WorkflowPlanDetail,
  WorkflowPlanSaveResult,
  WorkflowVersion,
  WorkflowVersionDetail,
} from "@/types/workflow-plan-persistence";
import type {
  PlanningInput,
  WorkflowPlanPreview,
} from "@/types/workflow-planner";

const projectSelectionMock = vi.hoisted(() => ({
  projects: [] as Project[],
  selectedProject: null as Project | null,
  loading: false,
  projectListError: null as string | null,
  markProjectFilterApplied: vi.fn(),
  clearProjectFilterApplied: vi.fn(),
  selectProject: vi.fn(),
}));

vi.mock("@/lib/api/workflow-plans", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/api/workflow-plans")>();
  return { ...actual, previewWorkflowPlan: vi.fn() };
});

vi.mock("@/lib/api/workflow-plan-persistence", async (importOriginal) => {
  const actual =
    await importOriginal<
      typeof import("@/lib/api/workflow-plan-persistence")
    >();
  return {
    ...actual,
    createWorkflowPlan: vi.fn(),
    createWorkflowVersion: vi.fn(),
    getWorkflowPlan: vi.fn(),
    getWorkflowVersion: vi.fn(),
  };
});

vi.mock("@/components/layout/project-selection-provider", () => ({
  useProjectSelection: () => ({
    projects: projectSelectionMock.projects,
    selectedProject: projectSelectionMock.selectedProject,
    selectedProjectId: projectSelectionMock.selectedProject?.id ?? null,
    loading: projectSelectionMock.loading,
    projectListError: projectSelectionMock.projectListError,
    preferenceError: null,
    filterApplied: false,
    selectProject: projectSelectionMock.selectProject,
    markProjectFilterApplied: projectSelectionMock.markProjectFilterApplied,
    clearProjectFilterApplied: projectSelectionMock.clearProjectFilterApplied,
  }),
}));

const previewWorkflowPlanMock = vi.mocked(previewWorkflowPlan);
const createWorkflowPlanMock = vi.mocked(createWorkflowPlan);
const createWorkflowVersionMock = vi.mocked(createWorkflowVersion);
const getWorkflowPlanMock = vi.mocked(getWorkflowPlan);
const getWorkflowVersionMock = vi.mocked(getWorkflowVersion);

vi.stubGlobal("React", React);
(
  globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }
).IS_REACT_ACT_ENVIRONMENT = true;

type Rendered = {
  container: HTMLDivElement;
  root: Root;
};

function activeProject(
  id = "project-a",
  name = "Active Planner Project",
): Project {
  return {
    id,
    name,
    description: null,
    domain: "social",
    status: "active",
    intelligenceCount: 0,
    sourceCount: 0,
  };
}

function renderNode(node: React.ReactNode): Rendered {
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  act(() => root.render(node));
  return { container, root };
}

function buttonByName(container: HTMLElement, name: string): HTMLButtonElement {
  const button = [...container.querySelectorAll("button")].find(
    (candidate) => candidate.textContent?.trim() === name,
  );
  if (!(button instanceof HTMLButtonElement)) {
    throw new Error(`Button not found: ${name}`);
  }
  return button;
}

function setInputValue(input: HTMLInputElement, value: string): void {
  const setter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype,
    "value",
  )?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function setSelectValue(select: HTMLSelectElement, value: string): void {
  const setter = Object.getOwnPropertyDescriptor(
    HTMLSelectElement.prototype,
    "value",
  )?.set;
  setter?.call(select, value);
  select.dispatchEvent(new Event("change", { bubbles: true }));
}

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((innerResolve, innerReject) => {
    resolve = innerResolve;
    reject = innerReject;
  });
  return { promise, resolve, reject };
}

function createInspectionSentinel() {
  let inspectionCount = 0;
  const error = Object.defineProperties(
    {},
    {
      name: {
        get() {
          inspectionCount += 1;
          return "StaleSentinelError";
        },
      },
      message: {
        get() {
          inspectionCount += 1;
          return "stale sentinel must not be inspected";
        },
      },
    },
  );
  return { error, inspectionCount: () => inspectionCount };
}

function validBatchInput(term = "running shoes") {
  const draft = createWorkflowPlannerDraft("batch_research");
  draft.scopes[0].canonicalTerm = term;
  draft.defaultPlatforms = ["reddit"];
  return buildPlanningInput(draft);
}

async function createMockPreview(
  projectId = "project-a",
  term = "running shoes",
  allowPartialDegradation = false,
): Promise<WorkflowPlanPreview> {
  const input = validBatchInput(term);
  input.allowPartialDegradation = allowPartialDegradation;
  return buildMockWorkflowPlanPreview(projectId, input);
}

function makeWorkflowVersion(
  id: string,
  versionNumber: number,
  editableInput: PlanningInput,
  preview: WorkflowPlanPreview,
  planId = "plan-a",
): WorkflowVersion {
  return {
    id,
    workspaceId: "workspace-a",
    projectId: "project-a",
    workflowPlanId: planId,
    createdByUserId: "user-a",
    versionNumber,
    planningStatus: preview.planningStatus,
    plannerContractVersion: preview.plannerContractVersion,
    catalogSnapshotId: preview.catalogSnapshotId,
    policyVersion: preview.policyVersion,
    modeTemplateVersion: preview.modeTemplateVersion,
    queryVersions: preview.queryVersions,
    previewFingerprint: preview.previewFingerprint,
    createdAt: `2026-07-13T00:00:0${versionNumber}Z`,
    editableInput,
    preview,
  };
}

function makePlanDetail(
  currentVersion: WorkflowVersion,
  name = "Saved planner",
): WorkflowPlanDetail {
  return {
    databaseWrite: false,
    planChanged: false,
    providerCall: false,
    actorRun: false,
    browserRun: false,
    llmCall: false,
    workflowRunCreated: false,
    executionAuthorized: false,
    projectStatus: "active",
    plan: {
      id: currentVersion.workflowPlanId,
      workspaceId: currentVersion.workspaceId,
      projectId: currentVersion.projectId,
      createdByUserId: currentVersion.createdByUserId,
      name,
      flowMode: currentVersion.editableInput.flowMode,
      status: "previewed",
      currentVersionId: currentVersion.id,
      currentVersionNumber: currentVersion.versionNumber,
      planningStatus: currentVersion.planningStatus,
      scopeCount: currentVersion.editableInput.scopes.length,
      queryTermCount: currentVersion.preview.queryTerms.length,
      createdAt: currentVersion.createdAt,
      updatedAt: currentVersion.createdAt,
    },
    currentVersion,
  };
}

function makeVersionDetail(
  planDetail: WorkflowPlanDetail,
  version: WorkflowVersion,
): WorkflowVersionDetail {
  return {
    databaseWrite: false,
    planChanged: false,
    providerCall: false,
    actorRun: false,
    browserRun: false,
    llmCall: false,
    workflowRunCreated: false,
    executionAuthorized: false,
    projectStatus: "active",
    plan: planDetail.plan,
    version,
  };
}

function makeSaveResult(
  planDetail: WorkflowPlanDetail,
  version: WorkflowVersion,
  outcome: WorkflowPlanSaveResult["outcome"] = "created",
  idempotentReplay = false,
): WorkflowPlanSaveResult {
  return {
    providerCall: false,
    actorRun: false,
    browserRun: false,
    llmCall: false,
    workflowRunCreated: false,
    executionAuthorized: false,
    databaseWrite: !idempotentReplay,
    planChanged: !idempotentReplay && outcome === "created",
    outcome,
    idempotentReplay,
    plan: {
      ...planDetail.plan,
      currentVersionId: version.id,
      currentVersionNumber: version.versionNumber,
      planningStatus: version.planningStatus,
    },
    version,
  };
}

function GuardHarness({ dirty }: { dirty: boolean }) {
  useUnsavedWorkflowPlannerGuard(dirty);
  return null;
}

function advanceBatchWorkspaceToPreview(container: HTMLElement): void {
  act(() => buttonByName(container, "下一步").click());
  const canonical = container.querySelector("#planner-scope-0-canonical-term");
  if (!(canonical instanceof HTMLInputElement)) {
    throw new Error("Canonical term input was not rendered");
  }
  act(() => setInputValue(canonical, "running shoes"));
  act(() => buttonByName(container, "下一步").click());
  const reddit = container.querySelector("#planner-platform-reddit");
  if (!(reddit instanceof HTMLInputElement)) {
    throw new Error("Reddit platform input was not rendered");
  }
  act(() => reddit.click());
  act(() => buttonByName(container, "下一步").click());
}

describe("workflow planner preview request state", () => {
  const preview = {
    previewFingerprint: "sha256:test",
  } as WorkflowPlanPreview;
  const snapshot: PreviewSnapshot = {
    projectId: "project-a",
    mode: "periodic_monitoring",
    formRevision: 3,
    previewInput: {
      ...validBatchInput("snapshot input"),
      flowMode: "periodic_monitoring",
      scheduleIntent: { cadence: "daily", timezone: "UTC" },
    },
    preview,
  };

  it("marks a successful Preview stale when semantic context changes", () => {
    expect(
      isPreviewSnapshotCurrent(snapshot, {
        projectId: "project-a",
        mode: "periodic_monitoring",
        formRevision: 3,
      }),
    ).toBe(true);
    expect(
      isPreviewSnapshotCurrent(snapshot, {
        projectId: "project-a",
        mode: "periodic_monitoring",
        formRevision: 4,
      }),
    ).toBe(false);
    expect(
      isPreviewSnapshotCurrent(snapshot, {
        projectId: "project-b",
        mode: "periodic_monitoring",
        formRevision: 3,
      }),
    ).toBe(false);
    expect(
      isPreviewSnapshotCurrent(snapshot, {
        projectId: "project-a",
        mode: "batch_research",
        formRevision: 3,
      }),
    ).toBe(false);
  });

  it("requires sequence, Project, mode, and revision to accept a settlement", () => {
    const accepted = {
      responseSequence: 7,
      currentSequence: 7,
      responseContext: {
        projectId: "project-a",
        mode: "periodic_monitoring" as const,
        formRevision: 3,
      },
      currentContext: {
        projectId: "project-a",
        mode: "periodic_monitoring" as const,
        formRevision: 3,
      },
    };
    expect(shouldAcceptPreviewResponse(accepted)).toBe(true);
    expect(
      shouldAcceptPreviewResponse({ ...accepted, currentSequence: 8 }),
    ).toBe(false);
    expect(
      shouldAcceptPreviewResponse({
        ...accepted,
        currentContext: { ...accepted.currentContext, projectId: "project-b" },
      }),
    ).toBe(false);
    expect(
      shouldAcceptPreviewResponse({
        ...accepted,
        currentContext: {
          ...accepted.currentContext,
          mode: "batch_research",
        },
      }),
    ).toBe(false);
    expect(
      shouldAcceptPreviewResponse({
        ...accepted,
        currentContext: { ...accepted.currentContext, formRevision: 4 },
      }),
    ).toBe(false);
  });

  it("ignores an older Preview response that resolves after the latest one", async () => {
    const first = createDeferred<WorkflowPlanPreview>();
    const second = createDeferred<WorkflowPlanPreview>();
    let currentSequence = 1;
    let currentFingerprint: string | null = null;

    const settle = async (
      sequence: number,
      pending: Promise<WorkflowPlanPreview>,
    ) => {
      const settledPreview = await pending;
      if (
        shouldAcceptPreviewResponse({
          responseSequence: sequence,
          currentSequence,
          responseContext: {
            projectId: "project-a",
            mode: "periodic_monitoring",
            formRevision: sequence,
          },
          currentContext: {
            projectId: "project-a",
            mode: "periodic_monitoring",
            formRevision: currentSequence,
          },
        })
      ) {
        currentFingerprint = settledPreview.previewFingerprint;
      }
    };

    const firstRequest = settle(1, first.promise);
    currentSequence = 2;
    const secondRequest = settle(2, second.promise);
    second.resolve({ previewFingerprint: "sha256:new" } as WorkflowPlanPreview);
    await secondRequest;
    first.resolve({ previewFingerprint: "sha256:old" } as WorkflowPlanPreview);
    await firstRequest;

    expect(currentFingerprint).toBe("sha256:new");
  });

  it("leaves loading immediately and preserves prior success as stale", () => {
    expect(
      invalidatePreviewRequest({ status: "loading", sequence: 7 }),
    ).toEqual({ status: "idle" });

    const success: PreviewRequestState = {
      status: "success",
      snapshot,
      stale: false,
    };
    expect(invalidatePreviewRequest(success)).toEqual({
      ...success,
      stale: true,
    });

    const loadingWithPrevious: PreviewRequestState = {
      status: "loading",
      sequence: 8,
      previous: snapshot,
    };
    expect(invalidatePreviewRequest(loadingWithPrevious)).toEqual({
      status: "success",
      snapshot,
      stale: true,
    });
  });

  it("creates retryable 503 state with requestId and non-retryable 422 fields", () => {
    expect(
      createPreviewErrorState(
        new ApiRequestError(503, "Planner unavailable", {
          requestId: "request-503",
        }),
      ),
    ).toMatchObject({
      status: "error",
      message: "Planner unavailable",
      requestId: "request-503",
      httpStatus: 503,
      retryable: true,
      fieldErrors: {},
    });

    expect(
      createPreviewErrorState(
        new ApiRequestError(422, "Invalid input", {
          validationIssues: [
            {
              loc: ["body", "scopes", 0, "canonical_term"],
              msg: "Field required",
            },
          ],
          requestId: "request-422",
        }),
      ),
    ).toMatchObject({
      status: "error",
      requestId: "request-422",
      httpStatus: 422,
      retryable: false,
      fieldErrors: {
        "planner-scope-0-canonical-term": "Field required",
      },
    });

    expect(
      createPreviewErrorState(
        new ApiRequestError(500, "Internal planner error", {
          requestId: "request-500",
        }),
      ),
    ).toMatchObject({
      status: "error",
      requestId: "request-500",
      httpStatus: 500,
      retryable: true,
    });

    expect(
      createPreviewErrorState(new Error("Network unavailable")),
    ).toMatchObject({
      status: "error",
      message: "Network unavailable",
      requestId: null,
      httpStatus: null,
      retryable: true,
    });
  });

  it("treats AbortError as a silent non-error settlement", () => {
    expect(
      createPreviewErrorState(new DOMException("Aborted", "AbortError")),
    ).toBeNull();
  });
});

describe("workflow plan response views", () => {
  it("uses one Preview object across accessible tabs and one fingerprint testid", async () => {
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "true");
    const preview = await createMockPreview(
      "00000000-0000-4000-8000-000000000033",
    );
    const { container, root } = renderNode(
      createElement(WorkflowPlanPreviewPanel, { preview, stale: false }),
    );

    expect(container.querySelectorAll('[role="tab"]')).toHaveLength(2);
    expect(
      container.querySelector('[role="tab"][aria-selected="true"]')
        ?.textContent,
    ).toContain("简单视图");
    expect(
      container.querySelectorAll(
        '[data-testid="workflow-planner-fingerprint"]',
      ),
    ).toHaveLength(1);
    const simpleFingerprint = container.querySelector(
      '[data-testid="workflow-planner-fingerprint"]',
    )?.textContent;

    act(() => buttonByName(container, "高级视图").click());
    expect(
      container.querySelector('[role="tab"][aria-selected="true"]')
        ?.textContent,
    ).toContain("高级视图");
    expect(
      container.querySelectorAll(
        '[data-testid="workflow-planner-fingerprint"]',
      ),
    ).toHaveLength(1);
    expect(
      container.querySelector('[data-testid="workflow-planner-fingerprint"]')
        ?.textContent,
    ).toBe(simpleFingerprint);
    expect(
      container.querySelector('[data-testid="workflow-planner-primary"]'),
    ).not.toBeNull();
    expect(
      container.querySelector('[data-testid="workflow-planner-fallback"]'),
    ).not.toBeNull();
    expect(
      container.querySelector('[data-testid="workflow-planner-shadow"]'),
    ).not.toBeNull();

    act(() => root.unmount());
  });

  it("supports Arrow/Home/End tab keyboard focus without duplicate panels", async () => {
    const preview = await createMockPreview();
    const { container, root } = renderNode(
      createElement(WorkflowPlanPreviewPanel, { preview, stale: false }),
    );
    const tabs = [...container.querySelectorAll('[role="tab"]')];
    const simpleTab = tabs[0];
    if (!(simpleTab instanceof HTMLButtonElement)) {
      throw new Error("Simple tab was not rendered");
    }

    act(() => {
      simpleTab.focus();
      simpleTab.dispatchEvent(
        new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }),
      );
    });
    expect(document.activeElement?.textContent).toContain("高级视图");
    const panels = container.querySelectorAll('[role="tabpanel"]');
    expect(panels).toHaveLength(2);
    expect(
      container.querySelectorAll('[role="tabpanel"]:not([hidden])'),
    ).toHaveLength(1);
    for (const tab of tabs) {
      const controls = tab.getAttribute("aria-controls");
      expect(controls).not.toBeNull();
      expect(container.querySelector(`#${controls}`)).not.toBeNull();
    }

    const advancedTab = document.activeElement;
    act(() =>
      advancedTab?.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Home", bubbles: true }),
      ),
    );
    expect(document.activeElement?.textContent).toContain("简单视图");

    act(() =>
      document.activeElement?.dispatchEvent(
        new KeyboardEvent("keydown", { key: "End", bubbles: true }),
      ),
    );
    expect(document.activeElement?.textContent).toContain("高级视图");

    act(() => root.unmount());
  });

  it("renders held as a normal Preview with no Primary testid", async () => {
    const preview = await createMockPreview();
    const { container, root } = renderNode(
      createElement(WorkflowPlanPreviewPanel, { preview, stale: false }),
    );

    expect(
      container.querySelector('[data-testid="workflow-planner-preview"]')
        ?.textContent,
    ).toContain("held");
    act(() => buttonByName(container, "高级视图").click());
    expect(
      container.querySelector('[data-testid="workflow-planner-primary"]'),
    ).toBeNull();
    expect(container.textContent).toContain("execution_authorized=false");
    const shadow = container.querySelector(
      '[data-testid="workflow-planner-shadow"]',
    );
    expect(shadow?.textContent).toContain("enabled=false");
    expect(shadow?.textContent).toContain(
      preview.routePlans[0]?.shadowRule.reason,
    );
    expect(shadow?.textContent).toContain("shadow_execution_authorized=false");

    act(() => root.unmount());
  });

  it("shows partial approval and never renders unknown cost as zero", async () => {
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "true");
    const preview = await createMockPreview(
      "00000000-0000-4000-8000-000000000032",
      "running shoes",
      true,
    );
    const unknownBudgetPreview = {
      ...preview,
      budgetSummary: {
        ...preview.budgetSummary,
        knownSelectedUnitCost: null,
        unknownCount: 1,
        budgetStatus: "unknown" as const,
      },
    };
    const { container, root } = renderNode(
      createElement(WorkflowPlanSimpleView, {
        preview: unknownBudgetPreview,
      }),
    );

    expect(container.textContent).toContain("仍需审批");
    expect(container.textContent).toContain("未知");
    expect(container.textContent).not.toMatch(/已知成本[^\n]*0(?:\.0+)?\s*USD/);

    act(() => root.unmount());
  });

  it("shows backend coverage counters and partial approval facts without aggregation", async () => {
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "true");
    const base = await createMockPreview(
      "00000000-0000-4000-8000-000000000032",
      "running shoes",
      true,
    );
    const firstRoute = base.routePlans[0];
    if (!firstRoute) {
      throw new Error("Partial fixture did not include a route plan");
    }
    const preview = {
      ...base,
      coverage: {
        totalRequirements: 9,
        resolvedRequirements: 2,
        partialRequirements: 3,
        heldRequirements: 4,
      },
      routePlans: [
        {
          ...firstRoute,
          approvalRequired: true,
          approvalReasons: [
            {
              code: "distinctive_approval_code",
              reason: "distinctive approval reason",
            },
          ],
          missingOptionalFields: ["distinctive_optional_field"],
        },
        ...base.routePlans.slice(1),
      ],
    };
    const { container, root } = renderNode(
      createElement(WorkflowPlanSimpleView, { preview }),
    );
    const text = container.textContent ?? "";

    for (const expected of [
      "total=9",
      "resolved=2",
      "partial=3",
      "held=4",
      "distinctive_approval_code",
      "distinctive approval reason",
      "distinctive_optional_field",
    ]) {
      expect(text).toContain(expected);
    }
    expect(text).not.toContain("5/9");

    act(() => root.unmount());
  });

  it("shows backend Scope/platform coverage and route reasons in the simple view", async () => {
    const base = await createMockPreview();
    const firstScope = base.normalizedInput.scopes[0];
    const firstRoute = base.routePlans[0];
    if (!firstScope || !firstRoute) {
      throw new Error("Held fixture did not include Scope and route facts");
    }
    const preview = {
      ...base,
      normalizedInput: {
        ...base.normalizedInput,
        scopes: [
          {
            ...firstScope,
            scopeKey: "scope-brand",
            scopeType: "brand" as const,
            canonicalTerm: "Acme",
            effectivePlatforms: [
              "reddit",
              "youtube",
            ] satisfies CapabilityPlatform[],
          },
          {
            ...firstScope,
            scopeKey: "scope-category",
            scopeType: "category" as const,
            canonicalTerm: "running shoes",
            effectivePlatforms: ["tiktok"] satisfies CapabilityPlatform[],
          },
        ],
      },
      routePlans: [
        {
          ...firstRoute,
          exclusionReasons: [
            {
              code: "distinctive_exclusion_code",
              reason: "distinctive exclusion reason",
            },
          ],
          limitations: ["distinctive route limitation"],
        },
        ...base.routePlans.slice(1),
      ],
    };
    const { container, root } = renderNode(
      createElement(WorkflowPlanSimpleView, { preview }),
    );
    const text = container.textContent ?? "";

    for (const expected of [
      "brand",
      "Acme",
      "reddit",
      "youtube",
      "category",
      "running shoes",
      "tiktok",
      "distinctive_exclusion_code",
      "distinctive exclusion reason",
      "distinctive route limitation",
    ]) {
      expect(text).toContain(expected);
    }

    act(() => root.unmount());
  });

  it("renders unclassified URLs only from input diagnostics", async () => {
    const base = await createMockPreview();
    const withoutDiagnostic = {
      ...base,
      normalizedInput: {
        ...base.normalizedInput,
        scopes: base.normalizedInput.scopes.map((scope, index) =>
          index === 0
            ? {
                ...scope,
                seedUrls: ["https://external.example/item"],
              }
            : scope,
        ),
      },
      decisionTrace: { ...base.decisionTrace, inputDiagnostics: [] },
    };
    const first = renderNode(
      createElement(WorkflowPlanSimpleView, { preview: withoutDiagnostic }),
    );
    expect(
      first.container.querySelector(
        '[data-testid="workflow-planner-unclassified-url"]',
      ),
    ).toBeNull();
    act(() => first.root.unmount());

    const withDiagnostic = {
      ...withoutDiagnostic,
      decisionTrace: {
        ...withoutDiagnostic.decisionTrace,
        inputDiagnostics: [
          {
            code: "seed_url_unclassified",
            reason: "Seed URL host is not classified",
            scopeKeys: [],
            requirementRef: null,
            details: { seed_url: "https://external.example/item" },
          },
        ],
      },
    };
    const second = renderNode(
      createElement(WorkflowPlanSimpleView, { preview: withDiagnostic }),
    );
    expect(
      second.container.querySelector(
        '[data-testid="workflow-planner-unclassified-url"]',
      )?.textContent,
    ).toContain("https://external.example/item");
    act(() => second.root.unmount());
  });

  it("advanced view consumes response facts without recomputing route scores", async () => {
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "true");
    const preview = await createMockPreview(
      "00000000-0000-4000-8000-000000000033",
    );
    const { container, root } = renderNode(
      createElement(WorkflowPlanAdvancedView, { preview }),
    );

    expect(container.textContent).toContain(preview.catalogSnapshotId);
    expect(container.textContent).toContain(preview.policyVersion);
    expect(container.textContent).toContain(preview.modeTemplateVersion);
    expect(container.textContent).toContain(
      String(preview.routePlans[0]?.scoreBreakdown?.weightedScore),
    );
    expect(container.querySelector(".overflow-x-auto")).not.toBeNull();
    expect(container.querySelector(".break-all")).not.toBeNull();

    act(() => root.unmount());
  });

  it("renders the complete backend score breakdown and all false boundaries verbatim", async () => {
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "true");
    const base = await createMockPreview(
      "00000000-0000-4000-8000-000000000033",
    );
    const firstRoute = base.routePlans[0];
    if (!firstRoute) {
      throw new Error("Resolved fixture did not include a route plan");
    }
    const preview = {
      ...base,
      routePlans: [
        {
          ...firstRoute,
          scoreBreakdown: {
            rawDimensions: { distinctive_raw: 1 },
            effectiveDimensions: { distinctive_effective: 2 },
            weights: { distinctive_weight: 17 },
            weightedScore: 12345,
            traceCodes: ["distinctive_trace_code"],
          },
        },
        ...base.routePlans.slice(1),
      ],
    };
    const { container, root } = renderNode(
      createElement(WorkflowPlanAdvancedView, { preview }),
    );
    const text = container.textContent ?? "";

    for (const expected of [
      "distinctive_raw",
      "distinctive_effective",
      "distinctive_weight",
      "12345",
      "distinctive_trace_code",
      "execution_authorized=false",
      "provider_call=false",
      "actor_run=false",
      "browser_run=false",
      "llm_call=false",
      "workflow_run_created=false",
      "database_write=false",
      "route_execution_authorized=false",
      "shadow_execution_authorized=false",
    ]) {
      expect(text).toContain(expected);
    }

    act(() => root.unmount());
  });

  it("keeps machine codes and backend-readable reasons together in advanced view", async () => {
    const base = await createMockPreview();
    const firstRequirement = base.routeRequirements[0];
    const firstRoute = base.routePlans[0];
    if (!firstRequirement || !firstRoute) {
      throw new Error("Fixture did not include requirement and route facts");
    }
    const preview = {
      ...base,
      routeRequirements: [
        {
          ...firstRequirement,
          preconditionFailures: [
            {
              code: "distinctive_precondition_code",
              reason: "distinctive precondition reason",
            },
          ],
        },
        ...base.routeRequirements.slice(1),
      ],
      routePlans: [
        {
          ...firstRoute,
          policyGates: [
            {
              code: "distinctive_gate_code",
              reason: "distinctive gate reason",
            },
          ],
          exclusionReasons: [
            {
              code: "distinctive_exclusion_code",
              reason: "distinctive exclusion reason",
            },
          ],
        },
        ...base.routePlans.slice(1),
      ],
    };
    const { container, root } = renderNode(
      createElement(WorkflowPlanAdvancedView, { preview }),
    );
    const text = container.textContent ?? "";

    for (const expected of [
      "distinctive_precondition_code: distinctive precondition reason",
      "distinctive_gate_code: distinctive gate reason",
      "distinctive_exclusion_code: distinctive exclusion reason",
    ]) {
      expect(text).toContain(expected);
    }

    act(() => root.unmount());
  });
});

describe("workflow planner Preview transport", () => {
  it("accepts held as success and marks only the matching Project applied", async () => {
    const preview = await createMockPreview();
    previewWorkflowPlanMock.mockResolvedValueOnce(preview);
    projectSelectionMock.selectedProject = activeProject();
    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
      }),
    );
    advanceBatchWorkspaceToPreview(container);
    projectSelectionMock.markProjectFilterApplied.mockClear();
    projectSelectionMock.clearProjectFilterApplied.mockClear();

    const generate = buttonByName(container, "生成 Preview");
    expect(generate.disabled).toBe(false);
    await act(async () => {
      generate.click();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(previewWorkflowPlanMock).toHaveBeenCalledTimes(1);
    expect(previewWorkflowPlanMock.mock.calls[0]?.[0]).toBe("project-a");
    expect(previewWorkflowPlanMock.mock.calls[0]?.[1].flowMode).toBe(
      "batch_research",
    );
    expect(previewWorkflowPlanMock.mock.calls[0]?.[2]?.signal).toBeInstanceOf(
      AbortSignal,
    );
    expect(
      container.querySelector('[data-testid="workflow-planner-preview"]')
        ?.textContent,
    ).toContain("held");
    expect(projectSelectionMock.clearProjectFilterApplied).toHaveBeenCalled();
    expect(projectSelectionMock.markProjectFilterApplied).toHaveBeenCalledWith(
      "project-a",
    );

    act(() => root.unmount());
  });

  it("cancels an in-place Generate and accepts only the second same-context success", async () => {
    const first = createDeferred<WorkflowPlanPreview>();
    const second = createDeferred<WorkflowPlanPreview>();
    const base = await createMockPreview();
    const firstPreview = { ...base, previewFingerprint: "sha256:first" };
    const secondPreview = { ...base, previewFingerprint: "sha256:second" };
    previewWorkflowPlanMock
      .mockImplementationOnce(() => first.promise)
      .mockImplementationOnce(() => second.promise);
    projectSelectionMock.selectedProject = activeProject();
    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
      }),
    );
    advanceBatchWorkspaceToPreview(container);
    projectSelectionMock.markProjectFilterApplied.mockClear();

    act(() => buttonByName(container, "生成 Preview").click());
    const firstSignal = previewWorkflowPlanMock.mock.calls[0]?.[2]?.signal;
    act(() => buttonByName(container, "生成 Preview").click());
    expect(firstSignal?.aborted).toBe(true);

    await act(async () => {
      second.resolve(secondPreview);
      await second.promise;
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      first.resolve(firstPreview);
      await first.promise;
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(
      container.querySelector('[data-testid="workflow-planner-fingerprint"]')
        ?.textContent,
    ).toBe("sha256:second");
    expect(projectSelectionMock.markProjectFilterApplied).toHaveBeenCalledTimes(
      1,
    );

    act(() => root.unmount());
  });

  it("keeps the second same-context 503 when the first success arrives late", async () => {
    const first = createDeferred<WorkflowPlanPreview>();
    const second = createDeferred<WorkflowPlanPreview>();
    const firstPreview = await createMockPreview();
    previewWorkflowPlanMock
      .mockImplementationOnce(() => first.promise)
      .mockImplementationOnce(() => second.promise);
    projectSelectionMock.selectedProject = activeProject();
    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
      }),
    );
    advanceBatchWorkspaceToPreview(container);
    projectSelectionMock.markProjectFilterApplied.mockClear();

    act(() => buttonByName(container, "生成 Preview").click());
    act(() => buttonByName(container, "生成 Preview").click());
    await act(async () => {
      second.reject(
        new ApiRequestError(503, "second request unavailable", {
          requestId: "second-request-503",
        }),
      );
      try {
        await second.promise;
      } catch {
        // The component handles this rejection; this await flushes the deferred.
      }
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      first.resolve(firstPreview);
      await first.promise;
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      "second request unavailable",
    );
    expect(container.textContent).toContain("second-request-503");
    expect(
      container.querySelector('[data-testid="workflow-planner-preview"]'),
    ).toBeNull();
    expect(
      projectSelectionMock.markProjectFilterApplied,
    ).not.toHaveBeenCalled();

    act(() => root.unmount());
  });

  it("leaves loading immediately after revision edit without resubmitting", async () => {
    const pending = createDeferred<WorkflowPlanPreview>();
    const latePreview = await createMockPreview();
    previewWorkflowPlanMock.mockImplementationOnce(() => pending.promise);
    projectSelectionMock.selectedProject = activeProject();
    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
      }),
    );
    advanceBatchWorkspaceToPreview(container);
    projectSelectionMock.markProjectFilterApplied.mockClear();
    projectSelectionMock.clearProjectFilterApplied.mockClear();
    act(() => buttonByName(container, "生成 Preview").click());
    const signal = previewWorkflowPlanMock.mock.calls[0]?.[2]?.signal;

    act(() => buttonByName(container, "上一步").click());
    act(() => buttonByName(container, "上一步").click());
    const canonical = container.querySelector(
      "#planner-scope-0-canonical-term",
    );
    if (!(canonical instanceof HTMLInputElement)) {
      throw new Error("Canonical input was not rendered");
    }
    act(() => setInputValue(canonical, "revision changed"));

    expect(signal?.aborted).toBe(true);
    expect(container.querySelector('[aria-busy="true"]')).toBeNull();
    expect(projectSelectionMock.clearProjectFilterApplied).toHaveBeenCalled();
    act(() => buttonByName(container, "下一步").click());
    act(() => buttonByName(container, "下一步").click());
    expect(container.textContent).toContain("尚未生成 Preview");
    expect(container.querySelector('[aria-busy="true"]')).toBeNull();
    expect(buttonByName(container, "生成 Preview").disabled).toBe(false);
    await act(async () => {
      pending.resolve(latePreview);
      await pending.promise;
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(
      projectSelectionMock.markProjectFilterApplied,
    ).not.toHaveBeenCalled();
    expect(container.textContent).toContain("尚未生成 Preview");
    expect(container.querySelector('[aria-busy="true"]')).toBeNull();
    expect(buttonByName(container, "生成 Preview").disabled).toBe(false);
    expect(
      container.querySelector('[data-testid="workflow-planner-preview"]'),
    ).toBeNull();

    act(() => root.unmount());
  });

  it("leaves loading immediately after mode change and ignores late rejection", async () => {
    const pending = createDeferred<WorkflowPlanPreview>();
    const staleSentinel = createInspectionSentinel();
    previewWorkflowPlanMock.mockImplementationOnce(() => pending.promise);
    projectSelectionMock.selectedProject = activeProject();
    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
      }),
    );
    advanceBatchWorkspaceToPreview(container);
    projectSelectionMock.markProjectFilterApplied.mockClear();
    projectSelectionMock.clearProjectFilterApplied.mockClear();
    act(() => buttonByName(container, "生成 Preview").click());
    const signal = previewWorkflowPlanMock.mock.calls[0]?.[2]?.signal;

    act(() => buttonByName(container, "上一步").click());
    act(() => buttonByName(container, "上一步").click());
    act(() => buttonByName(container, "上一步").click());
    const periodic = container.querySelector(
      "#planner-mode-periodic_monitoring",
    );
    if (!(periodic instanceof HTMLInputElement)) {
      throw new Error("Periodic mode input was not rendered");
    }
    act(() => periodic.click());

    expect(signal?.aborted).toBe(true);
    expect(container.querySelector('[aria-busy="true"]')).toBeNull();
    expect(projectSelectionMock.clearProjectFilterApplied).toHaveBeenCalled();
    await act(async () => {
      pending.reject(staleSentinel.error);
      try {
        await pending.promise;
      } catch {
        // The component handles this rejection; this await flushes the deferred.
      }
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(staleSentinel.inspectionCount()).toBe(0);
    expect(container.textContent).not.toContain(
      "stale sentinel must not be inspected",
    );
    expect(
      projectSelectionMock.markProjectFilterApplied,
    ).not.toHaveBeenCalled();

    act(() => root.unmount());
  });

  it.each(["resolve", "reject"] as const)(
    "aborts pending work on unmount and ignores a late %s",
    async (settlement) => {
      const pending = createDeferred<WorkflowPlanPreview>();
      const staleSentinel = createInspectionSentinel();
      const latePreview = await createMockPreview();
      previewWorkflowPlanMock.mockImplementationOnce(() => pending.promise);
      projectSelectionMock.selectedProject = activeProject();
      const { container, root } = renderNode(
        createElement(WorkflowPlannerWorkspace, {
          initialMode: "batch_research",
        }),
      );
      advanceBatchWorkspaceToPreview(container);
      projectSelectionMock.markProjectFilterApplied.mockClear();
      projectSelectionMock.clearProjectFilterApplied.mockClear();
      act(() => buttonByName(container, "生成 Preview").click());
      const signal = previewWorkflowPlanMock.mock.calls[0]?.[2]?.signal;

      act(() => root.unmount());
      expect(signal?.aborted).toBe(true);
      expect(projectSelectionMock.clearProjectFilterApplied).toHaveBeenCalled();
      await act(async () => {
        if (settlement === "resolve") {
          pending.resolve(latePreview);
        } else {
          pending.reject(staleSentinel.error);
        }
        try {
          await pending.promise;
        } catch {
          // The component handles this rejection; this await flushes the deferred.
        }
        await Promise.resolve();
        await Promise.resolve();
      });
      expect(
        projectSelectionMock.markProjectFilterApplied,
      ).not.toHaveBeenCalled();
      if (settlement === "reject") {
        expect(staleSentinel.inspectionCount()).toBe(0);
      }
    },
  );

  it("aborts on semantic edit and a non-abortable older success cannot overwrite", async () => {
    const first = createDeferred<WorkflowPlanPreview>();
    const second = createDeferred<WorkflowPlanPreview>();
    const base = await createMockPreview();
    const oldPreview = { ...base, previewFingerprint: "sha256:old" };
    const newPreview = { ...base, previewFingerprint: "sha256:new" };
    previewWorkflowPlanMock
      .mockImplementationOnce(() => first.promise)
      .mockImplementationOnce(() => second.promise);
    projectSelectionMock.selectedProject = activeProject();
    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
      }),
    );
    advanceBatchWorkspaceToPreview(container);

    act(() => buttonByName(container, "生成 Preview").click());
    const firstSignal = previewWorkflowPlanMock.mock.calls[0]?.[2]?.signal;
    act(() => buttonByName(container, "上一步").click());
    act(() => buttonByName(container, "上一步").click());
    const canonical = container.querySelector(
      "#planner-scope-0-canonical-term",
    );
    if (!(canonical instanceof HTMLInputElement)) {
      throw new Error("Canonical input was not rendered");
    }
    act(() => setInputValue(canonical, "newer running shoes"));
    expect(firstSignal?.aborted).toBe(true);
    act(() => buttonByName(container, "下一步").click());
    act(() => buttonByName(container, "下一步").click());
    act(() => buttonByName(container, "生成 Preview").click());

    await act(async () => {
      second.resolve(newPreview);
      await second.promise;
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      first.resolve(oldPreview);
      await first.promise;
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(
      container.querySelector('[data-testid="workflow-planner-fingerprint"]')
        ?.textContent,
    ).toBe("sha256:new");
    expect(
      projectSelectionMock.markProjectFilterApplied,
    ).toHaveBeenLastCalledWith("project-a");

    act(() => root.unmount());
  });

  it("guards the error catch so an older failure cannot replace newer success", async () => {
    const first = createDeferred<WorkflowPlanPreview>();
    const second = createDeferred<WorkflowPlanPreview>();
    const base = await createMockPreview();
    const newPreview = { ...base, previewFingerprint: "sha256:newer" };
    previewWorkflowPlanMock
      .mockImplementationOnce(() => first.promise)
      .mockImplementationOnce(() => second.promise);
    projectSelectionMock.selectedProject = activeProject();
    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
      }),
    );
    advanceBatchWorkspaceToPreview(container);

    act(() => buttonByName(container, "生成 Preview").click());
    act(() => buttonByName(container, "上一步").click());
    act(() => buttonByName(container, "上一步").click());
    const canonical = container.querySelector(
      "#planner-scope-0-canonical-term",
    );
    if (!(canonical instanceof HTMLInputElement)) {
      throw new Error("Canonical input was not rendered");
    }
    act(() => setInputValue(canonical, "new request"));
    act(() => buttonByName(container, "下一步").click());
    act(() => buttonByName(container, "下一步").click());
    act(() => buttonByName(container, "生成 Preview").click());

    await act(async () => {
      second.resolve(newPreview);
      await second.promise;
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      first.reject(
        new ApiRequestError(503, "stale failure", {
          requestId: "stale-request",
        }),
      );
      try {
        await first.promise;
      } catch {
        // The workspace owns the rejection; this await only flushes the deferred.
      }
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(container.textContent).not.toContain("stale failure");
    expect(
      container.querySelector('[data-testid="workflow-planner-fingerprint"]')
        ?.textContent,
    ).toBe("sha256:newer");

    act(() => root.unmount());
  });

  it("keeps prior success visible as stale and clears applied on edit", async () => {
    const preview = await createMockPreview();
    previewWorkflowPlanMock.mockResolvedValueOnce(preview);
    projectSelectionMock.selectedProject = activeProject();
    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
      }),
    );
    advanceBatchWorkspaceToPreview(container);
    await act(async () => {
      buttonByName(container, "生成 Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });
    projectSelectionMock.clearProjectFilterApplied.mockClear();

    act(() => buttonByName(container, "上一步").click());
    act(() => buttonByName(container, "上一步").click());
    const canonical = container.querySelector(
      "#planner-scope-0-canonical-term",
    );
    if (!(canonical instanceof HTMLInputElement)) {
      throw new Error("Canonical input was not rendered");
    }
    act(() => setInputValue(canonical, "changed"));
    expect(projectSelectionMock.clearProjectFilterApplied).toHaveBeenCalled();
    act(() => buttonByName(container, "下一步").click());
    act(() => buttonByName(container, "下一步").click());

    expect(
      container.querySelector('[data-testid="workflow-planner-stale"]'),
    ).not.toBeNull();
    expect(
      container.querySelector('[data-testid="workflow-planner-fingerprint"]')
        ?.textContent,
    ).toBe(preview.previewFingerprint);

    act(() => root.unmount());
  });

  it("maps 422 to the correct step, renders the issue, then focuses it", async () => {
    const frames: FrameRequestCallback[] = [];
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
      frames.push(callback);
      return frames.length;
    });
    previewWorkflowPlanMock.mockRejectedValueOnce(
      new ApiRequestError(422, "Invalid input", {
        validationIssues: [
          {
            loc: ["body", "scopes", 0, "canonical_term"],
            msg: "Server canonical error",
          },
        ],
        requestId: "request-422",
      }),
    );
    projectSelectionMock.selectedProject = activeProject();
    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
      }),
    );
    advanceBatchWorkspaceToPreview(container);

    await act(async () => {
      buttonByName(container, "生成 Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });
    act(() => frames.shift()?.(0));

    const canonical = container.querySelector(
      "#planner-scope-0-canonical-term",
    );
    expect(canonical?.getAttribute("aria-invalid")).toBe("true");
    expect(
      container.querySelector("#planner-scope-0-canonical-term-error")
        ?.textContent,
    ).toBe("Server canonical error");
    expect(document.activeElement).toBe(canonical);
    expect(
      [...container.querySelectorAll("button")].some(
        (button) => button.textContent?.trim() === "重试",
      ),
    ).toBe(false);

    act(() => root.unmount());
  });

  it("shows requestId and retries 503 without losing the form", async () => {
    const preview = await createMockPreview();
    previewWorkflowPlanMock
      .mockRejectedValueOnce(
        new ApiRequestError(503, "Planner unavailable", {
          requestId: "request-503",
        }),
      )
      .mockResolvedValueOnce(preview);
    projectSelectionMock.selectedProject = activeProject();
    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
      }),
    );
    advanceBatchWorkspaceToPreview(container);

    await act(async () => {
      buttonByName(container, "生成 Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      "Planner unavailable",
    );
    expect(container.textContent).toContain("request-503");

    await act(async () => {
      buttonByName(container, "重试").click();
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(previewWorkflowPlanMock).toHaveBeenCalledTimes(2);
    expect(
      previewWorkflowPlanMock.mock.calls[1]?.[1].scopes[0]?.canonicalTerm,
    ).toBe("running shoes");
    expect(
      container.querySelector('[data-testid="workflow-planner-preview"]'),
    ).not.toBeNull();

    act(() => root.unmount());
  });

  it("turns a current AbortError into idle with no alert", async () => {
    previewWorkflowPlanMock.mockRejectedValueOnce(
      new DOMException("Aborted", "AbortError"),
    );
    projectSelectionMock.selectedProject = activeProject();
    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
      }),
    );
    advanceBatchWorkspaceToPreview(container);

    await act(async () => {
      buttonByName(container, "生成 Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(container.querySelector('[role="alert"]')).toBeNull();
    expect(container.textContent).toContain("尚未生成 Preview");
    expect(buttonByName(container, "生成 Preview").disabled).toBe(false);

    act(() => root.unmount());
  });

  it("aborts and clears applied when Project changes before settlement", async () => {
    const pending = createDeferred<WorkflowPlanPreview>();
    const preview = await createMockPreview();
    previewWorkflowPlanMock.mockImplementationOnce(() => pending.promise);
    projectSelectionMock.selectedProject = activeProject("project-a", "A");
    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
      }),
    );
    advanceBatchWorkspaceToPreview(container);
    act(() => buttonByName(container, "生成 Preview").click());
    const signal = previewWorkflowPlanMock.mock.calls[0]?.[2]?.signal;
    projectSelectionMock.clearProjectFilterApplied.mockClear();

    projectSelectionMock.selectedProject = activeProject("project-b", "B");
    act(() =>
      root.render(
        createElement(WorkflowPlannerWorkspace, {
          initialMode: "batch_research",
        }),
      ),
    );
    expect(signal?.aborted).toBe(true);
    expect(projectSelectionMock.clearProjectFilterApplied).toHaveBeenCalled();
    await act(async () => {
      pending.resolve(preview);
      await pending.promise;
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(
      container.querySelector('[data-testid="workflow-planner-preview"]'),
    ).toBeNull();
    expect(container.textContent).toContain("B");

    act(() => root.unmount());
  });
});

describe("workflow planner persistence route and draft model", () => {
  it("parses the complete persistence query and fails closed on broken chains", () => {
    expect(
      parseWorkflowPlannerRouteQuery({
        mode: "batch_research",
        project_id: " project-a ",
        plan_id: "plan-a",
        source_version_id: "version-1",
      }),
    ).toEqual({
      mode: "batch_research",
      projectId: "project-a",
      planId: "plan-a",
      sourceVersionId: "version-1",
      error: null,
    });
    expect(
      parseWorkflowPlannerRouteQuery({
        mode: "periodic_monitoring",
        plan_id: "plan-without-project",
      }).error,
    ).toBe("plan_id requires project_id");
    expect(
      parseWorkflowPlannerRouteQuery({
        source_version_id: "version-without-plan",
      }).error,
    ).toBe("source_version_id requires plan_id and project_id");
  });

  it("hydrates periodic editableInput as a deep-cloned draft", () => {
    const input = validBatchInput("historical term");
    const periodic: PlanningInput = {
      ...input,
      flowMode: "periodic_monitoring",
      scheduleIntent: { cadence: "weekly", timezone: "Asia/Shanghai" },
    };
    periodic.scopes[0]!.aliases = ["historical alias"];
    periodic.defaultLanguages = ["zh-CN"];
    periodic.deliveryIntent = { outputs: ["dataset", "brief"] };
    periodic.rateLimitIntent = { maxRequests: 9, periodSeconds: 60 };

    const draft = workflowPlannerDraftFromEditableInput(periodic);

    expect(buildPlanningInput(draft)).toEqual(periodic);
    expect(draft.scheduleIntent).toEqual(periodic.scheduleIntent);
    expect(draft.revision).toBe(0);
    expect(draft.nextScopeSequence).toBe(2);
    draft.scopes[0]!.aliases.push("draft only");
    draft.defaultLanguages.push("en-US");
    draft.scheduleIntent!.timezone = "UTC";
    expect(periodic.scopes[0]!.aliases).toEqual(["historical alias"]);
    expect(periodic.defaultLanguages).toEqual(["zh-CN"]);
    expect(periodic.scheduleIntent.timezone).toBe("Asia/Shanghai");
  });

  it("hydrates batch without schedule and excludes revision counters from its semantic key", () => {
    const input = validBatchInput("batch source");
    const draft = workflowPlannerDraftFromEditableInput(input);
    const baseline = workflowPlannerDraftSemanticKey(draft);

    expect(draft.scheduleIntent).toBeNull();
    expect(buildPlanningInput(draft)).toEqual(input);
    expect(
      workflowPlannerDraftSemanticKey({
        ...draft,
        revision: 99,
        nextScopeSequence: 999,
      }),
    ).toBe(baseline);
    expect(
      workflowPlannerDraftSemanticKey({
        ...draft,
        purpose: "competitive_research",
      }),
    ).not.toBe(baseline);
  });
});

describe("workflow planner dirty navigation guard", () => {
  it("guards beforeunload and an ordinary same-origin anchor", () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { root } = renderNode(createElement(GuardHarness, { dirty: true }));

    const unload = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(unload);
    expect(unload.defaultPrevented).toBe(true);

    const anchor = document.createElement("a");
    anchor.href = new URL("/datasets", window.location.href).href;
    anchor.textContent = "leave";
    document.body.append(anchor);
    const click = new MouseEvent("click", {
      bubbles: true,
      cancelable: true,
      button: 0,
    });
    anchor.dispatchEvent(click);
    expect(click.defaultPrevented).toBe(true);
    expect(confirm).toHaveBeenCalledTimes(1);

    act(() => root.unmount());
  });

  it("ignores modified, targeted, downloaded, external, and same-document hash links and cleans up", () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { root } = renderNode(createElement(GuardHarness, { dirty: true }));
    const cases = [
      { href: "/datasets", metaKey: true },
      { href: "/datasets", target: "_blank" },
      { href: "/datasets", download: "export.csv" },
      { href: "https://example.invalid/elsewhere" },
      {
        href: `${window.location.pathname}${window.location.search}#scope-1`,
      },
    ];

    for (const candidate of cases) {
      const anchor = document.createElement("a");
      anchor.href = candidate.href;
      if (candidate.target) anchor.target = candidate.target;
      if (candidate.download) anchor.download = candidate.download;
      let reachedAnchor = false;
      anchor.addEventListener("click", (event) => {
        reachedAnchor = true;
        event.preventDefault();
      });
      document.body.append(anchor);
      const click = new MouseEvent("click", {
        bubbles: true,
        cancelable: true,
        button: 0,
        metaKey: candidate.metaKey ?? false,
      });
      anchor.dispatchEvent(click);
      expect(reachedAnchor).toBe(true);
    }
    expect(confirm).not.toHaveBeenCalled();

    act(() => root.unmount());
    const afterCleanup = document.createElement("a");
    afterCleanup.href = new URL("/automation", window.location.href).href;
    afterCleanup.addEventListener("click", (event) => event.preventDefault());
    document.body.append(afterCleanup);
    afterCleanup.dispatchEvent(
      new MouseEvent("click", {
        bubbles: true,
        cancelable: true,
        button: 0,
      }),
    );
    expect(confirm).not.toHaveBeenCalled();
  });
});

describe("workflow planner explicit persistence", () => {
  it("shows Save only for an accepted current Preview, requires a trimmed new name, and keeps held boundaries honest", async () => {
    const input = validBatchInput();
    const preview = await createMockPreview();
    const heldPreview = { ...preview, planningStatus: "held" as const };
    const version = makeWorkflowVersion("version-1", 1, input, heldPreview);
    const detail = makePlanDetail(version, "New saved plan");
    previewWorkflowPlanMock.mockResolvedValueOnce(heldPreview);
    createWorkflowPlanMock.mockResolvedValueOnce(
      makeSaveResult(detail, version),
    );
    projectSelectionMock.projects = [activeProject()];
    projectSelectionMock.selectedProject = activeProject();
    vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(
      "11111111-1111-4111-8111-111111111111",
    );

    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
      }),
    );
    advanceBatchWorkspaceToPreview(container);
    expect(
      container.querySelector('[data-testid="workflow-plan-save-panel"]'),
    ).toBeNull();

    await act(async () => {
      buttonByName(container, "生成 Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });

    const panel = container.querySelector(
      '[data-testid="workflow-plan-save-panel"]',
    );
    const name = container.querySelector("#workflow-plan-name");
    const save = container.querySelector('[data-testid="workflow-plan-save"]');
    expect(panel).not.toBeNull();
    expect(panel?.textContent).toContain("不会解除阻断、批准或启动运行");
    expect(name).toBeInstanceOf(HTMLInputElement);
    expect(save).toBeInstanceOf(HTMLButtonElement);
    expect((save as HTMLButtonElement).disabled).toBe(true);

    act(() => setInputValue(name as HTMLInputElement, "  New saved plan  "));
    expect((save as HTMLButtonElement).disabled).toBe(false);
    await act(async () => {
      (save as HTMLButtonElement).click();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(createWorkflowPlanMock).toHaveBeenCalledWith(
      "project-a",
      expect.objectContaining({
        name: "New saved plan",
        expectedPreviewFingerprint: heldPreview.previewFingerprint,
        previewInput: input,
        idempotencyKey: "11111111-1111-4111-8111-111111111111",
      }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(container.textContent).toContain("已创建 Plan 与 Version v1");
    expect(container.textContent).toContain("不会激活、运行或调用 Provider");

    projectSelectionMock.projects = [activeProject("project-b", "Project B")];
    projectSelectionMock.selectedProject = activeProject(
      "project-b",
      "Project B",
    );
    act(() =>
      root.render(
        createElement(WorkflowPlannerWorkspace, {
          initialMode: "batch_research",
        }),
      ),
    );
    expect(
      container.querySelector('[data-testid="workflow-plan-save-panel"]'),
    ).toBeNull();
    expect(buttonByName(container, "生成 Preview").disabled).toBe(true);

    act(() => root.unmount());
  });

  it("loads source v1 and current v3 in parallel, hydrates only editableInput, and saves against v3 as v4", async () => {
    const currentInput = validBatchInput("current v3");
    const sourceInput = validBatchInput("source v1");
    sourceInput.scopes[0]!.aliases = ["source alias"];
    const currentPreview = await buildMockWorkflowPlanPreview(
      "project-a",
      currentInput,
    );
    const sourcePreview = await buildMockWorkflowPlanPreview(
      "project-a",
      sourceInput,
    );
    sourcePreview.normalizedInput.scopes[0]!.canonicalTerm =
      "normalized preview must not hydrate the draft";
    const current = makeWorkflowVersion(
      "version-3",
      3,
      currentInput,
      currentPreview,
    );
    const source = makeWorkflowVersion(
      "version-1",
      1,
      sourceInput,
      sourcePreview,
    );
    const detail = makePlanDetail(current, "Historical recovery plan");
    const planPending = createDeferred<WorkflowPlanDetail>();
    const sourcePending = createDeferred<WorkflowVersionDetail>();
    getWorkflowPlanMock.mockImplementationOnce(() => planPending.promise);
    getWorkflowVersionMock.mockImplementationOnce(() => sourcePending.promise);
    projectSelectionMock.projects = [activeProject()];
    projectSelectionMock.selectedProject = activeProject();

    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
        initialProjectId: "project-a",
        initialPlanId: "plan-a",
        initialSourceVersionId: "version-1",
      }),
    );

    expect(getWorkflowPlanMock).toHaveBeenCalledWith(
      "project-a",
      "plan-a",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(getWorkflowVersionMock).toHaveBeenCalledWith(
      "project-a",
      "plan-a",
      "version-1",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );

    await act(async () => {
      planPending.resolve(detail);
      sourcePending.resolve(makeVersionDetail(detail, source));
      await Promise.all([planPending.promise, sourcePending.promise]);
      await Promise.resolve();
      await Promise.resolve();
    });

    const lockedMode = container.querySelector("#planner-mode-batch_research");
    expect(lockedMode).toBeInstanceOf(HTMLInputElement);
    expect((lockedMode as HTMLInputElement).disabled).toBe(true);
    expect(container.textContent).toContain("Historical recovery plan");
    expect(container.textContent).toContain("当前基线 v3");
    act(() => buttonByName(container, "下一步").click());
    const canonical = container.querySelector(
      "#planner-scope-0-canonical-term",
    );
    expect((canonical as HTMLInputElement).value).toBe("source v1");
    expect(sourceInput.scopes[0]!.aliases).toEqual(["source alias"]);
    act(() => buttonByName(container, "下一步").click());
    act(() => buttonByName(container, "下一步").click());

    const nextPreview = {
      ...sourcePreview,
      previewFingerprint: "sha256:source-v1-repreview",
    };
    previewWorkflowPlanMock.mockResolvedValueOnce(nextPreview);
    const v4 = makeWorkflowVersion("version-4", 4, sourceInput, nextPreview);
    createWorkflowVersionMock.mockResolvedValueOnce(makeSaveResult(detail, v4));
    await act(async () => {
      buttonByName(container, "生成 Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(container.querySelector("#workflow-plan-name")).toBeNull();
    await act(async () => {
      buttonByName(container, "Save Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(createWorkflowVersionMock).toHaveBeenCalledWith(
      "project-a",
      "plan-a",
      expect.objectContaining({
        expectedCurrentVersionId: "version-3",
        expectedPreviewFingerprint: "sha256:source-v1-repreview",
        previewInput: sourceInput,
      }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(container.textContent).toContain("已创建 Version v4");

    act(() => root.unmount());
  });

  it("freezes the exact Preview input and reuses one logical key for retry, then discards it after a semantic edit", async () => {
    const firstPreview = await createMockPreview();
    const secondInput = validBatchInput("changed after retry");
    const secondPreview = await buildMockWorkflowPlanPreview(
      "project-a",
      secondInput,
    );
    previewWorkflowPlanMock
      .mockResolvedValueOnce(firstPreview)
      .mockResolvedValueOnce(secondPreview);
    createWorkflowPlanMock
      .mockRejectedValueOnce(
        new ApiRequestError(503, "persistence unavailable", {
          code: "persistence_unavailable",
          requestId: "save-503-a",
        }),
      )
      .mockRejectedValueOnce(
        new ApiRequestError(503, "persistence still unavailable", {
          code: "persistence_unavailable",
          requestId: "save-503-b",
        }),
      );
    const savedVersion = makeWorkflowVersion(
      "version-1",
      1,
      secondInput,
      secondPreview,
    );
    const savedDetail = makePlanDetail(savedVersion, "Retry plan");
    createWorkflowPlanMock.mockResolvedValueOnce(
      makeSaveResult(savedDetail, savedVersion),
    );
    projectSelectionMock.projects = [activeProject()];
    projectSelectionMock.selectedProject = activeProject();
    vi.spyOn(globalThis.crypto, "randomUUID")
      .mockReturnValueOnce("11111111-1111-4111-8111-111111111111")
      .mockReturnValueOnce("22222222-2222-4222-8222-222222222222");

    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
      }),
    );
    advanceBatchWorkspaceToPreview(container);
    await act(async () => {
      buttonByName(container, "生成 Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });
    const name = container.querySelector("#workflow-plan-name");
    act(() => setInputValue(name as HTMLInputElement, "Retry plan"));

    await act(async () => {
      buttonByName(container, "Save Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      buttonByName(container, "重试保存").click();
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(
      createWorkflowPlanMock.mock.calls
        .slice(0, 2)
        .map((call) => call[1].idempotencyKey),
    ).toEqual([
      "11111111-1111-4111-8111-111111111111",
      "11111111-1111-4111-8111-111111111111",
    ]);
    expect(createWorkflowPlanMock.mock.calls[0]?.[1].previewInput).toEqual(
      validBatchInput(),
    );

    act(() => buttonByName(container, "上一步").click());
    act(() => buttonByName(container, "上一步").click());
    const canonical = container.querySelector(
      "#planner-scope-0-canonical-term",
    );
    act(() =>
      setInputValue(canonical as HTMLInputElement, "changed after retry"),
    );
    expect(
      container.querySelector('[data-testid="workflow-plan-save-panel"]'),
    ).toBeNull();
    act(() => buttonByName(container, "下一步").click());
    act(() => buttonByName(container, "下一步").click());
    await act(async () => {
      buttonByName(container, "生成 Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      buttonByName(container, "Save Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(createWorkflowPlanMock.mock.calls[2]?.[1]).toEqual(
      expect.objectContaining({
        idempotencyKey: "22222222-2222-4222-8222-222222222222",
        previewInput: secondInput,
      }),
    );
    expect(createWorkflowPlanMock.mock.calls[0]?.[1].previewInput).toEqual(
      validBatchInput(),
    );

    act(() => root.unmount());
  });

  it("keeps the draft but makes Preview stale after preview_stale", async () => {
    const preview = await createMockPreview();
    previewWorkflowPlanMock.mockResolvedValueOnce(preview);
    createWorkflowPlanMock.mockRejectedValueOnce(
      new ApiRequestError(409, "preview_stale", {
        code: "preview_stale",
        requestId: "save-stale",
      }),
    );
    projectSelectionMock.projects = [activeProject()];
    projectSelectionMock.selectedProject = activeProject();

    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
      }),
    );
    advanceBatchWorkspaceToPreview(container);
    await act(async () => {
      buttonByName(container, "生成 Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });
    act(() =>
      setInputValue(
        container.querySelector("#workflow-plan-name") as HTMLInputElement,
        "Stale plan",
      ),
    );
    await act(async () => {
      buttonByName(container, "Save Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(
      container.querySelector('[data-testid="workflow-planner-stale"]'),
    ).not.toBeNull();
    expect(
      container.querySelector('[data-testid="workflow-plan-save-panel"]'),
    ).toBeNull();
    expect(container.textContent).toContain("请重新生成 Preview 后再保存");
    act(() => buttonByName(container, "上一步").click());
    act(() => buttonByName(container, "上一步").click());
    expect(
      (
        container.querySelector(
          "#planner-scope-0-canonical-term",
        ) as HTMLInputElement
      ).value,
    ).toBe("running shoes");

    act(() => root.unmount());
  });

  it("refreshes the latest current baseline on version_conflict without merging or resubmitting", async () => {
    const input = validBatchInput("local draft");
    const preview = await buildMockWorkflowPlanPreview("project-a", input);
    const v3 = makeWorkflowVersion("version-3", 3, input, preview);
    const initialDetail = makePlanDetail(v3, "Conflict plan");
    const v4 = makeWorkflowVersion(
      "version-4",
      4,
      validBatchInput("remote current"),
      await buildMockWorkflowPlanPreview(
        "project-a",
        validBatchInput("remote current"),
      ),
    );
    const refreshedDetail = makePlanDetail(v4, "Conflict plan");
    const rePreview = {
      ...preview,
      previewFingerprint: "sha256:local-after-conflict",
    };
    const v5 = makeWorkflowVersion("version-5", 5, input, rePreview);
    getWorkflowPlanMock
      .mockResolvedValueOnce(initialDetail)
      .mockResolvedValueOnce(refreshedDetail);
    previewWorkflowPlanMock
      .mockResolvedValueOnce(preview)
      .mockResolvedValueOnce(rePreview);
    createWorkflowVersionMock
      .mockRejectedValueOnce(
        new ApiRequestError(409, "version_conflict", {
          code: "version_conflict",
          details: { current_version_id: "version-4" },
          requestId: "save-conflict",
        }),
      )
      .mockResolvedValueOnce(makeSaveResult(refreshedDetail, v5));
    projectSelectionMock.projects = [activeProject()];
    projectSelectionMock.selectedProject = activeProject();
    vi.spyOn(globalThis.crypto, "randomUUID")
      .mockReturnValueOnce("33333333-3333-4333-8333-333333333333")
      .mockReturnValueOnce("44444444-4444-4444-8444-444444444444");

    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
        initialProjectId: "project-a",
        initialPlanId: "plan-a",
      }),
    );
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    act(() => buttonByName(container, "下一步").click());
    act(() => buttonByName(container, "下一步").click());
    act(() => buttonByName(container, "下一步").click());
    await act(async () => {
      buttonByName(container, "生成 Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      buttonByName(container, "Save Preview").click();
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(getWorkflowPlanMock).toHaveBeenCalledTimes(2);
    expect(createWorkflowVersionMock).toHaveBeenCalledTimes(1);
    expect(container.textContent).toContain("当前基线 v4");
    expect(container.textContent).toContain("未自动合并或重提");
    expect(
      container.querySelector('[data-testid="workflow-planner-stale"]'),
    ).not.toBeNull();

    await act(async () => {
      buttonByName(container, "生成 Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      buttonByName(container, "Save Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(createWorkflowVersionMock).toHaveBeenCalledTimes(2);
    expect(createWorkflowVersionMock.mock.calls[0]?.[2].idempotencyKey).toBe(
      "33333333-3333-4333-8333-333333333333",
    );
    expect(createWorkflowVersionMock.mock.calls[1]?.[2]).toEqual(
      expect.objectContaining({
        expectedCurrentVersionId: "version-4",
        idempotencyKey: "44444444-4444-4444-8444-444444444444",
      }),
    );
    act(() => buttonByName(container, "上一步").click());
    act(() => buttonByName(container, "上一步").click());
    expect(
      (
        container.querySelector(
          "#planner-scope-0-canonical-term",
        ) as HTMLInputElement
      ).value,
    ).toBe("local draft");

    act(() => root.unmount());
  });

  it("marks an untouched v3 draft dirty when version_conflict refreshes a semantically different v4 baseline", async () => {
    const localInput = validBatchInput("source current v3");
    const localPreview = await buildMockWorkflowPlanPreview(
      "project-a",
      localInput,
    );
    const v3 = makeWorkflowVersion("version-3", 3, localInput, localPreview);
    const initialDetail = makePlanDetail(v3, "Conflict dirty guard plan");
    const remoteInput = validBatchInput("remote current v4");
    const remotePreview = await buildMockWorkflowPlanPreview(
      "project-a",
      remoteInput,
    );
    const v4 = makeWorkflowVersion("version-4", 4, remoteInput, remotePreview);
    const refreshedDetail = makePlanDetail(v4, "Conflict dirty guard plan");
    getWorkflowPlanMock
      .mockResolvedValueOnce(initialDetail)
      .mockResolvedValueOnce(refreshedDetail);
    previewWorkflowPlanMock.mockResolvedValueOnce(localPreview);
    createWorkflowVersionMock.mockRejectedValueOnce(
      new ApiRequestError(409, "version_conflict", {
        code: "version_conflict",
        details: { current_version_id: "version-4" },
      }),
    );
    projectSelectionMock.projects = [activeProject()];
    projectSelectionMock.selectedProject = activeProject();

    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
        initialProjectId: "project-a",
        initialPlanId: "plan-a",
      }),
    );
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    act(() => buttonByName(container, "下一步").click());
    act(() => buttonByName(container, "下一步").click());
    act(() => buttonByName(container, "下一步").click());
    await act(async () => {
      buttonByName(container, "生成 Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      buttonByName(container, "Save Preview").click();
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    const unload = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(unload);
    expect(unload.defaultPrevented).toBe(true);
    act(() => buttonByName(container, "上一步").click());
    act(() => buttonByName(container, "上一步").click());
    expect(
      (
        container.querySelector(
          "#planner-scope-0-canonical-term",
        ) as HTMLInputElement
      ).value,
    ).toBe("source current v3");

    act(() => root.unmount());
  });

  it("hydrates an archived Project by URL for read-only editing while keeping Preview and Save disabled", async () => {
    const input = validBatchInput("archived source");
    const preview = await buildMockWorkflowPlanPreview("project-a", input);
    const version = makeWorkflowVersion("version-2", 2, input, preview);
    const detail = {
      ...makePlanDetail(version, "Archived plan"),
      projectStatus: "archived" as const,
    };
    getWorkflowPlanMock.mockResolvedValueOnce(detail);
    projectSelectionMock.projects = [
      activeProject("project-other", "Other active Project"),
    ];
    projectSelectionMock.selectedProject = activeProject(
      "project-other",
      "Other active Project",
    );

    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
        initialProjectId: "project-a",
        initialPlanId: "plan-a",
      }),
    );
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(getWorkflowPlanMock).toHaveBeenCalledWith(
      "project-a",
      "plan-a",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(projectSelectionMock.selectProject).not.toHaveBeenCalled();
    expect(container.textContent).toContain(
      "Archived Project 仅允许读取历史草稿",
    );
    act(() => buttonByName(container, "下一步").click());
    expect(
      (
        container.querySelector(
          "#planner-scope-0-canonical-term",
        ) as HTMLInputElement
      ).value,
    ).toBe("archived source");
    act(() => buttonByName(container, "下一步").click());
    act(() => buttonByName(container, "下一步").click());
    expect(buttonByName(container, "生成 Preview").disabled).toBe(true);
    expect(previewWorkflowPlanMock).not.toHaveBeenCalled();
    expect(
      container.querySelector('[data-testid="workflow-plan-save-panel"]'),
    ).toBeNull();

    act(() => root.unmount());
  });

  it("fails closed when the loaded Project, Plan, Version, or mode chain does not match the route", async () => {
    const input = validBatchInput("mismatched route");
    const preview = await buildMockWorkflowPlanPreview("project-a", input);
    const version = makeWorkflowVersion("version-2", 2, input, preview);
    const detail = makePlanDetail(version, "Mismatched plan");
    getWorkflowPlanMock.mockResolvedValueOnce({
      ...detail,
      plan: { ...detail.plan, projectId: "different-project" },
    });
    projectSelectionMock.projects = [activeProject()];
    projectSelectionMock.selectedProject = activeProject();

    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
        initialProjectId: "project-a",
        initialPlanId: "plan-a",
      }),
    );
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(container.textContent).toContain(
      "WorkflowPlan route context mismatch",
    );
    expect(buttonByName(container, "下一步").disabled).toBe(true);
    expect(previewWorkflowPlanMock).not.toHaveBeenCalled();
    expect(createWorkflowVersionMock).not.toHaveBeenCalled();

    act(() => root.unmount());
  });

  it("ignores a late Save response after the draft changes in flight", async () => {
    const input = validBatchInput();
    const preview = await createMockPreview();
    const version = makeWorkflowVersion("version-1", 1, input, preview);
    const detail = makePlanDetail(version, "Late save plan");
    const pending = createDeferred<WorkflowPlanSaveResult>();
    previewWorkflowPlanMock.mockResolvedValueOnce(preview);
    createWorkflowPlanMock.mockImplementationOnce(() => pending.promise);
    projectSelectionMock.projects = [activeProject()];
    projectSelectionMock.selectedProject = activeProject();

    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
      }),
    );
    advanceBatchWorkspaceToPreview(container);
    await act(async () => {
      buttonByName(container, "生成 Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });
    act(() =>
      setInputValue(
        container.querySelector("#workflow-plan-name") as HTMLInputElement,
        "Late save plan",
      ),
    );
    act(() => buttonByName(container, "Save Preview").click());
    const saveSignal = createWorkflowPlanMock.mock.calls[0]?.[2]?.signal;
    expect(saveSignal?.aborted).toBe(false);

    act(() => buttonByName(container, "上一步").click());
    act(() => buttonByName(container, "上一步").click());
    act(() =>
      setInputValue(
        container.querySelector(
          "#planner-scope-0-canonical-term",
        ) as HTMLInputElement,
        "newer local draft",
      ),
    );
    expect(saveSignal?.aborted).toBe(true);

    await act(async () => {
      pending.resolve(makeSaveResult(detail, version));
      await pending.promise;
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(container.textContent).not.toContain("已创建 Plan 与 Version v1");
    expect(container.textContent).toContain("新 Plan");
    expect(container.textContent).not.toContain("当前基线 v1");
    expect(
      (
        container.querySelector(
          "#planner-scope-0-canonical-term",
        ) as HTMLInputElement
      ).value,
    ).toBe("newer local draft");

    act(() => root.unmount());
  });

  it("labels idempotent replay as confirmation without claiming a repeated write", async () => {
    const input = validBatchInput();
    const preview = await createMockPreview();
    const version = makeWorkflowVersion("version-1", 1, input, preview);
    const detail = makePlanDetail(version, "Replay plan");
    previewWorkflowPlanMock.mockResolvedValueOnce(preview);
    createWorkflowPlanMock.mockResolvedValueOnce(
      makeSaveResult(detail, version, "created", true),
    );
    projectSelectionMock.projects = [activeProject()];
    projectSelectionMock.selectedProject = activeProject();

    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
      }),
    );
    advanceBatchWorkspaceToPreview(container);
    await act(async () => {
      buttonByName(container, "生成 Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });
    act(() =>
      setInputValue(
        container.querySelector("#workflow-plan-name") as HTMLInputElement,
        "Replay plan",
      ),
    );
    await act(async () => {
      buttonByName(container, "Save Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(container.textContent).toContain("idempotent replay");
    expect(container.textContent).toContain("本次未重复写入");
    expect(container.textContent).not.toContain("已创建 Plan 与 Version v1");

    act(() => root.unmount());
  });

  it("reports semantic no-op without claiming a new Version", async () => {
    const input = validBatchInput("unchanged");
    const preview = await buildMockWorkflowPlanPreview("project-a", input);
    const version = makeWorkflowVersion("version-3", 3, input, preview);
    const detail = makePlanDetail(version, "No-op plan");
    getWorkflowPlanMock.mockResolvedValueOnce(detail);
    previewWorkflowPlanMock.mockResolvedValueOnce(preview);
    createWorkflowVersionMock.mockResolvedValueOnce(
      makeSaveResult(detail, version, "semantic_no_op"),
    );
    projectSelectionMock.projects = [activeProject()];
    projectSelectionMock.selectedProject = activeProject();

    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
        initialProjectId: "project-a",
        initialPlanId: "plan-a",
      }),
    );
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    act(() => buttonByName(container, "下一步").click());
    act(() => buttonByName(container, "下一步").click());
    act(() => buttonByName(container, "下一步").click());
    await act(async () => {
      buttonByName(container, "生成 Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      buttonByName(container, "Save Preview").click();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(container.textContent).toContain("语义未变化，未创建新 Version");
    expect(container.textContent).not.toContain("已创建 Version v3");

    act(() => root.unmount());
  });
});

describe("workflow planner form model", () => {
  it("parses only the two supported modes", () => {
    expect(parseWorkflowPlannerMode("periodic_monitoring")).toBe(
      "periodic_monitoring",
    );
    expect(parseWorkflowPlannerMode(["batch_research"])).toBe("batch_research");
    expect(parseWorkflowPlannerMode(["unknown", "batch_research"])).toBe(
      "periodic_monitoring",
    );
    expect(parseWorkflowPlannerMode("unknown")).toBe("periodic_monitoring");
    expect(parseWorkflowPlannerMode(null)).toBe("periodic_monitoring");
    expect(parseWorkflowPlannerMode(undefined)).toBe("periodic_monitoring");
  });

  it("creates stable non-random scope refs and one initial scope", () => {
    expect(createScopeDraft(1, "brand").scopeRef).toBe("scope-1");
    expect(createScopeDraft(2, "topic").scopeRef).toBe("scope-2");

    const draft = createWorkflowPlannerDraft("periodic_monitoring");
    expect(draft.scopes).toHaveLength(1);
    expect(draft.scopes[0]?.scopeRef).toBe("scope-1");
    expect(draft.nextScopeSequence).toBe(2);
    expect(draft.scheduleIntent).toBeNull();
  });

  it("keeps scope refs monotonic after removal and never removes the final scope", () => {
    const initial = createWorkflowPlannerDraft("batch_research");
    const withSecond = addScopeDraft(initial, "topic");
    const withoutSecond = removeScopeDraft(withSecond, "scope-2");
    const withThird = addScopeDraft(withoutSecond, "campaign");

    expect(withThird.scopes.map((scope) => scope.scopeRef)).toEqual([
      "scope-1",
      "scope-3",
    ]);
    expect(() => removeScopeDraft(initial, "scope-1")).toThrow(
      "at least one Scope",
    );
  });

  it("fails closed when adding more than twenty scopes", () => {
    let draft = createWorkflowPlannerDraft("batch_research");
    for (let index = 1; index < 20; index += 1) {
      draft = addScopeDraft(draft, "topic");
    }

    expect(draft.scopes).toHaveLength(20);
    expect(() => addScopeDraft(draft, "topic")).toThrow("at most 20 Scopes");
  });

  it("validates canonical and Seed-capable scope shapes with stable DOM ids", () => {
    const draft = createWorkflowPlannerDraft("batch_research");
    expect(validatePlannerStep(draft, "scopes")).toEqual([
      expect.objectContaining({
        fieldId: "planner-scope-0-canonical-term",
      }),
    ]);

    draft.scopes[0] = createScopeDraft(1, "topic");
    expect(validatePlannerStep(draft, "scopes")).toEqual([
      expect.objectContaining({
        fieldId: "planner-scope-0-canonical-term",
      }),
    ]);

    draft.scopes[0].seedUrls = ["https://example.com/unclassified"];
    expect(validatePlannerStep(draft, "scopes")).toEqual([]);
  });

  it("validates only Seed URL syntax and keeps unknown hosts for backend classification", () => {
    const draft = createWorkflowPlannerDraft("batch_research");
    draft.scopes[0] = createScopeDraft(1, "topic");
    draft.scopes[0].seedUrls = [
      "ftp://example.com/item",
      "not-a-url",
      "https://",
      "https://unknown-provider.example/item",
    ];

    expect(validatePlannerStep(draft, "scopes")).toEqual([
      expect.objectContaining({ fieldId: "planner-scope-0-seed-url-0" }),
      expect.objectContaining({ fieldId: "planner-scope-0-seed-url-1" }),
      expect.objectContaining({ fieldId: "planner-scope-0-seed-url-2" }),
    ]);
    expect(
      validatePlannerStep(draft, "scopes").map(
        (fieldIssue) => fieldIssue.fieldId,
      ),
    ).not.toContain("planner-scope-0-seed-url-3");
  });

  it("enforces raw request-array limits before normalization or de-duplication", () => {
    const duplicateAliases = createWorkflowPlannerDraft("batch_research");
    duplicateAliases.scopes[0].canonicalTerm = "Acme";
    duplicateAliases.scopes[0].aliases = Array(51).fill("same alias");
    expect(validatePlannerStep(duplicateAliases, "scopes")).toContainEqual(
      expect.objectContaining({ fieldId: "planner-scope-0-aliases" }),
    );

    const oneScopeSeeds = createWorkflowPlannerDraft("batch_research");
    oneScopeSeeds.scopes[0] = createScopeDraft(1, "topic");
    oneScopeSeeds.scopes[0].seedUrls = Array.from(
      { length: 101 },
      (_, index) => `https://example.com/${index}`,
    );
    expect(validatePlannerStep(oneScopeSeeds, "scopes")).toContainEqual(
      expect.objectContaining({ fieldId: "planner-scope-0-seed-urls" }),
    );

    const crossScopeSeeds = addScopeDraft(
      createWorkflowPlannerDraft("batch_research"),
      "topic",
    );
    crossScopeSeeds.scopes[0] = createScopeDraft(1, "topic");
    crossScopeSeeds.scopes[0].seedUrls = Array.from(
      { length: 60 },
      (_, index) => `https://one.example/${index}`,
    );
    crossScopeSeeds.scopes[1].seedUrls = Array.from(
      { length: 41 },
      (_, index) => `https://two.example/${index}`,
    );
    expect(validatePlannerStep(crossScopeSeeds, "scopes")).toContainEqual(
      expect.objectContaining({ fieldId: "planner-scopes" }),
    );
  });

  it("normalizes duplicates only after a raw list remains within its limit", () => {
    const draft = createWorkflowPlannerDraft("batch_research");
    draft.scopes[0].canonicalTerm = "Acme";
    draft.scopes[0].aliases = Array(50).fill(" same alias ");
    draft.defaultPlatforms = ["reddit"];

    expect(buildPlanningInput(draft).scopes[0]?.aliases).toEqual([
      "same alias",
    ]);
  });

  it("requires schedule only for periodic mode and omits it structurally for batch", () => {
    const periodic = createWorkflowPlannerDraft("periodic_monitoring");
    const periodicIssues = validatePlannerStep(periodic, "constraints");
    expect(periodicIssues.map((issue) => issue.fieldId)).toContain(
      "planner-schedule-cadence",
    );
    expect(periodicIssues.map((issue) => issue.fieldId)).toContain(
      "planner-schedule-timezone",
    );

    const batch = createWorkflowPlannerDraft("batch_research");
    batch.scopes[0].canonicalTerm = "running shoes";
    batch.defaultPlatforms = ["reddit"];
    const input = buildPlanningInput(batch);
    const dto = mapPlanningInputToDto(input);

    expect(input).not.toHaveProperty("scheduleIntent");
    expect(dto).not.toHaveProperty("schedule_intent");
    expect(Object.keys(dto)).not.toContain("schedule_intent");
  });

  it("allows platformless periodic Seed URL input to reach backend classification", () => {
    const periodic = createWorkflowPlannerDraft("periodic_monitoring");
    periodic.scheduleIntent = { cadence: "daily", timezone: "UTC" };
    periodic.defaultPlatforms = [];
    periodic.scopes[0].platforms = [];
    periodic.scopes[0].seedUrls = ["https://youtu.be/demo"];

    expect(
      validatePlannerStep(periodic, "constraints").map(
        (issue) => issue.fieldId,
      ),
    ).not.toContain("planner-scope-0-platforms");
  });

  it("requires a platform for periodic non-Seed scopes", () => {
    const periodic = createWorkflowPlannerDraft("periodic_monitoring");
    periodic.scheduleIntent = { cadence: "daily", timezone: "UTC" };
    periodic.scopes[0].canonicalTerm = "Acme";

    expect(validatePlannerStep(periodic, "constraints")).toContainEqual(
      expect.objectContaining({ fieldId: "planner-scope-0-platforms" }),
    );
  });

  it("normalizes and de-duplicates field lists and rejects overlap", () => {
    const draft = createWorkflowPlannerDraft("batch_research");
    draft.scopes[0].canonicalTerm = " running shoes ";
    draft.defaultPlatforms = ["reddit"];
    draft.requiredFields = [" title ", "URL", "title", ""];
    draft.optionalFields = [" author ", "url"];

    expect(validatePlannerStep(draft, "constraints")).toContainEqual(
      expect.objectContaining({ fieldId: "planner-optional-fields" }),
    );
    expect(() => buildPlanningInput(draft)).toThrow("Planner draft is invalid");

    draft.optionalFields = [" author ", "AUTHOR", ""];
    const input = buildPlanningInput(draft);
    expect(input.requiredFields).toEqual(["title", "URL"]);
    expect(input.optionalFields).toEqual(["author"]);
    expect(input.scopes[0]?.canonicalTerm).toBe("running shoes");
  });

  it("fails fast instead of asserting invalid drafts into a request", () => {
    const periodic = createWorkflowPlannerDraft("periodic_monitoring");
    periodic.scopes[0].canonicalTerm = "Acme";
    periodic.defaultPlatforms = ["reddit"];

    expect(() => buildPlanningInput(periodic)).toThrow(
      "Planner draft is invalid",
    );
  });

  it("builds only the public PlanningInput contract", () => {
    const draft = createWorkflowPlannerDraft("batch_research");
    draft.scopes[0].canonicalTerm = " Acme ";
    draft.scopes[0].aliases = [" ACME Inc ", "acme inc"];
    draft.defaultPlatforms = ["reddit"];
    const input = buildPlanningInput(draft);

    expect(input.scopes[0]).toEqual(
      expect.objectContaining({
        scopeRef: "scope-1",
        canonicalTerm: "Acme",
        aliases: ["ACME Inc"],
      }),
    );
    expect(input).not.toHaveProperty("revision");
    expect(input).not.toHaveProperty("nextScopeSequence");
    expect(input).not.toHaveProperty("projectId");
    expect(input.scopes[0]).not.toHaveProperty("scopeKey");
    expect(input).not.toHaveProperty("readiness");
  });
});

describe("workflow planner accessible form", () => {
  it("renders the ordered four-step contract and the selected active Project", () => {
    projectSelectionMock.selectedProject = activeProject();
    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "periodic_monitoring",
      }),
    );

    expect(
      container.querySelector('[data-testid="workflow-planner-workspace"]'),
    ).not.toBeNull();
    const stepItems = container.querySelectorAll("ol li");
    expect(stepItems).toHaveLength(4);
    expect(stepItems[0]?.getAttribute("aria-current")).toBe("step");
    expect(container.textContent).toContain("Active Planner Project");
    expect(container.textContent).not.toMatch(/保存|激活/);
    expect(
      [...container.querySelectorAll("button")].every(
        (button) => button.getAttribute("type") === "button",
      ),
    ).toBe(true);

    act(() => root.unmount());
  });

  it("focuses the first exact invalid Scope field after Next", () => {
    projectSelectionMock.selectedProject = activeProject();
    const frames: FrameRequestCallback[] = [];
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
      frames.push(callback);
      return frames.length;
    });
    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "periodic_monitoring",
      }),
    );

    act(() => buttonByName(container, "下一步").click());
    act(() => buttonByName(container, "下一步").click());
    act(() => frames.shift()?.(0));

    const canonical = container.querySelector(
      "#planner-scope-0-canonical-term",
    );
    expect(canonical?.getAttribute("aria-invalid")).toBe("true");
    expect(document.activeElement).toBe(canonical);

    act(() => root.unmount());
  });

  it("routes hidden constraint errors back to the real Scope field before focus", () => {
    projectSelectionMock.selectedProject = activeProject();
    const frames: FrameRequestCallback[] = [];
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
      frames.push(callback);
      return frames.length;
    });
    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "periodic_monitoring",
      }),
    );

    act(() => buttonByName(container, "下一步").click());
    const canonical = container.querySelector(
      "#planner-scope-0-canonical-term",
    );
    if (!(canonical instanceof HTMLInputElement)) {
      throw new Error("Canonical term input was not rendered");
    }
    act(() => setInputValue(canonical, "Acme"));
    act(() => buttonByName(container, "下一步").click());

    const cadence = container.querySelector("#planner-schedule-cadence");
    const timezone = container.querySelector("#planner-schedule-timezone");
    if (!(cadence instanceof HTMLSelectElement)) {
      throw new Error("Cadence select was not rendered");
    }
    if (!(timezone instanceof HTMLInputElement)) {
      throw new Error("Timezone input was not rendered");
    }
    act(() => setSelectValue(cadence, "daily"));
    act(() => setInputValue(timezone, "Asia/Shanghai"));
    act(() => buttonByName(container, "下一步").click());
    act(() => frames.shift()?.(0));

    const platforms = container.querySelector("#planner-scope-0-platforms");
    expect(platforms?.getAttribute("aria-invalid")).toBe("true");
    expect(document.activeElement).toBe(platforms);

    act(() => root.unmount());
  });

  it("binds unified field errors to exact Scope controls", () => {
    const draft = createWorkflowPlannerDraft("batch_research");
    const { container, root } = renderNode(
      createElement(PlannerScopeStep, {
        draft,
        fieldErrors: {
          "planner-scope-0-type": "类型错误",
          "planner-scope-0-canonical-term": "核心词错误",
          "planner-scope-0-seed-url-0": "URL 错误",
          "planner-scope-0-seed-urls": "URL 列表错误",
          "planner-scope-0-platforms": "平台错误",
        },
        onDraftChange: vi.fn(),
      }),
    );

    for (const id of [
      "planner-scope-0-type",
      "planner-scope-0-canonical-term",
      "planner-scope-0-seed-url-0",
      "planner-scope-0-seed-urls",
      "planner-scope-0-platforms",
    ]) {
      const field = container.querySelector(`#${id}`);
      expect(field?.getAttribute("aria-invalid")).toBe("true");
      expect(field?.getAttribute("aria-describedby")).toBe(`${id}-error`);
      expect(container.querySelector(`#${id}-error`)?.textContent).not.toBe("");
    }
    const platformFieldset = container.querySelector(
      "#planner-scope-0-platforms",
    );
    expect(platformFieldset?.getAttribute("tabindex")).toBe("-1");
    expect(
      container
        .querySelector("#planner-scope-0-seed-urls")
        ?.getAttribute("tabindex"),
    ).toBe("-1");
    expect(
      container.querySelector('button[aria-label="添加 Scope"]'),
    ).not.toBeNull();

    act(() => root.unmount());
  });

  it("binds aggregate Scope errors to a real focusable collection", () => {
    const draft = createWorkflowPlannerDraft("batch_research");
    const { container, root } = renderNode(
      createElement(PlannerScopeStep, {
        draft,
        fieldErrors: { "planner-scopes": "Seed URL 总数超过 100" },
        onDraftChange: vi.fn(),
      }),
    );

    const collection = container.querySelector("#planner-scopes");
    expect(collection?.getAttribute("tabindex")).toBe("-1");
    expect(collection?.getAttribute("aria-invalid")).toBe("true");
    expect(collection?.getAttribute("aria-describedby")).toBe(
      "planner-scopes-error",
    );
    expect(container.querySelector("#planner-scopes-error")?.textContent).toBe(
      "Seed URL 总数超过 100",
    );

    act(() => root.unmount());
  });

  it("never renders cadence controls in batch mode and exposes exact platform ids", () => {
    const draft = createWorkflowPlannerDraft("batch_research");
    const { container, root } = renderNode(
      createElement(PlannerConstraintsStep, {
        draft,
        fieldErrors: { "planner-default-platforms": "请选择平台" },
        onDraftChange: vi.fn(),
      }),
    );

    expect(container.querySelector("#planner-schedule-cadence")).toBeNull();
    expect(container.querySelector("#planner-schedule-timezone")).toBeNull();
    for (const platform of [
      "youtube",
      "reddit",
      "x",
      "instagram",
      "threads",
      "tiktok",
      "linkedin",
    ]) {
      expect(
        container.querySelector(`#planner-platform-${platform}`),
      ).not.toBeNull();
    }

    act(() => root.unmount());
  });

  it("keeps Generate Preview honest and disabled without an active Project", () => {
    projectSelectionMock.selectedProject = null;
    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
      }),
    );

    act(() => buttonByName(container, "下一步").click());
    const canonical = container.querySelector(
      "#planner-scope-0-canonical-term",
    );
    if (!(canonical instanceof HTMLInputElement)) {
      throw new Error("Canonical term input was not rendered");
    }
    act(() => setInputValue(canonical, "running shoes"));
    act(() => buttonByName(container, "下一步").click());
    const reddit = container.querySelector("#planner-platform-reddit");
    if (!(reddit instanceof HTMLInputElement)) {
      throw new Error("Reddit platform input was not rendered");
    }
    act(() => reddit.click());
    act(() => buttonByName(container, "下一步").click());

    const generate = container.querySelector(
      '[data-testid="workflow-planner-generate-preview"]',
    );
    expect(generate).toBeInstanceOf(HTMLButtonElement);
    expect((generate as HTMLButtonElement).disabled).toBe(true);
    expect(container.textContent).toContain("请先选择一个 active Project");
    expect(container.textContent).toContain("尚未生成 Preview");

    act(() => root.unmount());
  });

  it("enables the integrated Generate control with an active Project", () => {
    projectSelectionMock.selectedProject = activeProject();
    const { container, root } = renderNode(
      createElement(WorkflowPlannerWorkspace, {
        initialMode: "batch_research",
      }),
    );

    act(() => buttonByName(container, "下一步").click());
    const canonical = container.querySelector(
      "#planner-scope-0-canonical-term",
    );
    if (!(canonical instanceof HTMLInputElement)) {
      throw new Error("Canonical term input was not rendered");
    }
    act(() => setInputValue(canonical, "running shoes"));
    act(() => buttonByName(container, "下一步").click());
    const reddit = container.querySelector("#planner-platform-reddit");
    if (!(reddit instanceof HTMLInputElement)) {
      throw new Error("Reddit platform input was not rendered");
    }
    act(() => reddit.click());
    act(() => buttonByName(container, "下一步").click());

    const generate = container.querySelector(
      '[data-testid="workflow-planner-generate-preview"]',
    );
    expect(generate).toBeInstanceOf(HTMLButtonElement);
    expect((generate as HTMLButtonElement).disabled).toBe(false);
    expect(container.textContent).not.toContain("Preview 请求尚未接入");

    act(() => root.unmount());
  });
});

afterEach(() => {
  projectSelectionMock.projects = [];
  projectSelectionMock.selectedProject = null;
  projectSelectionMock.loading = false;
  projectSelectionMock.projectListError = null;
  projectSelectionMock.markProjectFilterApplied.mockReset();
  projectSelectionMock.clearProjectFilterApplied.mockReset();
  projectSelectionMock.selectProject.mockReset();
  previewWorkflowPlanMock.mockReset();
  createWorkflowPlanMock.mockReset();
  createWorkflowVersionMock.mockReset();
  getWorkflowPlanMock.mockReset();
  getWorkflowVersionMock.mockReset();
  document.body.replaceChildren();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});
