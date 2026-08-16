import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "@/lib/api/client";
import {
  WORKFLOW_PLAN_PERSISTENCE_TEST_FIXTURE_PROJECT_ID,
  cloneWorkflowPlanMock,
  copyMonitoringScopeTemplateMock,
  compareWorkflowPlanVersionsMock,
  createWorkflowPlanMock,
  createWorkflowVersionMock,
  getWorkflowPlanMock,
  getWorkflowVersionMock,
  listMonitoringScopesMock,
  listWorkflowPlansMock,
  listWorkflowPlanVersionsMock,
  resetWorkflowPlanPersistenceMockForTests,
  seedWorkflowPlanPersistenceMockForTests,
} from "@/lib/workflow-plan-persistence-mock";
import { buildMockWorkflowPlanPreview } from "@/lib/workflow-planner-mock";
import type { WorkflowVersionCreateInput } from "@/types/workflow-plan-persistence";
import type { PlanningInput } from "@/types/workflow-planner";

const PROJECT_A = "10000000-0000-4000-8000-000000000001";
const PROJECT_B = "10000000-0000-4000-8000-000000000002";

function planningInput(term: string): PlanningInput {
  return {
    flowMode: "batch_research",
    scopes: [
      {
        scopeRef: "scope-1",
        scopeType: "topic",
        canonicalTerm: term,
        aliases: [],
        includeTerms: [],
        excludeTerms: [],
        officialAccounts: [],
        seedUrls: [],
        languages: ["en"],
        regions: ["US"],
        platforms: ["reddit"],
        matchMode: "phrase",
      },
    ],
    defaultLanguages: ["en"],
    defaultRegions: ["US"],
    defaultPlatforms: ["reddit"],
    deliveryIntent: { outputs: ["dataset"] },
    policyProfile: "market_monitoring_balanced",
    purpose: "market_research",
    requiredFields: ["id", "url", "text"],
    optionalFields: ["author"],
    budgetCeiling: null,
    rateLimitIntent: null,
    retentionIntent: { days: 30 },
    allowPartialDegradation: false,
  };
}

async function createPlan(
  projectId: string,
  term = "running shoes",
  idempotencyKey = "create-plan-key-0001",
) {
  const previewInput = planningInput(term);
  const preview = await buildMockWorkflowPlanPreview(projectId, previewInput);
  return createWorkflowPlanMock(projectId, {
    name: "Competitor monitoring",
    previewInput,
    expectedPreviewFingerprint: preview.previewFingerprint,
    idempotencyKey,
  });
}

async function versionInput(
  projectId: string,
  term: string,
  expectedCurrentVersionId: string,
  idempotencyKey: string,
): Promise<WorkflowVersionCreateInput> {
  const previewInput = planningInput(term);
  const preview = await buildMockWorkflowPlanPreview(projectId, previewInput);
  return {
    previewInput,
    expectedPreviewFingerprint: preview.previewFingerprint,
    expectedCurrentVersionId,
    idempotencyKey,
  };
}

describe("workflow plan persistence mock store", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_MOCK_API", "true");
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "false");
    resetWorkflowPlanPersistenceMockForTests();
  });

  afterEach(() => {
    resetWorkflowPlanPersistenceMockForTests();
    vi.unstubAllEnvs();
  });

  it("is unavailable outside mock mode and starts empty in normal mock development", async () => {
    const empty = await listWorkflowPlansMock(PROJECT_A);
    expect(empty).toMatchObject({
      projectStatus: "active",
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
      databaseWrite: false,
      planChanged: false,
    });

    vi.stubEnv("NEXT_PUBLIC_MOCK_API", "false");
    await expect(listWorkflowPlansMock(PROJECT_A)).rejects.toMatchObject({
      status: 503,
      code: "persistence_unavailable",
      message: "mock_api_disabled",
    } satisfies Partial<ApiRequestError>);
  });

  it("saves a held v1, exposes read facts, and isolates projects without browser storage", async () => {
    const localStorage = { setItem: vi.fn(), getItem: vi.fn() };
    const sessionStorage = { setItem: vi.fn(), getItem: vi.fn() };
    vi.stubGlobal("localStorage", localStorage);
    vi.stubGlobal("sessionStorage", sessionStorage);

    const saved = await createPlan(PROJECT_A);

    expect(saved).toMatchObject({
      databaseWrite: true,
      planChanged: true,
      outcome: "created",
      idempotentReplay: false,
      providerCall: false,
      actorRun: false,
      browserRun: false,
      llmCall: false,
      workflowRunCreated: false,
      executionAuthorized: false,
      plan: {
        projectId: PROJECT_A,
        currentVersionNumber: 1,
        planningStatus: "held",
      },
      version: { versionNumber: 1, planningStatus: "held" },
    });

    const plans = await listWorkflowPlansMock(PROJECT_A);
    const detail = await getWorkflowPlanMock(PROJECT_A, saved.plan.id);
    const versions = await listWorkflowPlanVersionsMock(
      PROJECT_A,
      saved.plan.id,
    );
    const version = await getWorkflowVersionMock(
      PROJECT_A,
      saved.plan.id,
      saved.version.id,
    );
    const scopes = await listMonitoringScopesMock(PROJECT_A);

    expect(plans.items.map((plan) => plan.id)).toEqual([saved.plan.id]);
    expect(detail.currentVersion.id).toBe(saved.version.id);
    expect(versions.items.map((item) => item.versionNumber)).toEqual([1]);
    expect(version.version.preview.previewFingerprint).toBe(
      saved.version.preview.previewFingerprint,
    );
    expect(scopes.items).toHaveLength(1);
    expect(scopes.items[0]).toMatchObject({
      projectId: PROJECT_A,
      canonicalTerm: "running shoes",
    });

    expect(await listWorkflowPlansMock(PROJECT_B)).toMatchObject({ total: 0 });
    expect(await listMonitoringScopesMock(PROJECT_B)).toMatchObject({
      total: 0,
    });
    await expect(
      getWorkflowPlanMock(PROJECT_B, saved.plan.id),
    ).rejects.toMatchObject({ status: 404, code: "workflow_plan_not_found" });
    expect(localStorage.setItem).not.toHaveBeenCalled();
    expect(localStorage.getItem).not.toHaveBeenCalled();
    expect(sessionStorage.setItem).not.toHaveBeenCalled();
    expect(sessionStorage.getItem).not.toHaveBeenCalled();
  });

  it("clones a frozen Version and copies a Scope without mutating the canonical Scope", async () => {
    const source = await createPlan(PROJECT_A);
    const scopesBefore = await listMonitoringScopesMock(PROJECT_A);
    const sourceScope = scopesBefore.items[0];
    expect(sourceScope).toBeDefined();

    const cloned = await cloneWorkflowPlanMock(PROJECT_A, source.plan.id, {
      name: "Independent copy",
      sourceVersionId: source.version.id,
      idempotencyKey: "clone-plan-key-0001",
    });
    expect(cloned).toMatchObject({
      databaseWrite: true,
      planChanged: true,
      idempotentReplay: false,
      sourcePlanId: source.plan.id,
      sourceVersionId: source.version.id,
      plan: {
        name: "Independent copy",
        sourcePlanId: source.plan.id,
        sourceVersionId: source.version.id,
        currentVersionNumber: 1,
      },
      version: {
        workflowPlanId: cloned.plan.id,
        versionNumber: 1,
        editableInput: source.version.editableInput,
      },
    });
    expect(cloned.plan.id).not.toBe(source.plan.id);
    expect(cloned.version.id).not.toBe(source.version.id);

    const replay = await cloneWorkflowPlanMock(PROJECT_A, source.plan.id, {
      name: "Independent copy",
      sourceVersionId: source.version.id,
      idempotencyKey: "clone-plan-key-0001",
    });
    expect(replay).toMatchObject({
      databaseWrite: false,
      planChanged: false,
      idempotentReplay: true,
      plan: { id: cloned.plan.id },
    });

    const copied = await copyMonitoringScopeTemplateMock(
      PROJECT_A,
      sourceScope!.id,
      {
        sourceVersionId: source.version.id,
        idempotencyKey: "copy-scope-key-0001",
      },
    );
    expect(copied).toMatchObject({
      databaseWrite: true,
      idempotentReplay: false,
      template: {
        sourceScopeId: sourceScope!.id,
        sourcePlanId: source.plan.id,
        sourceVersionId: source.version.id,
        scopeKey: sourceScope!.scopeKey,
      },
    });
    expect(copied.template.id).not.toBe(sourceScope!.id);
    expect((await listMonitoringScopesMock(PROJECT_A)).total).toBe(
      scopesBefore.total,
    );

    const scopeReplay = await copyMonitoringScopeTemplateMock(
      PROJECT_A,
      sourceScope!.id,
      {
        sourceVersionId: source.version.id,
        idempotencyKey: "copy-scope-key-0001",
      },
    );
    expect(scopeReplay).toMatchObject({
      databaseWrite: false,
      idempotentReplay: true,
      template: { id: copied.template.id },
    });

    const changedInput: PlanningInput = {
      ...source.version.editableInput,
      requiredFields: [
        ...source.version.editableInput.requiredFields,
        "comments",
      ],
    };
    const changedPreview = await buildMockWorkflowPlanPreview(
      PROJECT_A,
      changedInput,
    );
    const secondVersion = await createWorkflowVersionMock(
      PROJECT_A,
      source.plan.id,
      {
        previewInput: changedInput,
        expectedPreviewFingerprint: changedPreview.previewFingerprint,
        expectedCurrentVersionId: source.version.id,
        idempotencyKey: "copy-scope-version-key-0001",
      },
    );
    await expect(
      copyMonitoringScopeTemplateMock(PROJECT_A, sourceScope!.id, {
        sourceVersionId: secondVersion.version.id,
        idempotencyKey: "copy-scope-key-0001",
      }),
    ).rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
  });

  it("implements replay, key conflict, version conflict, semantic no-op, and A to B to A v3", async () => {
    const first = await createPlan(PROJECT_A);
    const firstReplay = await createPlan(PROJECT_A);

    expect(firstReplay).toMatchObject({
      databaseWrite: false,
      planChanged: false,
      outcome: "created",
      idempotentReplay: true,
      plan: { id: first.plan.id },
      version: { id: first.version.id },
    });

    const firstInput = planningInput("running shoes");
    const firstPreview = await buildMockWorkflowPlanPreview(
      PROJECT_A,
      firstInput,
    );
    await expect(
      createWorkflowPlanMock(PROJECT_A, {
        name: "Different request",
        previewInput: firstInput,
        expectedPreviewFingerprint: firstPreview.previewFingerprint,
        idempotencyKey: "create-plan-key-0001",
      }),
    ).rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });

    const secondInput = await versionInput(
      PROJECT_A,
      "trail shoes",
      first.version.id,
      "create-version-key-0002",
    );
    const second = await createWorkflowVersionMock(
      PROJECT_A,
      first.plan.id,
      secondInput,
    );
    expect(second).toMatchObject({
      outcome: "created",
      planChanged: true,
      version: { versionNumber: 2 },
    });

    const noOpInput = await versionInput(
      PROJECT_A,
      "trail shoes",
      second.version.id,
      "no-op-version-key-0003",
    );
    const noOp = await createWorkflowVersionMock(
      PROJECT_A,
      first.plan.id,
      noOpInput,
    );
    const noOpReplay = await createWorkflowVersionMock(
      PROJECT_A,
      first.plan.id,
      noOpInput,
    );
    expect(noOp).toMatchObject({
      databaseWrite: true,
      planChanged: false,
      outcome: "semantic_no_op",
      idempotentReplay: false,
      version: { id: second.version.id, versionNumber: 2 },
    });
    expect(noOpReplay).toMatchObject({
      databaseWrite: false,
      planChanged: false,
      outcome: "semantic_no_op",
      idempotentReplay: true,
      version: { id: second.version.id },
    });
    expect(
      (await listWorkflowPlanVersionsMock(PROJECT_A, first.plan.id)).items,
    ).toHaveLength(2);

    const changedSameKey = await versionInput(
      PROJECT_A,
      "road shoes",
      second.version.id,
      "no-op-version-key-0003",
    );
    await expect(
      createWorkflowVersionMock(PROJECT_A, first.plan.id, changedSameKey),
    ).rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });

    const staleExpectedVersion = await versionInput(
      PROJECT_A,
      "road shoes",
      first.version.id,
      "version-conflict-key-0004",
    );
    await expect(
      createWorkflowVersionMock(PROJECT_A, first.plan.id, staleExpectedVersion),
    ).rejects.toMatchObject({ status: 409, code: "version_conflict" });

    const backToFirstInput = await versionInput(
      PROJECT_A,
      "running shoes",
      second.version.id,
      "back-to-a-key-0005",
    );
    const third = await createWorkflowVersionMock(
      PROJECT_A,
      first.plan.id,
      backToFirstInput,
    );
    const replayAfterPlanAdvanced = await createPlan(PROJECT_A);
    const history = await listWorkflowPlanVersionsMock(
      PROJECT_A,
      first.plan.id,
    );
    expect(third).toMatchObject({
      outcome: "created",
      version: {
        versionNumber: 3,
        previewFingerprint: first.version.previewFingerprint,
      },
    });
    expect(history.items.map((item) => item.versionNumber)).toEqual([3, 2, 1]);
    expect(replayAfterPlanAdvanced).toMatchObject({
      idempotentReplay: true,
      plan: { currentVersionId: first.version.id, currentVersionNumber: 1 },
      version: { id: first.version.id, versionNumber: 1 },
    });
  });

  it("rejects a stale preview fingerprint without persisting a plan", async () => {
    const input = planningInput("running shoes");
    await expect(
      createWorkflowPlanMock(PROJECT_A, {
        name: "Stale preview",
        previewInput: input,
        expectedPreviewFingerprint: `sha256:${"0".repeat(64)}`,
        idempotencyKey: "stale-preview-key-0001",
      }),
    ).rejects.toMatchObject({ status: 409, code: "preview_stale" });
    expect(await listWorkflowPlansMock(PROJECT_A)).toMatchObject({ total: 0 });
  });

  it("keeps one-shot save-time stale and conflict triggers fixture-only", async () => {
    const normal = await createPlan(
      PROJECT_A,
      "e2e-version-conflict-save",
      "fixture-gate-off-create-key-0001",
    );
    const normalVersion = await createWorkflowVersionMock(
      PROJECT_A,
      normal.plan.id,
      await versionInput(
        PROJECT_A,
        "e2e-version-conflict-save",
        normal.version.id,
        "fixture-gate-off-version-key-0002",
      ),
    );
    expect(normalVersion).toMatchObject({
      outcome: "semantic_no_op",
      version: { versionNumber: 1 },
    });

    resetWorkflowPlanPersistenceMockForTests();
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "true");
    const fixtureProjectId = WORKFLOW_PLAN_PERSISTENCE_TEST_FIXTURE_PROJECT_ID;
    const first = await createPlan(
      fixtureProjectId,
      "fixture trigger baseline",
      "fixture-trigger-create-key-0001",
    );

    await expect(
      createWorkflowVersionMock(
        fixtureProjectId,
        first.plan.id,
        await versionInput(
          fixtureProjectId,
          "e2e-preview-stale-save",
          first.version.id,
          "fixture-stale-version-key-0002",
        ),
      ),
    ).rejects.toMatchObject({ status: 409, code: "preview_stale" });
    expect(
      (
        await listWorkflowPlanVersionsMock(fixtureProjectId, first.plan.id)
      ).items.map((version) => version.versionNumber),
    ).toEqual([1]);

    const staleRetry = await createWorkflowVersionMock(
      fixtureProjectId,
      first.plan.id,
      await versionInput(
        fixtureProjectId,
        "e2e-preview-stale-save",
        first.version.id,
        "fixture-stale-retry-key-0003",
      ),
    );
    expect(staleRetry).toMatchObject({
      outcome: "created",
      version: {
        versionNumber: 2,
        editableInput: {
          scopes: [{ canonicalTerm: "e2e-preview-stale-save" }],
        },
      },
    });

    const conflictPlan = await createPlan(
      fixtureProjectId,
      "fixture conflict baseline",
      "fixture-conflict-create-key-0004",
    );

    await expect(
      createWorkflowVersionMock(
        fixtureProjectId,
        conflictPlan.plan.id,
        await versionInput(
          fixtureProjectId,
          "e2e-version-conflict-save",
          conflictPlan.version.id,
          "fixture-conflict-version-key-0005",
        ),
      ),
    ).rejects.toMatchObject({
      status: 409,
      code: "version_conflict",
    });
    const afterConflict = await getWorkflowPlanMock(
      fixtureProjectId,
      conflictPlan.plan.id,
    );
    expect(afterConflict).toMatchObject({
      plan: { currentVersionNumber: 2 },
      currentVersion: {
        versionNumber: 2,
        editableInput: {
          scopes: [{ canonicalTerm: "e2e-version-conflict-remote" }],
        },
      },
    });

    const retry = await createWorkflowVersionMock(
      fixtureProjectId,
      conflictPlan.plan.id,
      await versionInput(
        fixtureProjectId,
        "e2e-version-conflict-save",
        afterConflict.plan.currentVersionId,
        "fixture-conflict-retry-key-0006",
      ),
    );
    expect(retry).toMatchObject({
      outcome: "created",
      version: {
        versionNumber: 3,
        editableInput: {
          scopes: [{ canonicalTerm: "e2e-version-conflict-save" }],
        },
      },
    });
  });

  it("returns deterministic compare facts from the store", async () => {
    const first = await createPlan(PROJECT_A);
    const second = await createWorkflowVersionMock(
      PROJECT_A,
      first.plan.id,
      await versionInput(
        PROJECT_A,
        "trail shoes",
        first.version.id,
        "compare-version-key-0002",
      ),
    );

    const changed = await compareWorkflowPlanVersionsMock(
      PROJECT_A,
      first.plan.id,
      first.version.id,
      second.version.id,
    );
    const repeated = await compareWorkflowPlanVersionsMock(
      PROJECT_A,
      first.plan.id,
      first.version.id,
      second.version.id,
    );
    const same = await compareWorkflowPlanVersionsMock(
      PROJECT_A,
      first.plan.id,
      first.version.id,
      first.version.id,
    );

    expect(changed.sameVersion).toBe(false);
    expect(changed.sections.map((section) => section.key)).toEqual([
      "scopes",
      "query_terms",
      "routes",
      "steps",
    ]);
    expect(JSON.stringify(changed.sections)).toContain('"scope_key"');
    expect(JSON.stringify(changed.sections)).not.toContain('"scopeKey"');
    expect(repeated.sections).toEqual(changed.sections);
    expect(same).toMatchObject({ sameVersion: true, sections: [] });
  });

  it("freezes canonical editable input per Version without guessing defaults from normalized scopes", async () => {
    const firstInput = planningInput("  Running Shoes  ");
    firstInput.defaultLanguages = [" FR "];
    firstInput.defaultRegions = [" CA "];
    firstInput.defaultPlatforms = ["youtube"];
    firstInput.scopes[0].languages = [" EN "];
    firstInput.scopes[0].regions = [" US "];
    firstInput.scopes[0].platforms = ["reddit"];
    const firstPreview = await buildMockWorkflowPlanPreview(
      PROJECT_A,
      firstInput,
    );
    const first = await createWorkflowPlanMock(PROJECT_A, {
      name: "Canonical editable input",
      previewInput: firstInput,
      expectedPreviewFingerprint: firstPreview.previewFingerprint,
      idempotencyKey: "editable-input-create-0001",
    });

    firstInput.defaultLanguages.push("de");
    firstInput.scopes[0].canonicalTerm = "mutated after save";

    const secondInput = planningInput("Trail Shoes");
    secondInput.defaultLanguages = [" DE "];
    secondInput.defaultRegions = [" DE "];
    secondInput.defaultPlatforms = ["youtube"];
    secondInput.scopes[0].languages = [" EN "];
    secondInput.scopes[0].regions = [" GB "];
    secondInput.scopes[0].platforms = ["reddit"];
    const secondPreview = await buildMockWorkflowPlanPreview(
      PROJECT_A,
      secondInput,
    );
    const second = await createWorkflowVersionMock(PROJECT_A, first.plan.id, {
      previewInput: secondInput,
      expectedPreviewFingerprint: secondPreview.previewFingerprint,
      expectedCurrentVersionId: first.version.id,
      idempotencyKey: "editable-input-version-0002",
    });

    const historical = (
      await getWorkflowVersionMock(PROJECT_A, first.plan.id, first.version.id)
    ).version;
    const current = (
      await getWorkflowVersionMock(PROJECT_A, first.plan.id, second.version.id)
    ).version;

    expect(historical.editableInput).toMatchObject({
      defaultLanguages: ["fr"],
      defaultRegions: ["ca"],
      defaultPlatforms: ["youtube"],
      scopes: [
        {
          scopeRef: "scope-1",
          canonicalTerm: "running shoes",
          languages: ["en"],
          regions: ["us"],
          platforms: ["reddit"],
        },
      ],
    });
    expect(current.editableInput).toMatchObject({
      defaultLanguages: ["de"],
      defaultRegions: ["de"],
      defaultPlatforms: ["youtube"],
      scopes: [
        {
          scopeRef: "scope-1",
          canonicalTerm: "trail shoes",
          languages: ["en"],
          regions: ["gb"],
          platforms: ["reddit"],
        },
      ],
    });

    const [historicalPreview, currentPreview] = await Promise.all([
      buildMockWorkflowPlanPreview(PROJECT_A, historical.editableInput),
      buildMockWorkflowPlanPreview(PROJECT_A, current.editableInput),
    ]);
    expect(historicalPreview.previewFingerprint).toBe(
      historical.previewFingerprint,
    );
    expect(currentPreview.previewFingerprint).toBe(current.previewFingerprint);
  });

  it("preserves default inheritance and collapses duplicate scopes in the canonical editable input", async () => {
    const input = planningInput("Running Shoes");
    input.scopes = [
      {
        ...input.scopes[0],
        scopeRef: "raw-scope-a",
        languages: [],
        regions: [],
        platforms: [],
      },
      {
        ...input.scopes[0],
        scopeRef: "raw-scope-b",
        languages: [],
        regions: [],
        platforms: [],
      },
    ];
    const preview = await buildMockWorkflowPlanPreview(PROJECT_A, input);
    const saved = await createWorkflowPlanMock(PROJECT_A, {
      name: "Inherited defaults",
      previewInput: input,
      expectedPreviewFingerprint: preview.previewFingerprint,
      idempotencyKey: "editable-inheritance-0001",
    });

    expect(preview.normalizedInput.scopes).toHaveLength(1);
    expect(saved.version.editableInput.scopes).toEqual([
      expect.objectContaining({
        scopeRef: "scope-1",
        canonicalTerm: "running shoes",
        languages: [],
        regions: [],
        platforms: [],
      }),
    ]);
    const rebuilt = await buildMockWorkflowPlanPreview(
      PROJECT_A,
      saved.version.editableInput,
    );
    expect(rebuilt.previewFingerprint).toBe(saved.version.previewFingerprint);
  });

  it("auto-seeds one stable two-version asset only under the fixture flag", async () => {
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "true");
    resetWorkflowPlanPersistenceMockForTests();
    await seedWorkflowPlanPersistenceMockForTests();

    const firstRead = await listWorkflowPlansMock(
      WORKFLOW_PLAN_PERSISTENCE_TEST_FIXTURE_PROJECT_ID,
    );
    expect(firstRead.total).toBe(1);
    const firstHistory = await listWorkflowPlanVersionsMock(
      WORKFLOW_PLAN_PERSISTENCE_TEST_FIXTURE_PROJECT_ID,
      firstRead.items[0].id,
    );
    expect(firstHistory.items.map((version) => version.versionNumber)).toEqual([
      2, 1,
    ]);
    expect(firstRead.items[0]).toMatchObject({
      createdAt: "2026-07-13T00:00:01.000Z",
      updatedAt: "2026-07-13T00:00:02.000Z",
    });
    const firstVersionIds = firstHistory.items.map((version) => version.id);

    resetWorkflowPlanPersistenceMockForTests();
    const secondRead = await listWorkflowPlansMock(
      WORKFLOW_PLAN_PERSISTENCE_TEST_FIXTURE_PROJECT_ID,
    );
    expect(secondRead.items[0].id).toBe(firstRead.items[0].id);
    expect(
      (
        await listWorkflowPlanVersionsMock(
          WORKFLOW_PLAN_PERSISTENCE_TEST_FIXTURE_PROJECT_ID,
          secondRead.items[0].id,
        )
      ).items.map((version) => version.id),
    ).toEqual(firstVersionIds);

    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "false");
    resetWorkflowPlanPersistenceMockForTests();
    await expect(
      seedWorkflowPlanPersistenceMockForTests(),
    ).rejects.toMatchObject({
      status: 503,
      code: "persistence_unavailable",
      message: "workflow_plan_fixture_disabled",
    });
    expect(
      await listWorkflowPlansMock(
        WORKFLOW_PLAN_PERSISTENCE_TEST_FIXTURE_PROJECT_ID,
      ),
    ).toMatchObject({ total: 0 });
  });
});
