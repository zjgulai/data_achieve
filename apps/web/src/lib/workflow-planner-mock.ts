import { ApiRequestError } from "@/lib/api/client";
import type { Project } from "@/types/project";
import type {
  NormalizedPlanningInput,
  PlannerJsonValue,
  PlanningInput,
  QueryTerm,
  RouteCandidateDecision,
  RoutePlanPreview,
  ScopeRefMapping,
  WorkflowPlanPreview,
} from "@/types/workflow-planner";

export type WorkflowPlannerMockScenario =
  | "canonical-held"
  | "synthetic-partial"
  | "synthetic-resolved"
  | "service-unavailable";

const CANONICAL_HELD_PROJECT_ID = "00000000-0000-4000-8000-000000000031";
const SYNTHETIC_PARTIAL_PROJECT_ID = "00000000-0000-4000-8000-000000000032";
const SYNTHETIC_RESOLVED_PROJECT_ID = "00000000-0000-4000-8000-000000000033";
const SERVICE_UNAVAILABLE_PROJECT_ID = "00000000-0000-4000-8000-000000000034";

const SUPPORTED_SEED_URL_HOSTS = new Set([
  "youtube.com",
  "www.youtube.com",
  "m.youtube.com",
  "youtu.be",
  "reddit.com",
  "www.reddit.com",
  "old.reddit.com",
  "x.com",
  "www.x.com",
  "twitter.com",
  "www.twitter.com",
  "instagram.com",
  "www.instagram.com",
  "threads.net",
  "www.threads.net",
  "tiktok.com",
  "www.tiktok.com",
  "m.tiktok.com",
  "linkedin.com",
  "www.linkedin.com",
]);

export const WORKFLOW_PLANNER_TEST_PROJECTS: Project[] = [
  {
    id: CANONICAL_HELD_PROJECT_ID,
    name: "Planner Fixture - Canonical Held",
    description: "Candidate-only canonical catalog preview fixture.",
    domain: "social",
    status: "active",
    intelligenceCount: 0,
    sourceCount: 0,
  },
  {
    id: SYNTHETIC_PARTIAL_PROJECT_ID,
    name: "Planner Fixture - Synthetic Partial",
    description: "Approval-required partial route preview fixture.",
    domain: "social",
    status: "active",
    intelligenceCount: 0,
    sourceCount: 0,
  },
  {
    id: SYNTHETIC_RESOLVED_PROJECT_ID,
    name: "Planner Fixture - Synthetic Resolved",
    description: "Resolved Primary, Fallback, and Shadow preview fixture.",
    domain: "social",
    status: "active",
    intelligenceCount: 0,
    sourceCount: 0,
  },
  {
    id: SERVICE_UNAVAILABLE_PROJECT_ID,
    name: "Planner Fixture - Service Unavailable",
    description: "Planner service-unavailable error fixture.",
    domain: "social",
    status: "active",
    intelligenceCount: 0,
    sourceCount: 0,
  },
];

const scoreBreakdown = {
  rawDimensions: { coverage: 5, policy: 5 },
  effectiveDimensions: { coverage: 5, policy: 5 },
  weights: { coverage: 3, policy: 2 },
  weightedScore: 25,
  traceCodes: ["fixture_score"],
};

const partialDecision = {
  assertionId: "reddit.partial.search",
  implementationId: "reddit.partial",
  capabilityStatus: "partial",
  scoreBreakdown,
  weightedScore: 25,
  routeEligible: true,
  readinessStatus: "ready",
  approvalRequired: true,
  approvalReasons: [
    {
      code: "partial_route_requires_approval",
      reason: "Partial routes require a separate execution approval.",
    },
  ],
  missingOptionalFields: ["author"],
  evidenceRefs: ["reddit.partial:evidence:fixture"],
} satisfies RouteCandidateDecision;

const verifiedDecision = {
  assertionId: "reddit.verified.search",
  implementationId: "reddit.verified",
  capabilityStatus: "verified",
  scoreBreakdown,
  weightedScore: 25,
  routeEligible: true,
  readinessStatus: "ready",
  approvalRequired: false,
  approvalReasons: [],
  missingOptionalFields: [],
  evidenceRefs: ["reddit.verified:evidence:fixture"],
} satisfies RouteCandidateDecision;

const verifiedFallbackDecision = {
  ...verifiedDecision,
  assertionId: "reddit.verified.fallback.search",
  implementationId: "reddit.verified.fallback",
  weightedScore: 20,
  scoreBreakdown: {
    ...scoreBreakdown,
    weightedScore: 20,
    traceCodes: ["fixture_fallback_score"],
  },
  evidenceRefs: ["reddit.verified.fallback:evidence:fixture"],
} satisfies RouteCandidateDecision;

const heldRoute = {
  requirementRef: "requirement-1",
  status: "held",
  primaryImplementation: null,
  fallbackImplementations: [],
  shadowRule: {
    enabled: false,
    fallbackImplementationId: null,
    sampleRate: null,
    maxItems: null,
    reason: "No execution-eligible fallback is available.",
    executionAuthorized: false,
  },
  requiredFields: ["id", "url", "text"],
  optionalFields: ["author"],
  missingOptionalFields: ["author"],
  budgetStatus: "not_applicable",
  rateLimitPolicy: null,
  retentionPolicy: { days: 30 },
  routeEligible: false,
  readinessStatus: null,
  approvalRequired: false,
  approvalReasons: [],
  policyGates: [],
  scoreBreakdown: null,
  exclusionReasons: [
    {
      code: "candidate_not_execution_eligible",
      reason: "Candidate capability assertions cannot become a Primary route.",
    },
  ],
  degradationRule: null,
  limitations: ["candidate_catalog_only"],
  executionAuthorized: false,
} satisfies RoutePlanPreview;

const partialRoute = {
  ...heldRoute,
  status: "partial",
  primaryImplementation: partialDecision,
  missingOptionalFields: ["author"],
  budgetStatus: "not_applicable",
  routeEligible: true,
  readinessStatus: "ready",
  approvalRequired: true,
  approvalReasons: partialDecision.approvalReasons,
  policyGates: [
    {
      code: "partial_degradation_allowed",
      reason: "The fixture permits a proposed partial route for review.",
    },
  ],
  scoreBreakdown,
  exclusionReasons: [],
  degradationRule: {
    code: "optional_field_degradation",
    reason: "The optional author field is not available.",
  },
  limitations: ["approval_required"],
} satisfies RoutePlanPreview;

const resolvedRoute = {
  ...heldRoute,
  status: "resolved",
  primaryImplementation: verifiedDecision,
  fallbackImplementations: [verifiedFallbackDecision],
  shadowRule: {
    enabled: true,
    fallbackImplementationId: verifiedFallbackDecision.implementationId,
    sampleRate: 0.1,
    maxItems: 10,
    reason: "Fixture-only Shadow comparison; execution remains unauthorized.",
    executionAuthorized: false,
  },
  missingOptionalFields: [],
  budgetStatus: "not_applicable",
  rateLimitPolicy: { maxRequests: 60, periodSeconds: 60 },
  routeEligible: true,
  readinessStatus: "ready",
  policyGates: [
    {
      code: "verified_primary_selected",
      reason: "A verified synthetic fixture is eligible as Primary.",
    },
  ],
  scoreBreakdown,
  exclusionReasons: [],
  limitations: ["synthetic_fixture_only"],
} satisfies RoutePlanPreview;

const partialDisallowedRoute = {
  ...heldRoute,
  exclusionReasons: [
    {
      code: "partial_degradation_not_allowed",
      reason: "Partial route proposal was not explicitly enabled.",
    },
  ],
  limitations: ["partial_degradation_not_allowed", "execution_not_authorized"],
} satisfies RoutePlanPreview;

type WorkflowPlanPreviewBase = Omit<
  WorkflowPlanPreview,
  | "planningStatus"
  | "routePlans"
  | "coverage"
  | "budgetSummary"
  | "previewFingerprint"
  | "requestId"
>;

const basePreview = {
  schemaVersion: "workflow_plan_preview.v1",
  plannerContractVersion: "workflow_planner.v1",
  projectId: CANONICAL_HELD_PROJECT_ID,
  flowMode: "batch_research",
  normalizedInput: {
    flowMode: "batch_research",
    scopes: [
      {
        scopeKey: "scope-key-1",
        sourceScopeRefs: ["scope-1"],
        scopeType: "topic",
        canonicalTerm: "running shoes",
        aliases: [],
        includeTerms: [],
        excludeTerms: [],
        officialAccounts: [],
        seedUrls: [],
        effectiveLanguages: ["en"],
        effectiveRegions: ["US"],
        effectivePlatforms: ["reddit"],
        matchMode: "phrase",
      },
    ],
    scheduleIntent: null,
    deliveryIntent: { outputs: ["dataset"] },
    policyProfile: "market_monitoring_balanced",
    purpose: "market_research",
    requiredFields: ["id", "url", "text"],
    optionalFields: ["author"],
    budgetCeiling: null,
    rateLimitIntent: null,
    retentionIntent: { days: 30 },
    allowPartialDegradation: false,
  },
  scopeRefMap: [{ scopeRef: "scope-1", scopeKey: "scope-key-1" }],
  queryTerms: [
    {
      term: "running shoes",
      normalizedTerm: "running shoes",
      scopeRef: "scope-1",
      scopeKey: "scope-key-1",
      origin: "canonical",
      status: "active",
      reason: null,
      source: "user_input",
      score: 1,
      conflictCodes: [],
    },
  ],
  compiledQueries: [
    {
      platform: "reddit",
      scopeKeys: ["scope-key-1"],
      sourceScopeRefs: ["scope-1"],
      resourceType: "content",
      operation: "search_discover",
      queryVersion: "reddit.query.v1",
      normalizedExpression: "running shoes",
      includeTerms: ["running shoes"],
      excludeTerms: [],
      accountFilters: [],
      urlInputs: [],
      limitations: ["fixture_only"],
    },
  ],
  steps: [
    {
      stepRef: "step-1",
      templateKey: "batch.search",
      sequence: 1,
      label: "Compile and route search",
      executionKind: "future_capability",
      dependsOn: [],
      platform: "reddit",
      scopeKeys: ["scope-key-1"],
      resourceType: "content",
      operation: "search_discover",
      requirementRef: "requirement-1",
      inputContract: {
        schemaVersion: "planner.step.input.v1",
        fields: [
          {
            name: "query",
            dataType: "string",
            cardinality: "one",
            required: true,
            sourceStepRef: null,
            description: "Compiled search expression.",
          },
        ],
      },
      outputContract: {
        schemaVersion: "planner.step.output.v1",
        fields: [
          {
            name: "url",
            dataType: "string",
            cardinality: "many",
            required: true,
            sourceStepRef: "step-1",
            description: "Future collected result URL.",
          },
        ],
      },
      planningStatus: "held",
      limitations: ["planning_only"],
    },
  ],
  routeRequirements: [
    {
      requirementRef: "requirement-1",
      scopeKeys: ["scope-key-1"],
      stepRefs: ["step-1"],
      platform: "reddit",
      resourceType: "content",
      operation: "search_discover",
      purpose: "market_research",
      regions: ["US"],
      requiredFields: ["id", "url", "text"],
      optionalFields: ["author"],
      budgetCeiling: null,
      freshnessRequirement: null,
      rateLimitRequirement: null,
      retentionRequirement: { days: 30 },
      allowPartialDegradation: false,
      preconditionFailures: [],
    },
  ],
  limitations: ["fixture_only", "execution_not_authorized"],
  decisionTrace: {
    semanticEntries: [
      {
        code: "fixture_route_evaluated",
        reason: "The static fixture route was evaluated.",
        scopeKeys: ["scope-key-1"],
        requirementRef: "requirement-1",
        details: { fixture: true },
      },
    ],
    inputDiagnostics: [],
  },
  attributionContract: {
    matchedScopeId: "matched_scope_id",
    matchedTerm: "matched_term",
    matchReason: "match_reason",
    queryVersion: "query_version",
    requirementRef: "requirement_ref",
    routePlanRef: "route_plan_ref",
  },
  catalogSnapshotId: "catalog.fixture.v1",
  policyVersion: "market_monitoring_balanced.v1",
  modeTemplateVersion: "batch_research.v1",
  queryVersions: { reddit: "reddit.query.v1" },
  executionAuthorized: false,
  providerCall: false,
  actorRun: false,
  browserRun: false,
  llmCall: false,
  workflowRunCreated: false,
  databaseWrite: false,
  generatedAt: "2026-07-13T00:00:00Z",
} satisfies WorkflowPlanPreviewBase;

const canonicalHeldPreview = {
  ...basePreview,
  planningStatus: "held",
  routePlans: [heldRoute],
  coverage: {
    totalRequirements: 1,
    resolvedRequirements: 0,
    partialRequirements: 0,
    heldRequirements: 1,
  },
  budgetSummary: {
    currency: "USD",
    knownSelectedUnitCost: null,
    unknownCount: 0,
    budgetStatus: "not_applicable",
  },
  previewFingerprint: `sha256:${"3".repeat(64)}`,
  requestId: "planner-mock-canonical-held",
} satisfies WorkflowPlanPreview;

const syntheticPartialPreview = {
  ...basePreview,
  projectId: SYNTHETIC_PARTIAL_PROJECT_ID,
  planningStatus: "partially_resolved",
  steps: basePreview.steps.map((step) => ({
    ...step,
    planningStatus: "partial" as const,
  })),
  routeRequirements: basePreview.routeRequirements.map((requirement) => ({
    ...requirement,
    allowPartialDegradation: true,
  })),
  routePlans: [partialRoute],
  coverage: {
    totalRequirements: 1,
    resolvedRequirements: 0,
    partialRequirements: 1,
    heldRequirements: 0,
  },
  budgetSummary: {
    currency: "USD",
    knownSelectedUnitCost: "0.0200",
    unknownCount: 0,
    budgetStatus: "not_applicable",
  },
  previewFingerprint: `sha256:${"4".repeat(64)}`,
  requestId: "planner-mock-synthetic-partial",
} satisfies WorkflowPlanPreview;

const syntheticPartialDisallowedPreview = {
  ...basePreview,
  projectId: SYNTHETIC_PARTIAL_PROJECT_ID,
  planningStatus: "held",
  routePlans: [partialDisallowedRoute],
  coverage: {
    totalRequirements: 1,
    resolvedRequirements: 0,
    partialRequirements: 0,
    heldRequirements: 1,
  },
  budgetSummary: {
    currency: "USD",
    knownSelectedUnitCost: null,
    unknownCount: 0,
    budgetStatus: "not_applicable",
  },
  previewFingerprint: `sha256:${"6".repeat(64)}`,
  requestId: "planner-mock-synthetic-partial-disallowed",
} satisfies WorkflowPlanPreview;

const syntheticResolvedPreview = {
  ...basePreview,
  projectId: SYNTHETIC_RESOLVED_PROJECT_ID,
  planningStatus: "resolved",
  steps: basePreview.steps.map((step) => ({
    ...step,
    planningStatus: "planned" as const,
  })),
  routePlans: [resolvedRoute],
  coverage: {
    totalRequirements: 1,
    resolvedRequirements: 1,
    partialRequirements: 0,
    heldRequirements: 0,
  },
  budgetSummary: {
    currency: "USD",
    knownSelectedUnitCost: "0.0100",
    unknownCount: 0,
    budgetStatus: "not_applicable",
  },
  previewFingerprint: `sha256:${"5".repeat(64)}`,
  requestId: "planner-mock-synthetic-resolved",
} satisfies WorkflowPlanPreview;

const previewByScenario = {
  "canonical-held": canonicalHeldPreview,
  "synthetic-partial": syntheticPartialPreview,
  "synthetic-resolved": syntheticResolvedPreview,
} satisfies Record<
  Exclude<WorkflowPlannerMockScenario, "service-unavailable">,
  WorkflowPlanPreview
>;

function fixtureModeEnabled(): boolean {
  return process.env.NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES === "true";
}

function resolveScenario(projectId: string): WorkflowPlannerMockScenario {
  if (!fixtureModeEnabled()) {
    return "canonical-held";
  }
  if (projectId === SYNTHETIC_PARTIAL_PROJECT_ID) {
    return "synthetic-partial";
  }
  if (projectId === SYNTHETIC_RESOLVED_PROJECT_ID) {
    return "synthetic-resolved";
  }
  if (projectId === SERVICE_UNAVAILABLE_PROJECT_ID) {
    return "service-unavailable";
  }
  return "canonical-held";
}

export async function waitForWorkflowPlannerTestDelay(
  projectId: string,
  input: PlanningInput,
): Promise<void> {
  if (!fixtureModeEnabled() || projectId !== SYNTHETIC_RESOLVED_PROJECT_ID) {
    return;
  }
  const term = input.scopes[0]?.canonicalTerm?.trim().toLowerCase();
  const delayMs =
    term === "e2e-slow-first" ? 250 : term === "e2e-fast-second" ? 10 : 0;
  if (delayMs > 0) {
    await new Promise((resolve) => globalThis.setTimeout(resolve, delayMs));
  }
}

export function resolveWorkflowPlannerMockFingerprint(
  projectId: string,
  input: PlanningInput,
  fallback: string,
): string {
  if (!fixtureModeEnabled() || projectId !== SYNTHETIC_RESOLVED_PROJECT_ID) {
    return fallback;
  }
  const term = input.scopes[0]?.canonicalTerm?.trim().toLowerCase();
  if (term === "e2e-slow-first") {
    return `sha256:${"1".repeat(64)}`;
  }
  if (term === "e2e-fast-second") {
    return `sha256:${"2".repeat(64)}`;
  }
  return fallback;
}

export async function buildMockWorkflowPlanPreview(
  projectId: string,
  input: PlanningInput,
): Promise<WorkflowPlanPreview> {
  const scenario = resolveScenario(projectId);
  if (scenario === "service-unavailable") {
    throw new ApiRequestError(503, "Workflow planner service unavailable");
  }

  const template =
    scenario === "synthetic-partial" && !input.allowPartialDegradation
      ? syntheticPartialDisallowedPreview
      : previewByScenario[scenario];
  const { normalizedInput, scopeRefMap, inputDiagnostics } =
    await normalizeMockPlanningInput(input);
  const queryTerms = buildMockQueryTerms(normalizedInput);
  const scopeKeys = normalizedInput.scopes.map((scope) => scope.scopeKey);
  const sourceScopeRefs = sortStrings(
    normalizedInput.scopes.flatMap((scope) => scope.sourceScopeRefs),
  );
  const canonicalTerms = normalizedInput.scopes.flatMap((scope) =>
    scope.canonicalTerm ? [scope.canonicalTerm] : [],
  );
  const includeTerms = sortStrings(
    normalizedInput.scopes.flatMap((scope) => scope.includeTerms),
  );
  const excludeTerms = sortStrings(
    normalizedInput.scopes.flatMap((scope) => scope.excludeTerms),
  );
  const officialAccounts = sortStrings(
    normalizedInput.scopes.flatMap((scope) => scope.officialAccounts),
  );
  const seedUrls = sortStrings(
    normalizedInput.scopes.flatMap((scope) => scope.seedUrls),
  );
  const compiledQueries = template.compiledQueries.map((query, index) =>
    index === 0
      ? {
          ...query,
          scopeKeys,
          sourceScopeRefs,
          normalizedExpression:
            canonicalTerms.join(" OR ") || query.normalizedExpression,
          includeTerms: sortStrings([...canonicalTerms, ...includeTerms]),
          excludeTerms,
          accountFilters: officialAccounts,
          urlInputs: seedUrls,
        }
      : query,
  );
  const steps = template.steps.map((step) => ({
    ...step,
    scopeKeys,
    templateKey:
      input.flowMode === "periodic_monitoring"
        ? "periodic.monitor"
        : "batch.search",
  }));
  const routeRequirements = template.routeRequirements.map((requirement) => ({
    ...requirement,
    scopeKeys,
  }));
  const decisionTrace = {
    ...template.decisionTrace,
    semanticEntries: template.decisionTrace.semanticEntries.map((entry) => ({
      ...entry,
      scopeKeys,
    })),
    inputDiagnostics: [
      ...template.decisionTrace.inputDiagnostics,
      ...inputDiagnostics,
    ],
  };
  const preview = {
    ...template,
    projectId,
    flowMode: input.flowMode,
    normalizedInput,
    scopeRefMap,
    queryTerms,
    compiledQueries,
    steps,
    routeRequirements,
    decisionTrace,
    modeTemplateVersion:
      input.flowMode === "periodic_monitoring"
        ? "periodic_monitoring.v1"
        : "batch_research.v1",
    previewFingerprint: resolveWorkflowPlannerMockFingerprint(
      projectId,
      input,
      await buildSemanticMockFingerprint(scenario, input, normalizedInput),
    ),
  } satisfies WorkflowPlanPreview;

  return preview;
}

async function buildSemanticMockFingerprint(
  scenario: Exclude<WorkflowPlannerMockScenario, "service-unavailable">,
  input: PlanningInput,
  normalizedInput: NormalizedPlanningInput,
): Promise<string> {
  const payload: PlannerJsonValue = {
    fingerprintSchemaVersion: "workflow_planner_mock_fingerprint.v1",
    scenario,
    flowMode: input.flowMode,
    scopes: normalizedInput.scopes.map((scope) => ({
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
    })),
    defaultLanguages: normalizeTermSet(input.defaultLanguages),
    defaultRegions: normalizeTermSet(input.defaultRegions),
    defaultPlatforms: sortStrings(input.defaultPlatforms),
    scheduleIntent:
      input.flowMode === "periodic_monitoring"
        ? {
            cadence: input.scheduleIntent.cadence,
            timezone: normalizeText(input.scheduleIntent.timezone),
          }
        : null,
    deliveryIntent: input.deliveryIntent
      ? { outputs: sortStrings(input.deliveryIntent.outputs) }
      : null,
    policyProfile: input.policyProfile,
    purpose: input.purpose,
    requiredFields: normalizeTermSet(input.requiredFields),
    optionalFields: normalizeTermSet(input.optionalFields),
    budgetCeiling: input.budgetCeiling,
    rateLimitIntent: input.rateLimitIntent,
    retentionIntent: input.retentionIntent,
    allowPartialDegradation: input.allowPartialDegradation,
  };
  return sha256CanonicalJson(payload);
}

function normalizeOptionalTerm(value: string | null): string | null {
  const normalized = value ? normalizeText(value) : "";
  return normalized.length > 0 ? normalized : null;
}

function normalizeTermSet(values: string[]): string[] {
  return sortStrings(values.map(normalizeText).filter(Boolean));
}

function normalizeText(value: string): string {
  return value.normalize("NFKC").trim().toLowerCase();
}

function sortStrings<T extends string>(values: T[]): T[] {
  return [...new Set(values)].sort(compareStrings);
}

function compareStrings(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
}

function canonicalJson(value: PlannerJsonValue): string {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJson).join(",")}]`;
  }
  return `{${Object.keys(value)
    .sort(compareStrings)
    .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key] ?? null)}`)
    .join(",")}}`;
}

async function sha256CanonicalJson(value: PlannerJsonValue): Promise<string> {
  if (!globalThis.crypto?.subtle) {
    throw new Error("Web Crypto SHA-256 is unavailable");
  }
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(canonicalJson(value)),
  );
  const hex = Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
  return `sha256:${hex}`;
}

type NormalizedMockScope = NormalizedPlanningInput["scopes"][number];
type SemanticMockScope = Omit<NormalizedMockScope, "scopeKey" | "sourceScopeRefs">;
type MockInputDiagnostic =
  WorkflowPlanPreview["decisionTrace"]["inputDiagnostics"][number];

async function normalizeMockPlanningInput(input: PlanningInput): Promise<{
  normalizedInput: NormalizedPlanningInput;
  scopeRefMap: ScopeRefMapping[];
  inputDiagnostics: MockInputDiagnostic[];
}> {
  const defaultLanguages = normalizeTermSet(input.defaultLanguages);
  const defaultRegions = normalizeTermSet(input.defaultRegions);
  const defaultPlatforms = sortStrings(input.defaultPlatforms);
  const candidates = await Promise.all(
    input.scopes.map(async (scope) => {
      const scopeLanguages = normalizeTermSet(scope.languages);
      const scopeRegions = normalizeTermSet(scope.regions);
      const scopePlatforms = sortStrings(scope.platforms);
      const semanticScope = {
        scopeType: scope.scopeType,
        canonicalTerm: normalizeOptionalTerm(scope.canonicalTerm),
        aliases: normalizeTermSet(scope.aliases),
        includeTerms: normalizeTermSet(scope.includeTerms),
        excludeTerms: normalizeTermSet(scope.excludeTerms),
        officialAccounts: normalizeTermSet(scope.officialAccounts),
        seedUrls: normalizeSeedUrls(scope.seedUrls),
        effectiveLanguages:
          scopeLanguages.length > 0 ? scopeLanguages : defaultLanguages,
        effectiveRegions:
          scopeRegions.length > 0 ? scopeRegions : defaultRegions,
        effectivePlatforms:
          scopePlatforms.length > 0 ? scopePlatforms : defaultPlatforms,
        matchMode: scope.matchMode ?? defaultMatchMode(scope.scopeType),
      } satisfies SemanticMockScope;
      return {
        scopeRef: scope.scopeRef,
        scopeKey: await sha256CanonicalJson(semanticScope),
        semanticScope,
      };
    }),
  );
  const scopeRefMap = candidates.map(
    ({ scopeRef, scopeKey }) => ({ scopeRef, scopeKey }) satisfies ScopeRefMapping,
  );
  const normalizedScopeByKey = new Map<string, NormalizedMockScope>();
  const inputDiagnostics: MockInputDiagnostic[] = [];
  for (const candidate of candidates) {
    for (const seedUrl of candidate.semanticScope.seedUrls) {
      if (!isSupportedSeedUrl(seedUrl)) {
        inputDiagnostics.push({
          code: "seed_url_unclassified",
          reason: "Seed URL does not match a supported platform host",
          scopeKeys: [candidate.scopeKey],
          requirementRef: null,
          details: {
            scope_ref: candidate.scopeRef,
            seed_url: seedUrl,
          },
        });
      }
    }
    const existing = normalizedScopeByKey.get(candidate.scopeKey);
    if (existing) {
      const retainedScopeRef = existing.sourceScopeRefs[0] ?? candidate.scopeRef;
      if (!existing.sourceScopeRefs.includes(candidate.scopeRef)) {
        existing.sourceScopeRefs.push(candidate.scopeRef);
      }
      inputDiagnostics.push({
        code: "duplicate_scope_collapsed",
        reason: "Semantically duplicate Scope collapsed",
        scopeKeys: [candidate.scopeKey],
        requirementRef: null,
        details: {
          scope_ref: candidate.scopeRef,
          retained_scope_ref: retainedScopeRef,
        },
      });
      continue;
    }
    normalizedScopeByKey.set(candidate.scopeKey, {
      scopeKey: candidate.scopeKey,
      sourceScopeRefs: [candidate.scopeRef],
      ...candidate.semanticScope,
    });
  }
  const scopes = [...normalizedScopeByKey.values()].sort((left, right) =>
    compareStrings(left.scopeKey, right.scopeKey),
  );
  return {
    normalizedInput: {
      flowMode: input.flowMode,
      scopes,
      scheduleIntent:
        input.flowMode === "periodic_monitoring"
          ? {
              cadence: input.scheduleIntent.cadence,
              timezone: input.scheduleIntent.timezone.normalize("NFKC").trim(),
            }
          : null,
      deliveryIntent: input.deliveryIntent
        ? { outputs: sortStrings(input.deliveryIntent.outputs) }
        : null,
      policyProfile: input.policyProfile,
      purpose: input.purpose,
      requiredFields: normalizeTermSet(input.requiredFields),
      optionalFields: normalizeTermSet(input.optionalFields),
      budgetCeiling: input.budgetCeiling,
      rateLimitIntent: input.rateLimitIntent,
      retentionIntent: input.retentionIntent,
      allowPartialDegradation: input.allowPartialDegradation,
    },
    scopeRefMap,
    inputDiagnostics,
  };
}

function buildMockQueryTerms(
  normalizedInput: NormalizedPlanningInput,
): QueryTerm[] {
  return normalizedInput.scopes.flatMap((scope) => {
    const scopeRef = scope.sourceScopeRefs[0] ?? scope.scopeKey;
    const terms: QueryTerm[] = [];
    if (scope.canonicalTerm) {
      terms.push({
        term: scope.canonicalTerm,
        normalizedTerm: scope.canonicalTerm,
        scopeRef,
        scopeKey: scope.scopeKey,
        origin: "canonical",
        status: "active",
        reason: null,
        source: "user_input",
        score: 1,
        conflictCodes: [],
      });
    }
    for (const url of scope.seedUrls) {
      terms.push({
        term: url,
        normalizedTerm: url,
        scopeRef,
        scopeKey: scope.scopeKey,
        origin: "seed_url",
        status: "active",
        reason: null,
        source: "user_input",
        score: null,
        conflictCodes: [],
      });
    }
    return terms;
  });
}

function normalizeSeedUrls(values: string[]): string[] {
  return sortStrings(values.map(normalizeSeedUrl));
}

function normalizeSeedUrl(value: string): string {
  const parsed = new URL(value.normalize("NFKC").trim());
  if (
    !["http:", "https:"].includes(parsed.protocol) ||
    parsed.username ||
    parsed.password
  ) {
    throw new Error("seed_url_invalid");
  }
  parsed.hash = "";
  parsed.searchParams.sort();
  const query = parsed.searchParams.toString();
  return `${parsed.protocol.toLowerCase()}//${parsed.host.toLowerCase()}${parsed.pathname}${query ? `?${query}` : ""}`;
}

function isSupportedSeedUrl(value: string): boolean {
  return SUPPORTED_SEED_URL_HOSTS.has(new URL(value).hostname.toLowerCase());
}

function defaultMatchMode(
  scopeType: PlanningInput["scopes"][number]["scopeType"],
): NormalizedMockScope["matchMode"] {
  return scopeType === "category" ? "hybrid" : "phrase";
}
