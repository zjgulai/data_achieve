import {
  apiFetch,
  mockApiEnabled,
  type ApiValidationIssue,
} from "@/lib/api/client";
import {
  buildMockWorkflowPlanPreview,
  waitForWorkflowPlannerTestDelay,
} from "@/lib/workflow-planner-mock";
import type {
  BatchPlanningInputDto,
  CompiledPlatformQuery,
  DecisionTraceEntry,
  MonitoringScopeDraft,
  MonitoringScopeDraftDto,
  NormalizedMonitoringScope,
  NormalizedPlanningInput,
  PeriodicPlanningInputDto,
  PlanningInput,
  PlanningInputDto,
  QueryTerm,
  RateLimitIntent,
  RateLimitIntentDto,
  RouteCandidateDecision,
  RoutePlanPreview,
  RouteRequirement,
  ScoreBreakdown,
  ScopeRefMapping,
  ShadowRule,
  StepDataContract,
  WorkflowStepPreview,
  WorkflowPlanPreview,
  WorkflowPlanPreviewDto,
} from "@/types/workflow-planner";

function mapMonitoringScopeToDto(
  scope: MonitoringScopeDraft,
): MonitoringScopeDraftDto {
  return {
    scope_ref: scope.scopeRef,
    scope_type: scope.scopeType,
    canonical_term: scope.canonicalTerm,
    aliases: scope.aliases,
    include_terms: scope.includeTerms,
    exclude_terms: scope.excludeTerms,
    official_accounts: scope.officialAccounts,
    seed_urls: scope.seedUrls,
    languages: scope.languages,
    regions: scope.regions,
    platforms: scope.platforms,
    match_mode: scope.matchMode,
  };
}

function mapRateLimitIntentToDto(
  intent: RateLimitIntent | null,
): RateLimitIntentDto | null {
  return intent
    ? {
        max_requests: intent.maxRequests,
        period_seconds: intent.periodSeconds,
      }
    : null;
}

export function mapPlanningInputToDto(input: PlanningInput): PlanningInputDto {
  const base = {
    scopes: input.scopes.map(mapMonitoringScopeToDto),
    default_languages: input.defaultLanguages,
    default_regions: input.defaultRegions,
    default_platforms: input.defaultPlatforms,
    delivery_intent: input.deliveryIntent,
    policy_profile: input.policyProfile,
    purpose: input.purpose,
    required_fields: input.requiredFields,
    optional_fields: input.optionalFields,
    budget_ceiling: input.budgetCeiling,
    rate_limit_intent: mapRateLimitIntentToDto(input.rateLimitIntent),
    retention_intent: input.retentionIntent,
    allow_partial_degradation: input.allowPartialDegradation,
  };

  if (input.flowMode === "periodic_monitoring") {
    return {
      ...base,
      flow_mode: input.flowMode,
      schedule_intent: input.scheduleIntent,
    } satisfies PeriodicPlanningInputDto;
  }

  return {
    ...base,
    flow_mode: input.flowMode,
  } satisfies BatchPlanningInputDto;
}

export function mapPlannerValidationIssues(
  issues: ApiValidationIssue[],
): Record<string, string> {
  const fieldErrors: Record<string, string> = {};

  for (const issue of issues) {
    const fieldId = resolvePlannerFieldId(issue);
    if (!(fieldId in fieldErrors)) {
      fieldErrors[fieldId] = issue.msg;
    }
  }

  return fieldErrors;
}

function resolvePlannerFieldId(issue: ApiValidationIssue): string {
  const code = issue.msg.toLowerCase();
  const scopeIndex = findScopeIndex(issue.loc);

  if (code.includes("canonical_term_required") && scopeIndex !== null) {
    return `planner-scope-${scopeIndex}-canonical-term`;
  }
  if (code.includes("periodic_schedule_required")) {
    return "planner-schedule-cadence";
  }

  const loc = issue.loc[0] === "body" ? issue.loc.slice(1) : issue.loc;
  if (loc[0] === "scopes" && typeof loc[1] === "number") {
    if (loc[2] === "seed_urls" && typeof loc[3] === "number") {
      return `planner-scope-${loc[1]}-seed-url-${loc[3]}`;
    }
    if (loc[2] === "scope_type") {
      return `planner-scope-${loc[1]}-type`;
    }
    const field = typeof loc[2] === "string" ? loc[2] : "scope";
    return `planner-scope-${loc[1]}-${toKebabCase(field)}`;
  }
  if (loc[0] === "schedule_intent") {
    const field = typeof loc[1] === "string" ? loc[1] : "cadence";
    return `planner-schedule-${toKebabCase(field)}`;
  }
  const field = [...loc].reverse().find((part) => typeof part === "string");
  return typeof field === "string"
    ? `planner-${toKebabCase(field)}`
    : "planner-form";
}

function findScopeIndex(loc: Array<string | number>): number | null {
  const scopePosition = loc.indexOf("scopes");
  const index = loc[scopePosition + 1];
  return scopePosition >= 0 && typeof index === "number" ? index : null;
}

function toKebabCase(value: string): string {
  return value.replaceAll("_", "-");
}

export function mapWorkflowPlanPreview(
  response: WorkflowPlanPreviewDto,
): WorkflowPlanPreview {
  return {
    schemaVersion: response.schema_version,
    plannerContractVersion: response.planner_contract_version,
    projectId: response.project_id,
    flowMode: response.flow_mode,
    planningStatus: response.planning_status,
    normalizedInput: mapNormalizedPlanningInput(response.normalized_input),
    scopeRefMap: response.scope_ref_map.map(mapScopeRefMapping),
    queryTerms: response.query_terms.map(mapQueryTerm),
    compiledQueries: response.compiled_queries.map(mapCompiledPlatformQuery),
    steps: response.steps.map(mapWorkflowStepPreview),
    routeRequirements: response.route_requirements.map(mapRouteRequirement),
    routePlans: response.route_plans.map(mapRoutePlanPreview),
    coverage: {
      totalRequirements: response.coverage.total_requirements,
      resolvedRequirements: response.coverage.resolved_requirements,
      partialRequirements: response.coverage.partial_requirements,
      heldRequirements: response.coverage.held_requirements,
    },
    budgetSummary: {
      currency: response.budget_summary.currency,
      knownSelectedUnitCost: response.budget_summary.known_selected_unit_cost,
      unknownCount: response.budget_summary.unknown_count,
      budgetStatus: response.budget_summary.budget_status,
    },
    limitations: response.limitations,
    decisionTrace: {
      semanticEntries: response.decision_trace.semantic_entries.map(
        mapDecisionTraceEntry,
      ),
      inputDiagnostics: response.decision_trace.input_diagnostics.map(
        mapDecisionTraceEntry,
      ),
    },
    attributionContract: {
      matchedScopeId: response.attribution_contract.matched_scope_id,
      matchedTerm: response.attribution_contract.matched_term,
      matchReason: response.attribution_contract.match_reason,
      queryVersion: response.attribution_contract.query_version,
      requirementRef: response.attribution_contract.requirement_ref,
      routePlanRef: response.attribution_contract.route_plan_ref,
    },
    catalogSnapshotId: response.catalog_snapshot_id,
    policyVersion: response.policy_version,
    modeTemplateVersion: response.mode_template_version,
    queryVersions: response.query_versions,
    previewFingerprint: response.preview_fingerprint,
    executionAuthorized: response.execution_authorized,
    providerCall: response.provider_call,
    actorRun: response.actor_run,
    browserRun: response.browser_run,
    llmCall: response.llm_call,
    workflowRunCreated: response.workflow_run_created,
    databaseWrite: response.database_write,
    generatedAt: response.generated_at,
    requestId: response.request_id,
  };
}

function mapNormalizedPlanningInput(
  input: WorkflowPlanPreviewDto["normalized_input"],
): NormalizedPlanningInput {
  return {
    flowMode: input.flow_mode,
    scopes: input.scopes.map(mapNormalizedMonitoringScope),
    scheduleIntent: input.schedule_intent,
    deliveryIntent: input.delivery_intent,
    policyProfile: input.policy_profile,
    purpose: input.purpose,
    requiredFields: input.required_fields,
    optionalFields: input.optional_fields,
    budgetCeiling: input.budget_ceiling,
    rateLimitIntent: mapRateLimitIntent(input.rate_limit_intent),
    retentionIntent: input.retention_intent,
    allowPartialDegradation: input.allow_partial_degradation,
  };
}

function mapNormalizedMonitoringScope(
  scope: WorkflowPlanPreviewDto["normalized_input"]["scopes"][number],
): NormalizedMonitoringScope {
  return {
    scopeKey: scope.scope_key,
    sourceScopeRefs: scope.source_scope_refs,
    scopeType: scope.scope_type,
    canonicalTerm: scope.canonical_term,
    aliases: scope.aliases,
    includeTerms: scope.include_terms,
    excludeTerms: scope.exclude_terms,
    officialAccounts: scope.official_accounts,
    seedUrls: scope.seed_urls,
    effectiveLanguages: scope.effective_languages,
    effectiveRegions: scope.effective_regions,
    effectivePlatforms: scope.effective_platforms,
    matchMode: scope.match_mode,
  };
}

function mapScopeRefMapping(
  mapping: WorkflowPlanPreviewDto["scope_ref_map"][number],
): ScopeRefMapping {
  return {
    scopeRef: mapping.scope_ref,
    scopeKey: mapping.scope_key,
  };
}

function mapQueryTerm(
  term: WorkflowPlanPreviewDto["query_terms"][number],
): QueryTerm {
  return {
    term: term.term,
    normalizedTerm: term.normalized_term,
    scopeRef: term.scope_ref,
    scopeKey: term.scope_key,
    origin: term.origin,
    status: term.status,
    reason: term.reason,
    source: term.source,
    score: term.score,
    conflictCodes: term.conflict_codes,
  };
}

function mapCompiledPlatformQuery(
  query: WorkflowPlanPreviewDto["compiled_queries"][number],
): CompiledPlatformQuery {
  return {
    platform: query.platform,
    scopeKeys: query.scope_keys,
    sourceScopeRefs: query.source_scope_refs,
    resourceType: query.resource_type,
    operation: query.operation,
    queryVersion: query.query_version,
    normalizedExpression: query.normalized_expression,
    includeTerms: query.include_terms,
    excludeTerms: query.exclude_terms,
    accountFilters: query.account_filters,
    urlInputs: query.url_inputs,
    limitations: query.limitations,
  };
}

function mapRouteRequirement(
  requirement: WorkflowPlanPreviewDto["route_requirements"][number],
): RouteRequirement {
  return {
    requirementRef: requirement.requirement_ref,
    scopeKeys: requirement.scope_keys,
    stepRefs: requirement.step_refs,
    platform: requirement.platform,
    resourceType: requirement.resource_type,
    operation: requirement.operation,
    purpose: requirement.purpose,
    regions: requirement.regions,
    requiredFields: requirement.required_fields,
    optionalFields: requirement.optional_fields,
    budgetCeiling: requirement.budget_ceiling,
    freshnessRequirement: requirement.freshness_requirement,
    rateLimitRequirement: mapRateLimitIntent(
      requirement.rate_limit_requirement,
    ),
    retentionRequirement: requirement.retention_requirement,
    allowPartialDegradation: requirement.allow_partial_degradation,
    preconditionFailures: requirement.precondition_failures,
  };
}

function mapScoreBreakdown(
  score: NonNullable<
    WorkflowPlanPreviewDto["route_plans"][number]["score_breakdown"]
  >,
): ScoreBreakdown {
  return {
    rawDimensions: score.raw_dimensions,
    effectiveDimensions: score.effective_dimensions,
    weights: score.weights,
    weightedScore: score.weighted_score,
    traceCodes: score.trace_codes,
  };
}

function mapNullableScoreBreakdown(
  score: WorkflowPlanPreviewDto["route_plans"][number]["score_breakdown"],
): ScoreBreakdown | null {
  return score ? mapScoreBreakdown(score) : null;
}

function mapRouteCandidateDecision(
  candidate: NonNullable<
    WorkflowPlanPreviewDto["route_plans"][number]["primary_implementation"]
  >,
): RouteCandidateDecision {
  return {
    assertionId: candidate.assertion_id,
    implementationId: candidate.implementation_id,
    capabilityStatus: candidate.capability_status,
    scoreBreakdown: mapNullableScoreBreakdown(candidate.score_breakdown),
    weightedScore: candidate.weighted_score,
    routeEligible: candidate.route_eligible,
    readinessStatus: candidate.readiness_status,
    approvalRequired: candidate.approval_required,
    approvalReasons: candidate.approval_reasons,
    missingOptionalFields: candidate.missing_optional_fields,
    evidenceRefs: candidate.evidence_refs,
  };
}

function mapShadowRule(
  shadow: WorkflowPlanPreviewDto["route_plans"][number]["shadow_rule"],
): ShadowRule {
  return {
    enabled: shadow.enabled,
    fallbackImplementationId: shadow.fallback_implementation_id,
    sampleRate: shadow.sample_rate,
    maxItems: shadow.max_items,
    reason: shadow.reason,
    executionAuthorized: shadow.execution_authorized,
  };
}

function mapRoutePlanPreview(
  route: WorkflowPlanPreviewDto["route_plans"][number],
): RoutePlanPreview {
  return {
    requirementRef: route.requirement_ref,
    status: route.status,
    primaryImplementation: route.primary_implementation
      ? mapRouteCandidateDecision(route.primary_implementation)
      : null,
    fallbackImplementations: route.fallback_implementations.map(
      mapRouteCandidateDecision,
    ),
    shadowRule: mapShadowRule(route.shadow_rule),
    requiredFields: route.required_fields,
    optionalFields: route.optional_fields,
    missingOptionalFields: route.missing_optional_fields,
    budgetStatus: route.budget_status,
    rateLimitPolicy: mapRateLimitIntent(route.rate_limit_policy),
    retentionPolicy: route.retention_policy,
    routeEligible: route.route_eligible,
    readinessStatus: route.readiness_status,
    approvalRequired: route.approval_required,
    approvalReasons: route.approval_reasons,
    policyGates: route.policy_gates,
    scoreBreakdown: mapNullableScoreBreakdown(route.score_breakdown),
    exclusionReasons: route.exclusion_reasons,
    degradationRule: route.degradation_rule,
    limitations: route.limitations,
    executionAuthorized: route.execution_authorized,
  };
}

function mapStepDataContract(
  contract: WorkflowPlanPreviewDto["steps"][number]["input_contract"],
): StepDataContract {
  return {
    schemaVersion: contract.schema_version,
    fields: contract.fields.map((field) => ({
      name: field.name,
      dataType: field.data_type,
      cardinality: field.cardinality,
      required: field.required,
      sourceStepRef: field.source_step_ref,
      description: field.description,
    })),
  };
}

function mapWorkflowStepPreview(
  step: WorkflowPlanPreviewDto["steps"][number],
): WorkflowStepPreview {
  return {
    stepRef: step.step_ref,
    templateKey: step.template_key,
    sequence: step.sequence,
    label: step.label,
    executionKind: step.execution_kind,
    dependsOn: step.depends_on,
    platform: step.platform,
    scopeKeys: step.scope_keys,
    resourceType: step.resource_type,
    operation: step.operation,
    requirementRef: step.requirement_ref,
    inputContract: mapStepDataContract(step.input_contract),
    outputContract: mapStepDataContract(step.output_contract),
    planningStatus: step.planning_status,
    limitations: step.limitations,
  };
}

function mapDecisionTraceEntry(
  entry: WorkflowPlanPreviewDto["decision_trace"]["semantic_entries"][number],
): DecisionTraceEntry {
  return {
    code: entry.code,
    reason: entry.reason,
    scopeKeys: entry.scope_keys,
    requirementRef: entry.requirement_ref,
    details: entry.details,
  };
}

function mapRateLimitIntent(
  intent: RateLimitIntentDto | null,
): RateLimitIntent | null {
  return intent
    ? {
        maxRequests: intent.max_requests,
        periodSeconds: intent.period_seconds,
      }
    : null;
}

export async function previewWorkflowPlan(
  projectId: string,
  input: PlanningInput,
  options: { signal?: AbortSignal } = {},
): Promise<WorkflowPlanPreview> {
  if (mockApiEnabled) {
    await waitForWorkflowPlannerTestDelay(projectId, input);
    return buildMockWorkflowPlanPreview(projectId, input);
  }

  const response = await apiFetch<WorkflowPlanPreviewDto>(
    `/api/projects/${encodeURIComponent(projectId)}/workflow-plans/preview`,
    {
      method: "POST",
      body: JSON.stringify(mapPlanningInputToDto(input)),
      signal: options.signal,
    },
  );
  return mapWorkflowPlanPreview(response);
}
