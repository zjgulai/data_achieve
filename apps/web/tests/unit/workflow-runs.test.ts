// @vitest-environment jsdom

import * as React from "react";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WorkflowRunHistoryWorkspace } from "@/components/workflow-execution/workflow-run-history-workspace";
import {
  createWorkflowFixtureRun,
  getWorkflowFixtureRunGate,
  getWorkflowRun,
  getWorkflowRunAttemptFallbackEvidence,
  getWorkflowRunCheckpointBudgetEvidence,
  getWorkflowRunExecutorEvidence,
  getWorkflowRunActionGates,
  getWorkflowRunLineagePreview,
  getWorkflowRunProviderHealthEvidence,
  getWorkflowRunShadowComparisons,
  listWorkflowRuns,
  mapWorkflowAttemptFallbackEvidence,
  mapWorkflowCheckpointBudgetEvidence,
  mapWorkflowExecutorEvidence,
  mapWorkflowLineagePreview,
  mapWorkflowRunDetail,
  mapWorkflowRunActionGates,
  mapWorkflowRunList,
  mapWorkflowProviderHealthEvidence,
  mapWorkflowShadowComparisonList,
  type WorkflowRunTransport,
} from "@/lib/api/workflow-runs";
import {
  buildMockWorkflowAttemptFallbackEvidenceDto,
  buildMockWorkflowCheckpointBudgetEvidenceDto,
  buildMockWorkflowExecutorEvidenceDto,
  buildMockWorkflowFixtureRunCreateDto,
  buildMockWorkflowRunDetailDto,
  buildMockWorkflowRunActionGatesDto,
  buildMockWorkflowRunLineagePreviewDto,
  buildMockWorkflowRunListDto,
  buildMockWorkflowProviderHealthEvidenceDto,
  buildMockWorkflowShadowComparisonListDto,
} from "@/lib/workflow-run-mock";
import type { WorkflowRunActionGates } from "@/types/workflow-run";

const PROJECT_ID = "10000000-0000-4000-8000-000000000101";
const OTHER_PROJECT_ID = "10000000-0000-4000-8000-000000000102";
const RUN_ID = "20000000-0000-4000-8000-000000000201";
const SECOND_RUN_ID = "20000000-0000-4000-8000-000000000202";
const PLAN_ID = "50000000-0000-4000-8000-000000000501";
const VERSION_ID = "60000000-0000-4000-8000-000000000601";
const PREVIEW_FINGERPRINT = `sha256:${"a".repeat(64)}`;
const mutationTransportStubs: Pick<
  WorkflowRunTransport,
  "createAction" | "createActionApproval"
> = {
  async createActionApproval() {
    throw new Error("workflow_action_mutation_unavailable_in_test");
  },
  async createAction() {
    throw new Error("workflow_action_mutation_unavailable_in_test");
  },
};

function buildV2ActionGatesDomain(
  projectId: string,
  runId: string,
): WorkflowRunActionGates {
  const v1 = mapWorkflowRunActionGates(
    buildMockWorkflowRunActionGatesDto(projectId, runId),
  );
  if (v1.schemaVersion !== "workflow_run_action_gates.v1") {
    throw new Error("expected_workflow_run_action_gates_v1");
  }
  return {
    ...v1,
    schemaVersion: "workflow_run_action_gates.v2",
    actionGateDigest: `sha256:${"d".repeat(64)}`,
    actionContextVersion: 1,
    gates: v1.gates.map((gate) => ({
      action: gate.action,
      preconditionStatus:
        gate.action === "cancel" ? "ready_for_review" : "blocked",
      preconditionBlockerCodes:
        gate.action === "cancel"
          ? []
          : ["retry_policy_snapshot_unavailable"],
      submissionAvailable: gate.action === "cancel",
      availabilityBlockerCodes: [],
      approvalKind:
        gate.action === "budget_override"
          ? "owner_policy_override"
          : gate.action === "route_switch"
            ? "owner_route_override"
            : "owner_confirmation",
      approvalReceiptRequired: true,
      evidenceRefs: gate.evidenceRefs,
      expiresAt: "2026-07-27T13:15:00Z",
    })),
    readyForReviewTotal: 1,
    blockedTotal: 4,
    notApplicableTotal: 0,
    availableActionTotal: 1,
    mutationEndpointsAvailable: true,
    durableActionAuditAvailable: true,
    actionMutationExecuted: false,
  };
}

const projectSelectionMock = vi.hoisted(() => ({
  selectedProjectId: "10000000-0000-4000-8000-000000000101",
  markProjectFilterApplied: vi.fn(),
  clearProjectFilterApplied: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...actual, mockApiEnabled: false };
});

vi.mock("@/lib/api/projects", () => ({
  listProjects: vi.fn(async () => [
    {
      id: "10000000-0000-4000-8000-000000000101",
      name: "社媒监测项目",
      description: null,
      domain: "social",
      status: "active",
      intelligenceCount: 0,
      sourceCount: 0,
    },
  ]),
}));

vi.mock("@/components/layout/project-selection-provider", () => ({
  useProjectSelection: () => {
    const projectId = projectSelectionMock.selectedProjectId;
    return {
      projects: [],
      selectedProject: {
        id: projectId,
        name: "社媒监测项目",
        description: null,
        domain: "social",
        status: "active",
        intelligenceCount: 0,
        sourceCount: 0,
      },
      selectedProjectId: projectId,
      loading: false,
      projectListError: null,
      preferenceError: null,
      filterApplied: false,
      selectProject: vi.fn(),
      markProjectFilterApplied: projectSelectionMock.markProjectFilterApplied,
      clearProjectFilterApplied: projectSelectionMock.clearProjectFilterApplied,
    };
  },
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/automation/runs",
}));

(
  globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }
).IS_REACT_ACT_ENVIRONMENT = true;

beforeEach(() => {
  projectSelectionMock.selectedProjectId = PROJECT_ID;
  projectSelectionMock.markProjectFilterApplied.mockReset();
  projectSelectionMock.clearProjectFilterApplied.mockReset();
  vi.stubGlobal("React", React);
});

afterEach(() => {
  document.body.replaceChildren();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.resetModules();
});

async function settle(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

function renderWorkspace(transport: WorkflowRunTransport): {
  container: HTMLDivElement;
  root: Root;
} {
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  act(() => {
    root.render(createElement(WorkflowRunHistoryWorkspace, { transport }));
  });
  return { container, root };
}

describe("workflow run transport", () => {
  it("maps fixture list/detail and preserves immutable lineage and boundaries", () => {
    const list = mapWorkflowRunList(buildMockWorkflowRunListDto(PROJECT_ID));
    const detail = mapWorkflowRunDetail(
      buildMockWorkflowRunDetailDto(PROJECT_ID, RUN_ID),
    );

    expect(list.items[0]).toMatchObject({
      projectId: PROJECT_ID,
      workflowTemplateId: expect.any(String),
      workflowTemplateRevisionId: expect.any(String),
      executionMode: "fixture",
      providerCallAttempted: false,
    });
    expect(list.databaseWrite).toBe(false);
    expect(list.rawRecordWrite).toBe(false);
    expect(list.datasetWrite).toBe(false);
    expect(detail.run.id).toBe(RUN_ID);
    expect(detail.run.status).toBe("held");
    expect(detail.run.statusReasonCode).toBe("fallback_blocked");
    expect(detail.run.missingFields).toEqual(["author_profile.country"]);
    expect(detail.run.finishedAt).toBeNull();
    expect(detail.steps[0]?.sequence).toBe(1);
    expect(detail.steps[0]?.evidenceRefs.length).toBeGreaterThan(0);
    const operationalEvidence = mapWorkflowAttemptFallbackEvidence(
      buildMockWorkflowAttemptFallbackEvidenceDto(PROJECT_ID, RUN_ID),
    );
    expect(operationalEvidence.attemptTotal).toBe(3);
    expect(operationalEvidence.fallbackDecisionTotal).toBe(1);
    expect(operationalEvidence.fallbackDecisions[0]).toMatchObject({
      outcome: "blocked",
      switchExecuted: false,
      providerCallAttempted: false,
    });
    const checkpointBudget = mapWorkflowCheckpointBudgetEvidence(
      buildMockWorkflowCheckpointBudgetEvidenceDto(PROJECT_ID, RUN_ID),
    );
    expect(checkpointBudget).toMatchObject({
      checkpointPageTotal: 1,
      budgetStatus: "held",
      heldReasonCode: "workflow_request_budget_exceeded",
      resumeActionAvailable: false,
      budgetOverrideAvailable: false,
    });
    const providerHealth = mapWorkflowProviderHealthEvidence(
      buildMockWorkflowProviderHealthEvidenceDto(PROJECT_ID, RUN_ID),
    );
    expect(providerHealth).toMatchObject({
      observedCandidateTotal: 2,
      routingActiveCandidateTotal: 1,
      attentionCandidateTotal: 1,
      routeFeedbackTotal: 1,
      healthProbeAttempted: false,
      catalogMutationApplied: false,
      automaticRouteSwitchExecuted: false,
      routeSwitchActionAvailable: false,
    });
    const actionGates = mapWorkflowRunActionGates(
      buildMockWorkflowRunActionGatesDto(PROJECT_ID, RUN_ID),
    );
    expect(actionGates).toMatchObject({
      runStatus: "held",
      readyForReviewTotal: 1,
      blockedTotal: 4,
      notApplicableTotal: 0,
      availableActionTotal: 0,
      mutationEndpointsAvailable: false,
      durableActionAuditAvailable: false,
      actionMutationExecuted: false,
    });
    expect(actionGates.gates.map((item) => item.action)).toEqual([
      "retry",
      "resume",
      "cancel",
      "budget_override",
      "route_switch",
    ]);
  });

  it("uses only the existing read endpoints and maps query pagination", async () => {
    const response = buildMockWorkflowRunListDto(PROJECT_ID);
    const fetchMock = vi.fn<
      (request: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    >(
      async () =>
        new Response(JSON.stringify(response), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await listWorkflowRuns(PROJECT_ID, {
      limit: 10,
      offset: 20,
    });
    const [request] = fetchMock.mock.calls[0] ?? [];

    expect(String(request)).toBe(
      `http://localhost:8000/api/projects/${PROJECT_ID}/workflow-runs?limit=10&offset=20`,
    );
    expect(result.items).toHaveLength(response.items.length);

    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify(buildMockWorkflowRunDetailDto(PROJECT_ID, RUN_ID)),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    await getWorkflowRun(PROJECT_ID, RUN_ID);
    expect(String(fetchMock.mock.calls[1]?.[0])).toBe(
      `http://localhost:8000/api/projects/${PROJECT_ID}/workflow-runs/${RUN_ID}`,
    );

    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify(
          buildMockWorkflowAttemptFallbackEvidenceDto(PROJECT_ID, RUN_ID),
        ),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    const operationalEvidence = await getWorkflowRunAttemptFallbackEvidence(
      PROJECT_ID,
      RUN_ID,
    );
    expect(String(fetchMock.mock.calls[2]?.[0])).toBe(
      `http://localhost:8000/api/projects/${PROJECT_ID}/workflow-runs/${RUN_ID}/attempt-fallback-evidence`,
    );
    expect(operationalEvidence.attemptTotal).toBe(3);
    expect(operationalEvidence.databaseWrite).toBe(false);

    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify(
          buildMockWorkflowCheckpointBudgetEvidenceDto(PROJECT_ID, RUN_ID),
        ),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    const checkpointBudget = await getWorkflowRunCheckpointBudgetEvidence(
      PROJECT_ID,
      RUN_ID,
    );
    expect(String(fetchMock.mock.calls[3]?.[0])).toBe(
      `http://localhost:8000/api/projects/${PROJECT_ID}/workflow-runs/${RUN_ID}/checkpoint-budget-evidence`,
    );
    expect(checkpointBudget.budgetStatus).toBe("held");
    expect(checkpointBudget.resumeActionAvailable).toBe(false);

    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify(
          buildMockWorkflowProviderHealthEvidenceDto(PROJECT_ID, RUN_ID),
        ),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    const providerHealth = await getWorkflowRunProviderHealthEvidence(
      PROJECT_ID,
      RUN_ID,
    );
    expect(String(fetchMock.mock.calls[4]?.[0])).toBe(
      `http://localhost:8000/api/projects/${PROJECT_ID}/workflow-runs/${RUN_ID}/provider-health-evidence`,
    );
    expect(providerHealth.attentionCandidateTotal).toBe(1);
    expect(providerHealth.routeSwitchActionAvailable).toBe(false);

    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify(buildMockWorkflowRunActionGatesDto(PROJECT_ID, RUN_ID)),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    const actionGates = await getWorkflowRunActionGates(PROJECT_ID, RUN_ID);
    expect(String(fetchMock.mock.calls[5]?.[0])).toBe(
      `http://localhost:8000/api/projects/${PROJECT_ID}/workflow-runs/${RUN_ID}/action-gates`,
    );
    expect(actionGates.availableActionTotal).toBe(0);

    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify(
          buildMockWorkflowRunLineagePreviewDto(PROJECT_ID, RUN_ID),
        ),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    const lineage = await getWorkflowRunLineagePreview(PROJECT_ID, RUN_ID);
    expect(String(fetchMock.mock.calls[6]?.[0])).toBe(
      `http://localhost:8000/api/projects/${PROJECT_ID}/workflow-runs/${RUN_ID}/lineage-preview`,
    );
    expect(lineage.rawRecord.materialized).toBe(false);
    expect(lineage.dataset.materialized).toBe(false);

    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify(
          buildMockWorkflowShadowComparisonListDto(PROJECT_ID, RUN_ID),
        ),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    const shadow = await getWorkflowRunShadowComparisons(PROJECT_ID, RUN_ID);
    expect(String(fetchMock.mock.calls[7]?.[0])).toBe(
      `http://localhost:8000/api/projects/${PROJECT_ID}/workflow-runs/${RUN_ID}/shadow-comparisons`,
    );
    expect(shadow).toMatchObject({
      total: 1,
      databaseWrite: false,
      providerCall: false,
      items: [
        {
          equivalenceStatus: "different",
          routingRecommendation: "keep_primary_investigate_shadow",
          catalogMutationApplied: false,
          routeRankingMutationApplied: false,
        },
      ],
    });
  });

  it("maps and fetches strict executor evidence without live authority", async () => {
    const dto = buildMockWorkflowExecutorEvidenceDto(PROJECT_ID, RUN_ID);
    const mapped = mapWorkflowExecutorEvidence(dto);
    expect(mapped).toMatchObject({
      schemaVersion: "workflow_executor_evidence.v1",
      evidenceGrade: "L2_fixture_local",
      dispatchTotal: 1,
      businessCauseCode: "executor_waiting_exact_live_authority",
      credentialReadAttempted: false,
      clientConstruction: false,
      providerCall: false,
      networkCall: false,
      liveProviderProof: false,
    });
    expect(mapped.dispatches[0]).toMatchObject({
      preflightState: "eligible",
      nextRequiredAuthority: "exact_live_provider_call_authorization",
      auditTotal: 1,
      credentialPermitIds: [],
      providerPermitIds: [],
      cancellation: {
        requested: true,
        acknowledged: false,
      },
    });

    const fetchMock = vi.fn<
      (request: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    >(
      async () =>
        new Response(JSON.stringify(dto), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const fetched = await getWorkflowRunExecutorEvidence(PROJECT_ID, RUN_ID);

    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      `http://localhost:8000/api/projects/${PROJECT_ID}/workflow-runs/${RUN_ID}/executor-evidence`,
    );
    expect(fetched.dispatchTotal).toBe(1);
  });

  it("rejects invalid Shadow partitions and mutation claims", () => {
    const dto = buildMockWorkflowShadowComparisonListDto(PROJECT_ID, RUN_ID);
    expect(() =>
      mapWorkflowShadowComparisonList({
        ...dto,
        items: dto.items.map((item) => ({
          ...item,
          catalog_mutation_applied: true as never,
        })),
      }),
    ).toThrow("workflow_shadow_comparison_boundary_invalid");
  });

  it("rejects broken attempt sequence and silent Fallback switch claims", () => {
    const dto = buildMockWorkflowAttemptFallbackEvidenceDto(PROJECT_ID, RUN_ID);
    expect(() =>
      mapWorkflowAttemptFallbackEvidence({
        ...dto,
        attempts: dto.attempts.map((attempt, index) =>
          index === 2 ? { ...attempt, attempt_number: 3 } : attempt,
        ),
      }),
    ).toThrow("workflow_attempt_fallback_evidence_boundary_invalid");

    expect(() =>
      mapWorkflowAttemptFallbackEvidence({
        ...dto,
        fallback_decisions: dto.fallback_decisions.map((decision) => ({
          ...decision,
          switch_executed: true as never,
        })),
      }),
    ).toThrow("workflow_attempt_fallback_evidence_boundary_invalid");
  });

  it("rejects broken checkpoint ownership and action availability claims", () => {
    const dto = buildMockWorkflowCheckpointBudgetEvidenceDto(
      PROJECT_ID,
      RUN_ID,
    );
    expect(() =>
      mapWorkflowCheckpointBudgetEvidence({
        ...dto,
        execution_session_id: SECOND_RUN_ID,
      }),
    ).toThrow("workflow_checkpoint_budget_evidence_boundary_invalid");
    expect(() =>
      mapWorkflowCheckpointBudgetEvidence({
        ...dto,
        resume_action_available: true as never,
      }),
    ).toThrow("workflow_checkpoint_budget_evidence_boundary_invalid");
  });

  it("rejects Provider Health side effects and mismatched candidate evidence", () => {
    const dto = buildMockWorkflowProviderHealthEvidenceDto(PROJECT_ID, RUN_ID);
    expect(() =>
      mapWorkflowProviderHealthEvidence({
        ...dto,
        automatic_route_switch_executed: true as never,
      }),
    ).toThrow("workflow_provider_health_evidence_boundary_invalid");
    expect(() =>
      mapWorkflowProviderHealthEvidence({
        ...dto,
        steps: dto.steps.map((step, index) =>
          index === 0
            ? {
                ...step,
                selected_implementation_id: "fixture.tampered.v1",
              }
            : step,
        ),
      }),
    ).toThrow("workflow_provider_health_step_boundary_invalid");
  });

  it("rejects reordered action gates and any mutation availability claim", () => {
    const dto = buildMockWorkflowRunActionGatesDto(PROJECT_ID, RUN_ID);
    if (dto.schema_version !== "workflow_run_action_gates.v1") {
      throw new Error("expected_workflow_run_action_gates_v1");
    }
    expect(() =>
      mapWorkflowRunActionGates({
        ...dto,
        gates: [...dto.gates].reverse(),
      }),
    ).toThrow("workflow_run_action_gates_boundary_invalid");
    expect(() =>
      mapWorkflowRunActionGates({
        ...dto,
        gates: dto.gates.map((gate, index) =>
          index === 0 ? { ...gate, action_available: true as never } : gate,
        ),
      }),
    ).toThrow("workflow_run_action_gate_boundary_invalid");
  });

  it("reads the current Version gate and creates only an idempotent local fixture Run", async () => {
    const gateResponse = {
      execution_mode: "fixture" as const,
      live_execution_authorized: false as const,
      provider_call: false as const,
      provider_call_attempted: false as const,
      credential_read_attempted: false as const,
      actor_run: false as const,
      browser_run: false as const,
      llm_call: false as const,
      raw_record_write: false as const,
      dataset_write: false as const,
      production_write_allowed: false as const,
      database_write: false as const,
      gate_contract_version: "workflow_fixture_run_gate.v1" as const,
      project_status: "active" as const,
      workflow_plan_id: PLAN_ID,
      workflow_version_id: VERSION_ID,
      current_version_id: VERSION_ID,
      plan_status: "active" as const,
      planning_status: "resolved" as const,
      is_current_version: true,
      runnable: true,
      blocker_codes: [],
      next_action_codes: ["create_fixture_run"] as const,
      evidence_refs: [
        `project:${PROJECT_ID}`,
        `workflow_plan:${PLAN_ID}`,
        `workflow_version:${VERSION_ID}`,
      ],
    };
    const createResponse = buildMockWorkflowFixtureRunCreateDto({
      projectId: PROJECT_ID,
      planId: PLAN_ID,
      versionId: VERSION_ID,
      previewFingerprint: PREVIEW_FINGERPRINT,
      fixtureProfileId: "fixture-primary-v1",
    });
    const responses = [gateResponse, createResponse];
    const fetchMock = vi.fn<
      (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    >(
      async () =>
        new Response(JSON.stringify(responses.shift()), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const gate = await getWorkflowFixtureRunGate(
      PROJECT_ID,
      PLAN_ID,
      VERSION_ID,
    );
    const result = await createWorkflowFixtureRun(
      PROJECT_ID,
      PLAN_ID,
      VERSION_ID,
      {
        expectedPreviewFingerprint: PREVIEW_FINGERPRINT,
        fixtureProfileId: "fixture-primary-v1",
        idempotencyKey: "fixture-run-key-0001",
      },
    );

    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      `http://localhost:8000/api/projects/${PROJECT_ID}/workflow-plans/${PLAN_ID}/versions/${VERSION_ID}/fixture-run-gate`,
    );
    expect(gate).toMatchObject({
      runnable: true,
      isCurrentVersion: true,
      planStatus: "active",
      blockerCodes: [],
      nextActionCodes: ["create_fixture_run"],
      databaseWrite: false,
      providerCall: false,
      credentialReadAttempted: false,
    });

    const [createUrl, createInit] = fetchMock.mock.calls[1] ?? [];
    expect(String(createUrl)).toBe(
      `http://localhost:8000/api/projects/${PROJECT_ID}/workflow-plans/${PLAN_ID}/versions/${VERSION_ID}/fixture-runs`,
    );
    expect(createInit).toMatchObject({
      method: "POST",
      credentials: "include",
    });
    expect(new Headers(createInit?.headers).get("Idempotency-Key")).toBe(
      "fixture-run-key-0001",
    );
    expect(JSON.parse(String(createInit?.body))).toEqual({
      expected_preview_fingerprint: PREVIEW_FINGERPRINT,
      fixture_profile_id: "fixture-primary-v1",
    });
    expect(result).toMatchObject({
      executionMode: "fixture",
      liveExecutionAuthorized: false,
      providerCall: false,
      providerCallAttempted: false,
      credentialReadAttempted: false,
      actorRun: false,
      browserRun: false,
      llmCall: false,
      rawRecordWrite: false,
      datasetWrite: false,
      productionWriteAllowed: false,
      databaseWrite: true,
      idempotentReplay: false,
      run: {
        workflowPlanId: PLAN_ID,
        workflowVersionId: VERSION_ID,
        previewFingerprint: PREVIEW_FINGERPRINT,
        fixtureProfileId: "fixture-primary-v1",
      },
    });
  });
});

describe("workflow run history workspace", () => {
  it("renders read-only Run history, lineage and ordered StepRun detail", async () => {
    const transport: WorkflowRunTransport = {
      ...mutationTransportStubs,
      async listRuns(_projectId, options) {
        return mapWorkflowRunList(
          buildMockWorkflowRunListDto(PROJECT_ID, {
            limit: options?.limit,
            offset: options?.offset,
          }),
        );
      },
      async getRun(projectId, runId) {
        return mapWorkflowRunDetail(
          buildMockWorkflowRunDetailDto(projectId, runId),
        );
      },
      async getAttemptFallbackEvidence(projectId, runId) {
        return mapWorkflowAttemptFallbackEvidence(
          buildMockWorkflowAttemptFallbackEvidenceDto(projectId, runId),
        );
      },
      async getCheckpointBudgetEvidence(projectId, runId) {
        return mapWorkflowCheckpointBudgetEvidence(
          buildMockWorkflowCheckpointBudgetEvidenceDto(projectId, runId),
        );
      },
      async getProviderHealthEvidence(projectId, runId) {
        return mapWorkflowProviderHealthEvidence(
          buildMockWorkflowProviderHealthEvidenceDto(projectId, runId),
        );
      },
      async getExecutorEvidence(projectId, runId) {
        return mapWorkflowExecutorEvidence(
          buildMockWorkflowExecutorEvidenceDto(projectId, runId),
        );
      },
      async getActionGates(projectId, runId) {
        return mapWorkflowRunActionGates(
          buildMockWorkflowRunActionGatesDto(projectId, runId),
        );
      },
      async getLineagePreview(projectId, runId) {
        return mapWorkflowLineagePreview(
          buildMockWorkflowRunLineagePreviewDto(projectId, runId),
        );
      },
      async getShadowComparisons(projectId, runId) {
        return mapWorkflowShadowComparisonList(
          buildMockWorkflowShadowComparisonListDto(projectId, runId),
        );
      },
    };
    const rendered = renderWorkspace(transport);
    await settle();

    expect(rendered.container.textContent).toContain("WorkflowRun 运行记录");
    expect(rendered.container.textContent).toContain("证据读取保持无副作用");
    expect(
      rendered.container.querySelector(`[data-workflow-run-id="${RUN_ID}"]`),
    ).not.toBeNull();

    const trigger = rendered.container.querySelector<HTMLButtonElement>(
      `[data-workflow-run-id="${RUN_ID}"] button`,
    );
    expect(trigger).not.toBeNull();
    act(() => trigger?.click());
    await settle();

    expect(rendered.container.textContent).toContain(
      "Template / Revision lineage",
    );
    expect(rendered.container.textContent).toContain("已暂停，等待处理");
    expect(rendered.container.textContent).toContain(
      "主路径失败，Fallback 证据门未允许切换",
    );
    expect(rendered.container.textContent).toContain(
      "当前步骤未完成，后续步骤尚未启动",
    );
    expect(rendered.container.textContent).toContain("author_profile.country");
    expect(rendered.container.textContent).toContain("检查 Fallback 门证据");
    expect(rendered.container.textContent).toContain("尚未结束");
    expect(rendered.container.textContent).toContain("未生成 fixture receipt");
    expect(rendered.container.textContent).toContain("fixture_case_");
    expect(rendered.container.textContent).toContain("证据引用");
    expect(rendered.container.textContent).toContain("尝试记录与备用路线判断");
    expect(rendered.container.textContent).toContain("共 2 次尝试");
    expect(rendered.container.textContent).toContain("数据合同不满足");
    expect(rendered.container.textContent).toContain("切换已阻止");
    expect(rendered.container.textContent).toContain("等待人工审批");
    expect(rendered.container.textContent).toContain(
      "不会重试、切换路线或调用 Provider",
    );
    expect(rendered.container.textContent).toContain("断点与预算");
    expect(rendered.container.textContent).toContain("预算已暂停");
    expect(rendered.container.textContent).toContain(
      "已确认 1 页、保存 2 条记录",
    );
    expect(rendered.container.textContent).toContain("1 / 1 次");
    expect(rendered.container.textContent).toContain(
      "不提供恢复执行或覆盖预算操作",
    );
    expect(rendered.container.textContent).toContain("Provider 健康证据");
    expect(rendered.container.textContent).toContain("需要关注");
    expect(rendered.container.textContent).toContain("成功率 33.33%");
    expect(rendered.container.textContent).toContain(
      "观测反馈建议调整候选顺序",
    );
    expect(rendered.container.textContent).toContain(
      "只读建议，未应用到此 Run",
    );
    expect(rendered.container.textContent).toContain(
      "不会主动探测 Provider，也不会修改当前 Run",
    );
    expect(rendered.container.textContent).toContain("下一步操作门禁");
    expect(rendered.container.textContent).toContain("可评审 0");
    expect(rendered.container.textContent).toContain("重试失败步骤");
    expect(rendered.container.textContent).toContain("最新失败为不可重试错误");
    expect(rendered.container.textContent).toContain("取消当前运行");
    expect(rendered.container.textContent).toContain("条件可评审");
    expect(rendered.container.textContent).toContain(
      "v1 未开放变更端点与持久化动作审计",
    );
    expect(rendered.container.textContent).toContain(
      "Provider / RawRecord / Dataset lineage preview",
    );
    expect(rendered.container.textContent).toContain("not materialized");
    expect(rendered.container.textContent).toContain("路线对比（Shadow）");
    expect(rendered.container.textContent).toContain("发现差异");
    expect(rendered.container.textContent).toContain(
      "保留主路线，并调查 Shadow 差异",
    );
    expect(rendered.container.textContent).toContain("author_profile.country");
    expect(rendered.container.textContent).toContain(
      "不会自动修改 Catalog、切换路线或调用 Provider",
    );
    expect(rendered.container.textContent).toContain(
      "Catalog mutation: false · Route ranking mutation: false",
    );
    expect(
      rendered.container.querySelector(
        '[data-workflow-run-surface="evidence-and-review"]',
      ),
    ).not.toBeNull();

    const noShadowTrigger = rendered.container.querySelector<HTMLButtonElement>(
      `[data-workflow-run-id="${SECOND_RUN_ID}"] button`,
    );
    act(() => noShadowTrigger?.click());
    await settle();
    expect(rendered.container.textContent).toContain(
      "当前 Run 没有 Shadow 对比证据",
    );
    expect(rendered.container.textContent).toContain("不代表路线等价");
    expect(rendered.container.textContent).toContain("这不代表可以安全恢复");
    expect(rendered.container.textContent).toContain("这不代表预算无限");
    expect(rendered.container.textContent).toContain(
      "这不代表 Provider 健康，也不代表可以安全切换路线",
    );

    const mutationButtons = [
      ...rendered.container.querySelectorAll("button"),
    ].filter((button) =>
      /执行|重试|取消|激活|调度|Provider/.test(button.textContent ?? ""),
    );
    expect(mutationButtons).toHaveLength(0);
    act(() => rendered.root.unmount());
  });

  it("renders executor authority evidence with collapsed diagnostics", async () => {
    const transport: WorkflowRunTransport = {
      ...mutationTransportStubs,
      async listRuns(_projectId, options) {
        return mapWorkflowRunList(
          buildMockWorkflowRunListDto(PROJECT_ID, {
            limit: options?.limit,
            offset: options?.offset,
          }),
        );
      },
      async getRun(projectId, runId) {
        return mapWorkflowRunDetail(
          buildMockWorkflowRunDetailDto(projectId, runId),
        );
      },
      async getAttemptFallbackEvidence(projectId, runId) {
        return mapWorkflowAttemptFallbackEvidence(
          buildMockWorkflowAttemptFallbackEvidenceDto(projectId, runId),
        );
      },
      async getCheckpointBudgetEvidence(projectId, runId) {
        return mapWorkflowCheckpointBudgetEvidence(
          buildMockWorkflowCheckpointBudgetEvidenceDto(projectId, runId),
        );
      },
      async getProviderHealthEvidence(projectId, runId) {
        return mapWorkflowProviderHealthEvidence(
          buildMockWorkflowProviderHealthEvidenceDto(projectId, runId),
        );
      },
      async getExecutorEvidence(projectId, runId) {
        return mapWorkflowExecutorEvidence(
          buildMockWorkflowExecutorEvidenceDto(projectId, runId),
        );
      },
      async getActionGates(projectId, runId) {
        return mapWorkflowRunActionGates(
          buildMockWorkflowRunActionGatesDto(projectId, runId),
        );
      },
      async getLineagePreview(projectId, runId) {
        return mapWorkflowLineagePreview(
          buildMockWorkflowRunLineagePreviewDto(projectId, runId),
        );
      },
      async getShadowComparisons(projectId, runId) {
        return mapWorkflowShadowComparisonList(
          buildMockWorkflowShadowComparisonListDto(projectId, runId),
        );
      },
    };
    const rendered = renderWorkspace(transport);
    await settle();
    const trigger = rendered.container.querySelector<HTMLButtonElement>(
      `[data-workflow-run-id="${RUN_ID}"] button`,
    );
    act(() => trigger?.click());
    await settle();

    const panel = rendered.container.querySelector<HTMLElement>(
      '[data-testid="workflow-executor-evidence"]',
    );
    expect(panel).not.toBeNull();
    expect(panel?.textContent).toContain("执行器证据与授权边界");
    expect(panel?.textContent).toContain("尚缺精确 Live Provider 授权");
    expect(panel?.textContent).toContain("取消意图待 Worker 确认");
    expect(panel?.textContent).toContain("不会读取 Credential");
    expect(panel?.textContent).toContain("运行中取消仍保持禁用");

    const diagnostics = panel?.querySelector("details");
    const summary = diagnostics?.querySelector("summary");
    expect(diagnostics?.open).toBe(false);
    expect(summary?.className).toContain("min-h-[var(--touch-target)]");
    act(() => summary?.click());
    expect(diagnostics?.open).toBe(true);
    expect(diagnostics?.textContent).toContain("Credential permit");
    expect(diagnostics?.textContent).toContain("Provider permit");
    expect(diagnostics?.textContent).toContain("youtube.fixture / search");
  });

  it("reviews the v2 held cancel, renders the receipt and restores focus", async () => {
    const createActionApproval = vi.fn<
      WorkflowRunTransport["createActionApproval"]
    >(async () => ({
      id: "70000000-0000-4000-8000-000000000701",
      action: "cancel",
      approvalKind: "owner_confirmation",
      proposalDigest: `sha256:${"e".repeat(64)}`,
      actionGateDigest: `sha256:${"d".repeat(64)}`,
      evidenceDigests: [`sha256:${"d".repeat(64)}`],
      expectedActionContextVersion: 1,
      expectedRunStatus: "held",
      reasonCode: "cancel_operator_request",
      reason: "Cancel this held fixture Run after Owner review.",
      issuedAt: "2026-07-27T13:00:00Z",
      expiresAt: "2026-07-27T13:15:00Z",
      databaseWrite: true,
      idempotentReplay: false,
    }));
    const createAction = vi.fn<WorkflowRunTransport["createAction"]>(
      async () => ({
        id: "80000000-0000-4000-8000-000000000801",
        requestId: "90000000-0000-4000-8000-000000000901",
        action: "cancel",
        outcome: "accepted",
        beforeActionContextVersion: 1,
        afterActionContextVersion: 2,
        beforeRunStatus: "held",
        afterRunStatus: "cancelled",
        stateChanged: true,
        databaseWrite: true,
        idempotentReplay: false,
        nextActionCode: "workflow_run_cancelled",
        receiptDigest: `sha256:${"f".repeat(64)}`,
        createdAt: "2026-07-27T13:01:00Z",
      }),
    );
    const transport: WorkflowRunTransport = {
      async listRuns(_projectId, options) {
        return mapWorkflowRunList(
          buildMockWorkflowRunListDto(PROJECT_ID, {
            limit: options?.limit,
            offset: options?.offset,
          }),
        );
      },
      async getRun(projectId, runId) {
        return mapWorkflowRunDetail(
          buildMockWorkflowRunDetailDto(projectId, runId),
        );
      },
      async getAttemptFallbackEvidence(projectId, runId) {
        return mapWorkflowAttemptFallbackEvidence(
          buildMockWorkflowAttemptFallbackEvidenceDto(projectId, runId),
        );
      },
      async getCheckpointBudgetEvidence(projectId, runId) {
        return mapWorkflowCheckpointBudgetEvidence(
          buildMockWorkflowCheckpointBudgetEvidenceDto(projectId, runId),
        );
      },
      async getProviderHealthEvidence(projectId, runId) {
        return mapWorkflowProviderHealthEvidence(
          buildMockWorkflowProviderHealthEvidenceDto(projectId, runId),
        );
      },
      async getExecutorEvidence(projectId, runId) {
        return mapWorkflowExecutorEvidence(
          buildMockWorkflowExecutorEvidenceDto(projectId, runId),
        );
      },
      async getActionGates(projectId, runId) {
        return buildV2ActionGatesDomain(projectId, runId);
      },
      createActionApproval,
      createAction,
      async getLineagePreview(projectId, runId) {
        return mapWorkflowLineagePreview(
          buildMockWorkflowRunLineagePreviewDto(projectId, runId),
        );
      },
      async getShadowComparisons(projectId, runId) {
        return mapWorkflowShadowComparisonList(
          buildMockWorkflowShadowComparisonListDto(projectId, runId),
        );
      },
    };
    const rendered = renderWorkspace(transport);
    await settle();
    const runTrigger = rendered.container.querySelector<HTMLButtonElement>(
      `[data-workflow-run-id="${RUN_ID}"] button`,
    );
    act(() => runTrigger?.click());
    await settle();

    const reviewTrigger = [...rendered.container.querySelectorAll("button")].find(
      (button) => button.textContent?.includes("打开审核"),
    );
    expect(reviewTrigger).toBeDefined();
    act(() => reviewTrigger?.click());
    await settle();
    expect(
      rendered.container.querySelector('[role="dialog"]'),
    ).not.toBeNull();
    expect(rendered.container.textContent).toContain("不会发生");
    expect(rendered.container.textContent).toContain("不调用 Provider");

    const dialog = rendered.container.querySelector('[role="dialog"]');
    act(() =>
      dialog?.dispatchEvent(
        new KeyboardEvent("keydown", { bubbles: true, key: "Escape" }),
      ),
    );
    await settle();
    expect(document.activeElement).toBe(reviewTrigger);
    act(() => reviewTrigger?.click());
    await settle();

    const confirm = [...rendered.container.querySelectorAll("button")].find(
      (button) => button.textContent?.includes("确认并记录本地动作"),
    );
    act(() => confirm?.click());
    await settle();
    await settle();

    expect(createActionApproval).toHaveBeenCalledTimes(1);
    expect(createAction).toHaveBeenCalledTimes(1);
    expect(rendered.container.textContent).toContain("本地动作已记录");
    expect(rendered.container.textContent).toContain(
      "80000000-0000-4000-8000-000000000801",
    );
    const complete = [...rendered.container.querySelectorAll("button")].find(
      (button) => button.textContent === "完成",
    );
    act(() => complete?.click());
    await settle();
    expect(document.activeElement).toBe(
      rendered.container.querySelector("#workflow-run-history-heading"),
    );
    act(() => rendered.root.unmount());
  });

  it("renders already materialized lineage without treating it as a write boundary", async () => {
    const transport: WorkflowRunTransport = {
      ...mutationTransportStubs,
      async listRuns(_projectId, options) {
        return mapWorkflowRunList(
          buildMockWorkflowRunListDto(PROJECT_ID, {
            limit: options?.limit,
            offset: options?.offset,
          }),
        );
      },
      async getRun(projectId, runId) {
        return mapWorkflowRunDetail(
          buildMockWorkflowRunDetailDto(projectId, runId),
        );
      },
      async getAttemptFallbackEvidence(projectId, runId) {
        return mapWorkflowAttemptFallbackEvidence(
          buildMockWorkflowAttemptFallbackEvidenceDto(projectId, runId),
        );
      },
      async getCheckpointBudgetEvidence(projectId, runId) {
        return mapWorkflowCheckpointBudgetEvidence(
          buildMockWorkflowCheckpointBudgetEvidenceDto(projectId, runId),
        );
      },
      async getProviderHealthEvidence(projectId, runId) {
        return mapWorkflowProviderHealthEvidence(
          buildMockWorkflowProviderHealthEvidenceDto(projectId, runId),
        );
      },
      async getExecutorEvidence(projectId, runId) {
        return mapWorkflowExecutorEvidence(
          buildMockWorkflowExecutorEvidenceDto(projectId, runId),
        );
      },
      async getActionGates(projectId, runId) {
        return mapWorkflowRunActionGates(
          buildMockWorkflowRunActionGatesDto(projectId, runId),
        );
      },
      async getLineagePreview(projectId, runId) {
        const dto = buildMockWorkflowRunLineagePreviewDto(projectId, runId);
        const rawRecordIds = [
          "30000000-0000-4000-8000-000000000301",
          "30000000-0000-4000-8000-000000000302",
        ];
        return mapWorkflowLineagePreview({
          ...dto,
          materialization_eligible: false,
          raw_record: {
            ...dto.raw_record,
            materialized_raw_record_ids: rawRecordIds,
            materialized: true,
            blocked_reasons: [],
          },
          dataset: {
            ...dto.dataset,
            dataset_id: "40000000-0000-4000-8000-000000000401",
            dataset_version_id: "40000000-0000-4000-8000-000000000402",
            source_raw_record_ids: rawRecordIds,
            materialized: true,
            blocked_reasons: [],
          },
          blocked_reasons: ["workflow_run_already_materialized"],
        });
      },
      async getShadowComparisons(projectId, runId) {
        return mapWorkflowShadowComparisonList(
          buildMockWorkflowShadowComparisonListDto(projectId, runId),
        );
      },
    };
    const rendered = renderWorkspace(transport);
    await settle();
    const trigger = rendered.container.querySelector<HTMLButtonElement>(
      `[data-workflow-run-id="${RUN_ID}"] button`,
    );
    act(() => trigger?.click());
    await settle();

    expect(rendered.container.textContent).toContain("materialized");
    expect(rendered.container.textContent).toContain(
      "已生成 RawRecord 与 Dataset 实体",
    );
    expect(rendered.container.textContent).not.toContain(
      "当前没有 RawRecord 或 Dataset 实体",
    );
    expect(rendered.container.textContent).not.toContain(
      "workflow_lineage_preview_response_context_mismatch",
    );
    act(() => rendered.root.unmount());
  });

  it("starts from the first page when the selected project changes", async () => {
    const calls: Array<{ projectId: string; offset: number }> = [];
    const detailCalls: Array<{ projectId: string; runId: string }> = [];
    const transport: WorkflowRunTransport = {
      ...mutationTransportStubs,
      async listRuns(projectId, options) {
        const offset = options?.offset ?? 0;
        calls.push({ projectId, offset });
        const firstPage = mapWorkflowRunList(
          buildMockWorkflowRunListDto(projectId, { limit: 20, offset: 0 }),
        );
        return projectId === PROJECT_ID
          ? {
              ...firstPage,
              items: offset === 0 ? firstPage.items : [firstPage.items[0]!],
              total: 21,
              offset,
            }
          : {
              ...firstPage,
              items: firstPage.items.slice(0, 1),
              total: 1,
              offset,
            };
      },
      async getRun(projectId, runId) {
        detailCalls.push({ projectId, runId });
        return mapWorkflowRunDetail(
          buildMockWorkflowRunDetailDto(projectId, runId),
        );
      },
      async getAttemptFallbackEvidence(projectId, runId) {
        return mapWorkflowAttemptFallbackEvidence(
          buildMockWorkflowAttemptFallbackEvidenceDto(projectId, runId),
        );
      },
      async getCheckpointBudgetEvidence(projectId, runId) {
        return mapWorkflowCheckpointBudgetEvidence(
          buildMockWorkflowCheckpointBudgetEvidenceDto(projectId, runId),
        );
      },
      async getProviderHealthEvidence(projectId, runId) {
        return mapWorkflowProviderHealthEvidence(
          buildMockWorkflowProviderHealthEvidenceDto(projectId, runId),
        );
      },
      async getExecutorEvidence(projectId, runId) {
        return mapWorkflowExecutorEvidence(
          buildMockWorkflowExecutorEvidenceDto(projectId, runId),
        );
      },
      async getActionGates(projectId, runId) {
        return mapWorkflowRunActionGates(
          buildMockWorkflowRunActionGatesDto(projectId, runId),
        );
      },
      async getLineagePreview(projectId, runId) {
        return mapWorkflowLineagePreview(
          buildMockWorkflowRunLineagePreviewDto(projectId, runId),
        );
      },
      async getShadowComparisons(projectId, runId) {
        return mapWorkflowShadowComparisonList(
          buildMockWorkflowShadowComparisonListDto(projectId, runId),
        );
      },
    };
    const rendered = renderWorkspace(transport);
    await settle();
    const trigger = rendered.container.querySelector<HTMLButtonElement>(
      `[data-workflow-run-id="${RUN_ID}"] button`,
    );
    act(() => trigger?.click());
    await settle();
    expect(detailCalls).toEqual([{ projectId: PROJECT_ID, runId: RUN_ID }]);

    const next = [...rendered.container.querySelectorAll("button")].find(
      (button) => button.textContent === "下一页",
    );
    act(() => next?.click());
    await settle();
    expect(calls.at(-1)).toEqual({ projectId: PROJECT_ID, offset: 20 });

    projectSelectionMock.selectedProjectId = OTHER_PROJECT_ID;
    act(() => {
      rendered.root.render(
        createElement(WorkflowRunHistoryWorkspace, { transport }),
      );
    });
    await settle();

    expect(calls.at(-1)).toEqual({ projectId: OTHER_PROJECT_ID, offset: 0 });
    expect(detailCalls).toEqual([{ projectId: PROJECT_ID, runId: RUN_ID }]);
    act(() => rendered.root.unmount());
  });
});
