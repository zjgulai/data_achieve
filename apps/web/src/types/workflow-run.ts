export type WorkflowRunStatus =
  | "draft"
  | "ready"
  | "running"
  | "completed"
  | "degraded"
  | "held"
  | "cancelled"
  | "empty_valid";

export type WorkflowStepRunStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type WorkflowRunDto = {
  id: string;
  workspace_id: string;
  project_id: string;
  workflow_plan_id: string;
  workflow_version_id: string;
  workflow_template_id: string | null;
  workflow_template_revision_id: string | null;
  created_by_user_id: string;
  execution_contract_version: "workflow_execution_fixture.v1";
  execution_mode: "fixture";
  status: WorkflowRunStatus;
  planner_contract_version: string;
  preview_fingerprint: string;
  catalog_snapshot_id: string;
  policy_version: string;
  mode_template_version: string;
  query_versions: Record<string, string>;
  fixture_profile_id: string;
  fixture_profile_hash: string;
  total_steps: number;
  completed_steps: number;
  records_count: number;
  status_reason_code: string | null;
  impact_code: string | null;
  missing_fields: string[];
  recovery_action_codes: string[];
  provider_call_attempted: false;
  credential_read_attempted: false;
  actor_run: false;
  browser_run: false;
  llm_call: false;
  production_write_allowed: false;
  started_at: string;
  finished_at: string | null;
  created_at: string;
};

export type WorkflowStepRunDto = {
  id: string;
  workflow_run_id: string;
  workspace_id: string;
  project_id: string;
  step_ref: string;
  requirement_ref: string;
  sequence: number;
  platform: string;
  resource_type: string;
  operation: string;
  assertion_id: string;
  implementation_id: string;
  route_plan_snapshot: Record<string, unknown>;
  evidence_refs: string[];
  fixture_case_id: string | null;
  fixture_content_hash: string | null;
  input_digest: string;
  output_digest: string | null;
  idempotency_scope: string;
  idempotency_key_hash: string;
  status: WorkflowStepRunStatus;
  records_count: number;
  provider_call_attempted: false;
  credential_read_attempted: false;
  actor_run: false;
  browser_run: false;
  llm_call: false;
  production_write_allowed: false;
  started_at: string;
  finished_at: string | null;
  created_at: string;
};

export type WorkflowFixtureReadBoundaryDto = {
  execution_mode: "fixture";
  live_execution_authorized: false;
  provider_call: false;
  provider_call_attempted: false;
  credential_read_attempted: false;
  actor_run: false;
  browser_run: false;
  llm_call: false;
  raw_record_write: false;
  dataset_write: false;
  production_write_allowed: false;
  database_write: false;
};

export type WorkflowExecutorLeaseEvidenceDto = {
  id: string;
  state: "active" | "released" | "expired" | "superseded" | "terminal";
  fencing_token: number;
  version: number;
  heartbeat_at: string;
  expires_at: string;
  fresh: boolean;
};

export type WorkflowExecutorEventEvidenceDto = {
  id: string;
  sequence: number;
  event_type:
    | "dispatch_created"
    | "dispatch_replayed"
    | "lease_claimed"
    | "lease_heartbeat"
    | "lease_expired"
    | "lease_taken_over"
    | "lease_released"
    | "preflight_blocked"
    | "preflight_eligible"
    | "credential_permit_issued"
    | "credential_permit_consumed"
    | "credential_resolution_failed"
    | "provider_permit_issued"
    | "provider_permit_consumed"
    | "provider_permit_revoked"
    | "provider_attempting"
    | "provider_succeeded"
    | "provider_failed"
    | "provider_uncertain"
    | "cancel_requested"
    | "cancel_acknowledged"
    | "terminal_committed";
  event_digest: string;
  occurred_at: string;
};

export type WorkflowExecutorAuditEvidenceDto = {
  id: string;
  attempt_ordinal: number;
  provider_id: string;
  operation_id: string;
  preflight_id: string;
  transport_state:
    | "not_attempted"
    | "attempting"
    | "succeeded"
    | "failed"
    | "uncertain";
  outcome_code: string | null;
  environment: "local" | "test" | "staging" | "production";
  started_at: string | null;
  finished_at: string | null;
};

export type WorkflowExecutorCancellationEvidenceDto = {
  requested: boolean;
  acknowledged: boolean;
  request_id: string | null;
  reason_code: string | null;
  requested_at: string | null;
  acknowledgement_id: string | null;
  safe_point: string | null;
  outcome:
    | "cancelled_before_effect"
    | "cancelled_after_current_effect"
    | "cancel_pending_external_outcome"
    | null;
  acknowledged_at: string | null;
};

export type WorkflowExecutorDispatchEvidenceDto = {
  id: string;
  workflow_step_run_id: string;
  attempt_generation: number;
  source_action_request_id: string | null;
  source_action_receipt_id: string | null;
  state: "pending" | "claimable" | "terminal";
  created_at: string;
  lease: WorkflowExecutorLeaseEvidenceDto | null;
  last_event: WorkflowExecutorEventEvidenceDto | null;
  preflight_state: "not_evaluated" | "blocked" | "eligible";
  preflight_blocker_codes: string[];
  next_required_authority: "exact_live_provider_call_authorization" | null;
  credential_permit_ids: string[];
  provider_permit_ids: string[];
  audits: WorkflowExecutorAuditEvidenceDto[];
  audit_total: number;
  budget_reservation_state: "not_recorded";
  cancellation: WorkflowExecutorCancellationEvidenceDto;
};

export type WorkflowExecutorEvidenceResponseDto =
  WorkflowFixtureReadBoundaryDto & {
    schema_version: "workflow_executor_evidence.v1";
    workspace_id: string;
    project_id: string;
    workflow_run_id: string;
    evidence_grade: "L2_fixture_local";
    environment: "local";
    evaluated_at: string;
    dispatches: WorkflowExecutorDispatchEvidenceDto[];
    dispatch_total: number;
    business_cause_code:
      | "executor_dispatch_not_created"
      | "executor_dispatch_pending"
      | "executor_preflight_blocked"
      | "executor_waiting_exact_live_authority";
    business_impact_code:
      | "workflow_execution_not_started"
      | "workflow_execution_waiting";
    next_action_code:
      | "review_action_receipt_and_dispatch_gate"
      | "wait_for_disabled_executor_evidence"
      | "resolve_preflight_blocker"
      | "request_exact_live_provider_authorization";
    client_construction: false;
    network_call: false;
    live_provider_proof: false;
  };

export type WorkflowFixtureRunGateBlockerCode =
  | "project_not_active"
  | "workflow_plan_not_active"
  | "workflow_version_not_current"
  | "workflow_version_contract_not_runnable";

export type WorkflowFixtureRunGateActionCode =
  | "activate_project"
  | "approve_and_activate_plan"
  | "select_current_version"
  | "resolve_version_contract"
  | "create_fixture_run";

export type WorkflowFixtureRunGateDto = WorkflowFixtureReadBoundaryDto & {
  gate_contract_version: "workflow_fixture_run_gate.v1";
  project_status: "active" | "archived";
  workflow_plan_id: string;
  workflow_version_id: string;
  current_version_id: string | null;
  plan_status:
    | "draft"
    | "previewed"
    | "approved"
    | "active"
    | "paused"
    | "archived";
  planning_status: "resolved" | "partially_resolved" | "held";
  is_current_version: boolean;
  runnable: boolean;
  blocker_codes: WorkflowFixtureRunGateBlockerCode[];
  next_action_codes: WorkflowFixtureRunGateActionCode[];
  evidence_refs: string[];
};

export type WorkflowFixtureRunGate = WorkflowFixtureReadBoundary & {
  gateContractVersion: "workflow_fixture_run_gate.v1";
  projectStatus: "active" | "archived";
  workflowPlanId: string;
  workflowVersionId: string;
  currentVersionId: string | null;
  planStatus: WorkflowFixtureRunGateDto["plan_status"];
  planningStatus: WorkflowFixtureRunGateDto["planning_status"];
  isCurrentVersion: boolean;
  runnable: boolean;
  blockerCodes: WorkflowFixtureRunGateBlockerCode[];
  nextActionCodes: WorkflowFixtureRunGateActionCode[];
  evidenceRefs: string[];
};

export type WorkflowFixtureRunCreateInput = {
  expectedPreviewFingerprint: string;
  fixtureProfileId: string;
  idempotencyKey: string;
};

export type WorkflowFixtureRunCreateRequestDto = {
  expected_preview_fingerprint: string;
  fixture_profile_id: string;
};

export type WorkflowFixtureRunCreateResponseDto = Omit<
  WorkflowFixtureReadBoundaryDto,
  "database_write"
> & {
  database_write: boolean;
  idempotent_replay: boolean;
  run: WorkflowRunDto;
  steps: WorkflowStepRunDto[];
};

export type WorkflowFixtureRunCreateResult = Omit<
  WorkflowFixtureReadBoundary,
  "databaseWrite"
> & {
  databaseWrite: boolean;
  idempotentReplay: boolean;
  run: WorkflowRun;
  steps: WorkflowStepRun[];
};

export type WorkflowRunListResponseDto = WorkflowFixtureReadBoundaryDto & {
  project_status: "active" | "archived";
  items: WorkflowRunDto[];
  total: number;
  limit: number;
  offset: number;
};

export type WorkflowRunDetailResponseDto = WorkflowFixtureReadBoundaryDto & {
  project_status: "active" | "archived";
  run: WorkflowRunDto;
  steps: WorkflowStepRunDto[];
};

export type WorkflowStepAttemptStatus =
  | "succeeded"
  | "retryable_error"
  | "timeout"
  | "terminal_error";

export type WorkflowStepAttemptEvidenceDto = {
  id: string;
  workspace_id: string;
  project_id: string;
  workflow_run_id: string;
  step_run_id: string;
  attempt_number: number;
  attempt_key_hash: string;
  status: WorkflowStepAttemptStatus;
  error_code: string | null;
  backoff_ms: number;
  provider_call_attempted: false;
  credential_read_attempted: false;
  actor_run: false;
  browser_run: false;
  llm_call: false;
  production_write_allowed: false;
  started_at: string;
  finished_at: string;
  created_at: string;
};

export type WorkflowFallbackGateName =
  | "trigger"
  | "policy"
  | "credential"
  | "budget"
  | "fields"
  | "evidence"
  | "approval";

export type WorkflowFallbackGateEvidenceDto = {
  gate: WorkflowFallbackGateName;
  status: "passed" | "blocked";
  code: string;
  evidence_refs: string[];
};

export type WorkflowFallbackFieldDifferenceDto = {
  evidence_status: "verified" | "unavailable";
  required_fields: string[];
  missing_required_fields: string[];
  primary_missing_optional_fields: string[];
  fallback_missing_optional_fields: string[];
};

export type WorkflowFallbackCostEvidenceDto = {
  evidence_status: "verified" | "unavailable";
  currency: "USD";
  unit_cost_usd: string | number | null;
  ceiling_usd: string | number | null;
  within_ceiling: boolean | null;
};

export type WorkflowFallbackDecisionEvidenceDto = {
  id: string;
  workspace_id: string;
  project_id: string;
  workflow_plan_id: string;
  workflow_version_id: string;
  workflow_run_id: string;
  step_run_id: string;
  created_by_user_id: string;
  step_ref: string;
  requirement_ref: string;
  contract_version: "workflow_fallback_gate_replay.v1";
  decision_digest: string;
  primary_failure_code: string;
  primary_assertion_id: string;
  primary_implementation_id: string;
  fallback_assertion_id: string | null;
  fallback_implementation_id: string | null;
  outcome: "eligible" | "blocked";
  gates: WorkflowFallbackGateEvidenceDto[];
  field_difference: WorkflowFallbackFieldDifferenceDto;
  cost_snapshot: WorkflowFallbackCostEvidenceDto;
  evidence_refs: string[];
  approval_required: boolean;
  approval_status:
    | "not_required"
    | "approved"
    | "pending"
    | "rejected"
    | "unavailable";
  switch_executed: false;
  provider_call_attempted: false;
  credential_read_attempted: false;
  actor_run: false;
  browser_run: false;
  llm_call: false;
  production_write_allowed: false;
  created_at: string;
};

export type WorkflowAttemptFallbackEvidenceResponseDto =
  WorkflowFixtureReadBoundaryDto & {
    schema_version: "workflow_attempt_fallback_evidence.v1";
    workspace_id: string;
    project_id: string;
    workflow_run_id: string;
    attempts: WorkflowStepAttemptEvidenceDto[];
    fallback_decisions: WorkflowFallbackDecisionEvidenceDto[];
    attempt_total: number;
    fallback_decision_total: number;
  };

export type WorkflowCheckpointDto = {
  id: string;
  execution_session_id: string;
  workspace_id: string;
  project_id: string;
  workflow_plan_id: string;
  workflow_version_id: string;
  step_ref: string;
  requirement_ref: string;
  implementation_id: string;
  contract_version: "workflow_step_checkpoint.v1";
  fixture_profile_id: string;
  fixture_profile_hash: string;
  step_input_digest: string;
  page_number: number;
  cursor_before: string | null;
  cursor_before_digest: string;
  cursor_after: string | null;
  cursor_after_digest: string | null;
  side_effect_key_hash: string;
  page_output_digest: string;
  checkpoint_digest: string;
  records_count: number;
  terminal: boolean;
  evidence_refs: string[];
  provider_call_attempted: false;
  credential_read_attempted: false;
  actor_run: false;
  browser_run: false;
  llm_call: false;
  raw_record_write: false;
  dataset_write: false;
  production_write_allowed: false;
  confirmed_at: string;
  created_at: string;
};

export type WorkflowCheckpointStepEvidenceDto = {
  step_run_id: string;
  execution_session_id: string;
  step_ref: string;
  requirement_ref: string;
  implementation_id: string;
  checkpoints: WorkflowCheckpointDto[];
  confirmed_pages: number;
  confirmed_records: number;
  terminal: boolean;
  next_page_number: number;
  next_cursor: string | null;
  resume_action_available: false;
};

export type WorkflowBudgetEvidenceStatus =
  | "not_configured"
  | "configured"
  | "within_limit"
  | "held";

export type WorkflowBudgetBlockerCode =
  | "workflow_request_budget_exceeded"
  | "workflow_item_budget_exceeded"
  | "workflow_quota_budget_exceeded"
  | "workflow_cost_budget_exceeded"
  | "workflow_time_budget_exceeded";

export type WorkflowBudgetAccountDto = {
  id: string;
  execution_session_id: string;
  workspace_id: string;
  project_id: string;
  workflow_plan_id: string;
  workflow_version_id: string;
  contract_version: "workflow_budget_account.v1";
  policy_digest: string;
  max_requests: number;
  max_items: number;
  quota_ceilings: Record<string, number>;
  max_cost_usd: string | number;
  max_time_ms: number;
  evidence_refs: string[];
  provider_call_attempted: false;
  credential_read_attempted: false;
  actor_run: false;
  browser_run: false;
  llm_call: false;
  raw_record_write: false;
  dataset_write: false;
  production_write_allowed: false;
};

export type WorkflowBudgetLedgerEntryDto = {
  id: string;
  budget_account_id: string;
  execution_session_id: string;
  workspace_id: string;
  project_id: string;
  contract_version: "workflow_budget_ledger.v1";
  policy_digest: string;
  entry_number: number;
  step_ref: string;
  page_number: number;
  side_effect_key_hash: string;
  status: "reserved" | "blocked";
  blocker_code: WorkflowBudgetBlockerCode | null;
  request_count: number;
  item_count: number;
  quota_units: Record<string, number>;
  estimated_cost_usd: string | number;
  reserved_time_ms: number;
  cumulative_request_count: number;
  cumulative_item_count: number;
  cumulative_quota_units: Record<string, number>;
  cumulative_cost_usd: string | number;
  cumulative_time_ms: number;
  previous_ledger_digest: string | null;
  ledger_digest: string;
  provider_call_attempted: false;
  credential_read_attempted: false;
  actor_run: false;
  browser_run: false;
  llm_call: false;
  raw_record_write: false;
  dataset_write: false;
  production_write_allowed: false;
};

export type WorkflowBudgetUsageEvidenceDto = {
  request_count: number;
  request_limit: number;
  item_count: number;
  item_limit: number;
  quota_units: Record<string, number>;
  quota_ceilings: Record<string, number>;
  cost_usd: string | number;
  cost_limit_usd: string | number;
  time_ms: number;
  time_limit_ms: number;
};

export type WorkflowCheckpointBudgetEvidenceResponseDto =
  WorkflowFixtureReadBoundaryDto & {
    schema_version: "workflow_checkpoint_budget_evidence.v1";
    workspace_id: string;
    project_id: string;
    workflow_plan_id: string;
    workflow_version_id: string;
    workflow_run_id: string;
    execution_session_id: string;
    checkpoint_steps: WorkflowCheckpointStepEvidenceDto[];
    checkpoint_step_total: number;
    checkpoint_page_total: number;
    budget_status: WorkflowBudgetEvidenceStatus;
    budget_account: WorkflowBudgetAccountDto | null;
    budget_entries: WorkflowBudgetLedgerEntryDto[];
    budget_entry_total: number;
    usage: WorkflowBudgetUsageEvidenceDto | null;
    held_reason_code: WorkflowBudgetBlockerCode | null;
    resume_action_available: false;
    budget_override_available: false;
  };

export type ProviderHealthStatus =
  | "unknown"
  | "healthy"
  | "degraded"
  | "unhealthy";

export type WorkflowProviderHealthStatus =
  | "not_observed"
  | ProviderHealthStatus;

export type WorkflowProviderHealthRoutingState =
  | "not_observed"
  | "routing_active"
  | "routing_expired";

export type ProviderHealthSnapshotDto = Omit<
  WorkflowFixtureReadBoundaryDto,
  "database_write"
> & {
  id: string;
  workspace_id: string;
  project_id: string;
  contract_version: "provider_health_snapshot.v1";
  scope_key: string;
  aggregation_key: string;
  snapshot_version: number;
  platform_id: string;
  implementation_id: string;
  resource_type: string;
  operation: string;
  window_started_at: string;
  window_ended_at: string;
  evaluated_at: string;
  status: ProviderHealthStatus;
  sample_count: number;
  success_count: number;
  timeout_count: number;
  rate_limited_count: number;
  transient_error_count: number;
  terminal_error_count: number;
  success_rate_bps: number;
  p95_latency_ms: number;
  reason_codes: string[];
  policy_snapshot: Record<string, number>;
  observation_manifest: Array<Record<string, unknown>>;
  evidence_refs: string[];
  previous_snapshot_digest: string | null;
  snapshot_digest: string;
  routing_valid_until: string;
  evidence_retain_until: string;
  health_probe_attempted: false;
};

export type ProviderHealthRouteFeedbackDto = Omit<
  WorkflowFixtureReadBoundaryDto,
  "database_write"
> & {
  id: string;
  workspace_id: string;
  project_id: string;
  contract_version: "provider_health_route_feedback.v1";
  route_key: string;
  feedback_key: string;
  feedback_version: number;
  platform_id: string;
  resource_type: string;
  operation: string;
  original_candidate_order: string[];
  adjusted_candidate_order: string[];
  candidate_score_manifest: Array<Record<string, unknown>>;
  source_snapshot_manifest: Array<Record<string, unknown>>;
  ranking_changed: boolean;
  reason_codes: string[];
  evidence_refs: string[];
  previous_feedback_digest: string | null;
  feedback_digest: string;
  evaluated_at: string;
  evidence_retain_until: string;
  health_probe_attempted: false;
  catalog_mutation_applied: false;
  automatic_route_switch_executed: false;
};

export type WorkflowProviderHealthCandidateEvidenceDto = {
  implementation_id: string;
  selected_for_run: boolean;
  health_status: WorkflowProviderHealthStatus;
  routing_state: WorkflowProviderHealthRoutingState;
  snapshot: ProviderHealthSnapshotDto | null;
};

export type WorkflowProviderHealthStepEvidenceDto = {
  step_run_id: string;
  step_ref: string;
  requirement_ref: string;
  platform_id: string;
  resource_type: string;
  operation: string;
  selected_implementation_id: string;
  candidates: WorkflowProviderHealthCandidateEvidenceDto[];
  route_feedback: ProviderHealthRouteFeedbackDto | null;
  route_feedback_match: "not_available" | "ordered_candidate_match";
  route_decision_applied_to_run: false;
};

export type WorkflowProviderHealthEvidenceResponseDto =
  WorkflowFixtureReadBoundaryDto & {
    schema_version: "workflow_provider_health_evidence.v1";
    workspace_id: string;
    project_id: string;
    workflow_run_id: string;
    read_at: string;
    steps: WorkflowProviderHealthStepEvidenceDto[];
    step_total: number;
    observed_candidate_total: number;
    routing_active_candidate_total: number;
    attention_candidate_total: number;
    route_feedback_total: number;
    health_probe_attempted: false;
    catalog_mutation_applied: false;
    automatic_route_switch_executed: false;
    route_switch_action_available: false;
  };

export type WorkflowRunAction =
  | "retry"
  | "resume"
  | "cancel"
  | "budget_override"
  | "route_switch";

export type WorkflowRunActionPreconditionStatus =
  | "ready_for_review"
  | "blocked"
  | "not_applicable";

export type WorkflowRunActionPreconditionBlockerCode =
  | "run_state_not_retryable"
  | "failed_step_unavailable"
  | "retry_evidence_unavailable"
  | "terminal_failure_not_retryable"
  | "retry_policy_snapshot_unavailable"
  | "run_state_not_resumable"
  | "resume_checkpoint_unavailable"
  | "resume_checkpoint_terminal"
  | "budget_account_unavailable"
  | "budget_limit_exceeded"
  | "run_state_not_cancellable"
  | "budget_not_held"
  | "owner_approval_receipt_unavailable"
  | "run_state_not_switchable"
  | "fallback_decision_unavailable"
  | "fallback_gate_blocked"
  | "route_feedback_unavailable";

export type WorkflowRunActionAvailabilityBlockerCode =
  | "mutation_endpoint_unavailable"
  | "durable_action_audit_unavailable"
  | "workflow_action_owner_required"
  | "workflow_action_approval_required"
  | "workflow_action_persistence_unavailable"
  | "workflow_action_executor_ack_unavailable";

export type WorkflowActionApprovalKind =
  | "owner_confirmation"
  | "owner_policy_override"
  | "owner_route_override";

export type WorkflowRunActionNextActionCode =
  | "no_action_required"
  | "inspect_retry_evidence"
  | "restore_checkpoint_budget"
  | "review_resume_request"
  | "review_cancel_request"
  | "request_budget_override_approval"
  | "resolve_fallback_gates"
  | "review_route_switch";

export type WorkflowRunActionGateEvidenceDto = {
  action: WorkflowRunAction;
  precondition_status: WorkflowRunActionPreconditionStatus;
  action_available: false;
  precondition_blocker_codes: WorkflowRunActionPreconditionBlockerCode[];
  availability_blocker_codes: WorkflowRunActionAvailabilityBlockerCode[];
  next_action_code: WorkflowRunActionNextActionCode;
  evidence_refs: string[];
};

export type WorkflowRunActionGatesV1ResponseDto =
  WorkflowFixtureReadBoundaryDto & {
    schema_version: "workflow_run_action_gates.v1";
    workspace_id: string;
    project_id: string;
    workflow_plan_id: string;
    workflow_version_id: string;
    workflow_run_id: string;
    run_status: WorkflowRunStatus;
    gates: WorkflowRunActionGateEvidenceDto[];
    ready_for_review_total: number;
    blocked_total: number;
    not_applicable_total: number;
    available_action_total: 0;
    mutation_endpoints_available: false;
    durable_action_audit_available: false;
    action_mutation_executed: false;
  };

export type WorkflowRunActionGateV2EvidenceDto = {
  action: WorkflowRunAction;
  precondition_status: WorkflowRunActionPreconditionStatus;
  precondition_blocker_codes: WorkflowRunActionPreconditionBlockerCode[];
  submission_available: boolean;
  availability_blocker_codes: WorkflowRunActionAvailabilityBlockerCode[];
  approval_kind: WorkflowActionApprovalKind;
  approval_receipt_required: true;
  evidence_refs: string[];
  expires_at: string;
};

export type WorkflowRunActionGatesV2ResponseDto =
  WorkflowFixtureReadBoundaryDto & {
    schema_version: "workflow_run_action_gates.v2";
    workspace_id: string;
    project_id: string;
    workflow_plan_id: string;
    workflow_version_id: string;
    workflow_run_id: string;
    run_status: WorkflowRunStatus;
    action_gate_digest: string;
    action_context_version: number;
    gates: WorkflowRunActionGateV2EvidenceDto[];
    ready_for_review_total: number;
    blocked_total: number;
    not_applicable_total: number;
    available_action_total: number;
    mutation_endpoints_available: true;
    durable_action_audit_available: true;
    action_mutation_executed: false;
  };

export type WorkflowRunActionGatesResponseDto =
  | WorkflowRunActionGatesV1ResponseDto
  | WorkflowRunActionGatesV2ResponseDto;

export type WorkflowProviderLineagePreviewDto = {
  step_run_id: string;
  implementation_id: string;
  platform: string;
  resource_type: string;
  operation: string;
  fixture_case_id: string;
  fixture_content_hash: string;
  output_digest: string;
  records_count: number;
  evidence_refs: string[];
};

export type WorkflowRawRecordLineagePreviewDto = {
  source_task_run_id: string | null;
  source_step_run_ids: string[];
  materialized_raw_record_ids: string[];
  expected_record_count: number;
  raw_record_write: false;
  materialized: boolean;
  blocked_reasons: string[];
};

export type WorkflowDatasetLineagePreviewDto = {
  dataset_id: string | null;
  dataset_version_id: string | null;
  source_step_run_ids: string[];
  source_raw_record_ids: string[];
  expected_record_count: number;
  dataset_write: false;
  materialized: boolean;
  blocked_reasons: string[];
};

export type WorkflowRunLineagePreviewDto = WorkflowFixtureReadBoundaryDto & {
  schema_version: "workflow_lineage_preview.v2";
  workflow_run_id: string;
  workspace_id: string;
  project_id: string;
  lineage_digest: string;
  materialization_eligible: boolean;
  provider_evidence: WorkflowProviderLineagePreviewDto[];
  raw_record: WorkflowRawRecordLineagePreviewDto;
  dataset: WorkflowDatasetLineagePreviewDto;
  blocked_reasons: string[];
};

export type WorkflowShadowEquivalenceStatus = "equivalent" | "different";

export type WorkflowShadowRoutingRecommendation =
  | "eligible_for_governance_review"
  | "keep_primary_investigate_shadow";

export type WorkflowShadowDifferenceEvidenceDto = {
  sampled_record_keys: string[];
  matched_record_keys: string[];
  mismatched_record_keys: string[];
  primary_only_record_keys: string[];
  shadow_only_record_keys: string[];
  missing_required_fields: string[];
  primary_only_fields: string[];
  shadow_only_fields: string[];
};

export type WorkflowShadowComparisonDto = WorkflowFixtureReadBoundaryDto & {
  id: string;
  workspace_id: string;
  project_id: string;
  workflow_run_id: string;
  step_run_id: string;
  requirement_ref: string;
  contract_version: "workflow_shadow_comparison.v1";
  comparison_digest: string;
  primary_implementation_id: string;
  shadow_implementation_id: string;
  fixture_profile_id: string;
  fixture_profile_hash: string;
  primary_fixture_case_id: string;
  primary_fixture_content_hash: string;
  shadow_fixture_case_id: string;
  shadow_fixture_content_hash: string;
  sample_rate: number;
  max_items: number;
  sampled_items: number;
  matched_items: number;
  mismatched_items: number;
  primary_only_items: number;
  shadow_only_items: number;
  equivalence_status: WorkflowShadowEquivalenceStatus;
  difference_evidence: WorkflowShadowDifferenceEvidenceDto;
  routing_recommendation: WorkflowShadowRoutingRecommendation;
  evidence_refs: string[];
  catalog_mutation_applied: false;
  route_ranking_mutation_applied: false;
  created_at: string;
};

export type WorkflowShadowComparisonListResponseDto =
  WorkflowFixtureReadBoundaryDto & {
    items: WorkflowShadowComparisonDto[];
    total: number;
  };

export type WorkflowRun = {
  id: string;
  workspaceId: string;
  projectId: string;
  workflowPlanId: string;
  workflowVersionId: string;
  workflowTemplateId: string | null;
  workflowTemplateRevisionId: string | null;
  createdByUserId: string;
  executionContractVersion: "workflow_execution_fixture.v1";
  executionMode: "fixture";
  status: WorkflowRunStatus;
  plannerContractVersion: string;
  previewFingerprint: string;
  catalogSnapshotId: string;
  policyVersion: string;
  modeTemplateVersion: string;
  queryVersions: Record<string, string>;
  fixtureProfileId: string;
  fixtureProfileHash: string;
  totalSteps: number;
  completedSteps: number;
  recordsCount: number;
  statusReasonCode: string | null;
  impactCode: string | null;
  missingFields: string[];
  recoveryActionCodes: string[];
  providerCallAttempted: false;
  credentialReadAttempted: false;
  actorRun: false;
  browserRun: false;
  llmCall: false;
  productionWriteAllowed: false;
  startedAt: string;
  finishedAt: string | null;
  createdAt: string;
};

export type WorkflowStepRun = {
  id: string;
  workflowRunId: string;
  workspaceId: string;
  projectId: string;
  stepRef: string;
  requirementRef: string;
  sequence: number;
  platform: string;
  resourceType: string;
  operation: string;
  assertionId: string;
  implementationId: string;
  routePlanSnapshot: Record<string, unknown>;
  evidenceRefs: string[];
  fixtureCaseId: string | null;
  fixtureContentHash: string | null;
  inputDigest: string;
  outputDigest: string | null;
  idempotencyScope: string;
  idempotencyKeyHash: string;
  status: WorkflowStepRunStatus;
  recordsCount: number;
  providerCallAttempted: false;
  credentialReadAttempted: false;
  actorRun: false;
  browserRun: false;
  llmCall: false;
  productionWriteAllowed: false;
  startedAt: string;
  finishedAt: string | null;
  createdAt: string;
};

export type WorkflowFixtureReadBoundary = {
  executionMode: "fixture";
  liveExecutionAuthorized: false;
  providerCall: false;
  providerCallAttempted: false;
  credentialReadAttempted: false;
  actorRun: false;
  browserRun: false;
  llmCall: false;
  rawRecordWrite: false;
  datasetWrite: false;
  productionWriteAllowed: false;
  databaseWrite: false;
};

export type WorkflowExecutorEvidence = WorkflowFixtureReadBoundary & {
  schemaVersion: "workflow_executor_evidence.v1";
  workspaceId: string;
  projectId: string;
  workflowRunId: string;
  evidenceGrade: "L2_fixture_local";
  environment: "local";
  evaluatedAt: string;
  dispatches: Array<{
    id: string;
    workflowStepRunId: string;
    attemptGeneration: number;
    sourceActionRequestId: string | null;
    sourceActionReceiptId: string | null;
    state: "pending" | "claimable" | "terminal";
    createdAt: string;
    lease: null | {
      id: string;
      state: "active" | "released" | "expired" | "superseded" | "terminal";
      fencingToken: number;
      version: number;
      heartbeatAt: string;
      expiresAt: string;
      fresh: boolean;
    };
    lastEvent: null | {
      id: string;
      sequence: number;
      eventType: WorkflowExecutorEventEvidenceDto["event_type"];
      eventDigest: string;
      occurredAt: string;
    };
    preflightState: "not_evaluated" | "blocked" | "eligible";
    preflightBlockerCodes: string[];
    nextRequiredAuthority: "exact_live_provider_call_authorization" | null;
    credentialPermitIds: string[];
    providerPermitIds: string[];
    audits: Array<{
      id: string;
      attemptOrdinal: number;
      providerId: string;
      operationId: string;
      preflightId: string;
      transportState: WorkflowExecutorAuditEvidenceDto["transport_state"];
      outcomeCode: string | null;
      environment: WorkflowExecutorAuditEvidenceDto["environment"];
      startedAt: string | null;
      finishedAt: string | null;
    }>;
    auditTotal: number;
    budgetReservationState: "not_recorded";
    cancellation: {
      requested: boolean;
      acknowledged: boolean;
      requestId: string | null;
      reasonCode: string | null;
      requestedAt: string | null;
      acknowledgementId: string | null;
      safePoint: string | null;
      outcome: WorkflowExecutorCancellationEvidenceDto["outcome"];
      acknowledgedAt: string | null;
    };
  }>;
  dispatchTotal: number;
  businessCauseCode: WorkflowExecutorEvidenceResponseDto["business_cause_code"];
  businessImpactCode: WorkflowExecutorEvidenceResponseDto["business_impact_code"];
  nextActionCode: WorkflowExecutorEvidenceResponseDto["next_action_code"];
  clientConstruction: false;
  networkCall: false;
  liveProviderProof: false;
};

export type WorkflowRunListResult = WorkflowFixtureReadBoundary & {
  projectStatus: "active" | "archived";
  items: WorkflowRun[];
  total: number;
  limit: number;
  offset: number;
};

export type WorkflowRunDetail = WorkflowFixtureReadBoundary & {
  projectStatus: "active" | "archived";
  run: WorkflowRun;
  steps: WorkflowStepRun[];
};

export type WorkflowStepAttemptEvidence = {
  id: string;
  workspaceId: string;
  projectId: string;
  workflowRunId: string;
  stepRunId: string;
  attemptNumber: number;
  attemptKeyHash: string;
  status: WorkflowStepAttemptStatus;
  errorCode: string | null;
  backoffMs: number;
  providerCallAttempted: false;
  credentialReadAttempted: false;
  actorRun: false;
  browserRun: false;
  llmCall: false;
  productionWriteAllowed: false;
  startedAt: string;
  finishedAt: string;
  createdAt: string;
};

export type WorkflowFallbackGateEvidence = {
  gate: WorkflowFallbackGateName;
  status: "passed" | "blocked";
  code: string;
  evidenceRefs: string[];
};

export type WorkflowFallbackFieldDifference = {
  evidenceStatus: "verified" | "unavailable";
  requiredFields: string[];
  missingRequiredFields: string[];
  primaryMissingOptionalFields: string[];
  fallbackMissingOptionalFields: string[];
};

export type WorkflowFallbackCostEvidence = {
  evidenceStatus: "verified" | "unavailable";
  currency: "USD";
  unitCostUsd: string | null;
  ceilingUsd: string | null;
  withinCeiling: boolean | null;
};

export type WorkflowFallbackDecisionEvidence = {
  id: string;
  workspaceId: string;
  projectId: string;
  workflowPlanId: string;
  workflowVersionId: string;
  workflowRunId: string;
  stepRunId: string;
  createdByUserId: string;
  stepRef: string;
  requirementRef: string;
  contractVersion: "workflow_fallback_gate_replay.v1";
  decisionDigest: string;
  primaryFailureCode: string;
  primaryAssertionId: string;
  primaryImplementationId: string;
  fallbackAssertionId: string | null;
  fallbackImplementationId: string | null;
  outcome: "eligible" | "blocked";
  gates: WorkflowFallbackGateEvidence[];
  fieldDifference: WorkflowFallbackFieldDifference;
  costSnapshot: WorkflowFallbackCostEvidence;
  evidenceRefs: string[];
  approvalRequired: boolean;
  approvalStatus: WorkflowFallbackDecisionEvidenceDto["approval_status"];
  switchExecuted: false;
  providerCallAttempted: false;
  credentialReadAttempted: false;
  actorRun: false;
  browserRun: false;
  llmCall: false;
  productionWriteAllowed: false;
  createdAt: string;
};

export type WorkflowAttemptFallbackEvidence = WorkflowFixtureReadBoundary & {
  schemaVersion: "workflow_attempt_fallback_evidence.v1";
  workspaceId: string;
  projectId: string;
  workflowRunId: string;
  attempts: WorkflowStepAttemptEvidence[];
  fallbackDecisions: WorkflowFallbackDecisionEvidence[];
  attemptTotal: number;
  fallbackDecisionTotal: number;
};

export type WorkflowCheckpoint = {
  id: string;
  executionSessionId: string;
  workspaceId: string;
  projectId: string;
  workflowPlanId: string;
  workflowVersionId: string;
  stepRef: string;
  requirementRef: string;
  implementationId: string;
  contractVersion: "workflow_step_checkpoint.v1";
  fixtureProfileId: string;
  fixtureProfileHash: string;
  stepInputDigest: string;
  pageNumber: number;
  cursorBefore: string | null;
  cursorBeforeDigest: string;
  cursorAfter: string | null;
  cursorAfterDigest: string | null;
  sideEffectKeyHash: string;
  pageOutputDigest: string;
  checkpointDigest: string;
  recordsCount: number;
  terminal: boolean;
  evidenceRefs: string[];
  providerCallAttempted: false;
  credentialReadAttempted: false;
  actorRun: false;
  browserRun: false;
  llmCall: false;
  rawRecordWrite: false;
  datasetWrite: false;
  productionWriteAllowed: false;
  confirmedAt: string;
  createdAt: string;
};

export type WorkflowCheckpointStepEvidence = {
  stepRunId: string;
  executionSessionId: string;
  stepRef: string;
  requirementRef: string;
  implementationId: string;
  checkpoints: WorkflowCheckpoint[];
  confirmedPages: number;
  confirmedRecords: number;
  terminal: boolean;
  nextPageNumber: number;
  nextCursor: string | null;
  resumeActionAvailable: false;
};

export type WorkflowBudgetAccount = {
  id: string;
  executionSessionId: string;
  workspaceId: string;
  projectId: string;
  workflowPlanId: string;
  workflowVersionId: string;
  contractVersion: "workflow_budget_account.v1";
  policyDigest: string;
  maxRequests: number;
  maxItems: number;
  quotaCeilings: Record<string, number>;
  maxCostUsd: string;
  maxTimeMs: number;
  evidenceRefs: string[];
};

export type WorkflowBudgetLedgerEntry = {
  id: string;
  budgetAccountId: string;
  executionSessionId: string;
  workspaceId: string;
  projectId: string;
  contractVersion: "workflow_budget_ledger.v1";
  policyDigest: string;
  entryNumber: number;
  stepRef: string;
  pageNumber: number;
  sideEffectKeyHash: string;
  status: "reserved" | "blocked";
  blockerCode: WorkflowBudgetBlockerCode | null;
  requestCount: number;
  itemCount: number;
  quotaUnits: Record<string, number>;
  estimatedCostUsd: string;
  reservedTimeMs: number;
  cumulativeRequestCount: number;
  cumulativeItemCount: number;
  cumulativeQuotaUnits: Record<string, number>;
  cumulativeCostUsd: string;
  cumulativeTimeMs: number;
  previousLedgerDigest: string | null;
  ledgerDigest: string;
};

export type WorkflowBudgetUsageEvidence = {
  requestCount: number;
  requestLimit: number;
  itemCount: number;
  itemLimit: number;
  quotaUnits: Record<string, number>;
  quotaCeilings: Record<string, number>;
  costUsd: string;
  costLimitUsd: string;
  timeMs: number;
  timeLimitMs: number;
};

export type WorkflowCheckpointBudgetEvidence = WorkflowFixtureReadBoundary & {
  schemaVersion: "workflow_checkpoint_budget_evidence.v1";
  workspaceId: string;
  projectId: string;
  workflowPlanId: string;
  workflowVersionId: string;
  workflowRunId: string;
  executionSessionId: string;
  checkpointSteps: WorkflowCheckpointStepEvidence[];
  checkpointStepTotal: number;
  checkpointPageTotal: number;
  budgetStatus: WorkflowBudgetEvidenceStatus;
  budgetAccount: WorkflowBudgetAccount | null;
  budgetEntries: WorkflowBudgetLedgerEntry[];
  budgetEntryTotal: number;
  usage: WorkflowBudgetUsageEvidence | null;
  heldReasonCode: WorkflowBudgetBlockerCode | null;
  resumeActionAvailable: false;
  budgetOverrideAvailable: false;
};

export type ProviderHealthSnapshot = {
  id: string;
  contractVersion: "provider_health_snapshot.v1";
  scopeKey: string;
  aggregationKey: string;
  snapshotVersion: number;
  platformId: string;
  implementationId: string;
  resourceType: string;
  operation: string;
  windowStartedAt: string;
  windowEndedAt: string;
  evaluatedAt: string;
  status: ProviderHealthStatus;
  sampleCount: number;
  successCount: number;
  timeoutCount: number;
  rateLimitedCount: number;
  transientErrorCount: number;
  terminalErrorCount: number;
  successRateBps: number;
  p95LatencyMs: number;
  reasonCodes: string[];
  policySnapshot: Record<string, number>;
  observationManifest: Array<Record<string, unknown>>;
  evidenceRefs: string[];
  previousSnapshotDigest: string | null;
  snapshotDigest: string;
  routingValidUntil: string;
  evidenceRetainUntil: string;
};

export type ProviderHealthRouteFeedback = {
  id: string;
  contractVersion: "provider_health_route_feedback.v1";
  routeKey: string;
  feedbackKey: string;
  feedbackVersion: number;
  platformId: string;
  resourceType: string;
  operation: string;
  originalCandidateOrder: string[];
  adjustedCandidateOrder: string[];
  candidateScoreManifest: Array<Record<string, unknown>>;
  sourceSnapshotManifest: Array<Record<string, unknown>>;
  rankingChanged: boolean;
  reasonCodes: string[];
  evidenceRefs: string[];
  previousFeedbackDigest: string | null;
  feedbackDigest: string;
  evaluatedAt: string;
  evidenceRetainUntil: string;
};

export type WorkflowProviderHealthCandidateEvidence = {
  implementationId: string;
  selectedForRun: boolean;
  healthStatus: WorkflowProviderHealthStatus;
  routingState: WorkflowProviderHealthRoutingState;
  snapshot: ProviderHealthSnapshot | null;
};

export type WorkflowProviderHealthStepEvidence = {
  stepRunId: string;
  stepRef: string;
  requirementRef: string;
  platformId: string;
  resourceType: string;
  operation: string;
  selectedImplementationId: string;
  candidates: WorkflowProviderHealthCandidateEvidence[];
  routeFeedback: ProviderHealthRouteFeedback | null;
  routeFeedbackMatch: "not_available" | "ordered_candidate_match";
  routeDecisionAppliedToRun: false;
};

export type WorkflowProviderHealthEvidence = WorkflowFixtureReadBoundary & {
  schemaVersion: "workflow_provider_health_evidence.v1";
  workspaceId: string;
  projectId: string;
  workflowRunId: string;
  readAt: string;
  steps: WorkflowProviderHealthStepEvidence[];
  stepTotal: number;
  observedCandidateTotal: number;
  routingActiveCandidateTotal: number;
  attentionCandidateTotal: number;
  routeFeedbackTotal: number;
  healthProbeAttempted: false;
  catalogMutationApplied: false;
  automaticRouteSwitchExecuted: false;
  routeSwitchActionAvailable: false;
};

export type WorkflowRunActionGateEvidence = {
  action: WorkflowRunAction;
  preconditionStatus: WorkflowRunActionPreconditionStatus;
  actionAvailable: false;
  preconditionBlockerCodes: WorkflowRunActionPreconditionBlockerCode[];
  availabilityBlockerCodes: WorkflowRunActionAvailabilityBlockerCode[];
  nextActionCode: WorkflowRunActionNextActionCode;
  evidenceRefs: string[];
};

export type WorkflowRunActionGatesV1 = WorkflowFixtureReadBoundary & {
  schemaVersion: "workflow_run_action_gates.v1";
  workspaceId: string;
  projectId: string;
  workflowPlanId: string;
  workflowVersionId: string;
  workflowRunId: string;
  runStatus: WorkflowRunStatus;
  gates: WorkflowRunActionGateEvidence[];
  readyForReviewTotal: number;
  blockedTotal: number;
  notApplicableTotal: number;
  availableActionTotal: 0;
  mutationEndpointsAvailable: false;
  durableActionAuditAvailable: false;
  actionMutationExecuted: false;
};

export type WorkflowRunActionGateV2Evidence = {
  action: WorkflowRunAction;
  preconditionStatus: WorkflowRunActionPreconditionStatus;
  preconditionBlockerCodes: WorkflowRunActionPreconditionBlockerCode[];
  submissionAvailable: boolean;
  availabilityBlockerCodes: WorkflowRunActionAvailabilityBlockerCode[];
  approvalKind: WorkflowActionApprovalKind;
  approvalReceiptRequired: true;
  evidenceRefs: string[];
  expiresAt: string;
};

export type WorkflowRunActionGatesV2 = WorkflowFixtureReadBoundary & {
  schemaVersion: "workflow_run_action_gates.v2";
  workspaceId: string;
  projectId: string;
  workflowPlanId: string;
  workflowVersionId: string;
  workflowRunId: string;
  runStatus: WorkflowRunStatus;
  actionGateDigest: string;
  actionContextVersion: number;
  gates: WorkflowRunActionGateV2Evidence[];
  readyForReviewTotal: number;
  blockedTotal: number;
  notApplicableTotal: number;
  availableActionTotal: number;
  mutationEndpointsAvailable: true;
  durableActionAuditAvailable: true;
  actionMutationExecuted: false;
};

export type WorkflowRunActionGates =
  | WorkflowRunActionGatesV1
  | WorkflowRunActionGatesV2;

export type WorkflowActionReasonCode =
  | "retry_after_retryable_failure"
  | "resume_from_confirmed_checkpoint"
  | "cancel_operator_request"
  | "cancel_policy_violation"
  | "budget_override_business_exception"
  | "route_switch_verified_fallback"
  | "override_revoked_before_consumption";

export type WorkflowRetryActionParametersDto = {
  action: "retry";
  target_step_run_ids: string[];
  expected_retry_generation: number;
  attempt_evidence_digest: string;
  retry_policy_digest: string;
};

export type WorkflowResumeActionParametersDto = {
  action: "resume";
  checkpoint_digest: string;
  budget_policy_digest: string;
  budget_ledger_digest: string;
};

export type WorkflowCancelActionParametersDto = {
  action: "cancel";
  cancel_scope: "held_run" | "running_run";
};

export type WorkflowBudgetOverrideActionParametersDto = {
  action: "budget_override";
  request_limit: number;
  item_limit: number;
  quota_unit_limit: number;
  cost_limit_usd: string;
  time_limit_ms: number;
  expires_at: string;
};

export type WorkflowRouteSwitchActionParametersDto = {
  action: "route_switch";
  step_run_id: string;
  primary_implementation_id: string;
  fallback_implementation_id: string;
  fallback_decision_digest: string;
  field_difference_digest: string;
  cost_digest: string;
  provider_health_digest: string;
};

export type WorkflowActionParametersDto =
  | WorkflowRetryActionParametersDto
  | WorkflowResumeActionParametersDto
  | WorkflowCancelActionParametersDto
  | WorkflowBudgetOverrideActionParametersDto
  | WorkflowRouteSwitchActionParametersDto;

type WorkflowActionProposalDto = {
  action: WorkflowRunAction;
  expected_action_context_version: number;
  expected_run_status: WorkflowRunStatus;
  action_gate_digest: string;
  reason_code: WorkflowActionReasonCode;
  reason: string;
  parameters: WorkflowActionParametersDto;
};

export type WorkflowActionApprovalRequestDto = WorkflowActionProposalDto & {
  schema_version: "workflow_action_approval_request.v1";
  approval_kind: WorkflowActionApprovalKind;
};

export type WorkflowRunActionRequestDto = WorkflowActionProposalDto & {
  schema_version: "workflow_run_action_request.v1";
  approval_receipt_id: string;
};

export type WorkflowActionApprovalReceiptDto = {
  schema_version: "workflow_action_approval_receipt.v1";
  id: string;
  workspace_id: string;
  project_id: string;
  workflow_run_id: string;
  approver_user_id: string;
  action: WorkflowRunAction;
  approval_kind: WorkflowActionApprovalKind;
  proposal_digest: string;
  expected_action_context_version: number;
  expected_run_status: WorkflowRunStatus;
  action_gate_digest: string;
  evidence_digests: string[];
  reason_code: WorkflowActionReasonCode;
  reason: string;
  issued_at: string;
  expires_at: string;
  database_write: boolean;
  idempotent_replay: boolean;
  provider_call: false;
  credential_read_attempted: false;
  execution_started: false;
  production_write_allowed: false;
};

export type WorkflowActionReceiptDto = {
  schema_version: "workflow_action_receipt.v1";
  id: string;
  request_id: string;
  workspace_id: string;
  project_id: string;
  workflow_run_id: string;
  action: WorkflowRunAction;
  outcome: "accepted" | "accepted_pending_executor_ack";
  before_action_context_version: number;
  after_action_context_version: number;
  before_run_status: WorkflowRunStatus;
  after_run_status: WorkflowRunStatus;
  state_changed: boolean;
  database_write: boolean;
  idempotent_replay: boolean;
  provider_call: false;
  credential_read_attempted: false;
  execution_started: false;
  production_write_allowed: false;
  next_action_code:
    | "await_fixture_executor"
    | "refresh_workflow_run"
    | "workflow_run_cancelled"
    | "review_resume_after_budget_override"
    | "review_retry_after_route_override";
  receipt_digest: string;
  created_at: string;
};

export type WorkflowActionApprovalReceipt = {
  id: string;
  action: WorkflowRunAction;
  approvalKind: WorkflowActionApprovalKind;
  proposalDigest: string;
  actionGateDigest: string;
  evidenceDigests: string[];
  expectedActionContextVersion: number;
  expectedRunStatus: WorkflowRunStatus;
  reasonCode: WorkflowActionReasonCode;
  reason: string;
  issuedAt: string;
  expiresAt: string;
  databaseWrite: boolean;
  idempotentReplay: boolean;
};

export type WorkflowActionReceipt = {
  id: string;
  requestId: string;
  action: WorkflowRunAction;
  outcome: "accepted" | "accepted_pending_executor_ack";
  beforeActionContextVersion: number;
  afterActionContextVersion: number;
  beforeRunStatus: WorkflowRunStatus;
  afterRunStatus: WorkflowRunStatus;
  stateChanged: boolean;
  databaseWrite: boolean;
  idempotentReplay: boolean;
  nextActionCode: WorkflowActionReceiptDto["next_action_code"];
  receiptDigest: string;
  createdAt: string;
};

export type WorkflowProviderLineagePreview = {
  stepRunId: string;
  implementationId: string;
  platform: string;
  resourceType: string;
  operation: string;
  fixtureCaseId: string;
  fixtureContentHash: string;
  outputDigest: string;
  recordsCount: number;
  evidenceRefs: string[];
};

export type WorkflowRawRecordLineagePreview = {
  sourceTaskRunId: string | null;
  sourceStepRunIds: string[];
  materializedRawRecordIds: string[];
  expectedRecordCount: number;
  rawRecordWrite: false;
  materialized: boolean;
  blockedReasons: string[];
};

export type WorkflowDatasetLineagePreview = {
  datasetId: string | null;
  datasetVersionId: string | null;
  sourceStepRunIds: string[];
  sourceRawRecordIds: string[];
  expectedRecordCount: number;
  datasetWrite: false;
  materialized: boolean;
  blockedReasons: string[];
};

export type WorkflowRunLineagePreview = WorkflowFixtureReadBoundary & {
  schemaVersion: "workflow_lineage_preview.v2";
  workflowRunId: string;
  workspaceId: string;
  projectId: string;
  lineageDigest: string;
  materializationEligible: boolean;
  providerEvidence: WorkflowProviderLineagePreview[];
  rawRecord: WorkflowRawRecordLineagePreview;
  dataset: WorkflowDatasetLineagePreview;
  blockedReasons: string[];
};

export type WorkflowShadowDifferenceEvidence = {
  sampledRecordKeys: string[];
  matchedRecordKeys: string[];
  mismatchedRecordKeys: string[];
  primaryOnlyRecordKeys: string[];
  shadowOnlyRecordKeys: string[];
  missingRequiredFields: string[];
  primaryOnlyFields: string[];
  shadowOnlyFields: string[];
};

export type WorkflowShadowComparison = WorkflowFixtureReadBoundary & {
  id: string;
  workspaceId: string;
  projectId: string;
  workflowRunId: string;
  stepRunId: string;
  requirementRef: string;
  contractVersion: "workflow_shadow_comparison.v1";
  comparisonDigest: string;
  primaryImplementationId: string;
  shadowImplementationId: string;
  fixtureProfileId: string;
  fixtureProfileHash: string;
  primaryFixtureCaseId: string;
  primaryFixtureContentHash: string;
  shadowFixtureCaseId: string;
  shadowFixtureContentHash: string;
  sampleRate: number;
  maxItems: number;
  sampledItems: number;
  matchedItems: number;
  mismatchedItems: number;
  primaryOnlyItems: number;
  shadowOnlyItems: number;
  equivalenceStatus: WorkflowShadowEquivalenceStatus;
  differenceEvidence: WorkflowShadowDifferenceEvidence;
  routingRecommendation: WorkflowShadowRoutingRecommendation;
  evidenceRefs: string[];
  catalogMutationApplied: false;
  routeRankingMutationApplied: false;
  createdAt: string;
};

export type WorkflowShadowComparisonListResult = WorkflowFixtureReadBoundary & {
  items: WorkflowShadowComparison[];
  total: number;
};
