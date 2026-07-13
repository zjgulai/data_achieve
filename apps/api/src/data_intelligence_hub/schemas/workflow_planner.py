from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityOperation,
    CapabilityStatus,
    PlatformId,
    ResourceType,
)


class WorkflowPlannerContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FlowMode(StrEnum):
    PERIODIC_MONITORING = "periodic_monitoring"
    BATCH_RESEARCH = "batch_research"


class MonitoringScopeType(StrEnum):
    BRAND = "brand"
    CATEGORY = "category"
    COMPETITOR = "competitor"
    TOPIC = "topic"
    CAMPAIGN = "campaign"


class MatchMode(StrEnum):
    EXACT = "exact"
    PHRASE = "phrase"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class PolicyProfile(StrEnum):
    MARKET_MONITORING_BALANCED = "market_monitoring_balanced"


class AuthReadiness(StrEnum):
    NOT_REQUIRED = "not_required"
    READY = "ready"
    MISSING = "missing"
    NOT_CHECKED = "not_checked"


class PlanningStatus(StrEnum):
    RESOLVED = "resolved"
    PARTIALLY_RESOLVED = "partially_resolved"
    HELD = "held"


class RoutePlanStatus(StrEnum):
    RESOLVED = "resolved"
    PARTIAL = "partial"
    HELD = "held"


class WorkflowStepPlanningStatus(StrEnum):
    PLANNED = "planned"
    PARTIAL = "partial"
    HELD = "held"
    NOT_APPLICABLE = "not_applicable"


class BudgetStatus(StrEnum):
    WITHIN_CEILING = "within_ceiling"
    EXCEEDED = "exceeded"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class ScheduleIntent(WorkflowPlannerContract):
    cadence: Literal["hourly", "daily", "weekly"]
    timezone: str = Field(min_length=1, max_length=100)


class DeliveryIntent(WorkflowPlannerContract):
    outputs: list[Literal["dataset", "alert", "brief"]] = Field(min_length=1)


class BudgetCeiling(WorkflowPlannerContract):
    amount: Decimal = Field(ge=0)
    currency: Literal["USD"] = "USD"


class RateLimitIntent(WorkflowPlannerContract):
    max_requests: int = Field(ge=1)
    period_seconds: int = Field(ge=1)


class RetentionIntent(WorkflowPlannerContract):
    days: int = Field(ge=1, le=3650)


class MonitoringScopeDraft(WorkflowPlannerContract):
    scope_ref: str = Field(min_length=1, max_length=100)
    scope_type: MonitoringScopeType
    canonical_term: str | None = Field(default=None, max_length=500)
    aliases: list[str] = Field(default_factory=list, max_length=50)
    include_terms: list[str] = Field(default_factory=list, max_length=50)
    exclude_terms: list[str] = Field(default_factory=list, max_length=50)
    official_accounts: list[str] = Field(default_factory=list, max_length=50)
    seed_urls: list[str] = Field(default_factory=list, max_length=100)
    languages: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    platforms: list[PlatformId] = Field(default_factory=list)
    match_mode: MatchMode | None = None

    @model_validator(mode="after")
    def validate_scope_content(self) -> Self:
        if self.scope_type in {
            MonitoringScopeType.BRAND,
            MonitoringScopeType.CATEGORY,
            MonitoringScopeType.COMPETITOR,
        } and not (self.canonical_term and self.canonical_term.strip()):
            raise ValueError("canonical_term_required")
        if self.scope_type in {
            MonitoringScopeType.TOPIC,
            MonitoringScopeType.CAMPAIGN,
        } and not any(
            (
                self.canonical_term and self.canonical_term.strip(),
                self.aliases,
                self.include_terms,
                self.official_accounts,
                self.seed_urls,
            )
        ):
            raise ValueError("scope_input_required")
        return self


class PlanningInput(WorkflowPlannerContract):
    flow_mode: FlowMode
    scopes: list[MonitoringScopeDraft] = Field(min_length=1, max_length=20)
    default_languages: list[str] = Field(default_factory=list)
    default_regions: list[str] = Field(default_factory=list)
    default_platforms: list[PlatformId] = Field(default_factory=list)
    schedule_intent: ScheduleIntent | None = None
    delivery_intent: DeliveryIntent | None = None
    policy_profile: PolicyProfile = PolicyProfile.MARKET_MONITORING_BALANCED
    purpose: Literal["brand_monitoring", "market_research", "competitive_research"]
    required_fields: list[str] = Field(default_factory=list)
    optional_fields: list[str] = Field(default_factory=list)
    budget_ceiling: BudgetCeiling | None = None
    rate_limit_intent: RateLimitIntent | None = None
    retention_intent: RetentionIntent | None = None
    allow_partial_degradation: bool = False

    @model_validator(mode="after")
    def validate_flow_contract(self) -> Self:
        refs = [scope.scope_ref for scope in self.scopes]
        if len(refs) != len(set(refs)):
            raise ValueError("duplicate_scope_ref")
        if sum(len(scope.seed_urls) for scope in self.scopes) > 100:
            raise ValueError("seed_url_limit_exceeded")
        if self.flow_mode is FlowMode.PERIODIC_MONITORING:
            if self.schedule_intent is None:
                raise ValueError("periodic_schedule_required")
            if any(
                not (scope.platforms or self.default_platforms or scope.seed_urls)
                for scope in self.scopes
            ):
                raise ValueError("periodic_platform_or_seed_url_required")
        else:
            if "schedule_intent" in self.model_fields_set:
                raise ValueError("batch_schedule_not_allowed")
            if not any(
                (
                    scope.canonical_term and scope.canonical_term.strip(),
                    scope.aliases,
                    scope.include_terms,
                    scope.official_accounts,
                    scope.seed_urls,
                )
                for scope in self.scopes
            ):
                raise ValueError("batch_input_required")
            if any(
                any(
                    (
                        scope.canonical_term and scope.canonical_term.strip(),
                        scope.aliases,
                        scope.include_terms,
                        scope.official_accounts,
                    )
                )
                and not (scope.platforms or self.default_platforms)
                for scope in self.scopes
            ):
                raise ValueError("batch_query_platform_required")
        return self


class NormalizedMonitoringScope(WorkflowPlannerContract):
    scope_key: str
    source_scope_refs: list[str]
    scope_type: MonitoringScopeType
    canonical_term: str | None
    aliases: list[str]
    include_terms: list[str]
    exclude_terms: list[str]
    official_accounts: list[str]
    seed_urls: list[str]
    effective_languages: list[str]
    effective_regions: list[str]
    effective_platforms: list[PlatformId]
    match_mode: MatchMode


class NormalizedPlanningInput(WorkflowPlannerContract):
    flow_mode: FlowMode
    scopes: list[NormalizedMonitoringScope]
    schedule_intent: ScheduleIntent | None
    delivery_intent: DeliveryIntent | None
    policy_profile: PolicyProfile
    purpose: Literal["brand_monitoring", "market_research", "competitive_research"]
    required_fields: list[str]
    optional_fields: list[str]
    budget_ceiling: BudgetCeiling | None
    rate_limit_intent: RateLimitIntent | None
    retention_intent: RetentionIntent | None
    allow_partial_degradation: bool


class ScopeRefMapping(WorkflowPlannerContract):
    scope_ref: str
    scope_key: str


class DecisionReason(WorkflowPlannerContract):
    code: str
    reason: str


class QueryTerm(WorkflowPlannerContract):
    term: str
    normalized_term: str
    scope_ref: str
    scope_key: str
    origin: Literal[
        "canonical",
        "alias",
        "include",
        "official_account",
        "seed_url",
        "fixture_candidate_expansion",
    ]
    status: Literal["active", "candidate", "rejected"]
    reason: str | None
    source: str
    score: float | None
    conflict_codes: list[str]


class SemanticQueryTerm(WorkflowPlannerContract):
    term: str
    normalized_term: str
    scope_key: str
    origin: Literal[
        "canonical",
        "alias",
        "include",
        "official_account",
        "seed_url",
        "fixture_candidate_expansion",
    ]
    status: Literal["active", "candidate", "rejected"]
    reason: str | None
    source: str
    score: float | None
    conflict_codes: list[str]


class CompiledPlatformQuery(WorkflowPlannerContract):
    platform: PlatformId
    scope_keys: list[str]
    source_scope_refs: list[str]
    resource_type: ResourceType
    operation: CapabilityOperation
    query_version: str
    normalized_expression: str
    include_terms: list[str]
    exclude_terms: list[str]
    account_filters: list[str]
    url_inputs: list[str]
    limitations: list[str]


class SemanticCompiledPlatformQuery(WorkflowPlannerContract):
    platform: PlatformId
    scope_keys: list[str]
    resource_type: ResourceType
    operation: CapabilityOperation
    query_version: str
    normalized_expression: str
    include_terms: list[str]
    exclude_terms: list[str]
    account_filters: list[str]
    url_inputs: list[str]
    limitations: list[str]


class QueryCompilerFailure(WorkflowPlannerContract):
    platform: PlatformId
    scope_keys: list[str]
    code: Literal["compiler_missing"] = "compiler_missing"
    reason: str


class RouteRequirement(WorkflowPlannerContract):
    requirement_ref: str
    scope_keys: list[str]
    step_refs: list[str]
    platform: PlatformId
    resource_type: ResourceType
    operation: CapabilityOperation
    purpose: Literal["brand_monitoring", "market_research", "competitive_research"]
    regions: list[str]
    required_fields: list[str]
    optional_fields: list[str]
    budget_ceiling: BudgetCeiling | None
    freshness_requirement: str | None
    rate_limit_requirement: RateLimitIntent | None
    retention_requirement: RetentionIntent | None
    allow_partial_degradation: bool
    precondition_failures: list[DecisionReason] = Field(default_factory=list)


class CapabilityReadinessSnapshot(WorkflowPlannerContract):
    implementation_id: str
    auth_readiness: AuthReadiness
    source: str
    credential_read_status: Literal["not_read"] = "not_read"


class ScoreBreakdown(WorkflowPlannerContract):
    raw_dimensions: dict[str, int]
    effective_dimensions: dict[str, int]
    weights: dict[str, int]
    weighted_score: int
    trace_codes: list[str]


class RouteCandidateDecision(WorkflowPlannerContract):
    assertion_id: str
    implementation_id: str
    capability_status: CapabilityStatus
    score_breakdown: ScoreBreakdown | None
    weighted_score: int | None
    route_eligible: bool
    readiness_status: AuthReadiness
    approval_required: bool
    approval_reasons: list[DecisionReason]
    missing_optional_fields: list[str]
    evidence_refs: list[str]


class ShadowRule(WorkflowPlannerContract):
    enabled: bool
    fallback_implementation_id: str | None
    sample_rate: float | None
    max_items: int | None
    reason: str
    execution_authorized: Literal[False] = False


class RoutePlanPreview(WorkflowPlannerContract):
    requirement_ref: str
    status: RoutePlanStatus
    primary_implementation: RouteCandidateDecision | None
    fallback_implementations: list[RouteCandidateDecision]
    shadow_rule: ShadowRule
    required_fields: list[str]
    optional_fields: list[str]
    missing_optional_fields: list[str]
    budget_status: BudgetStatus
    rate_limit_policy: RateLimitIntent | None
    retention_policy: RetentionIntent | None
    route_eligible: bool
    readiness_status: AuthReadiness | None
    approval_required: bool
    approval_reasons: list[DecisionReason]
    policy_gates: list[DecisionReason]
    score_breakdown: ScoreBreakdown | None
    exclusion_reasons: list[DecisionReason]
    degradation_rule: DecisionReason | None
    limitations: list[str]
    execution_authorized: Literal[False] = False


class StepDataContractField(WorkflowPlannerContract):
    name: str
    data_type: str
    cardinality: str
    required: bool
    source_step_ref: str | None
    description: str


class StepDataContract(WorkflowPlannerContract):
    schema_version: str
    fields: list[StepDataContractField]


class WorkflowStepPreview(WorkflowPlannerContract):
    step_ref: str
    template_key: str
    sequence: int = Field(ge=1)
    label: str
    execution_kind: Literal["planner_internal", "future_capability"]
    depends_on: list[str]
    platform: PlatformId | None
    scope_keys: list[str]
    resource_type: ResourceType | None
    operation: CapabilityOperation | None
    requirement_ref: str | None
    input_contract: StepDataContract
    output_contract: StepDataContract
    planning_status: WorkflowStepPlanningStatus
    limitations: list[str]


class DecisionTraceEntry(WorkflowPlannerContract):
    code: str
    reason: str
    scope_keys: list[str]
    requirement_ref: str | None
    details: dict[str, JsonValue]


class DecisionTrace(WorkflowPlannerContract):
    semantic_entries: list[DecisionTraceEntry]
    input_diagnostics: list[DecisionTraceEntry]


class CoverageSummary(WorkflowPlannerContract):
    total_requirements: int = Field(ge=0)
    resolved_requirements: int = Field(ge=0)
    partial_requirements: int = Field(ge=0)
    held_requirements: int = Field(ge=0)


class BudgetSummary(WorkflowPlannerContract):
    currency: Literal["USD"] = "USD"
    known_selected_unit_cost: Decimal | None
    unknown_count: int = Field(ge=0)
    budget_status: BudgetStatus


class AttributionContract(WorkflowPlannerContract):
    matched_scope_id: str
    matched_term: str
    match_reason: str
    query_version: str
    requirement_ref: str
    route_plan_ref: str


FINGERPRINT_FORBIDDEN_REFERENCE_FIELDS = frozenset(
    {
        "scope_ref",
        "source_scope_refs",
        "project_id",
        "generated_at",
        "request_id",
    }
)


def _reject_fingerprint_reference_fields(value: object) -> None:
    if isinstance(value, BaseModel):
        _reject_fingerprint_reference_fields(value.model_dump(mode="python"))
    elif isinstance(value, dict):
        for key, nested_value in value.items():
            if key in FINGERPRINT_FORBIDDEN_REFERENCE_FIELDS:
                raise ValueError(f"fingerprint_reference_field_forbidden:{key}")
            _reject_fingerprint_reference_fields(nested_value)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_fingerprint_reference_fields(item)


class WorkflowPlanFingerprintPayload(WorkflowPlannerContract):
    planner_contract_version: str
    fingerprint_input: dict[str, JsonValue]
    catalog_snapshot_id: str
    policy_version: str
    mode_template_version: str
    query_versions: dict[PlatformId, str]
    candidate_fixture_version: str
    semantic_query_terms: list[SemanticQueryTerm]
    semantic_steps: list[WorkflowStepPreview]
    semantic_compiled_queries: list[SemanticCompiledPlatformQuery]
    route_plans: list[RoutePlanPreview]
    coverage: CoverageSummary
    budget_summary: BudgetSummary
    limitations: list[str]
    semantic_decision_trace: list[DecisionTraceEntry]

    @model_validator(mode="after")
    def validate_reference_free(self) -> Self:
        _reject_fingerprint_reference_fields(self)
        return self


class WorkflowPlanPreview(WorkflowPlannerContract):
    schema_version: Literal["workflow_plan_preview.v1"]
    planner_contract_version: str
    project_id: UUID
    flow_mode: FlowMode
    planning_status: PlanningStatus
    normalized_input: NormalizedPlanningInput
    scope_ref_map: list[ScopeRefMapping]
    query_terms: list[QueryTerm]
    compiled_queries: list[CompiledPlatformQuery]
    steps: list[WorkflowStepPreview]
    route_requirements: list[RouteRequirement]
    route_plans: list[RoutePlanPreview]
    coverage: CoverageSummary
    budget_summary: BudgetSummary
    limitations: list[str]
    decision_trace: DecisionTrace
    attribution_contract: AttributionContract
    catalog_snapshot_id: str
    policy_version: str
    mode_template_version: str
    query_versions: dict[PlatformId, str]
    preview_fingerprint: str
    execution_authorized: Literal[False] = False
    provider_call: Literal[False] = False
    actor_run: Literal[False] = False
    browser_run: Literal[False] = False
    llm_call: Literal[False] = False
    workflow_run_created: Literal[False] = False
    database_write: Literal[False] = False
    generated_at: datetime
    request_id: str
