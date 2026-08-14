import { afterEach, describe, expect, it, vi } from "vitest";

const _mockEnabled = vi.hoisted(() => {
  process.env["NEXT_PUBLIC_MOCK_API"] = "false";
  return false;
});
void _mockEnabled;

import {
  cloneWorkflowPlan,
  copyMonitoringScopeTemplate,
  compareWorkflowPlanVersions,
  createWorkflowPlan,
  createWorkflowVersion,
  getWorkflowPlan,
  getWorkflowVersion,
  listMonitoringScopes,
  listWorkflowPlans,
  listWorkflowPlanVersions,
  transitionWorkflowPlanStatus,
} from "@/lib/api/workflow-plan-persistence";
import { mapPlanningInputToDto } from "@/lib/api/workflow-plans";
import type {
  MonitoringScopeListResultDto,
  MonitoringScopeTemplateCopyResultDto,
  WorkflowPlanDetailDto,
  WorkflowPlanCloneResultDto,
  WorkflowPlanListResultDto,
  WorkflowPlanSaveResultDto,
  WorkflowPlanTransitionResultDto,
  WorkflowPlanVersionCompareDto,
  WorkflowVersionDetailDto,
  WorkflowVersionListResultDto,
} from "@/types/workflow-plan-persistence";
import type {
  PlannerJsonValue,
  PlanningInput,
  WorkflowPlanPreviewDto,
} from "@/types/workflow-planner";

const planningInput: PlanningInput = {
  flowMode: "batch_research",
  scopes: [
    {
      scopeRef: "scope-1",
      scopeType: "topic",
      canonicalTerm: "running shoes",
      aliases: [],
      includeTerms: ["road"],
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
  requiredFields: ["id", "url"],
  optionalFields: ["author"],
  budgetCeiling: null,
  rateLimitIntent: null,
  retentionIntent: { days: 30 },
  allowPartialDegradation: false,
};

const fingerprint = `sha256:${"a".repeat(64)}`;

function buildPreviewDto(): WorkflowPlanPreviewDto {
  return {
    schema_version: "workflow_plan_preview.v1",
    planner_contract_version: "workflow_planner.v1",
    project_id: "project-a",
    flow_mode: "batch_research",
    planning_status: "resolved",
    normalized_input: {
      flow_mode: "batch_research",
      scopes: [],
      schedule_intent: null,
      delivery_intent: { outputs: ["dataset"] },
      policy_profile: "market_monitoring_balanced",
      purpose: "market_research",
      required_fields: ["id", "url"],
      optional_fields: ["author"],
      budget_ceiling: null,
      rate_limit_intent: null,
      retention_intent: { days: 30 },
      allow_partial_degradation: false,
    },
    scope_ref_map: [],
    query_terms: [],
    compiled_queries: [],
    steps: [],
    route_requirements: [],
    route_plans: [],
    coverage: {
      total_requirements: 1,
      resolved_requirements: 1,
      partial_requirements: 0,
      held_requirements: 0,
    },
    budget_summary: {
      currency: "USD",
      known_selected_unit_cost: "0.01",
      unknown_count: 0,
      budget_status: "within_ceiling",
    },
    limitations: [],
    decision_trace: { semantic_entries: [], input_diagnostics: [] },
    attribution_contract: {
      matched_scope_id: "scope-key-1",
      matched_term: "running shoes",
      match_reason: "canonical",
      query_version: "reddit.query.v1",
      requirement_ref: "requirement-1",
      route_plan_ref: "route-1",
    },
    catalog_snapshot_id: "catalog-snapshot-1",
    policy_version: "policy.v1",
    mode_template_version: "batch_research.v1",
    query_versions: { reddit: "reddit.query.v1" },
    preview_fingerprint: fingerprint,
    execution_authorized: false,
    provider_call: false,
    actor_run: false,
    browser_run: false,
    llm_call: false,
    workflow_run_created: false,
    database_write: false,
    generated_at: "2026-07-13T00:00:00Z",
    request_id: "preview-request-1",
  };
}

function buildPlanDto() {
  return {
    id: "plan-1",
    workspace_id: "workspace-1",
    project_id: "project-a",
    created_by_user_id: "user-1",
    name: "Competitor monitor",
    flow_mode: "batch_research" as const,
    status: "previewed" as const,
    current_version_id: "version-2",
    current_version_number: 2,
    planning_status: "resolved" as const,
    scope_count: 1,
    query_term_count: 2,
    created_at: "2026-07-13T00:00:00Z",
    updated_at: "2026-07-13T01:00:00Z",
  };
}

function buildVersionSummaryDto(versionNumber = 2) {
  return {
    id: `version-${versionNumber}`,
    workspace_id: "workspace-1",
    project_id: "project-a",
    workflow_plan_id: "plan-1",
    created_by_user_id: "user-1",
    version_number: versionNumber,
    planning_status: "resolved" as const,
    planner_contract_version: "workflow_planner.v1",
    catalog_snapshot_id: "catalog-snapshot-1",
    policy_version: "policy.v1",
    mode_template_version: "batch_research.v1",
    query_versions: { reddit: "reddit.query.v1" },
    preview_fingerprint: fingerprint,
    created_at: `2026-07-13T0${versionNumber}:00:00Z`,
  };
}

function buildVersionDto(versionNumber = 2) {
  const editableInput = mapPlanningInputToDto(planningInput);
  if (editableInput.flow_mode !== "batch_research") {
    throw new Error("batch_planning_input_expected");
  }
  return {
    ...buildVersionSummaryDto(versionNumber),
    editable_input: {
      ...editableInput,
      schedule_intent: null,
    },
    preview: buildPreviewDto(),
  };
}

const readBoundary = {
  database_write: false as const,
  plan_changed: false as const,
  provider_call: false as const,
  actor_run: false as const,
  browser_run: false as const,
  llm_call: false as const,
  workflow_run_created: false as const,
  execution_authorized: false as const,
};

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

function requestHeaders(call: readonly unknown[]): Headers {
  const init = call[1] as RequestInit | undefined;
  return new Headers(init?.headers);
}

describe("workflow plan persistence transport", () => {
  it("creates a Plan with an Idempotency-Key and only trusted preview input", async () => {
    const response: WorkflowPlanSaveResultDto = {
      database_write: true,
      plan_changed: true,
      outcome: "created",
      idempotent_replay: false,
      provider_call: false,
      actor_run: false,
      browser_run: false,
      llm_call: false,
      workflow_run_created: false,
      execution_authorized: false,
      plan: buildPlanDto(),
      version: buildVersionDto(1),
    };
    const fetchMock = vi.fn<
      (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    >(async () => jsonResponse(response));
    vi.stubGlobal("fetch", fetchMock);

    const result = await createWorkflowPlan("project/a b", {
      name: "Competitor monitor",
      previewInput: planningInput,
      expectedPreviewFingerprint: fingerprint,
      idempotencyKey: "logical-save-key-0001",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(url).toBe(
      "http://localhost:8000/api/projects/project%2Fa%20b/workflow-plans",
    );
    expect(init).toMatchObject({ method: "POST", credentials: "include" });
    expect(
      requestHeaders(fetchMock.mock.calls[0] ?? []).get("Idempotency-Key"),
    ).toBe("logical-save-key-0001");
    const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
    expect(body).toEqual({
      name: "Competitor monitor",
      preview_input: mapPlanningInputToDto(planningInput),
      expected_preview_fingerprint: fingerprint,
    });
    expect(body).not.toHaveProperty("plan_payload");
    expect(body).not.toHaveProperty("idempotency_key");
    expect(result).toMatchObject({
      databaseWrite: true,
      planChanged: true,
      idempotentReplay: false,
      outcome: "created",
      plan: {
        workspaceId: "workspace-1",
        currentVersionId: "version-2",
        currentVersionNumber: 2,
        queryTermCount: 2,
      },
      version: {
        workflowPlanId: "plan-1",
        versionNumber: 1,
        editableInput: planningInput,
        preview: { schemaVersion: "workflow_plan_preview.v1" },
      },
    });
    expect(result.version.editableInput).not.toHaveProperty("scheduleIntent");
    expect(
      mapPlanningInputToDto(result.version.editableInput),
    ).not.toHaveProperty("schedule_intent");
  });

  it("posts an explicit local-only Plan status transition without creating a Run", async () => {
    const response: WorkflowPlanTransitionResultDto = {
      database_write: true,
      plan_changed: true,
      idempotent_replay: false,
      provider_call: false,
      actor_run: false,
      browser_run: false,
      llm_call: false,
      workflow_run_created: false,
      execution_authorized: false,
      from_status: "previewed",
      to_status: "approved",
      reason: "reviewed locally",
      plan: {
        ...buildPlanDto(),
        status: "approved",
      },
    };
    const fetchMock = vi.fn<
      (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    >(async () => jsonResponse(response));
    vi.stubGlobal("fetch", fetchMock);

    const result = await transitionWorkflowPlanStatus(
      "project/a b",
      "plan/a b",
      {
        expectedStatus: "previewed",
        toStatus: "approved",
        reason: "reviewed locally",
      },
    );

    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(url).toBe(
      "http://localhost:8000/api/projects/project%2Fa%20b/workflow-plans/plan%2Fa%20b/status-transition",
    );
    expect(init).toMatchObject({ method: "POST", credentials: "include" });
    expect(requestHeaders(fetchMock.mock.calls[0] ?? []).has("Idempotency-Key")).toBe(
      false,
    );
    expect(JSON.parse(String(init?.body))).toEqual({
      expected_status: "previewed",
      to_status: "approved",
      reason: "reviewed locally",
    });
    expect(result).toMatchObject({
      databaseWrite: true,
      planChanged: true,
      idempotentReplay: false,
      fromStatus: "previewed",
      toStatus: "approved",
      reason: "reviewed locally",
      plan: { status: "approved" },
      providerCall: false,
      actorRun: false,
      browserRun: false,
      llmCall: false,
      workflowRunCreated: false,
      executionAuthorized: false,
    });
  });

  it("posts Plan clone and Scope template copy with explicit idempotency boundaries", async () => {
    const cloneResponse: WorkflowPlanCloneResultDto = {
      database_write: true,
      plan_changed: true,
      outcome: "created",
      idempotent_replay: false,
      provider_call: false,
      actor_run: false,
      browser_run: false,
      llm_call: false,
      workflow_run_created: false,
      execution_authorized: false,
      source_plan_id: "plan-1",
      source_version_id: "version-2",
      plan: {
        ...buildPlanDto(),
        id: "plan-clone",
        name: "Independent copy",
        current_version_id: "version-clone",
        current_version_number: 1,
        source_plan_id: "plan-1",
        source_version_id: "version-2",
      },
      version: {
        ...buildVersionDto(1),
        id: "version-clone",
        workflow_plan_id: "plan-clone",
      },
    };
    const copyResponse: MonitoringScopeTemplateCopyResultDto = {
      database_write: true,
      idempotent_replay: false,
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
        id: "scope-template-1",
        workspace_id: "workspace-1",
        project_id: "project-a",
        created_by_user_id: "user-1",
        source_scope_id: "scope-1",
        source_plan_id: "plan-1",
        source_version_id: "version-2",
        scope_key: "scope-key-1",
        scope_type: "topic",
        canonical_term: "running shoes",
        aliases: [],
        include_terms: ["road"],
        exclude_terms: [],
        official_accounts: [],
        seed_urls: [],
        effective_languages: ["en"],
        effective_regions: ["US"],
        effective_platforms: ["reddit"],
        match_mode: "phrase",
        created_at: "2026-07-13T02:00:00Z",
      },
    };
    const responses = [cloneResponse, copyResponse];
    const fetchMock = vi.fn<
      (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    >(async () => jsonResponse(responses.shift()));
    vi.stubGlobal("fetch", fetchMock);

    const clone = await cloneWorkflowPlan("project/a", "plan/a", {
      name: "Independent copy",
      sourceVersionId: "version-2",
      idempotencyKey: "clone-key-0001",
    });
    const copied = await copyMonitoringScopeTemplate(
      "project/a",
      "scope/a",
      {
        sourceVersionId: "version-2",
        idempotencyKey: "scope-copy-key-0001",
      },
    );

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "http://localhost:8000/api/projects/project%2Fa/workflow-plans/plan%2Fa/clone",
      "http://localhost:8000/api/projects/project%2Fa/monitoring-scopes/scope%2Fa/copy",
    ]);
    expect(requestHeaders(fetchMock.mock.calls[0] ?? []).get("Idempotency-Key")).toBe(
      "clone-key-0001",
    );
    expect(requestHeaders(fetchMock.mock.calls[1] ?? []).get("Idempotency-Key")).toBe(
      "scope-copy-key-0001",
    );
    expect(JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body))).toEqual({
      name: "Independent copy",
      source_version_id: "version-2",
    });
    expect(JSON.parse(String((fetchMock.mock.calls[1]?.[1] as RequestInit).body))).toEqual({
      source_version_id: "version-2",
    });
    expect(clone).toMatchObject({
      databaseWrite: true,
      planChanged: true,
      sourcePlanId: "plan-1",
      sourceVersionId: "version-2",
      plan: { id: "plan-clone", sourcePlanId: "plan-1" },
    });
    expect(copied).toMatchObject({
      databaseWrite: true,
      template: {
        id: "scope-template-1",
        sourceScopeId: "scope-1",
        sourcePlanId: "plan-1",
      },
    });
  });

  it("creates a Version with an encoded Plan ID and concurrency baseline", async () => {
    const response: WorkflowPlanSaveResultDto = {
      database_write: true,
      plan_changed: true,
      outcome: "created",
      idempotent_replay: false,
      provider_call: false,
      actor_run: false,
      browser_run: false,
      llm_call: false,
      workflow_run_created: false,
      execution_authorized: false,
      plan: buildPlanDto(),
      version: buildVersionDto(),
    };
    const fetchMock = vi.fn<
      (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    >(async () => jsonResponse(response));
    vi.stubGlobal("fetch", fetchMock);

    await createWorkflowVersion("project/a", "plan/a b", {
      previewInput: planningInput,
      expectedPreviewFingerprint: fingerprint,
      expectedCurrentVersionId: "version-1",
      idempotencyKey: "logical-version-key-0001",
    });

    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(url).toBe(
      "http://localhost:8000/api/projects/project%2Fa/workflow-plans/plan%2Fa%20b/versions",
    );
    expect(init).toMatchObject({ method: "POST" });
    expect(
      requestHeaders(fetchMock.mock.calls[0] ?? []).get("Idempotency-Key"),
    ).toBe("logical-version-key-0001");
    const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
    expect(body).toEqual({
      preview_input: mapPlanningInputToDto(planningInput),
      expected_preview_fingerprint: fingerprint,
      expected_current_version_id: "version-1",
    });
    expect(body).not.toHaveProperty("name");
    expect(body).not.toHaveProperty("plan_payload");
  });

  it("maps a periodic editable_input response without dropping nested intent fields", async () => {
    const periodicInput: PlanningInput = {
      ...planningInput,
      flowMode: "periodic_monitoring",
      scheduleIntent: { cadence: "daily", timezone: "UTC" },
      budgetCeiling: { amount: "25.00", currency: "USD" },
      rateLimitIntent: { maxRequests: 100, periodSeconds: 60 },
    };
    const response: WorkflowVersionDetailDto = {
      ...readBoundary,
      project_status: "active",
      plan: buildPlanDto(),
      version: {
        ...buildVersionSummaryDto(),
        editable_input: mapPlanningInputToDto(periodicInput),
        preview: buildPreviewDto(),
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(response)),
    );

    const result = await getWorkflowVersion("project-a", "plan-1", "version-2");

    expect(result.version.editableInput).toEqual(periodicInput);
    expect(result.version.editableInput).toMatchObject({
      flowMode: "periodic_monitoring",
      scheduleIntent: { cadence: "daily", timezone: "UTC" },
      budgetCeiling: { amount: "25.00", currency: "USD" },
      rateLimitIntent: { maxRequests: 100, periodSeconds: 60 },
    });
  });

  it("uses all six GET endpoints, preserves zero pagination, and never sends Idempotency-Key", async () => {
    const planList: WorkflowPlanListResultDto = {
      ...readBoundary,
      project_status: "active",
      items: [buildPlanDto()],
      total: 1,
      limit: 0,
      offset: 0,
    };
    const planDetail: WorkflowPlanDetailDto = {
      ...readBoundary,
      project_status: "archived",
      plan: buildPlanDto(),
      current_version: buildVersionDto(),
    };
    const versionList: WorkflowVersionListResultDto = {
      ...readBoundary,
      project_status: "active",
      items: [buildVersionSummaryDto()],
      total: 1,
      limit: 25,
      offset: 0,
    };
    const versionDetail: WorkflowVersionDetailDto = {
      ...readBoundary,
      project_status: "active",
      plan: buildPlanDto(),
      version: buildVersionDto(),
    };
    const compare: WorkflowPlanVersionCompareDto = {
      ...readBoundary,
      project_status: "active",
      plan: buildPlanDto(),
      base_version: buildVersionSummaryDto(1),
      target_version: buildVersionSummaryDto(2),
      same_version: false,
      sections: [],
    };
    const scopes: MonitoringScopeListResultDto = {
      ...readBoundary,
      project_status: "active",
      items: [
        {
          id: "scope-1",
          workspace_id: "workspace-1",
          project_id: "project-a",
          created_by_user_id: "user-1",
          scope_key: "scope-key-1",
          scope_type: "topic",
          canonical_term: "running shoes",
          aliases: [],
          include_terms: ["road"],
          exclude_terms: [],
          official_accounts: [],
          seed_urls: [],
          effective_languages: ["en"],
          effective_regions: ["US"],
          effective_platforms: ["reddit"],
          match_mode: "phrase",
          created_at: "2026-07-13T00:00:00Z",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    };
    const responses = [
      planList,
      planDetail,
      versionList,
      versionDetail,
      compare,
      scopes,
    ];
    const fetchMock = vi.fn<
      (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    >(async () => jsonResponse(responses.shift()));
    vi.stubGlobal("fetch", fetchMock);

    const results = await Promise.all([
      listWorkflowPlans("project/a", { limit: 0, offset: 0 }),
      getWorkflowPlan("project/a", "plan/a"),
      listWorkflowPlanVersions("project/a", "plan/a", {
        limit: 25,
        offset: 0,
      }),
      getWorkflowVersion("project/a", "plan/a", "version/a"),
      compareWorkflowPlanVersions(
        "project/a",
        "plan/a",
        "version/base a",
        "version/target a",
      ),
      listMonitoringScopes("project/a", { limit: 50, offset: 0 }),
    ]);

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "http://localhost:8000/api/projects/project%2Fa/workflow-plans?limit=0&offset=0",
      "http://localhost:8000/api/projects/project%2Fa/workflow-plans/plan%2Fa",
      "http://localhost:8000/api/projects/project%2Fa/workflow-plans/plan%2Fa/versions?limit=25&offset=0",
      "http://localhost:8000/api/projects/project%2Fa/workflow-plans/plan%2Fa/versions/version%2Fa",
      "http://localhost:8000/api/projects/project%2Fa/workflow-plans/plan%2Fa/version-compare?base_version_id=version%2Fbase+a&target_version_id=version%2Ftarget+a",
      "http://localhost:8000/api/projects/project%2Fa/monitoring-scopes?limit=50&offset=0",
    ]);
    for (const call of fetchMock.mock.calls) {
      expect((call[1] as RequestInit | undefined)?.method).toBeUndefined();
      expect(requestHeaders(call).has("Idempotency-Key")).toBe(false);
    }
    expect(results[0]).toMatchObject({
      projectStatus: "active",
      databaseWrite: false,
      planChanged: false,
      items: [{ currentVersionNumber: 2 }],
      limit: 0,
      offset: 0,
    });
    expect(results[1]).toMatchObject({
      projectStatus: "archived",
      currentVersion: { versionNumber: 2, editableInput: planningInput },
    });
    expect(results[2]).toMatchObject({
      items: [{ workflowPlanId: "plan-1", versionNumber: 2 }],
    });
    expect(results[3]).toMatchObject({
      version: {
        editableInput: planningInput,
        preview: { previewFingerprint: fingerprint },
      },
    });
    expect(results[5]).toMatchObject({
      items: [
        {
          scopeKey: "scope-key-1",
          canonicalTerm: "running shoes",
          effectivePlatforms: ["reddit"],
        },
      ],
    });
  });

  it("maps Compare metadata while preserving arbitrary JSON before/after values", async () => {
    const before: PlannerJsonValue = {
      snake_case_key: ["unchanged", { nested_value: 1 }],
    };
    const after: PlannerJsonValue = {
      snake_case_key: ["changed", { nested_value: 2 }],
    };
    const response: WorkflowPlanVersionCompareDto = {
      ...readBoundary,
      project_status: "active",
      plan: buildPlanDto(),
      base_version: buildVersionSummaryDto(1),
      target_version: buildVersionSummaryDto(2),
      same_version: false,
      sections: [
        {
          key: "normalized_input",
          changes: [{ field: "scopes", before, after }],
        },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(response)),
    );

    const result = await compareWorkflowPlanVersions(
      "project-a",
      "plan-1",
      "version-1",
      "version-2",
    );

    expect(result).toMatchObject({
      projectStatus: "active",
      baseVersion: { versionNumber: 1 },
      targetVersion: { versionNumber: 2 },
      sameVersion: false,
      sections: [
        {
          key: "normalized_input",
          changes: [{ field: "scopes", before, after }],
        },
      ],
    });
    expect(result.sections[0]?.changes[0]?.before).toEqual(before);
    expect(result.sections[0]?.changes[0]?.after).toEqual(after);
    expect(result.sections[0]?.changes[0]?.before).toHaveProperty(
      "snake_case_key",
    );
    expect(result.sections[0]?.changes[0]?.before).not.toHaveProperty(
      "snakeCaseKey",
    );
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});
