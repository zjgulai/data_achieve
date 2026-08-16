import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  appendWorkflowTemplateRevisionMock,
  createWorkflowVersionMock,
  createWorkflowTemplateMock,
  getWorkflowTemplateMock,
  instantiateWorkflowPlanFromTemplateMock,
  listWorkflowTemplateRevisionsMock,
  listWorkflowTemplatesMock,
  resetWorkflowPlanPersistenceMockForTests,
  updateWorkflowTemplateMetadataMock,
} from "@/lib/workflow-plan-persistence-mock";
import { createWorkflowTemplate } from "@/lib/api/workflow-plan-persistence";
import { mapPlanningInputToDto } from "@/lib/api/workflow-plans";
import { buildMockWorkflowPlanPreview } from "@/lib/workflow-planner-mock";
import type { WorkflowTemplateMutationResultDto } from "@/types/workflow-plan-persistence";
import type { PlanningInput } from "@/types/workflow-planner";

const PROJECT_ID = "10000000-0000-4000-8000-000000000101";

function definition(term = "running shoes"): PlanningInput {
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

describe("workflow template persistence mock", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_MOCK_API", "true");
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "false");
    resetWorkflowPlanPersistenceMockForTests();
  });

  afterEach(() => {
    resetWorkflowPlanPersistenceMockForTests();
    vi.unstubAllEnvs();
  });

  it("keeps revisions append-only, isolates metadata and binds instantiated Plan lineage", async () => {
    const created = await createWorkflowTemplateMock(PROJECT_ID, {
      name: "Acme template",
      templateKey: "acme-template",
      description: "Reusable",
      definition: definition(),
      idempotencyKey: "template-create-key-0001",
    });
    expect(created).toMatchObject({
      databaseWrite: true,
      idempotentReplay: false,
      outcome: "created",
    });
    expect(created.revision?.revisionNumber).toBe(1);

    const metadata = await updateWorkflowTemplateMetadataMock(
      PROJECT_ID,
      created.template.id,
      {
        expectedRevisionId: created.revision!.id,
        name: "Acme renamed",
        idempotencyKey: "template-metadata-key-0001",
      },
    );
    expect(metadata.template.name).toBe("Acme renamed");
    expect(metadata.revision).toBeNull();

    const revision = await appendWorkflowTemplateRevisionMock(
      PROJECT_ID,
      created.template.id,
      {
        expectedRevisionId: created.revision!.id,
        definition: definition("trail shoes"),
        idempotencyKey: "template-revision-key-0001",
      },
    );
    expect(revision.revision?.revisionNumber).toBe(2);
    expect(revision.revision?.id).not.toBe(created.revision?.id);
    expect(created.revision?.definition.scopes[0]?.canonicalTerm).toBe(
      "running shoes",
    );

    const instantiated = await instantiateWorkflowPlanFromTemplateMock(
      PROJECT_ID,
      created.template.id,
      {
        revisionId: created.revision!.id,
        name: "Plan from v1",
        idempotencyKey: "template-instantiate-key-0001",
      },
    );
    expect(instantiated.plan.workflowTemplateId).toBe(created.template.id);
    expect(instantiated.plan.workflowTemplateRevisionId).toBe(
      created.revision!.id,
    );
    expect(instantiated.version.workflowTemplateRevisionId).toBe(
      created.revision!.id,
    );

    expect((await listWorkflowTemplatesMock(PROJECT_ID)).total).toBe(1);
    expect(
      (await listWorkflowTemplateRevisionsMock(PROJECT_ID, created.template.id))
        .items,
    ).toHaveLength(2);
    expect(
      (await getWorkflowTemplateMock(PROJECT_ID, created.template.id))
        .currentRevision.id,
    ).toBe(revision.revision!.id);
  });

  it("scopes instantiate idempotency by Template endpoint", async () => {
    const first = await createWorkflowTemplateMock(PROJECT_ID, {
      name: "First template",
      templateKey: "first-template",
      definition: definition("first topic"),
      idempotencyKey: "template-create-first-0001",
    });
    const second = await createWorkflowTemplateMock(PROJECT_ID, {
      name: "Second template",
      templateKey: "second-template",
      definition: definition("second topic"),
      idempotencyKey: "template-create-second-0001",
    });

    const firstPlan = await instantiateWorkflowPlanFromTemplateMock(
      PROJECT_ID,
      first.template.id,
      {
        revisionId: first.revision!.id,
        name: "First instantiated plan",
        idempotencyKey: "shared-template-instantiate-key-0001",
      },
    );
    const secondPlan = await instantiateWorkflowPlanFromTemplateMock(
      PROJECT_ID,
      second.template.id,
      {
        revisionId: second.revision!.id,
        name: "Second instantiated plan",
        idempotencyKey: "shared-template-instantiate-key-0001",
      },
    );

    expect(secondPlan.plan.id).not.toBe(firstPlan.plan.id);
    expect(secondPlan.plan.workflowTemplateId).toBe(second.template.id);
    expect(secondPlan.plan.workflowTemplateRevisionId).toBe(
      second.revision!.id,
    );
  });

  it("rejects the same instantiate key with a different revision", async () => {
    const sharedDefinition = definition("same revision payload");
    const created = await createWorkflowTemplateMock(PROJECT_ID, {
      name: "Revision idempotency",
      templateKey: "revision-idempotency",
      definition: sharedDefinition,
      idempotencyKey: "template-revision-scope-create-0001",
    });
    const appended = await appendWorkflowTemplateRevisionMock(
      PROJECT_ID,
      created.template.id,
      {
        expectedRevisionId: created.revision!.id,
        definition: sharedDefinition,
        idempotencyKey: "template-revision-scope-append-0001",
      },
    );

    await instantiateWorkflowPlanFromTemplateMock(
      PROJECT_ID,
      created.template.id,
      {
        revisionId: created.revision!.id,
        name: "Plan from shared revision payload",
        idempotencyKey: "template-revision-scope-instantiate-0001",
      },
    );

    await expect(
      instantiateWorkflowPlanFromTemplateMock(PROJECT_ID, created.template.id, {
        revisionId: appended.revision!.id,
        name: "Plan from shared revision payload",
        idempotencyKey: "template-revision-scope-instantiate-0001",
      }),
    ).rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
  });

  it("replays the original instantiate response after a newer Plan version exists", async () => {
    const created = await createWorkflowTemplateMock(PROJECT_ID, {
      name: "Replay snapshot",
      templateKey: "replay-snapshot",
      definition: definition("original topic"),
      idempotencyKey: "template-replay-create-0001",
    });
    const instantiateInput = {
      revisionId: created.revision!.id,
      name: "Plan with later version",
      idempotencyKey: "template-replay-instantiate-0001",
    };
    const first = await instantiateWorkflowPlanFromTemplateMock(
      PROJECT_ID,
      created.template.id,
      instantiateInput,
    );
    const nextDefinition = definition("updated topic");
    const nextPreview = await buildMockWorkflowPlanPreview(
      PROJECT_ID,
      nextDefinition,
    );
    await createWorkflowVersionMock(PROJECT_ID, first.plan.id, {
      previewInput: nextDefinition,
      expectedPreviewFingerprint: nextPreview.previewFingerprint,
      expectedCurrentVersionId: first.version.id,
      idempotencyKey: "template-replay-version-0001",
    });

    const replay = await instantiateWorkflowPlanFromTemplateMock(
      PROJECT_ID,
      created.template.id,
      instantiateInput,
    );

    expect(replay).toMatchObject({
      idempotentReplay: true,
      plan: { currentVersionId: first.version.id },
      version: { id: first.version.id },
    });
  });

  it("posts Template create with snake_case definition and Idempotency-Key", async () => {
    const input = definition();
    const response: WorkflowTemplateMutationResultDto = {
      database_write: true,
      idempotent_replay: false,
      outcome: "created",
      provider_call: false,
      actor_run: false,
      browser_run: false,
      llm_call: false,
      workflow_run_created: false,
      execution_authorized: false,
      template: {
        provider_call: false,
        actor_run: false,
        browser_run: false,
        llm_call: false,
        workflow_run_created: false,
        execution_authorized: false,
        id: "template-1",
        workspace_id: "workspace-1",
        project_id: PROJECT_ID,
        created_by_user_id: "user-1",
        name: "Acme",
        template_key: "acme",
        description: null,
        status: "draft",
        current_revision_id: "revision-1",
        created_at: "2026-07-16T00:00:00Z",
        updated_at: "2026-07-16T00:00:00Z",
      },
      revision: {
        provider_call: false,
        actor_run: false,
        browser_run: false,
        llm_call: false,
        workflow_run_created: false,
        execution_authorized: false,
        id: "revision-1",
        workspace_id: "workspace-1",
        project_id: PROJECT_ID,
        workflow_template_id: "template-1",
        created_by_user_id: "user-1",
        revision_number: 1,
        definition: mapPlanningInputToDto(input),
        definition_fingerprint: `sha256:${"a".repeat(64)}`,
        created_at: "2026-07-16T00:00:00Z",
      },
    };
    const fetchMock = vi.fn<
      (request: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    >(
      async () =>
        new Response(JSON.stringify(response), {
          status: 201,
          headers: { "content-type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubEnv("NEXT_PUBLIC_MOCK_API", "false");
    vi.resetModules();
    const { createWorkflowTemplate: createFn } = await import(
      "@/lib/api/workflow-plan-persistence"
    );

    const result = await createFn(PROJECT_ID, {
      name: "Acme",
      templateKey: "acme",
      definition: input,
      idempotencyKey: "template-create-key-0002",
    });

    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(url).toBe(
      `http://localhost:8000/api/projects/${PROJECT_ID}/workflow-templates`,
    );
    expect(new Headers(init?.headers).get("Idempotency-Key")).toBe(
      "template-create-key-0002",
    );
    expect(JSON.parse(String(init?.body))).toEqual({
      name: "Acme",
      template_key: "acme",
      definition: mapPlanningInputToDto(input),
    });
    expect(result).toMatchObject({
      databaseWrite: true,
      template: { id: "template-1", currentRevisionId: "revision-1" },
      revision: { definition: input },
    });
  });
});
