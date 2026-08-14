import { afterEach, describe, expect, it, vi } from "vitest";

import { apiFetch, ApiRequestError } from "@/lib/api/client";
import {
  mapPlanningInputToDto,
  mapPlannerValidationIssues,
  mapWorkflowPlanPreview,
  previewWorkflowPlan,
} from "@/lib/api/workflow-plans";
import {
  buildMockWorkflowPlanPreview,
  resolveWorkflowPlannerMockFingerprint,
  waitForWorkflowPlannerTestDelay,
  WORKFLOW_PLANNER_TEST_PROJECTS,
} from "@/lib/workflow-planner-mock";
import type {
  PlanningInput,
  WorkflowPlanPreview,
  WorkflowPlanPreviewDto,
} from "@/types/workflow-planner";

const validPlanningInput: PlanningInput = {
  flowMode: "batch_research",
  scopes: [
    {
      scopeRef: "scope-1",
      scopeType: "topic",
      canonicalTerm: "running shoes",
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

function buildPreviewDto(
  knownSelectedUnitCost: string | null = "0.0123",
): WorkflowPlanPreviewDto {
  const scoreBreakdown = {
    raw_dimensions: { coverage: 5 },
    effective_dimensions: { coverage: 4 },
    weights: { coverage: 3 },
    weighted_score: 12,
    trace_codes: ["coverage_weighted"],
  };
  const primary = {
    assertion_id: "assertion-primary",
    implementation_id: "reddit.primary",
    capability_status: "verified" as const,
    score_breakdown: scoreBreakdown,
    weighted_score: 12,
    route_eligible: true,
    readiness_status: "ready" as const,
    approval_required: false,
    approval_reasons: [],
    missing_optional_fields: [],
    evidence_refs: ["evidence-primary"],
  };

  return {
    schema_version: "workflow_plan_preview.v1",
    planner_contract_version: "workflow_planner.v1",
    project_id: "project-a",
    flow_mode: "batch_research",
    planning_status: "resolved",
    normalized_input: {
      flow_mode: "batch_research",
      scopes: [
        {
          scope_key: "scope-key-1",
          source_scope_refs: ["scope-1"],
          scope_type: "topic",
          canonical_term: "running shoes",
          aliases: ["trainers"],
          include_terms: ["road"],
          exclude_terms: ["used"],
          official_accounts: ["brand"],
          seed_urls: ["https://example.invalid/seed"],
          effective_languages: ["en"],
          effective_regions: ["US"],
          effective_platforms: ["reddit"],
          match_mode: "phrase",
        },
      ],
      schedule_intent: null,
      delivery_intent: { outputs: ["dataset"] },
      policy_profile: "market_monitoring_balanced",
      purpose: "market_research",
      required_fields: ["id", "url", "text"],
      optional_fields: ["author"],
      budget_ceiling: { amount: "12.50", currency: "USD" },
      rate_limit_intent: { max_requests: 10, period_seconds: 60 },
      retention_intent: { days: 30 },
      allow_partial_degradation: false,
    },
    scope_ref_map: [{ scope_ref: "scope-1", scope_key: "scope-key-1" }],
    query_terms: [
      {
        term: "running shoes",
        normalized_term: "running shoes",
        scope_ref: "scope-1",
        scope_key: "scope-key-1",
        origin: "canonical",
        status: "active",
        reason: null,
        source: "user",
        score: 1,
        conflict_codes: [],
      },
    ],
    compiled_queries: [
      {
        platform: "reddit",
        scope_keys: ["scope-key-1"],
        source_scope_refs: ["scope-1"],
        resource_type: "content",
        operation: "search_discover",
        query_version: "reddit.query.v1",
        normalized_expression: "running shoes",
        include_terms: ["running shoes"],
        exclude_terms: ["used"],
        account_filters: ["brand"],
        url_inputs: ["https://example.invalid/seed"],
        limitations: ["fixture_only"],
      },
    ],
    steps: [
      {
        step_ref: "step-1",
        template_key: "batch.search",
        sequence: 1,
        label: "Search Reddit",
        execution_kind: "future_capability",
        depends_on: [],
        platform: "reddit",
        scope_keys: ["scope-key-1"],
        resource_type: "content",
        operation: "search_discover",
        requirement_ref: "requirement-1",
        input_contract: {
          schema_version: "step-input.v1",
          fields: [
            {
              name: "query",
              data_type: "string",
              cardinality: "one",
              required: true,
              source_step_ref: null,
              description: "Compiled query",
            },
          ],
        },
        output_contract: {
          schema_version: "step-output.v1",
          fields: [
            {
              name: "url",
              data_type: "string",
              cardinality: "many",
              required: true,
              source_step_ref: "step-1",
              description: "Result URL",
            },
          ],
        },
        planning_status: "planned",
        limitations: [],
      },
    ],
    route_requirements: [
      {
        requirement_ref: "requirement-1",
        scope_keys: ["scope-key-1"],
        step_refs: ["step-1"],
        platform: "reddit",
        resource_type: "content",
        operation: "search_discover",
        purpose: "market_research",
        regions: ["US"],
        required_fields: ["id", "url", "text"],
        optional_fields: ["author"],
        budget_ceiling: { amount: "12.50", currency: "USD" },
        freshness_requirement: "daily",
        rate_limit_requirement: { max_requests: 10, period_seconds: 60 },
        retention_requirement: { days: 30 },
        allow_partial_degradation: false,
        precondition_failures: [
          { code: "fixture_notice", reason: "Fixture only" },
        ],
      },
    ],
    route_plans: [
      {
        requirement_ref: "requirement-1",
        status: "resolved",
        primary_implementation: primary,
        fallback_implementations: [
          {
            ...primary,
            assertion_id: "assertion-fallback",
            implementation_id: "reddit.fallback",
            capability_status: "partial",
            approval_required: true,
            approval_reasons: [
              { code: "partial_approval", reason: "Approval required" },
            ],
            missing_optional_fields: ["author"],
          },
        ],
        shadow_rule: {
          enabled: true,
          fallback_implementation_id: "reddit.fallback",
          sample_rate: 0.1,
          max_items: 10,
          reason: "Compare routes",
          execution_authorized: false,
        },
        required_fields: ["id", "url", "text"],
        optional_fields: ["author"],
        missing_optional_fields: [],
        budget_status: "within_ceiling",
        rate_limit_policy: { max_requests: 10, period_seconds: 60 },
        retention_policy: { days: 30 },
        route_eligible: true,
        readiness_status: "ready",
        approval_required: false,
        approval_reasons: [],
        policy_gates: [{ code: "policy_passed", reason: "Policy passed" }],
        score_breakdown: scoreBreakdown,
        exclusion_reasons: [],
        degradation_rule: {
          code: "degradation_disabled",
          reason: "No degradation",
        },
        limitations: ["fixture_only"],
        execution_authorized: false,
      },
    ],
    coverage: {
      total_requirements: 1,
      resolved_requirements: 1,
      partial_requirements: 0,
      held_requirements: 0,
    },
    budget_summary: {
      currency: "USD",
      known_selected_unit_cost: knownSelectedUnitCost,
      unknown_count: 0,
      budget_status: "within_ceiling",
    },
    limitations: ["fixture_only"],
    decision_trace: {
      semantic_entries: [
        {
          code: "route_resolved",
          reason: "Verified route selected",
          scope_keys: ["scope-key-1"],
          requirement_ref: "requirement-1",
          details: { weighted_score: 12 },
        },
      ],
      input_diagnostics: [
        {
          code: "scope_received",
          reason: "Scope accepted",
          scope_keys: ["scope-key-1"],
          requirement_ref: null,
          details: { scope_ref: "scope-1" },
        },
      ],
    },
    attribution_contract: {
      matched_scope_id: "matched_scope_id",
      matched_term: "matched_term",
      match_reason: "match_reason",
      query_version: "query_version",
      requirement_ref: "requirement_ref",
      route_plan_ref: "route_plan_ref",
    },
    catalog_snapshot_id: "catalog-snapshot-1",
    policy_version: "market_monitoring_balanced.v1",
    mode_template_version: "batch_research.v1",
    query_versions: { reddit: "reddit.query.v1" },
    preview_fingerprint: `sha256:${"a".repeat(64)}`,
    execution_authorized: false,
    provider_call: false,
    actor_run: false,
    browser_run: false,
    llm_call: false,
    workflow_run_created: false,
    database_write: false,
    generated_at: "2026-07-13T00:00:00Z",
    request_id: "request-success",
  };
}

function withCanonicalTerm(term: string): PlanningInput {
  return {
    ...validPlanningInput,
    scopes: validPlanningInput.scopes.map((scope, index) =>
      index === 0 ? { ...scope, canonicalTerm: term } : scope,
    ),
  };
}

describe("workflow plan preview api", () => {
  it("keeps the two-argument ApiRequestError constructor backward compatible", () => {
    const error = new ApiRequestError(409, "conflict");

    expect(error).toMatchObject({
      status: 409,
      message: "conflict",
      validationIssues: [],
      requestId: null,
      code: null,
      details: {},
    });
  });

  it("derives exact stable error codes from FastAPI string detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              detail: "preview_stale",
              code: "invented_error_code",
            }),
            {
              status: 409,
              headers: { "content-type": "application/json" },
            },
          ),
      ),
    );

    await expect(apiFetch("/api/test")).rejects.toMatchObject({
      message: "preview_stale",
      code: "preview_stale",
      details: {},
    });
  });

  it("keeps only allowlisted primitive recovery details", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              detail: "version_conflict",
              details: {
                workflow_plan_id: "plan-1",
                expected_current_version_id: "version-1",
                current_version_id: "version-2",
                idempotency_key: "must-not-leak",
                database_sql: "select secret",
                internal_path: "/srv/private/file.py",
                nested_payload: { token: "must-not-leak" },
              },
            }),
            {
              status: 409,
              headers: { "content-type": "application/json" },
            },
          ),
      ),
    );

    await expect(apiFetch("/api/test")).rejects.toMatchObject({
      code: "version_conflict",
      details: {
        workflowPlanId: "plan-1",
        expectedCurrentVersionId: "version-1",
        currentVersionId: "version-2",
      },
    });

    try {
      await apiFetch("/api/test");
    } catch (error) {
      expect(error).toBeInstanceOf(ApiRequestError);
      expect((error as ApiRequestError).details).not.toHaveProperty(
        "idempotencyKey",
      );
      expect((error as ApiRequestError).details).not.toHaveProperty(
        "databaseSql",
      );
      expect(JSON.stringify((error as ApiRequestError).details)).not.toContain(
        "must-not-leak",
      );
    }
  });

  it("does not promote unknown detail text or arbitrary payload to machine metadata", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              detail: "Project not found",
              code: "invented_error_code",
              details: { current_version_id: "must-not-leak" },
            }),
            {
              status: 404,
              headers: { "content-type": "application/json" },
            },
          ),
      ),
    );

    await expect(apiFetch("/api/test")).rejects.toMatchObject({
      message: "Project not found",
      code: null,
      details: {},
    });
  });

  it("ignores recovery-shaped details for non-recovery error codes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              detail: "persistence_unavailable",
              details: { current_version_id: "must-not-leak" },
            }),
            {
              status: 503,
              headers: { "content-type": "application/json" },
            },
          ),
      ),
    );

    await expect(apiFetch("/api/test")).rejects.toMatchObject({
      code: "persistence_unavailable",
      details: {},
    });
  });

  it("preserves FastAPI validation locations and X-Request-ID", async () => {
    vi.stubEnv("NEXT_PUBLIC_MOCK_API", "false");
    vi.resetModules();
    const { previewWorkflowPlan: previewFn } = await import(
      "@/lib/api/workflow-plans"
    );
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              detail: [
                {
                  loc: ["body", "scopes", 0, "canonical_term"],
                  msg: "Field required",
                  type: "missing",
                },
              ],
            }),
            {
              status: 422,
              headers: {
                "content-type": "application/json",
                "x-request-id": "request-422",
              },
            },
          ),
      ),
    );

    await expect(
      previewFn("project-a", validPlanningInput),
    ).rejects.toMatchObject({
      status: 422,
      requestId: "request-422",
      validationIssues: [
        {
          loc: ["body", "scopes", 0, "canonical_term"],
          msg: "Field required",
          type: "missing",
        },
      ],
    } satisfies Partial<ApiRequestError>);
  });

  it("maps backend field locations to stable form ids", () => {
    expect(
      mapPlannerValidationIssues([
        {
          loc: ["body", "scopes", 0, "canonical_term"],
          msg: "Field required",
          type: "missing",
        },
        {
          loc: ["body", "scopes", 0, "platforms"],
          msg: "periodic_effective_platform_required",
          type: "value_error",
        },
      ]),
    ).toEqual({
      "planner-scope-0-canonical-term": "Field required",
      "planner-scope-0-platforms": "periodic_effective_platform_required",
    });
  });

  it("maps indexed Seed URL locations to the exact repeated-field DOM id", () => {
    expect(
      mapPlannerValidationIssues([
        {
          loc: ["body", "scopes", 2, "seed_urls", 3],
          msg: "Input should be a valid URL",
          type: "url_parsing",
        },
      ]),
    ).toEqual({
      "planner-scope-2-seed-url-3": "Input should be a valid URL",
    });
  });

  it("maps scope_type to the exact scope type DOM id", () => {
    expect(
      mapPlannerValidationIssues([
        {
          loc: ["body", "scopes", 1, "scope_type"],
          msg: "Input should be a valid scope type",
          type: "enum",
        },
      ]),
    ).toEqual({
      "planner-scope-1-type": "Input should be a valid scope type",
    });
  });

  it("maps current Pydantic model-level canonical-term errors", () => {
    expect(
      mapPlannerValidationIssues([
        {
          loc: ["body", "scopes", 0],
          msg: "Value error, canonical_term_required",
          type: "value_error",
        },
      ]),
    ).toEqual({
      "planner-scope-0-canonical-term": "Value error, canonical_term_required",
    });
  });

  it("maps current Pydantic model-level periodic schedule errors", () => {
    expect(
      mapPlannerValidationIssues([
        {
          loc: ["body"],
          msg: "Value error, periodic_schedule_required",
          type: "value_error",
        },
      ]),
    ).toEqual({
      "planner-schedule-cadence": "Value error, periodic_schedule_required",
    });
  });

  it("omits schedule_intent from batch requests", () => {
    const dto = mapPlanningInputToDto(validPlanningInput);

    expect(dto).not.toHaveProperty("schedule_intent");
    expect(Object.keys(dto)).not.toContain("schedule_intent");
  });

  it("includes periodic schedule_intent and preserves Decimal strings", () => {
    const dto = mapPlanningInputToDto({
      ...validPlanningInput,
      flowMode: "periodic_monitoring",
      scheduleIntent: { cadence: "daily", timezone: "Asia/Shanghai" },
      budgetCeiling: { amount: "12.50", currency: "USD" },
    });

    expect(dto).toMatchObject({
      flow_mode: "periodic_monitoring",
      schedule_intent: { cadence: "daily", timezone: "Asia/Shanghai" },
      budget_ceiling: { amount: "12.50", currency: "USD" },
    });
    expect(typeof dto.budget_ceiling?.amount).toBe("string");
  });

  it("retains all JSON detail messages while only exposing valid locations", async () => {
    const response = new Response(
      JSON.stringify({
        detail: [
          {
            loc: ["body", "scopes", 0, "canonical_term"],
            msg: "First issue",
            type: "missing",
          },
          { msg: "Legacy message without loc" },
        ],
      }),
      {
        status: 422,
        headers: { "content-type": "application/json" },
      },
    );
    const jsonSpy = vi.spyOn(response, "json");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => response),
    );

    await expect(apiFetch("/api/test")).rejects.toMatchObject({
      message: "First issue; Legacy message without loc",
      validationIssues: [
        {
          loc: ["body", "scopes", 0, "canonical_term"],
          msg: "First issue",
          type: "missing",
        },
      ],
    });
    expect(jsonSpy).toHaveBeenCalledTimes(1);
  });

  it.each([
    [{ detail: "Structured detail" }, "Structured detail"],
    ["JSON string detail", "JSON string detail"],
  ])("reads JSON string-shaped API errors", async (body, expectedMessage) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify(body), {
            status: 400,
            headers: { "content-type": "application/json" },
          }),
      ),
    );

    await expect(apiFetch("/api/test")).rejects.toMatchObject({
      message: expectedMessage,
      validationIssues: [],
    });
  });

  it("uses the status fallback for non-JSON errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response("upstream unavailable", {
            status: 502,
            headers: { "content-type": "text/plain" },
          }),
      ),
    );

    await expect(apiFetch("/api/test")).rejects.toMatchObject({
      message: "API request failed: 502",
      validationIssues: [],
    });
  });

  it("maps every preview layer from snake_case to camelCase", () => {
    const preview = mapWorkflowPlanPreview(buildPreviewDto());

    expect(preview).toMatchObject({
      schemaVersion: "workflow_plan_preview.v1",
      plannerContractVersion: "workflow_planner.v1",
      projectId: "project-a",
      flowMode: "batch_research",
      planningStatus: "resolved",
      catalogSnapshotId: "catalog-snapshot-1",
      policyVersion: "market_monitoring_balanced.v1",
      modeTemplateVersion: "batch_research.v1",
      queryVersions: { reddit: "reddit.query.v1" },
      previewFingerprint: `sha256:${"a".repeat(64)}`,
      executionAuthorized: false,
      providerCall: false,
      actorRun: false,
      browserRun: false,
      llmCall: false,
      workflowRunCreated: false,
      databaseWrite: false,
      generatedAt: "2026-07-13T00:00:00Z",
      requestId: "request-success",
    });
    expect(preview.normalizedInput.scopes[0]).toMatchObject({
      scopeKey: "scope-key-1",
      sourceScopeRefs: ["scope-1"],
      canonicalTerm: "running shoes",
      effectivePlatforms: ["reddit"],
      matchMode: "phrase",
    });
    expect(preview.normalizedInput.rateLimitIntent).toEqual({
      maxRequests: 10,
      periodSeconds: 60,
    });
    expect(preview.scopeRefMap[0]).toEqual({
      scopeRef: "scope-1",
      scopeKey: "scope-key-1",
    });
    expect(preview.queryTerms[0]).toMatchObject({
      normalizedTerm: "running shoes",
      scopeRef: "scope-1",
      conflictCodes: [],
    });
    expect(preview.compiledQueries[0]).toMatchObject({
      scopeKeys: ["scope-key-1"],
      sourceScopeRefs: ["scope-1"],
      resourceType: "content",
      queryVersion: "reddit.query.v1",
      normalizedExpression: "running shoes",
      accountFilters: ["brand"],
      urlInputs: ["https://example.invalid/seed"],
    });
    expect(preview.steps[0]).toMatchObject({
      stepRef: "step-1",
      templateKey: "batch.search",
      executionKind: "future_capability",
      dependsOn: [],
      scopeKeys: ["scope-key-1"],
      requirementRef: "requirement-1",
      planningStatus: "planned",
    });
    expect(preview.steps[0]?.inputContract.fields[0]).toMatchObject({
      dataType: "string",
      sourceStepRef: null,
    });
    expect(preview.routeRequirements[0]).toMatchObject({
      requirementRef: "requirement-1",
      stepRefs: ["step-1"],
      requiredFields: ["id", "url", "text"],
      freshnessRequirement: "daily",
      allowPartialDegradation: false,
      preconditionFailures: [
        { code: "fixture_notice", reason: "Fixture only" },
      ],
    });
    expect(preview.routePlans[0]).toMatchObject({
      requirementRef: "requirement-1",
      primaryImplementation: {
        assertionId: "assertion-primary",
        implementationId: "reddit.primary",
        capabilityStatus: "verified",
        routeEligible: true,
        readinessStatus: "ready",
      },
      fallbackImplementations: [
        {
          assertionId: "assertion-fallback",
          implementationId: "reddit.fallback",
          approvalRequired: true,
          missingOptionalFields: ["author"],
        },
      ],
      shadowRule: {
        enabled: true,
        fallbackImplementationId: "reddit.fallback",
        sampleRate: 0.1,
        maxItems: 10,
        executionAuthorized: false,
      },
      rateLimitPolicy: { maxRequests: 10, periodSeconds: 60 },
      routeEligible: true,
      executionAuthorized: false,
    });
    expect(preview.routePlans[0]?.scoreBreakdown).toMatchObject({
      rawDimensions: { coverage: 5 },
      effectiveDimensions: { coverage: 4 },
      weightedScore: 12,
      traceCodes: ["coverage_weighted"],
    });
    expect(preview.coverage).toEqual({
      totalRequirements: 1,
      resolvedRequirements: 1,
      partialRequirements: 0,
      heldRequirements: 0,
    });
    expect(preview.budgetSummary).toEqual({
      currency: "USD",
      knownSelectedUnitCost: "0.0123",
      unknownCount: 0,
      budgetStatus: "within_ceiling",
    });
    expect(preview.decisionTrace.semanticEntries[0]).toMatchObject({
      scopeKeys: ["scope-key-1"],
      requirementRef: "requirement-1",
      details: { weighted_score: 12 },
    });
    expect(preview.attributionContract).toEqual({
      matchedScopeId: "matched_scope_id",
      matchedTerm: "matched_term",
      matchReason: "match_reason",
      queryVersion: "query_version",
      requirementRef: "requirement_ref",
      routePlanRef: "route_plan_ref",
    });
    expect(preview).not.toHaveProperty("normalized_input");
    expect(preview.routePlans[0]).not.toHaveProperty("shadow_rule");
  });

  it("preserves null for an unknown selected unit cost", () => {
    expect(
      mapWorkflowPlanPreview(buildPreviewDto(null)).budgetSummary
        .knownSelectedUnitCost,
    ).toBeNull();
  });

  it("encodes projectId and sends the POST body and AbortSignal", async () => {
    vi.stubEnv("NEXT_PUBLIC_MOCK_API", "false");
    vi.resetModules();
    const { previewWorkflowPlan: previewFn } = await import(
      "@/lib/api/workflow-plans"
    );
    const controller = new AbortController();
    const fetchMock = vi.fn(
      async (input: string | URL | Request, init?: RequestInit) => {
        void input;
        void init;
        return new Response(JSON.stringify(buildPreviewDto()), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    await previewFn("project/a b", validPlanningInput, {
      signal: controller.signal,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(url).toBe(
      "http://localhost:8000/api/projects/project%2Fa%20b/workflow-plans/preview",
    );
    expect(init).toMatchObject({
      method: "POST",
      credentials: "include",
      signal: controller.signal,
    });
    expect(JSON.parse(String(init?.body))).toEqual(
      mapPlanningInputToDto(validPlanningInput),
    );
  });

  it("does not convert a real API failure into mock success", async () => {
    vi.stubEnv("NEXT_PUBLIC_MOCK_API", "false");
    vi.resetModules();
    const { previewWorkflowPlan: previewFn } = await import(
      "@/lib/api/workflow-plans"
    );
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "planner unavailable" }), {
            status: 503,
            headers: { "content-type": "application/json" },
          }),
      ),
    );

    await expect(
      previewFn("project-a", validPlanningInput),
    ).rejects.toMatchObject({
      status: 503,
      message: "planner unavailable",
    });
  });
});

describe("workflow planner mock fixtures", () => {
  const heldId = "00000000-0000-4000-8000-000000000031";
  const partialId = "00000000-0000-4000-8000-000000000032";
  const resolvedId = "00000000-0000-4000-8000-000000000033";
  const unavailableId = "00000000-0000-4000-8000-000000000034";

  it("keeps ordinary mock Projects unchanged while fixture mode is off", async () => {
    vi.stubEnv("NEXT_PUBLIC_MOCK_API", "true");
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "false");
    vi.resetModules();
    const { listProjects } = await import("@/lib/api/projects");

    const projects = await listProjects();

    expect(projects.map((project) => project.id)).toEqual([
      "project_osint",
      "project_competitor",
      "project_marketplace_price",
      "project_social_launch",
      "project_growth_mix",
    ]);
    expect(projects.some((project) => project.id === heldId)).toBe(false);
  });

  it("appends four exact active social fixtures only behind the fixture flag", async () => {
    vi.stubEnv("NEXT_PUBLIC_MOCK_API", "true");
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "true");
    vi.resetModules();
    const { listProjects } = await import("@/lib/api/projects");

    const projects = await listProjects();
    const fixtures = projects.filter((project) =>
      project.id.startsWith("00000000-0000-4000-8000-00000000003"),
    );

    expect(fixtures).toEqual(WORKFLOW_PLANNER_TEST_PROJECTS);
    expect(
      fixtures.map(({ id, name, domain, status }) => ({
        id,
        name,
        domain,
        status,
      })),
    ).toEqual([
      {
        id: heldId,
        name: "Planner Fixture - Canonical Held",
        domain: "social",
        status: "active",
      },
      {
        id: partialId,
        name: "Planner Fixture - Synthetic Partial",
        domain: "social",
        status: "active",
      },
      {
        id: resolvedId,
        name: "Planner Fixture - Synthetic Resolved",
        domain: "social",
        status: "active",
      },
      {
        id: unavailableId,
        name: "Planner Fixture - Service Unavailable",
        domain: "social",
        status: "active",
      },
    ]);
  });

  it("returns canonical held without inventing an executable Primary", async () => {
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "true");

    const preview = await buildMockWorkflowPlanPreview(
      heldId,
      validPlanningInput,
    );

    expect(preview.planningStatus).toBe("held");
    expect(preview.routePlans[0]?.primaryImplementation).toBeNull();
    expect(preview.routePlans[0]?.readinessStatus).toBeNull();
    expect(preview.routePlans[0]?.exclusionReasons).toContainEqual({
      code: "candidate_not_execution_eligible",
      reason: expect.any(String),
    });
    expect(preview.steps[0]?.planningStatus).toBe("held");
    expect(preview.coverage).toMatchObject({
      resolvedRequirements: 0,
      partialRequirements: 0,
      heldRequirements: 1,
    });
    expect(preview.routePlans[0]?.budgetStatus).toBe("not_applicable");
    expect(preview.budgetSummary).toMatchObject({
      knownSelectedUnitCost: null,
      unknownCount: 0,
      budgetStatus: "not_applicable",
    });
    expectPreviewSideEffectsDisabled(preview);
  });

  it("keeps synthetic partial approval-required and unauthorized", async () => {
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "true");

    const preview = await buildMockWorkflowPlanPreview(partialId, {
      ...validPlanningInput,
      allowPartialDegradation: true,
    });

    expect(preview.planningStatus).toBe("partially_resolved");
    expect(preview.routePlans[0]).toMatchObject({
      status: "partial",
      budgetStatus: "not_applicable",
      approvalRequired: true,
      executionAuthorized: false,
      primaryImplementation: {
        capabilityStatus: "partial",
        approvalRequired: true,
      },
    });
    expect(preview.steps[0]?.planningStatus).toBe("partial");
    expect(preview.coverage).toMatchObject({
      resolvedRequirements: 0,
      partialRequirements: 1,
      heldRequirements: 0,
    });
    expect(preview.budgetSummary.budgetStatus).toBe("not_applicable");
    expect(preview.routeRequirements[0]?.allowPartialDegradation).toBe(true);
    expectPreviewSideEffectsDisabled(preview);
  });

  it("fails a partial fixture closed when partial degradation is not allowed", async () => {
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "true");

    const preview = await buildMockWorkflowPlanPreview(partialId, {
      ...validPlanningInput,
      allowPartialDegradation: false,
    });

    expect(preview.planningStatus).toBe("held");
    expect(preview.normalizedInput.allowPartialDegradation).toBe(false);
    expect(preview.routeRequirements[0]?.allowPartialDegradation).toBe(false);
    expect(preview.routePlans[0]).toMatchObject({
      status: "held",
      budgetStatus: "not_applicable",
      primaryImplementation: null,
      readinessStatus: null,
      approvalRequired: false,
      executionAuthorized: false,
      exclusionReasons: [
        {
          code: "partial_degradation_not_allowed",
          reason: expect.any(String),
        },
      ],
    });
    expect(preview.budgetSummary).toMatchObject({
      knownSelectedUnitCost: null,
      unknownCount: 0,
      budgetStatus: "not_applicable",
    });
    const canonicalHeld = await buildMockWorkflowPlanPreview(
      heldId,
      validPlanningInput,
    );
    expect(preview.previewFingerprint).not.toBe(
      canonicalHeld.previewFingerprint,
    );
  });

  it("returns resolved Primary, Fallback, and enabled unauthorized Shadow", async () => {
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "true");

    const preview = await buildMockWorkflowPlanPreview(
      resolvedId,
      validPlanningInput,
    );

    expect(preview.planningStatus).toBe("resolved");
    expect(preview.routePlans[0]?.primaryImplementation).not.toBeNull();
    expect(preview.routePlans[0]?.fallbackImplementations).toHaveLength(1);
    expect(preview.routePlans[0]?.shadowRule).toMatchObject({
      enabled: true,
      fallbackImplementationId: expect.any(String),
      executionAuthorized: false,
    });
    expect(preview.steps[0]?.planningStatus).toBe("planned");
    expect(preview.coverage).toMatchObject({
      resolvedRequirements: 1,
      partialRequirements: 0,
      heldRequirements: 0,
    });
    expect(preview.routePlans[0]?.budgetStatus).toBe("not_applicable");
    expect(preview.budgetSummary.budgetStatus).toBe("not_applicable");
    expectPreviewSideEffectsDisabled(preview);
  });

  it("keeps periodic mode, template version, step key, and schedule coherent", async () => {
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "true");
    const periodicInput: PlanningInput = {
      ...validPlanningInput,
      flowMode: "periodic_monitoring",
      scheduleIntent: { cadence: "daily", timezone: "Asia/Shanghai" },
    };

    const preview = await buildMockWorkflowPlanPreview(
      resolvedId,
      periodicInput,
    );

    expect(preview.flowMode).toBe("periodic_monitoring");
    expect(preview.normalizedInput).toMatchObject({
      flowMode: "periodic_monitoring",
      scheduleIntent: { cadence: "daily", timezone: "Asia/Shanghai" },
    });
    expect(preview.modeTemplateVersion).toBe("periodic_monitoring.v1");
    expect(preview.steps[0]).toMatchObject({
      templateKey: "periodic.monitor",
      planningStatus: "planned",
    });
  });

  it("throws 503 only for the exact unavailable fixture while enabled", async () => {
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "true");
    await expect(
      buildMockWorkflowPlanPreview(unavailableId, validPlanningInput),
    ).rejects.toMatchObject({ status: 503, name: "ApiRequestError" });

    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "false");
    const preview = await buildMockWorkflowPlanPreview(
      unavailableId,
      validPlanningInput,
    );
    expect(preview.planningStatus).toBe("held");
  });

  it("limits magic fingerprints to the enabled resolved fixture", () => {
    const fallback = `sha256:${"f".repeat(64)}`;
    const slowInput = withCanonicalTerm(" E2E-SLOW-FIRST ");

    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "true");
    expect(
      resolveWorkflowPlannerMockFingerprint(resolvedId, slowInput, fallback),
    ).toBe(`sha256:${"1".repeat(64)}`);
    expect(
      resolveWorkflowPlannerMockFingerprint(partialId, slowInput, fallback),
    ).toBe(fallback);

    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "false");
    expect(
      resolveWorkflowPlannerMockFingerprint(resolvedId, slowInput, fallback),
    ).toBe(fallback);
  });

  it("preserves external Seed URLs and keeps repeated mock fingerprints stable", async () => {
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "true");
    const seedUrl = "https://external.example/path?q=running-shoes";
    const input: PlanningInput = {
      ...validPlanningInput,
      scopes: validPlanningInput.scopes.map((scope, index) =>
        index === 0 ? { ...scope, seedUrls: [seedUrl] } : scope,
      ),
    };

    const [first, second] = await Promise.all([
      buildMockWorkflowPlanPreview(resolvedId, input),
      buildMockWorkflowPlanPreview(resolvedId, input),
    ]);

    expect(first.normalizedInput.scopes[0]?.seedUrls).toEqual([seedUrl]);
    expect(first.compiledQueries[0]?.urlInputs).toEqual([seedUrl]);
    expect(first.decisionTrace.inputDiagnostics).toContainEqual({
      code: "seed_url_unclassified",
      reason: "Seed URL does not match a supported platform host",
      scopeKeys: [first.normalizedInput.scopes[0]?.scopeKey],
      requirementRef: null,
      details: { scope_ref: "scope-1", seed_url: seedUrl },
    });
    expect(first.previewFingerprint).toBe(second.previewFingerprint);
  });

  it("does not mark known supported Seed URL hosts as unclassified", async () => {
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "true");
    const input: PlanningInput = {
      ...validPlanningInput,
      scopes: validPlanningInput.scopes.map((scope, index) =>
        index === 0
          ? {
              ...scope,
              seedUrls: ["https://www.reddit.com/r/running/"],
            }
          : scope,
      ),
    };

    const preview = await buildMockWorkflowPlanPreview(resolvedId, input);

    expect(
      preview.decisionTrace.inputDiagnostics.some(
        (diagnostic) => diagnostic.code === "seed_url_unclassified",
      ),
    ).toBe(false);
  });

  it("changes fingerprints for semantic input changes but ignores scopeRef-only changes", async () => {
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "true");
    const buildInput = (
      canonicalTerm: string,
      seedUrl: string,
      scopeRef = "scope-1",
    ): PlanningInput => ({
      ...validPlanningInput,
      scopes: validPlanningInput.scopes.map((scope, index) =>
        index === 0
          ? { ...scope, scopeRef, canonicalTerm, seedUrls: [seedUrl] }
          : scope,
      ),
    });
    const baselineInput = buildInput(
      "running shoes",
      "https://external.example/seed-a",
    );

    const [baseline, repeated, changedTerm, changedSeed, changedScopeRefOnly] =
      await Promise.all([
        buildMockWorkflowPlanPreview(resolvedId, baselineInput),
        buildMockWorkflowPlanPreview(resolvedId, baselineInput),
        buildMockWorkflowPlanPreview(
          resolvedId,
          buildInput("trail shoes", "https://external.example/seed-a"),
        ),
        buildMockWorkflowPlanPreview(
          resolvedId,
          buildInput("running shoes", "https://external.example/seed-b"),
        ),
        buildMockWorkflowPlanPreview(
          resolvedId,
          buildInput(
            "running shoes",
            "https://external.example/seed-a",
            "presentation-only-ref",
          ),
        ),
      ]);

    expect(repeated.previewFingerprint).toBe(baseline.previewFingerprint);
    expect(changedTerm.previewFingerprint).not.toBe(
      baseline.previewFingerprint,
    );
    expect(changedSeed.previewFingerprint).not.toBe(
      baseline.previewFingerprint,
    );
    expect(changedScopeRefOnly.previewFingerprint).toBe(
      baseline.previewFingerprint,
    );
  });

  it("canonicalizes order, duplicates, and duplicate semantic scopes", async () => {
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "true");
    const semanticScope = {
      ...validPlanningInput.scopes[0]!,
      scopeRef: "scope-a",
      canonicalTerm: " Running Shoes ",
      aliases: ["Sneakers", "trainers"],
      includeTerms: ["Road", "daily"],
      excludeTerms: ["Used", "damaged"],
      officialAccounts: ["Brand", "Retailer"],
      seedUrls: ["https://example.invalid/b", "https://example.invalid/a"],
      languages: ["zh", "en"],
      regions: ["us", "cn"],
      platforms: ["youtube", "reddit"] as const,
    };
    const baseline: PlanningInput = {
      ...validPlanningInput,
      scopes: [{ ...semanticScope, platforms: [...semanticScope.platforms] }],
      defaultLanguages: ["zh", "en"],
      defaultRegions: ["US", "CN"],
      defaultPlatforms: ["youtube", "reddit"],
      deliveryIntent: { outputs: ["alert", "dataset"] },
      requiredFields: ["url", "id"],
      optionalFields: ["author", "score"],
    };
    const duplicateScope = {
      ...semanticScope,
      scopeRef: "presentation-ref-b",
      canonicalTerm: "running shoes",
      aliases: ["trainers", "sneakers", "Sneakers"],
      includeTerms: ["daily", "road", "Road"],
      excludeTerms: ["damaged", "used", "Used"],
      officialAccounts: ["retailer", "brand", "Brand"],
      seedUrls: [
        "https://example.invalid/a",
        "https://example.invalid/b",
        "https://example.invalid/a",
      ],
      languages: ["en", "zh", "EN"],
      regions: ["CN", "US", "us"],
      platforms: ["reddit", "youtube", "reddit"] as const,
    };
    const reorderedWithDuplicates: PlanningInput = {
      ...baseline,
      scopes: [
        { ...duplicateScope, platforms: [...duplicateScope.platforms] },
        {
          ...duplicateScope,
          scopeRef: "presentation-ref-c",
          platforms: [...duplicateScope.platforms],
        },
      ],
      defaultLanguages: ["en", "zh", "EN"],
      defaultRegions: ["cn", "US", "us"],
      defaultPlatforms: ["reddit", "youtube", "reddit"],
      deliveryIntent: { outputs: ["dataset", "alert", "dataset"] },
      requiredFields: ["id", "url", "id"],
      optionalFields: ["score", "author", "author"],
    };

    const [first, second] = await Promise.all([
      buildMockWorkflowPlanPreview(resolvedId, baseline),
      buildMockWorkflowPlanPreview(resolvedId, reorderedWithDuplicates),
    ]);

    expect(second.previewFingerprint).toBe(first.previewFingerprint);
    expect(first.normalizedInput.scopes).toHaveLength(1);
    expect(second.normalizedInput.scopes).toHaveLength(1);
    expect(second.scopeRefMap).toHaveLength(2);
    expect(
      new Set(second.scopeRefMap.map((mapping) => mapping.scopeKey)),
    ).toEqual(new Set([first.normalizedInput.scopes[0]?.scopeKey]));
    const semanticQueryTerms = (preview: WorkflowPlanPreview) =>
      preview.queryTerms.map(({ scopeRef, ...term }) => {
        void scopeRef;
        return term;
      });
    const semanticCompiledQueries = (preview: WorkflowPlanPreview) =>
      preview.compiledQueries.map(({ sourceScopeRefs, ...query }) => {
        void sourceScopeRefs;
        return query;
      });
    expect(semanticQueryTerms(second)).toEqual(semanticQueryTerms(first));
    expect(semanticCompiledQueries(second)).toEqual(
      semanticCompiledQueries(first),
    );
    expect(second.routePlans).toEqual(first.routePlans);
    expect(second.coverage).toEqual(first.coverage);
    expect(second.budgetSummary).toEqual(first.budgetSummary);
    expect(second.limitations).toEqual(first.limitations);
    const mergedScopeKey = second.normalizedInput.scopes[0]?.scopeKey;
    expect(second.compiledQueries[0]?.scopeKeys).toEqual([mergedScopeKey]);
    expect(second.steps[0]?.scopeKeys).toEqual([mergedScopeKey]);
    expect(second.routeRequirements[0]?.scopeKeys).toEqual([mergedScopeKey]);
    expect(second.decisionTrace.semanticEntries[0]?.scopeKeys).toEqual([
      mergedScopeKey,
    ]);
    const duplicateDiagnostic = second.decisionTrace.inputDiagnostics.find(
      (diagnostic) => diagnostic.code === "duplicate_scope_collapsed",
    );
    expect(duplicateDiagnostic).toMatchObject({
      scopeKeys: [second.normalizedInput.scopes[0]?.scopeKey],
      requirementRef: null,
      details: {
        scope_ref: "presentation-ref-c",
        retained_scope_ref: "presentation-ref-b",
      },
    });
    expect(
      second.decisionTrace.semanticEntries.some(
        (entry) => entry.code === "duplicate_scope_collapsed",
      ),
    ).toBe(false);
  });

  it("limits the stale-response delay to magic terms on the enabled resolved fixture", async () => {
    vi.useFakeTimers();
    vi.stubEnv("NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES", "true");

    const delayed = waitForWorkflowPlannerTestDelay(
      resolvedId,
      withCanonicalTerm("e2e-fast-second"),
    );
    let settled = false;
    void delayed.then(() => {
      settled = true;
    });
    expect(vi.getTimerCount()).toBe(1);
    await vi.advanceTimersByTimeAsync(9);
    expect(settled).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    await delayed;
    expect(settled).toBe(true);

    await waitForWorkflowPlannerTestDelay(
      partialId,
      withCanonicalTerm("e2e-slow-first"),
    );
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("workflow planner Playwright fixture gate", () => {
  it("enables fixtures only for the local webServer branch", async () => {
    vi.stubEnv("PLAYWRIGHT_BASE_URL", "");
    vi.resetModules();
    const localConfig = (await import("../../playwright.config")).default;

    expect(localConfig.webServer).toMatchObject({
      command: expect.stringContaining(
        "NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES=true",
      ),
    });

    vi.stubEnv("PLAYWRIGHT_BASE_URL", "https://external.example");
    vi.resetModules();
    const externalConfig = (await import("../../playwright.config")).default;

    expect(externalConfig.use?.baseURL).toBe("https://external.example");
    expect(externalConfig.webServer).toBeUndefined();
  });
});

function expectPreviewSideEffectsDisabled(preview: WorkflowPlanPreview) {
  expect(preview).toMatchObject({
    executionAuthorized: false,
    providerCall: false,
    actorRun: false,
    browserRun: false,
    llmCall: false,
    workflowRunCreated: false,
    databaseWrite: false,
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.useRealTimers();
});
