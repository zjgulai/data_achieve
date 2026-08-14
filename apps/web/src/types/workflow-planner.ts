import type {
  CapabilityOperation,
  CapabilityPlatform,
  CapabilityResourceType,
  CapabilityStatus,
} from "@/types/capability";

export type WorkflowPlannerMode = "periodic_monitoring" | "batch_research";
export type MonitoringScopeType =
  | "brand"
  | "category"
  | "competitor"
  | "topic"
  | "campaign";
export type WorkflowPlannerMatchMode =
  | "exact"
  | "phrase"
  | "semantic"
  | "hybrid";
export type WorkflowPlannerPolicyProfile = "market_monitoring_balanced";
export type WorkflowPlannerPurpose =
  | "brand_monitoring"
  | "market_research"
  | "competitive_research";
export type WorkflowPlannerAuthReadiness =
  | "not_required"
  | "ready"
  | "missing"
  | "not_checked";
export type WorkflowPlanningStatus =
  | "resolved"
  | "partially_resolved"
  | "held";
export type RoutePlanStatus = "resolved" | "partial" | "held";
export type WorkflowStepPlanningStatus =
  | "planned"
  | "partial"
  | "held"
  | "not_applicable";
export type WorkflowBudgetStatus =
  | "within_ceiling"
  | "exceeded"
  | "unknown"
  | "not_applicable";

export type PlannerJsonValue =
  | string
  | number
  | boolean
  | null
  | PlannerJsonValue[]
  | { [key: string]: PlannerJsonValue };

export type ScheduleIntent = {
  cadence: "hourly" | "daily" | "weekly";
  timezone: string;
};

export type ScheduleIntentDto = ScheduleIntent;

export type DeliveryIntent = {
  outputs: Array<"dataset" | "alert" | "brief">;
};

export type DeliveryIntentDto = DeliveryIntent;

export type BudgetCeiling = {
  amount: string;
  currency: "USD";
};

export type BudgetCeilingDto = BudgetCeiling;

export type RateLimitIntent = {
  maxRequests: number;
  periodSeconds: number;
};

export type RateLimitIntentDto = {
  max_requests: number;
  period_seconds: number;
};

export type RetentionIntent = {
  days: number;
};

export type RetentionIntentDto = RetentionIntent;

export type MonitoringScopeDraft = {
  scopeRef: string;
  scopeType: MonitoringScopeType;
  canonicalTerm: string | null;
  aliases: string[];
  includeTerms: string[];
  excludeTerms: string[];
  officialAccounts: string[];
  seedUrls: string[];
  languages: string[];
  regions: string[];
  platforms: CapabilityPlatform[];
  matchMode: WorkflowPlannerMatchMode | null;
};

export type MonitoringScopeDraftDto = {
  scope_ref: string;
  scope_type: MonitoringScopeType;
  canonical_term: string | null;
  aliases: string[];
  include_terms: string[];
  exclude_terms: string[];
  official_accounts: string[];
  seed_urls: string[];
  languages: string[];
  regions: string[];
  platforms: CapabilityPlatform[];
  match_mode: WorkflowPlannerMatchMode | null;
};

type PlanningInputBase = {
  scopes: MonitoringScopeDraft[];
  defaultLanguages: string[];
  defaultRegions: string[];
  defaultPlatforms: CapabilityPlatform[];
  deliveryIntent: DeliveryIntent | null;
  policyProfile: WorkflowPlannerPolicyProfile;
  purpose: WorkflowPlannerPurpose;
  requiredFields: string[];
  optionalFields: string[];
  budgetCeiling: BudgetCeiling | null;
  rateLimitIntent: RateLimitIntent | null;
  retentionIntent: RetentionIntent | null;
  allowPartialDegradation: boolean;
};

export type PeriodicPlanningInput = PlanningInputBase & {
  flowMode: "periodic_monitoring";
  scheduleIntent: ScheduleIntent;
};

export type BatchPlanningInput = PlanningInputBase & {
  flowMode: "batch_research";
  scheduleIntent?: never;
};

export type PlanningInput = PeriodicPlanningInput | BatchPlanningInput;

type PlanningInputDtoBase = {
  scopes: MonitoringScopeDraftDto[];
  default_languages: string[];
  default_regions: string[];
  default_platforms: CapabilityPlatform[];
  delivery_intent: DeliveryIntentDto | null;
  policy_profile: WorkflowPlannerPolicyProfile;
  purpose: WorkflowPlannerPurpose;
  required_fields: string[];
  optional_fields: string[];
  budget_ceiling: BudgetCeilingDto | null;
  rate_limit_intent: RateLimitIntentDto | null;
  retention_intent: RetentionIntentDto | null;
  allow_partial_degradation: boolean;
};

export type PeriodicPlanningInputDto = PlanningInputDtoBase & {
  flow_mode: "periodic_monitoring";
  schedule_intent: ScheduleIntentDto;
};

export type BatchPlanningInputDto = PlanningInputDtoBase & {
  flow_mode: "batch_research";
  schedule_intent?: never;
};

export type PlanningInputDto =
  | PeriodicPlanningInputDto
  | BatchPlanningInputDto;

export type NormalizedMonitoringScopeDto = {
  scope_key: string;
  source_scope_refs: string[];
  scope_type: MonitoringScopeType;
  canonical_term: string | null;
  aliases: string[];
  include_terms: string[];
  exclude_terms: string[];
  official_accounts: string[];
  seed_urls: string[];
  effective_languages: string[];
  effective_regions: string[];
  effective_platforms: CapabilityPlatform[];
  match_mode: WorkflowPlannerMatchMode;
};

export type NormalizedMonitoringScope = {
  scopeKey: string;
  sourceScopeRefs: string[];
  scopeType: MonitoringScopeType;
  canonicalTerm: string | null;
  aliases: string[];
  includeTerms: string[];
  excludeTerms: string[];
  officialAccounts: string[];
  seedUrls: string[];
  effectiveLanguages: string[];
  effectiveRegions: string[];
  effectivePlatforms: CapabilityPlatform[];
  matchMode: WorkflowPlannerMatchMode;
};

export type NormalizedPlanningInputDto = {
  flow_mode: WorkflowPlannerMode;
  scopes: NormalizedMonitoringScopeDto[];
  schedule_intent: ScheduleIntentDto | null;
  delivery_intent: DeliveryIntentDto | null;
  policy_profile: WorkflowPlannerPolicyProfile;
  purpose: WorkflowPlannerPurpose;
  required_fields: string[];
  optional_fields: string[];
  budget_ceiling: BudgetCeilingDto | null;
  rate_limit_intent: RateLimitIntentDto | null;
  retention_intent: RetentionIntentDto | null;
  allow_partial_degradation: boolean;
};

export type NormalizedPlanningInput = {
  flowMode: WorkflowPlannerMode;
  scopes: NormalizedMonitoringScope[];
  scheduleIntent: ScheduleIntent | null;
  deliveryIntent: DeliveryIntent | null;
  policyProfile: WorkflowPlannerPolicyProfile;
  purpose: WorkflowPlannerPurpose;
  requiredFields: string[];
  optionalFields: string[];
  budgetCeiling: BudgetCeiling | null;
  rateLimitIntent: RateLimitIntent | null;
  retentionIntent: RetentionIntent | null;
  allowPartialDegradation: boolean;
};

export type ScopeRefMappingDto = {
  scope_ref: string;
  scope_key: string;
};

export type ScopeRefMapping = {
  scopeRef: string;
  scopeKey: string;
};

export type DecisionReason = {
  code: string;
  reason: string;
};

export type DecisionReasonDto = DecisionReason;

export type QueryTermDto = {
  term: string;
  normalized_term: string;
  scope_ref: string;
  scope_key: string;
  origin:
    | "canonical"
    | "alias"
    | "include"
    | "official_account"
    | "seed_url"
    | "fixture_candidate_expansion";
  status: "active" | "candidate" | "rejected";
  reason: string | null;
  source: string;
  score: number | null;
  conflict_codes: string[];
};

export type QueryTerm = {
  term: string;
  normalizedTerm: string;
  scopeRef: string;
  scopeKey: string;
  origin: QueryTermDto["origin"];
  status: QueryTermDto["status"];
  reason: string | null;
  source: string;
  score: number | null;
  conflictCodes: string[];
};

export type CompiledPlatformQueryDto = {
  platform: CapabilityPlatform;
  scope_keys: string[];
  source_scope_refs: string[];
  resource_type: CapabilityResourceType;
  operation: CapabilityOperation;
  query_version: string;
  normalized_expression: string;
  include_terms: string[];
  exclude_terms: string[];
  account_filters: string[];
  url_inputs: string[];
  limitations: string[];
};

export type CompiledPlatformQuery = {
  platform: CapabilityPlatform;
  scopeKeys: string[];
  sourceScopeRefs: string[];
  resourceType: CapabilityResourceType;
  operation: CapabilityOperation;
  queryVersion: string;
  normalizedExpression: string;
  includeTerms: string[];
  excludeTerms: string[];
  accountFilters: string[];
  urlInputs: string[];
  limitations: string[];
};

export type RouteRequirementDto = {
  requirement_ref: string;
  scope_keys: string[];
  step_refs: string[];
  platform: CapabilityPlatform;
  resource_type: CapabilityResourceType;
  operation: CapabilityOperation;
  purpose: WorkflowPlannerPurpose;
  regions: string[];
  required_fields: string[];
  optional_fields: string[];
  budget_ceiling: BudgetCeilingDto | null;
  freshness_requirement: string | null;
  rate_limit_requirement: RateLimitIntentDto | null;
  retention_requirement: RetentionIntentDto | null;
  allow_partial_degradation: boolean;
  precondition_failures: DecisionReasonDto[];
};

export type RouteRequirement = {
  requirementRef: string;
  scopeKeys: string[];
  stepRefs: string[];
  platform: CapabilityPlatform;
  resourceType: CapabilityResourceType;
  operation: CapabilityOperation;
  purpose: WorkflowPlannerPurpose;
  regions: string[];
  requiredFields: string[];
  optionalFields: string[];
  budgetCeiling: BudgetCeiling | null;
  freshnessRequirement: string | null;
  rateLimitRequirement: RateLimitIntent | null;
  retentionRequirement: RetentionIntent | null;
  allowPartialDegradation: boolean;
  preconditionFailures: DecisionReason[];
};

export type ScoreBreakdownDto = {
  raw_dimensions: Record<string, number>;
  effective_dimensions: Record<string, number>;
  weights: Record<string, number>;
  weighted_score: number;
  trace_codes: string[];
};

export type ScoreBreakdown = {
  rawDimensions: Record<string, number>;
  effectiveDimensions: Record<string, number>;
  weights: Record<string, number>;
  weightedScore: number;
  traceCodes: string[];
};

export type RouteCandidateDecisionDto = {
  assertion_id: string;
  implementation_id: string;
  capability_status: CapabilityStatus;
  score_breakdown: ScoreBreakdownDto | null;
  weighted_score: number | null;
  route_eligible: boolean;
  readiness_status: WorkflowPlannerAuthReadiness;
  approval_required: boolean;
  approval_reasons: DecisionReasonDto[];
  missing_optional_fields: string[];
  evidence_refs: string[];
};

export type RouteCandidateDecision = {
  assertionId: string;
  implementationId: string;
  capabilityStatus: CapabilityStatus;
  scoreBreakdown: ScoreBreakdown | null;
  weightedScore: number | null;
  routeEligible: boolean;
  readinessStatus: WorkflowPlannerAuthReadiness;
  approvalRequired: boolean;
  approvalReasons: DecisionReason[];
  missingOptionalFields: string[];
  evidenceRefs: string[];
};

export type ShadowRuleDto = {
  enabled: boolean;
  fallback_implementation_id: string | null;
  sample_rate: number | null;
  max_items: number | null;
  reason: string;
  execution_authorized: false;
};

export type ShadowRule = {
  enabled: boolean;
  fallbackImplementationId: string | null;
  sampleRate: number | null;
  maxItems: number | null;
  reason: string;
  executionAuthorized: false;
};

export type RoutePlanPreviewDto = {
  requirement_ref: string;
  status: RoutePlanStatus;
  primary_implementation: RouteCandidateDecisionDto | null;
  fallback_implementations: RouteCandidateDecisionDto[];
  shadow_rule: ShadowRuleDto;
  required_fields: string[];
  optional_fields: string[];
  missing_optional_fields: string[];
  budget_status: WorkflowBudgetStatus;
  rate_limit_policy: RateLimitIntentDto | null;
  retention_policy: RetentionIntentDto | null;
  route_eligible: boolean;
  readiness_status: WorkflowPlannerAuthReadiness | null;
  approval_required: boolean;
  approval_reasons: DecisionReasonDto[];
  policy_gates: DecisionReasonDto[];
  score_breakdown: ScoreBreakdownDto | null;
  exclusion_reasons: DecisionReasonDto[];
  degradation_rule: DecisionReasonDto | null;
  limitations: string[];
  execution_authorized: false;
};

export type RoutePlanPreview = {
  requirementRef: string;
  status: RoutePlanStatus;
  primaryImplementation: RouteCandidateDecision | null;
  fallbackImplementations: RouteCandidateDecision[];
  shadowRule: ShadowRule;
  requiredFields: string[];
  optionalFields: string[];
  missingOptionalFields: string[];
  budgetStatus: WorkflowBudgetStatus;
  rateLimitPolicy: RateLimitIntent | null;
  retentionPolicy: RetentionIntent | null;
  routeEligible: boolean;
  readinessStatus: WorkflowPlannerAuthReadiness | null;
  approvalRequired: boolean;
  approvalReasons: DecisionReason[];
  policyGates: DecisionReason[];
  scoreBreakdown: ScoreBreakdown | null;
  exclusionReasons: DecisionReason[];
  degradationRule: DecisionReason | null;
  limitations: string[];
  executionAuthorized: false;
};

export type StepDataContractFieldDto = {
  name: string;
  data_type: string;
  cardinality: string;
  required: boolean;
  source_step_ref: string | null;
  description: string;
};

export type StepDataContractField = {
  name: string;
  dataType: string;
  cardinality: string;
  required: boolean;
  sourceStepRef: string | null;
  description: string;
};

export type StepDataContractDto = {
  schema_version: string;
  fields: StepDataContractFieldDto[];
};

export type StepDataContract = {
  schemaVersion: string;
  fields: StepDataContractField[];
};

export type WorkflowStepPreviewDto = {
  step_ref: string;
  template_key: string;
  sequence: number;
  label: string;
  execution_kind: "planner_internal" | "future_capability";
  depends_on: string[];
  platform: CapabilityPlatform | null;
  scope_keys: string[];
  resource_type: CapabilityResourceType | null;
  operation: CapabilityOperation | null;
  requirement_ref: string | null;
  input_contract: StepDataContractDto;
  output_contract: StepDataContractDto;
  planning_status: WorkflowStepPlanningStatus;
  limitations: string[];
};

export type WorkflowStepPreview = {
  stepRef: string;
  templateKey: string;
  sequence: number;
  label: string;
  executionKind: "planner_internal" | "future_capability";
  dependsOn: string[];
  platform: CapabilityPlatform | null;
  scopeKeys: string[];
  resourceType: CapabilityResourceType | null;
  operation: CapabilityOperation | null;
  requirementRef: string | null;
  inputContract: StepDataContract;
  outputContract: StepDataContract;
  planningStatus: WorkflowStepPlanningStatus;
  limitations: string[];
};

export type DecisionTraceEntryDto = {
  code: string;
  reason: string;
  scope_keys: string[];
  requirement_ref: string | null;
  details: Record<string, PlannerJsonValue>;
};

export type DecisionTraceEntry = {
  code: string;
  reason: string;
  scopeKeys: string[];
  requirementRef: string | null;
  details: Record<string, PlannerJsonValue>;
};

export type DecisionTraceDto = {
  semantic_entries: DecisionTraceEntryDto[];
  input_diagnostics: DecisionTraceEntryDto[];
};

export type DecisionTrace = {
  semanticEntries: DecisionTraceEntry[];
  inputDiagnostics: DecisionTraceEntry[];
};

export type CoverageSummaryDto = {
  total_requirements: number;
  resolved_requirements: number;
  partial_requirements: number;
  held_requirements: number;
};

export type CoverageSummary = {
  totalRequirements: number;
  resolvedRequirements: number;
  partialRequirements: number;
  heldRequirements: number;
};

export type BudgetSummaryDto = {
  currency: "USD";
  known_selected_unit_cost: string | null;
  unknown_count: number;
  budget_status: WorkflowBudgetStatus;
};

export type BudgetSummary = {
  currency: "USD";
  knownSelectedUnitCost: string | null;
  unknownCount: number;
  budgetStatus: WorkflowBudgetStatus;
};

export type AttributionContractDto = {
  matched_scope_id: string;
  matched_term: string;
  match_reason: string;
  query_version: string;
  requirement_ref: string;
  route_plan_ref: string;
};

export type AttributionContract = {
  matchedScopeId: string;
  matchedTerm: string;
  matchReason: string;
  queryVersion: string;
  requirementRef: string;
  routePlanRef: string;
};

export type WorkflowPlanPreviewDto = {
  schema_version: "workflow_plan_preview.v1";
  planner_contract_version: string;
  project_id: string;
  flow_mode: WorkflowPlannerMode;
  planning_status: WorkflowPlanningStatus;
  normalized_input: NormalizedPlanningInputDto;
  scope_ref_map: ScopeRefMappingDto[];
  query_terms: QueryTermDto[];
  compiled_queries: CompiledPlatformQueryDto[];
  steps: WorkflowStepPreviewDto[];
  route_requirements: RouteRequirementDto[];
  route_plans: RoutePlanPreviewDto[];
  coverage: CoverageSummaryDto;
  budget_summary: BudgetSummaryDto;
  limitations: string[];
  decision_trace: DecisionTraceDto;
  attribution_contract: AttributionContractDto;
  catalog_snapshot_id: string;
  policy_version: string;
  mode_template_version: string;
  query_versions: Partial<Record<CapabilityPlatform, string>>;
  preview_fingerprint: string;
  execution_authorized: false;
  provider_call: false;
  actor_run: false;
  browser_run: false;
  llm_call: false;
  workflow_run_created: false;
  database_write: false;
  generated_at: string;
  request_id: string;
};

export type WorkflowPlanPreview = {
  schemaVersion: "workflow_plan_preview.v1";
  plannerContractVersion: string;
  projectId: string;
  flowMode: WorkflowPlannerMode;
  planningStatus: WorkflowPlanningStatus;
  normalizedInput: NormalizedPlanningInput;
  scopeRefMap: ScopeRefMapping[];
  queryTerms: QueryTerm[];
  compiledQueries: CompiledPlatformQuery[];
  steps: WorkflowStepPreview[];
  routeRequirements: RouteRequirement[];
  routePlans: RoutePlanPreview[];
  coverage: CoverageSummary;
  budgetSummary: BudgetSummary;
  limitations: string[];
  decisionTrace: DecisionTrace;
  attributionContract: AttributionContract;
  catalogSnapshotId: string;
  policyVersion: string;
  modeTemplateVersion: string;
  queryVersions: Partial<Record<CapabilityPlatform, string>>;
  previewFingerprint: string;
  executionAuthorized: false;
  providerCall: false;
  actorRun: false;
  browserRun: false;
  llmCall: false;
  workflowRunCreated: false;
  databaseWrite: false;
  generatedAt: string;
  requestId: string;
};
