import { ApiRequestError, apiFetch, mockApiEnabled } from "@/lib/api/client";
import {
  buildMockWorkflowAttemptFallbackEvidenceDto,
  buildMockWorkflowCheckpointBudgetEvidenceDto,
  buildMockWorkflowExecutorEvidenceDto,
  buildMockWorkflowFixtureRunCreateDto,
  buildMockWorkflowFixtureRunGateDto,
  buildMockWorkflowRunDetailDto,
  buildMockWorkflowRunLineagePreviewDto,
  buildMockWorkflowRunListDto,
  buildMockWorkflowProviderHealthEvidenceDto,
  buildMockWorkflowRunActionGatesDto,
  buildMockWorkflowShadowComparisonListDto,
} from "@/lib/workflow-run-mock";
import type {
  ProviderHealthRouteFeedback,
  ProviderHealthRouteFeedbackDto,
  ProviderHealthSnapshot,
  ProviderHealthSnapshotDto,
  WorkflowActionApprovalReceipt,
  WorkflowActionApprovalReceiptDto,
  WorkflowActionApprovalRequestDto,
  WorkflowActionReceipt,
  WorkflowActionReceiptDto,
  WorkflowAttemptFallbackEvidence,
  WorkflowAttemptFallbackEvidenceResponseDto,
  WorkflowBudgetAccount,
  WorkflowBudgetLedgerEntry,
  WorkflowCheckpoint,
  WorkflowCheckpointBudgetEvidence,
  WorkflowCheckpointBudgetEvidenceResponseDto,
  WorkflowCheckpointStepEvidence,
  WorkflowFallbackDecisionEvidence,
  WorkflowFallbackDecisionEvidenceDto,
  WorkflowExecutorEvidence,
  WorkflowExecutorEvidenceResponseDto,
  WorkflowFixtureReadBoundary,
  WorkflowFixtureReadBoundaryDto,
  WorkflowFixtureRunCreateInput,
  WorkflowFixtureRunCreateRequestDto,
  WorkflowFixtureRunCreateResponseDto,
  WorkflowFixtureRunCreateResult,
  WorkflowFixtureRunGate,
  WorkflowFixtureRunGateDto,
  WorkflowRun,
  WorkflowRunActionGateEvidence,
  WorkflowRunActionGateV2Evidence,
  WorkflowRunActionGates,
  WorkflowRunActionGatesResponseDto,
  WorkflowRunActionRequestDto,
  WorkflowRunDetail,
  WorkflowRunDetailResponseDto,
  WorkflowRunDto,
  WorkflowRunLineagePreview,
  WorkflowRunLineagePreviewDto,
  WorkflowRunListResponseDto,
  WorkflowRunListResult,
  WorkflowProviderHealthCandidateEvidence,
  WorkflowProviderHealthEvidence,
  WorkflowProviderHealthEvidenceResponseDto,
  WorkflowShadowComparison,
  WorkflowShadowComparisonDto,
  WorkflowShadowComparisonListResponseDto,
  WorkflowShadowComparisonListResult,
  WorkflowStepRun,
  WorkflowStepAttemptEvidence,
  WorkflowStepAttemptEvidenceDto,
  WorkflowStepRunDto,
} from "@/types/workflow-run";

export type WorkflowRunListOptions = {
  workflowPlanId?: string;
  workflowVersionId?: string;
  limit?: number;
  offset?: number;
  signal?: AbortSignal;
};

export type WorkflowRunTransport = {
  listRuns: (
    projectId: string,
    options?: WorkflowRunListOptions,
  ) => Promise<WorkflowRunListResult>;
  getRun: (
    projectId: string,
    runId: string,
    options?: { signal?: AbortSignal },
  ) => Promise<WorkflowRunDetail>;
  getAttemptFallbackEvidence: (
    projectId: string,
    runId: string,
    options?: { signal?: AbortSignal },
  ) => Promise<WorkflowAttemptFallbackEvidence>;
  getCheckpointBudgetEvidence: (
    projectId: string,
    runId: string,
    options?: { signal?: AbortSignal },
  ) => Promise<WorkflowCheckpointBudgetEvidence>;
  getProviderHealthEvidence: (
    projectId: string,
    runId: string,
    options?: { signal?: AbortSignal },
  ) => Promise<WorkflowProviderHealthEvidence>;
  getExecutorEvidence: (
    projectId: string,
    runId: string,
    options?: { signal?: AbortSignal },
  ) => Promise<WorkflowExecutorEvidence>;
  getActionGates: (
    projectId: string,
    runId: string,
    options?: { signal?: AbortSignal },
  ) => Promise<WorkflowRunActionGates>;
  createActionApproval: (
    projectId: string,
    runId: string,
    payload: WorkflowActionApprovalRequestDto,
    idempotencyKey: string,
    options?: { signal?: AbortSignal },
  ) => Promise<WorkflowActionApprovalReceipt>;
  createAction: (
    projectId: string,
    runId: string,
    payload: WorkflowRunActionRequestDto,
    idempotencyKey: string,
    options?: { signal?: AbortSignal },
  ) => Promise<WorkflowActionReceipt>;
  getLineagePreview: (
    projectId: string,
    runId: string,
    options?: { signal?: AbortSignal },
  ) => Promise<WorkflowRunLineagePreview>;
  getShadowComparisons: (
    projectId: string,
    runId: string,
    options?: { signal?: AbortSignal },
  ) => Promise<WorkflowShadowComparisonListResult>;
};

function assertTemplateLineagePair(
  templateId: string | null,
  revisionId: string | null,
): void {
  if ((templateId === null) !== (revisionId === null)) {
    throw new Error("workflow_run_template_lineage_pair_invalid");
  }
}

function mapWorkflowRun(response: WorkflowRunDto): WorkflowRun {
  assertTemplateLineagePair(
    response.workflow_template_id,
    response.workflow_template_revision_id,
  );
  return {
    id: response.id,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    workflowPlanId: response.workflow_plan_id,
    workflowVersionId: response.workflow_version_id,
    workflowTemplateId: response.workflow_template_id,
    workflowTemplateRevisionId: response.workflow_template_revision_id,
    createdByUserId: response.created_by_user_id,
    executionContractVersion: response.execution_contract_version,
    executionMode: response.execution_mode,
    status: response.status,
    plannerContractVersion: response.planner_contract_version,
    previewFingerprint: response.preview_fingerprint,
    catalogSnapshotId: response.catalog_snapshot_id,
    policyVersion: response.policy_version,
    modeTemplateVersion: response.mode_template_version,
    queryVersions: { ...response.query_versions },
    fixtureProfileId: response.fixture_profile_id,
    fixtureProfileHash: response.fixture_profile_hash,
    totalSteps: response.total_steps,
    completedSteps: response.completed_steps,
    recordsCount: response.records_count,
    statusReasonCode: response.status_reason_code,
    impactCode: response.impact_code,
    missingFields: [...response.missing_fields],
    recoveryActionCodes: [...response.recovery_action_codes],
    providerCallAttempted: response.provider_call_attempted,
    credentialReadAttempted: response.credential_read_attempted,
    actorRun: response.actor_run,
    browserRun: response.browser_run,
    llmCall: response.llm_call,
    productionWriteAllowed: response.production_write_allowed,
    startedAt: response.started_at,
    finishedAt: response.finished_at,
    createdAt: response.created_at,
  };
}

function mapWorkflowStepRun(response: WorkflowStepRunDto): WorkflowStepRun {
  return {
    id: response.id,
    workflowRunId: response.workflow_run_id,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    stepRef: response.step_ref,
    requirementRef: response.requirement_ref,
    sequence: response.sequence,
    platform: response.platform,
    resourceType: response.resource_type,
    operation: response.operation,
    assertionId: response.assertion_id,
    implementationId: response.implementation_id,
    routePlanSnapshot: { ...response.route_plan_snapshot },
    evidenceRefs: [...response.evidence_refs],
    fixtureCaseId: response.fixture_case_id,
    fixtureContentHash: response.fixture_content_hash,
    inputDigest: response.input_digest,
    outputDigest: response.output_digest,
    idempotencyScope: response.idempotency_scope,
    idempotencyKeyHash: response.idempotency_key_hash,
    status: response.status,
    recordsCount: response.records_count,
    providerCallAttempted: response.provider_call_attempted,
    credentialReadAttempted: response.credential_read_attempted,
    actorRun: response.actor_run,
    browserRun: response.browser_run,
    llmCall: response.llm_call,
    productionWriteAllowed: response.production_write_allowed,
    startedAt: response.started_at,
    finishedAt: response.finished_at,
    createdAt: response.created_at,
  };
}

function mapReadBoundary(
  response: WorkflowFixtureReadBoundaryDto,
): WorkflowFixtureReadBoundary {
  return {
    executionMode: response.execution_mode,
    liveExecutionAuthorized: response.live_execution_authorized,
    providerCall: response.provider_call,
    providerCallAttempted: response.provider_call_attempted,
    credentialReadAttempted: response.credential_read_attempted,
    actorRun: response.actor_run,
    browserRun: response.browser_run,
    llmCall: response.llm_call,
    rawRecordWrite: response.raw_record_write,
    datasetWrite: response.dataset_write,
    productionWriteAllowed: response.production_write_allowed,
    databaseWrite: response.database_write,
  };
}

export function mapWorkflowRunList(
  response: WorkflowRunListResponseDto,
): WorkflowRunListResult {
  return {
    ...mapReadBoundary(response),
    projectStatus: response.project_status,
    items: response.items.map(mapWorkflowRun),
    total: response.total,
    limit: response.limit,
    offset: response.offset,
  };
}

export function mapWorkflowRunDetail(
  response: WorkflowRunDetailResponseDto,
): WorkflowRunDetail {
  return {
    ...mapReadBoundary(response),
    projectStatus: response.project_status,
    run: mapWorkflowRun(response.run),
    steps: response.steps.map(mapWorkflowStepRun),
  };
}

export function mapWorkflowExecutorEvidence(
  response: WorkflowExecutorEvidenceResponseDto,
): WorkflowExecutorEvidence {
  const boundary = mapReadBoundary(response);
  const dispatches = response.dispatches.map((dispatch) => {
    const cancellation = dispatch.cancellation;
    const requestComplete =
      cancellation.request_id !== null &&
      cancellation.reason_code !== null &&
      cancellation.requested_at !== null;
    const acknowledgementComplete =
      cancellation.acknowledgement_id !== null &&
      cancellation.safe_point !== null &&
      cancellation.outcome !== null &&
      cancellation.acknowledged_at !== null;
    const lineagePairValid =
      (dispatch.source_action_request_id === null) ===
      (dispatch.source_action_receipt_id === null);
    const preflightValid =
      (dispatch.preflight_state === "eligible") ===
        (dispatch.next_required_authority ===
          "exact_live_provider_call_authorization") &&
      (dispatch.preflight_state === "blocked"
        ? dispatch.preflight_blocker_codes.length > 0
        : dispatch.preflight_blocker_codes.length === 0);
    const leaseValid =
      dispatch.lease === null ||
      (dispatch.lease.fencing_token >= 1 &&
        dispatch.lease.version >= 1 &&
        Date.parse(dispatch.lease.expires_at) >
          Date.parse(dispatch.lease.heartbeat_at));
    if (
      !lineagePairValid ||
      !preflightValid ||
      !leaseValid ||
      dispatch.attempt_generation < 0 ||
      dispatch.audit_total !== dispatch.audits.length ||
      cancellation.requested !== requestComplete ||
      cancellation.acknowledged !== acknowledgementComplete ||
      (cancellation.acknowledged && !cancellation.requested)
    ) {
      throw new Error("workflow_executor_dispatch_evidence_boundary_invalid");
    }
    return {
      id: dispatch.id,
      workflowStepRunId: dispatch.workflow_step_run_id,
      attemptGeneration: dispatch.attempt_generation,
      sourceActionRequestId: dispatch.source_action_request_id,
      sourceActionReceiptId: dispatch.source_action_receipt_id,
      state: dispatch.state,
      createdAt: dispatch.created_at,
      lease: dispatch.lease
        ? {
            id: dispatch.lease.id,
            state: dispatch.lease.state,
            fencingToken: dispatch.lease.fencing_token,
            version: dispatch.lease.version,
            heartbeatAt: dispatch.lease.heartbeat_at,
            expiresAt: dispatch.lease.expires_at,
            fresh: dispatch.lease.fresh,
          }
        : null,
      lastEvent: dispatch.last_event
        ? {
            id: dispatch.last_event.id,
            sequence: dispatch.last_event.sequence,
            eventType: dispatch.last_event.event_type,
            eventDigest: dispatch.last_event.event_digest,
            occurredAt: dispatch.last_event.occurred_at,
          }
        : null,
      preflightState: dispatch.preflight_state,
      preflightBlockerCodes: [...dispatch.preflight_blocker_codes],
      nextRequiredAuthority: dispatch.next_required_authority,
      credentialPermitIds: [...dispatch.credential_permit_ids],
      providerPermitIds: [...dispatch.provider_permit_ids],
      audits: dispatch.audits.map((audit) => ({
        id: audit.id,
        attemptOrdinal: audit.attempt_ordinal,
        providerId: audit.provider_id,
        operationId: audit.operation_id,
        preflightId: audit.preflight_id,
        transportState: audit.transport_state,
        outcomeCode: audit.outcome_code,
        environment: audit.environment,
        startedAt: audit.started_at,
        finishedAt: audit.finished_at,
      })),
      auditTotal: dispatch.audit_total,
      budgetReservationState: dispatch.budget_reservation_state,
      cancellation: {
        requested: cancellation.requested,
        acknowledged: cancellation.acknowledged,
        requestId: cancellation.request_id,
        reasonCode: cancellation.reason_code,
        requestedAt: cancellation.requested_at,
        acknowledgementId: cancellation.acknowledgement_id,
        safePoint: cancellation.safe_point,
        outcome: cancellation.outcome,
        acknowledgedAt: cancellation.acknowledged_at,
      },
    };
  });
  const boundaryInvalid =
    response.schema_version !== "workflow_executor_evidence.v1" ||
    response.evidence_grade !== "L2_fixture_local" ||
    response.environment !== "local" ||
    boundary.executionMode !== "fixture" ||
    boundary.liveExecutionAuthorized ||
    boundary.providerCall ||
    boundary.providerCallAttempted ||
    boundary.credentialReadAttempted ||
    boundary.actorRun ||
    boundary.browserRun ||
    boundary.llmCall ||
    boundary.rawRecordWrite ||
    boundary.datasetWrite ||
    boundary.productionWriteAllowed ||
    boundary.databaseWrite ||
    response.client_construction ||
    response.network_call ||
    response.live_provider_proof ||
    response.dispatch_total !== dispatches.length ||
    new Set(dispatches.map((dispatch) => dispatch.id)).size !==
      dispatches.length;
  if (boundaryInvalid) {
    throw new Error("workflow_executor_evidence_boundary_invalid");
  }
  return {
    ...boundary,
    schemaVersion: response.schema_version,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    workflowRunId: response.workflow_run_id,
    evidenceGrade: response.evidence_grade,
    environment: response.environment,
    evaluatedAt: response.evaluated_at,
    dispatches,
    dispatchTotal: response.dispatch_total,
    businessCauseCode: response.business_cause_code,
    businessImpactCode: response.business_impact_code,
    nextActionCode: response.next_action_code,
    clientConstruction: response.client_construction,
    networkCall: response.network_call,
    liveProviderProof: response.live_provider_proof,
  };
}

function mapWorkflowStepAttemptEvidence(
  response: WorkflowStepAttemptEvidenceDto,
): WorkflowStepAttemptEvidence {
  return {
    id: response.id,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    workflowRunId: response.workflow_run_id,
    stepRunId: response.step_run_id,
    attemptNumber: response.attempt_number,
    attemptKeyHash: response.attempt_key_hash,
    status: response.status,
    errorCode: response.error_code,
    backoffMs: response.backoff_ms,
    providerCallAttempted: response.provider_call_attempted,
    credentialReadAttempted: response.credential_read_attempted,
    actorRun: response.actor_run,
    browserRun: response.browser_run,
    llmCall: response.llm_call,
    productionWriteAllowed: response.production_write_allowed,
    startedAt: response.started_at,
    finishedAt: response.finished_at,
    createdAt: response.created_at,
  };
}

function mapWorkflowFallbackDecisionEvidence(
  response: WorkflowFallbackDecisionEvidenceDto,
): WorkflowFallbackDecisionEvidence {
  return {
    id: response.id,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    workflowPlanId: response.workflow_plan_id,
    workflowVersionId: response.workflow_version_id,
    workflowRunId: response.workflow_run_id,
    stepRunId: response.step_run_id,
    createdByUserId: response.created_by_user_id,
    stepRef: response.step_ref,
    requirementRef: response.requirement_ref,
    contractVersion: response.contract_version,
    decisionDigest: response.decision_digest,
    primaryFailureCode: response.primary_failure_code,
    primaryAssertionId: response.primary_assertion_id,
    primaryImplementationId: response.primary_implementation_id,
    fallbackAssertionId: response.fallback_assertion_id,
    fallbackImplementationId: response.fallback_implementation_id,
    outcome: response.outcome,
    gates: response.gates.map((gate) => ({
      gate: gate.gate,
      status: gate.status,
      code: gate.code,
      evidenceRefs: [...gate.evidence_refs],
    })),
    fieldDifference: {
      evidenceStatus: response.field_difference.evidence_status,
      requiredFields: [...response.field_difference.required_fields],
      missingRequiredFields: [
        ...response.field_difference.missing_required_fields,
      ],
      primaryMissingOptionalFields: [
        ...response.field_difference.primary_missing_optional_fields,
      ],
      fallbackMissingOptionalFields: [
        ...response.field_difference.fallback_missing_optional_fields,
      ],
    },
    costSnapshot: {
      evidenceStatus: response.cost_snapshot.evidence_status,
      currency: response.cost_snapshot.currency,
      unitCostUsd:
        response.cost_snapshot.unit_cost_usd === null
          ? null
          : String(response.cost_snapshot.unit_cost_usd),
      ceilingUsd:
        response.cost_snapshot.ceiling_usd === null
          ? null
          : String(response.cost_snapshot.ceiling_usd),
      withinCeiling: response.cost_snapshot.within_ceiling,
    },
    evidenceRefs: [...response.evidence_refs],
    approvalRequired: response.approval_required,
    approvalStatus: response.approval_status,
    switchExecuted: response.switch_executed,
    providerCallAttempted: response.provider_call_attempted,
    credentialReadAttempted: response.credential_read_attempted,
    actorRun: response.actor_run,
    browserRun: response.browser_run,
    llmCall: response.llm_call,
    productionWriteAllowed: response.production_write_allowed,
    createdAt: response.created_at,
  };
}

export function mapWorkflowAttemptFallbackEvidence(
  response: WorkflowAttemptFallbackEvidenceResponseDto,
): WorkflowAttemptFallbackEvidence {
  const boundary = mapReadBoundary(response);
  const attempts = response.attempts.map(mapWorkflowStepAttemptEvidence);
  const fallbackDecisions = response.fallback_decisions.map(
    mapWorkflowFallbackDecisionEvidence,
  );
  const boundaryInvalid =
    response.schema_version !== "workflow_attempt_fallback_evidence.v1" ||
    boundary.executionMode !== "fixture" ||
    boundary.liveExecutionAuthorized ||
    boundary.providerCall ||
    boundary.providerCallAttempted ||
    boundary.credentialReadAttempted ||
    boundary.actorRun ||
    boundary.browserRun ||
    boundary.llmCall ||
    boundary.rawRecordWrite ||
    boundary.datasetWrite ||
    boundary.productionWriteAllowed ||
    boundary.databaseWrite;
  const attemptIds = attempts.map((item) => item.id);
  const attemptsByStep = new Map<string, number[]>();
  for (const attempt of attempts) {
    const numbers = attemptsByStep.get(attempt.stepRunId) ?? [];
    numbers.push(attempt.attemptNumber);
    attemptsByStep.set(attempt.stepRunId, numbers);
  }
  const attemptInvalid =
    response.attempt_total !== attempts.length ||
    new Set(attemptIds).size !== attemptIds.length ||
    attempts.some(
      (item) =>
        item.workspaceId !== response.workspace_id ||
        item.projectId !== response.project_id ||
        item.workflowRunId !== response.workflow_run_id ||
        item.providerCallAttempted ||
        item.credentialReadAttempted ||
        item.actorRun ||
        item.browserRun ||
        item.llmCall ||
        item.productionWriteAllowed ||
        !Number.isInteger(item.attemptNumber) ||
        item.attemptNumber < 1 ||
        item.attemptNumber > 4 ||
        item.backoffMs < 0 ||
        (item.status === "succeeded"
          ? item.errorCode !== null || item.backoffMs !== 0
          : item.errorCode === null),
    ) ||
    [...attemptsByStep.values()].some((numbers) => {
      const sorted = [...numbers].sort((left, right) => left - right);
      return sorted.some((number, index) => number !== index + 1);
    });
  const expectedGateOrder = [
    "trigger",
    "policy",
    "credential",
    "budget",
    "fields",
    "evidence",
    "approval",
  ].join("|");
  const decisionIds = fallbackDecisions.map((item) => item.id);
  const decisionStepIds = fallbackDecisions.map((item) => item.stepRunId);
  const fallbackInvalid =
    response.fallback_decision_total !== fallbackDecisions.length ||
    new Set(decisionIds).size !== decisionIds.length ||
    new Set(decisionStepIds).size !== decisionStepIds.length ||
    fallbackDecisions.some((item) => {
      const allPassed = item.gates.every((gate) => gate.status === "passed");
      return (
        item.workspaceId !== response.workspace_id ||
        item.projectId !== response.project_id ||
        item.workflowRunId !== response.workflow_run_id ||
        item.contractVersion !== "workflow_fallback_gate_replay.v1" ||
        item.gates.map((gate) => gate.gate).join("|") !== expectedGateOrder ||
        (item.outcome === "eligible") !== allPassed ||
        (item.fallbackAssertionId === null) !==
          (item.fallbackImplementationId === null) ||
        (item.outcome === "eligible" &&
          item.fallbackImplementationId === null) ||
        item.approvalRequired === (item.approvalStatus === "not_required") ||
        item.switchExecuted ||
        item.providerCallAttempted ||
        item.credentialReadAttempted ||
        item.actorRun ||
        item.browserRun ||
        item.llmCall ||
        item.productionWriteAllowed
      );
    });
  if (boundaryInvalid || attemptInvalid || fallbackInvalid) {
    throw new Error("workflow_attempt_fallback_evidence_boundary_invalid");
  }
  return {
    ...boundary,
    schemaVersion: response.schema_version,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    workflowRunId: response.workflow_run_id,
    attempts,
    fallbackDecisions,
    attemptTotal: response.attempt_total,
    fallbackDecisionTotal: response.fallback_decision_total,
  };
}

function mapWorkflowCheckpoint(
  response: WorkflowCheckpointBudgetEvidenceResponseDto["checkpoint_steps"][number]["checkpoints"][number],
): WorkflowCheckpoint {
  return {
    id: response.id,
    executionSessionId: response.execution_session_id,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    workflowPlanId: response.workflow_plan_id,
    workflowVersionId: response.workflow_version_id,
    stepRef: response.step_ref,
    requirementRef: response.requirement_ref,
    implementationId: response.implementation_id,
    contractVersion: response.contract_version,
    fixtureProfileId: response.fixture_profile_id,
    fixtureProfileHash: response.fixture_profile_hash,
    stepInputDigest: response.step_input_digest,
    pageNumber: response.page_number,
    cursorBefore: response.cursor_before,
    cursorBeforeDigest: response.cursor_before_digest,
    cursorAfter: response.cursor_after,
    cursorAfterDigest: response.cursor_after_digest,
    sideEffectKeyHash: response.side_effect_key_hash,
    pageOutputDigest: response.page_output_digest,
    checkpointDigest: response.checkpoint_digest,
    recordsCount: response.records_count,
    terminal: response.terminal,
    evidenceRefs: [...response.evidence_refs],
    providerCallAttempted: response.provider_call_attempted,
    credentialReadAttempted: response.credential_read_attempted,
    actorRun: response.actor_run,
    browserRun: response.browser_run,
    llmCall: response.llm_call,
    rawRecordWrite: response.raw_record_write,
    datasetWrite: response.dataset_write,
    productionWriteAllowed: response.production_write_allowed,
    confirmedAt: response.confirmed_at,
    createdAt: response.created_at,
  };
}

function mapWorkflowBudgetAccount(
  response: NonNullable<
    WorkflowCheckpointBudgetEvidenceResponseDto["budget_account"]
  >,
): WorkflowBudgetAccount {
  return {
    id: response.id,
    executionSessionId: response.execution_session_id,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    workflowPlanId: response.workflow_plan_id,
    workflowVersionId: response.workflow_version_id,
    contractVersion: response.contract_version,
    policyDigest: response.policy_digest,
    maxRequests: response.max_requests,
    maxItems: response.max_items,
    quotaCeilings: { ...response.quota_ceilings },
    maxCostUsd: String(response.max_cost_usd),
    maxTimeMs: response.max_time_ms,
    evidenceRefs: [...response.evidence_refs],
  };
}

function mapWorkflowBudgetEntry(
  response: WorkflowCheckpointBudgetEvidenceResponseDto["budget_entries"][number],
): WorkflowBudgetLedgerEntry {
  return {
    id: response.id,
    budgetAccountId: response.budget_account_id,
    executionSessionId: response.execution_session_id,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    contractVersion: response.contract_version,
    policyDigest: response.policy_digest,
    entryNumber: response.entry_number,
    stepRef: response.step_ref,
    pageNumber: response.page_number,
    sideEffectKeyHash: response.side_effect_key_hash,
    status: response.status,
    blockerCode: response.blocker_code,
    requestCount: response.request_count,
    itemCount: response.item_count,
    quotaUnits: { ...response.quota_units },
    estimatedCostUsd: String(response.estimated_cost_usd),
    reservedTimeMs: response.reserved_time_ms,
    cumulativeRequestCount: response.cumulative_request_count,
    cumulativeItemCount: response.cumulative_item_count,
    cumulativeQuotaUnits: { ...response.cumulative_quota_units },
    cumulativeCostUsd: String(response.cumulative_cost_usd),
    cumulativeTimeMs: response.cumulative_time_ms,
    previousLedgerDigest: response.previous_ledger_digest,
    ledgerDigest: response.ledger_digest,
  };
}

function numericRecordEqual(
  left: Record<string, number>,
  right: Record<string, number>,
): boolean {
  const leftKeys = Object.keys(left).sort();
  const rightKeys = Object.keys(right).sort();
  return (
    leftKeys.join("|") === rightKeys.join("|") &&
    leftKeys.every((key) => left[key] === right[key])
  );
}

function hasFixtureSideEffectClaim(response: {
  provider_call_attempted: false;
  credential_read_attempted: false;
  actor_run: false;
  browser_run: false;
  llm_call: false;
  raw_record_write: false;
  dataset_write: false;
  production_write_allowed: false;
}): boolean {
  return (
    response.provider_call_attempted ||
    response.credential_read_attempted ||
    response.actor_run ||
    response.browser_run ||
    response.llm_call ||
    response.raw_record_write ||
    response.dataset_write ||
    response.production_write_allowed
  );
}

export function mapWorkflowCheckpointBudgetEvidence(
  response: WorkflowCheckpointBudgetEvidenceResponseDto,
): WorkflowCheckpointBudgetEvidence {
  const boundary = mapReadBoundary(response);
  const checkpointSteps: WorkflowCheckpointStepEvidence[] =
    response.checkpoint_steps.map((step) => ({
      stepRunId: step.step_run_id,
      executionSessionId: step.execution_session_id,
      stepRef: step.step_ref,
      requirementRef: step.requirement_ref,
      implementationId: step.implementation_id,
      checkpoints: step.checkpoints.map(mapWorkflowCheckpoint),
      confirmedPages: step.confirmed_pages,
      confirmedRecords: step.confirmed_records,
      terminal: step.terminal,
      nextPageNumber: step.next_page_number,
      nextCursor: step.next_cursor,
      resumeActionAvailable: step.resume_action_available,
    }));
  const account = response.budget_account
    ? mapWorkflowBudgetAccount(response.budget_account)
    : null;
  const entries = response.budget_entries.map(mapWorkflowBudgetEntry);
  const usage = response.usage
    ? {
        requestCount: response.usage.request_count,
        requestLimit: response.usage.request_limit,
        itemCount: response.usage.item_count,
        itemLimit: response.usage.item_limit,
        quotaUnits: { ...response.usage.quota_units },
        quotaCeilings: { ...response.usage.quota_ceilings },
        costUsd: String(response.usage.cost_usd),
        costLimitUsd: String(response.usage.cost_limit_usd),
        timeMs: response.usage.time_ms,
        timeLimitMs: response.usage.time_limit_ms,
      }
    : null;
  const boundaryInvalid =
    response.schema_version !== "workflow_checkpoint_budget_evidence.v1" ||
    boundary.executionMode !== "fixture" ||
    boundary.liveExecutionAuthorized ||
    boundary.providerCall ||
    boundary.providerCallAttempted ||
    boundary.credentialReadAttempted ||
    boundary.actorRun ||
    boundary.browserRun ||
    boundary.llmCall ||
    boundary.rawRecordWrite ||
    boundary.datasetWrite ||
    boundary.productionWriteAllowed ||
    boundary.databaseWrite ||
    response.resume_action_available ||
    response.budget_override_available;
  const ownerInvalid =
    response.execution_session_id !== response.workflow_run_id ||
    response.checkpoint_step_total !== checkpointSteps.length ||
    response.checkpoint_page_total !==
      checkpointSteps.reduce((total, step) => total + step.confirmedPages, 0) ||
    new Set(checkpointSteps.map((step) => step.stepRunId)).size !==
      checkpointSteps.length;
  const checkpointInvalid = checkpointSteps.some((step) => {
    const final = step.checkpoints.at(-1);
    let previous: WorkflowCheckpoint | undefined;
    const chainInvalid = step.checkpoints.some((checkpoint, index) => {
      const invalid =
        checkpoint.executionSessionId !== response.execution_session_id ||
        checkpoint.workspaceId !== response.workspace_id ||
        checkpoint.projectId !== response.project_id ||
        checkpoint.workflowPlanId !== response.workflow_plan_id ||
        checkpoint.workflowVersionId !== response.workflow_version_id ||
        checkpoint.stepRef !== step.stepRef ||
        checkpoint.requirementRef !== step.requirementRef ||
        checkpoint.implementationId !== step.implementationId ||
        checkpoint.pageNumber !== index + 1 ||
        checkpoint.recordsCount < 0 ||
        checkpoint.providerCallAttempted ||
        checkpoint.credentialReadAttempted ||
        checkpoint.actorRun ||
        checkpoint.browserRun ||
        checkpoint.llmCall ||
        checkpoint.rawRecordWrite ||
        checkpoint.datasetWrite ||
        checkpoint.productionWriteAllowed ||
        (previous !== undefined &&
          (previous.terminal ||
            checkpoint.cursorBefore !== previous.cursorAfter ||
            checkpoint.cursorBeforeDigest !== previous.cursorAfterDigest));
      previous = checkpoint;
      return invalid;
    });
    return (
      step.resumeActionAvailable ||
      step.executionSessionId !== response.execution_session_id ||
      step.checkpoints.length === 0 ||
      step.confirmedPages !== step.checkpoints.length ||
      step.confirmedRecords !==
        step.checkpoints.reduce(
          (total, checkpoint) => total + checkpoint.recordsCount,
          0,
        ) ||
      step.nextPageNumber !== step.confirmedPages + 1 ||
      final === undefined ||
      step.terminal !== final.terminal ||
      step.nextCursor !== final.cursorAfter ||
      chainInvalid
    );
  });

  let budgetInvalid = response.budget_entry_total !== entries.length;
  if (account === null) {
    budgetInvalid ||=
      response.budget_status !== "not_configured" ||
      entries.length > 0 ||
      usage !== null ||
      response.held_reason_code !== null;
  } else {
    budgetInvalid ||=
      response.budget_status === "not_configured" ||
      usage === null ||
      account.executionSessionId !== response.execution_session_id ||
      account.workspaceId !== response.workspace_id ||
      account.projectId !== response.project_id ||
      account.workflowPlanId !== response.workflow_plan_id ||
      account.workflowVersionId !== response.workflow_version_id ||
      hasFixtureSideEffectClaim(response.budget_account!);
    let previous: WorkflowBudgetLedgerEntry | undefined;
    for (const [index, entry] of entries.entries()) {
      budgetInvalid ||=
        entry.budgetAccountId !== account.id ||
        entry.executionSessionId !== response.execution_session_id ||
        entry.workspaceId !== response.workspace_id ||
        entry.projectId !== response.project_id ||
        entry.policyDigest !== account.policyDigest ||
        entry.entryNumber !== index + 1 ||
        entry.previousLedgerDigest !== (previous?.ledgerDigest ?? null) ||
        previous?.status === "blocked" ||
        hasFixtureSideEffectClaim(response.budget_entries[index]);
      previous = entry;
    }
    const final = entries.at(-1);
    const expectedStatus =
      final === undefined
        ? "configured"
        : final.status === "blocked"
          ? "held"
          : "within_limit";
    budgetInvalid ||=
      response.budget_status !== expectedStatus ||
      response.held_reason_code !==
        (final?.status === "blocked" ? final.blockerCode : null) ||
      usage === null ||
      usage.requestLimit !== account.maxRequests ||
      usage.itemLimit !== account.maxItems ||
      usage.costLimitUsd !== account.maxCostUsd ||
      usage.timeLimitMs !== account.maxTimeMs ||
      !numericRecordEqual(usage.quotaCeilings, account.quotaCeilings) ||
      usage.requestCount !== (final?.cumulativeRequestCount ?? 0) ||
      usage.itemCount !== (final?.cumulativeItemCount ?? 0) ||
      usage.costUsd !== (final?.cumulativeCostUsd ?? "0") ||
      usage.timeMs !== (final?.cumulativeTimeMs ?? 0) ||
      !numericRecordEqual(
        usage.quotaUnits,
        final?.cumulativeQuotaUnits ??
          Object.fromEntries(
            Object.keys(account.quotaCeilings).map((key) => [key, 0]),
          ),
      );
    const reservations = new Set(
      entries
        .filter((entry) => entry.status === "reserved")
        .map(
          (entry) =>
            `${entry.stepRef}|${entry.pageNumber}|${entry.sideEffectKeyHash}`,
        ),
    );
    budgetInvalid ||= checkpointSteps.some((step) =>
      step.checkpoints.some(
        (checkpoint) =>
          !reservations.has(
            `${checkpoint.stepRef}|${checkpoint.pageNumber}|${checkpoint.sideEffectKeyHash}`,
          ),
      ),
    );
  }
  if (boundaryInvalid || ownerInvalid || checkpointInvalid || budgetInvalid) {
    throw new Error("workflow_checkpoint_budget_evidence_boundary_invalid");
  }

  return {
    ...boundary,
    schemaVersion: response.schema_version,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    workflowPlanId: response.workflow_plan_id,
    workflowVersionId: response.workflow_version_id,
    workflowRunId: response.workflow_run_id,
    executionSessionId: response.execution_session_id,
    checkpointSteps,
    checkpointStepTotal: response.checkpoint_step_total,
    checkpointPageTotal: response.checkpoint_page_total,
    budgetStatus: response.budget_status,
    budgetAccount: account,
    budgetEntries: entries,
    budgetEntryTotal: response.budget_entry_total,
    usage,
    heldReasonCode: response.held_reason_code,
    resumeActionAvailable: response.resume_action_available,
    budgetOverrideAvailable: response.budget_override_available,
  };
}

function providerHealthBoundaryInvalid(
  response: Omit<WorkflowFixtureReadBoundaryDto, "database_write"> & {
    health_probe_attempted: false;
  },
): boolean {
  return (
    response.execution_mode !== "fixture" ||
    response.live_execution_authorized ||
    response.provider_call ||
    response.provider_call_attempted ||
    response.credential_read_attempted ||
    response.actor_run ||
    response.browser_run ||
    response.llm_call ||
    response.raw_record_write ||
    response.dataset_write ||
    response.production_write_allowed ||
    response.health_probe_attempted
  );
}

function mapProviderHealthSnapshot(
  response: ProviderHealthSnapshotDto,
): ProviderHealthSnapshot {
  const counts =
    response.success_count +
    response.timeout_count +
    response.rate_limited_count +
    response.transient_error_count +
    response.terminal_error_count;
  if (
    providerHealthBoundaryInvalid(response) ||
    response.contract_version !== "provider_health_snapshot.v1" ||
    response.snapshot_version < 1 ||
    response.sample_count < 1 ||
    counts !== response.sample_count ||
    response.observation_manifest.length !== response.sample_count ||
    response.success_rate_bps < 0 ||
    response.success_rate_bps > 10_000 ||
    response.p95_latency_ms < 0 ||
    Date.parse(response.window_ended_at) <=
      Date.parse(response.window_started_at) ||
    Date.parse(response.routing_valid_until) <=
      Date.parse(response.evaluated_at) ||
    Date.parse(response.evidence_retain_until) <=
      Date.parse(response.routing_valid_until)
  ) {
    throw new Error("workflow_provider_health_snapshot_boundary_invalid");
  }
  return {
    id: response.id,
    contractVersion: response.contract_version,
    scopeKey: response.scope_key,
    aggregationKey: response.aggregation_key,
    snapshotVersion: response.snapshot_version,
    platformId: response.platform_id,
    implementationId: response.implementation_id,
    resourceType: response.resource_type,
    operation: response.operation,
    windowStartedAt: response.window_started_at,
    windowEndedAt: response.window_ended_at,
    evaluatedAt: response.evaluated_at,
    status: response.status,
    sampleCount: response.sample_count,
    successCount: response.success_count,
    timeoutCount: response.timeout_count,
    rateLimitedCount: response.rate_limited_count,
    transientErrorCount: response.transient_error_count,
    terminalErrorCount: response.terminal_error_count,
    successRateBps: response.success_rate_bps,
    p95LatencyMs: response.p95_latency_ms,
    reasonCodes: [...response.reason_codes],
    policySnapshot: { ...response.policy_snapshot },
    observationManifest: response.observation_manifest.map((item) => ({
      ...item,
    })),
    evidenceRefs: [...response.evidence_refs],
    previousSnapshotDigest: response.previous_snapshot_digest,
    snapshotDigest: response.snapshot_digest,
    routingValidUntil: response.routing_valid_until,
    evidenceRetainUntil: response.evidence_retain_until,
  };
}

function mapProviderHealthRouteFeedback(
  response: ProviderHealthRouteFeedbackDto,
): ProviderHealthRouteFeedback {
  const sameCandidateSet =
    [...response.original_candidate_order].sort().join("|") ===
    [...response.adjusted_candidate_order].sort().join("|");
  if (
    providerHealthBoundaryInvalid(response) ||
    response.contract_version !== "provider_health_route_feedback.v1" ||
    response.catalog_mutation_applied ||
    response.automatic_route_switch_executed ||
    response.feedback_version < 1 ||
    response.original_candidate_order.length < 2 ||
    new Set(response.original_candidate_order).size !==
      response.original_candidate_order.length ||
    !sameCandidateSet ||
    response.ranking_changed !==
      (response.original_candidate_order.join("|") !==
        response.adjusted_candidate_order.join("|")) ||
    Date.parse(response.evidence_retain_until) <=
      Date.parse(response.evaluated_at)
  ) {
    throw new Error("workflow_provider_health_feedback_boundary_invalid");
  }
  return {
    id: response.id,
    contractVersion: response.contract_version,
    routeKey: response.route_key,
    feedbackKey: response.feedback_key,
    feedbackVersion: response.feedback_version,
    platformId: response.platform_id,
    resourceType: response.resource_type,
    operation: response.operation,
    originalCandidateOrder: [...response.original_candidate_order],
    adjustedCandidateOrder: [...response.adjusted_candidate_order],
    candidateScoreManifest: response.candidate_score_manifest.map((item) => ({
      ...item,
    })),
    sourceSnapshotManifest: response.source_snapshot_manifest.map((item) => ({
      ...item,
    })),
    rankingChanged: response.ranking_changed,
    reasonCodes: [...response.reason_codes],
    evidenceRefs: [...response.evidence_refs],
    previousFeedbackDigest: response.previous_feedback_digest,
    feedbackDigest: response.feedback_digest,
    evaluatedAt: response.evaluated_at,
    evidenceRetainUntil: response.evidence_retain_until,
  };
}

export function mapWorkflowProviderHealthEvidence(
  response: WorkflowProviderHealthEvidenceResponseDto,
): WorkflowProviderHealthEvidence {
  const boundary = mapReadBoundary(response);
  const steps = response.steps.map((step) => {
    const candidates: WorkflowProviderHealthCandidateEvidence[] =
      step.candidates.map((candidate) => ({
        implementationId: candidate.implementation_id,
        selectedForRun: candidate.selected_for_run,
        healthStatus: candidate.health_status,
        routingState: candidate.routing_state,
        snapshot: candidate.snapshot
          ? mapProviderHealthSnapshot(candidate.snapshot)
          : null,
      }));
    const feedback = step.route_feedback
      ? mapProviderHealthRouteFeedback(step.route_feedback)
      : null;
    const candidateIds = candidates.map(
      (candidate) => candidate.implementationId,
    );
    const selected = candidates.filter((candidate) => candidate.selectedForRun);
    const candidatesInvalid =
      candidateIds.length === 0 ||
      new Set(candidateIds).size !== candidateIds.length ||
      selected.length !== 1 ||
      selected[0]?.implementationId !== step.selected_implementation_id ||
      candidateIds[0] !== step.selected_implementation_id ||
      candidates.some(
        (candidate) =>
          (candidate.snapshot === null) !==
            (candidate.healthStatus === "not_observed") ||
          (candidate.snapshot === null) !==
            (candidate.routingState === "not_observed") ||
          (candidate.snapshot !== null &&
            (candidate.snapshot.implementationId !==
              candidate.implementationId ||
              candidate.snapshot.platformId !== step.platform_id ||
              candidate.snapshot.resourceType !== step.resource_type ||
              candidate.snapshot.operation !== step.operation ||
              candidate.snapshot.status !== candidate.healthStatus)),
      );
    const feedbackInvalid =
      (feedback === null) !== (step.route_feedback_match === "not_available") ||
      (feedback !== null &&
        (step.route_feedback_match !== "ordered_candidate_match" ||
          feedback.platformId !== step.platform_id ||
          feedback.resourceType !== step.resource_type ||
          feedback.operation !== step.operation ||
          feedback.originalCandidateOrder.join("|") !==
            candidateIds.join("|")));
    if (
      candidatesInvalid ||
      feedbackInvalid ||
      step.route_decision_applied_to_run
    ) {
      throw new Error("workflow_provider_health_step_boundary_invalid");
    }
    return {
      stepRunId: step.step_run_id,
      stepRef: step.step_ref,
      requirementRef: step.requirement_ref,
      platformId: step.platform_id,
      resourceType: step.resource_type,
      operation: step.operation,
      selectedImplementationId: step.selected_implementation_id,
      candidates,
      routeFeedback: feedback,
      routeFeedbackMatch: step.route_feedback_match,
      routeDecisionAppliedToRun: step.route_decision_applied_to_run,
    };
  });
  const candidates = steps.flatMap((step) => step.candidates);
  const boundaryInvalid =
    response.schema_version !== "workflow_provider_health_evidence.v1" ||
    boundary.executionMode !== "fixture" ||
    boundary.liveExecutionAuthorized ||
    boundary.providerCall ||
    boundary.providerCallAttempted ||
    boundary.credentialReadAttempted ||
    boundary.actorRun ||
    boundary.browserRun ||
    boundary.llmCall ||
    boundary.rawRecordWrite ||
    boundary.datasetWrite ||
    boundary.productionWriteAllowed ||
    boundary.databaseWrite ||
    response.health_probe_attempted ||
    response.catalog_mutation_applied ||
    response.automatic_route_switch_executed ||
    response.route_switch_action_available;
  const totalsInvalid =
    response.step_total !== steps.length ||
    new Set(steps.map((step) => step.stepRunId)).size !== steps.length ||
    response.observed_candidate_total !==
      candidates.filter((candidate) => candidate.snapshot !== null).length ||
    response.routing_active_candidate_total !==
      candidates.filter(
        (candidate) => candidate.routingState === "routing_active",
      ).length ||
    response.attention_candidate_total !==
      candidates.filter((candidate) =>
        ["degraded", "unhealthy"].includes(candidate.healthStatus),
      ).length ||
    response.route_feedback_total !==
      steps.filter((step) => step.routeFeedback !== null).length;
  if (boundaryInvalid || totalsInvalid) {
    throw new Error("workflow_provider_health_evidence_boundary_invalid");
  }
  return {
    ...boundary,
    schemaVersion: response.schema_version,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    workflowRunId: response.workflow_run_id,
    readAt: response.read_at,
    steps,
    stepTotal: response.step_total,
    observedCandidateTotal: response.observed_candidate_total,
    routingActiveCandidateTotal: response.routing_active_candidate_total,
    attentionCandidateTotal: response.attention_candidate_total,
    routeFeedbackTotal: response.route_feedback_total,
    healthProbeAttempted: response.health_probe_attempted,
    catalogMutationApplied: response.catalog_mutation_applied,
    automaticRouteSwitchExecuted: response.automatic_route_switch_executed,
    routeSwitchActionAvailable: response.route_switch_action_available,
  };
}

export function mapWorkflowRunActionGates(
  response: WorkflowRunActionGatesResponseDto,
): WorkflowRunActionGates {
  const boundary = mapReadBoundary(response);
  const expectedActions = [
    "retry",
    "resume",
    "cancel",
    "budget_override",
    "route_switch",
  ] as const;
  const commonBoundaryInvalid =
    boundary.executionMode !== "fixture" ||
    boundary.liveExecutionAuthorized ||
    boundary.providerCall ||
    boundary.providerCallAttempted ||
    boundary.credentialReadAttempted ||
    boundary.actorRun ||
    boundary.browserRun ||
    boundary.llmCall ||
    boundary.rawRecordWrite ||
    boundary.datasetWrite ||
    boundary.productionWriteAllowed ||
    boundary.databaseWrite ||
    response.action_mutation_executed;
  if (commonBoundaryInvalid) {
    throw new Error("workflow_run_action_gates_boundary_invalid");
  }
  if (response.schema_version === "workflow_run_action_gates.v2") {
    const gates: WorkflowRunActionGateV2Evidence[] = response.gates.map(
      (gate) => {
        const preconditionBlockers = [...gate.precondition_blocker_codes];
        const availabilityBlockers = [...gate.availability_blocker_codes];
        const evidenceRefs = [...gate.evidence_refs];
        const expectedApprovalKind =
          gate.action === "budget_override"
            ? "owner_policy_override"
            : gate.action === "route_switch"
              ? "owner_route_override"
              : "owner_confirmation";
        const expectedAvailable =
          gate.precondition_status === "ready_for_review" &&
          preconditionBlockers.length === 0 &&
          availabilityBlockers.length === 0;
        if (
          gate.submission_available !== expectedAvailable ||
          gate.approval_kind !== expectedApprovalKind ||
          !gate.approval_receipt_required ||
          Number.isNaN(Date.parse(gate.expires_at)) ||
          new Set(preconditionBlockers).size !== preconditionBlockers.length ||
          new Set(availabilityBlockers).size !== availabilityBlockers.length ||
          evidenceRefs.length === 0 ||
          new Set(evidenceRefs).size !== evidenceRefs.length ||
          (gate.precondition_status === "ready_for_review"
            ? preconditionBlockers.length !== 0
            : preconditionBlockers.length === 0)
        ) {
          throw new Error("workflow_run_action_gate_boundary_invalid");
        }
        return {
          action: gate.action,
          preconditionStatus: gate.precondition_status,
          preconditionBlockerCodes: preconditionBlockers,
          submissionAvailable: gate.submission_available,
          availabilityBlockerCodes: availabilityBlockers,
          approvalKind: gate.approval_kind,
          approvalReceiptRequired: gate.approval_receipt_required,
          evidenceRefs,
          expiresAt: gate.expires_at,
        };
      },
    );
    const totalsInvalid =
      gates.map((item) => item.action).join("|") !== expectedActions.join("|") ||
      response.ready_for_review_total !==
        gates.filter((item) => item.preconditionStatus === "ready_for_review")
          .length ||
      response.blocked_total !==
        gates.filter((item) => item.preconditionStatus === "blocked").length ||
      response.not_applicable_total !==
        gates.filter((item) => item.preconditionStatus === "not_applicable")
          .length ||
      response.available_action_total !==
        gates.filter((item) => item.submissionAvailable).length;
    if (
      totalsInvalid ||
      !/^sha256:[0-9a-f]{64}$/.test(response.action_gate_digest) ||
      !Number.isInteger(response.action_context_version) ||
      response.action_context_version < 1 ||
      !response.mutation_endpoints_available ||
      !response.durable_action_audit_available
    ) {
      throw new Error("workflow_run_action_gates_boundary_invalid");
    }
    return {
      ...boundary,
      schemaVersion: response.schema_version,
      workspaceId: response.workspace_id,
      projectId: response.project_id,
      workflowPlanId: response.workflow_plan_id,
      workflowVersionId: response.workflow_version_id,
      workflowRunId: response.workflow_run_id,
      runStatus: response.run_status,
      actionGateDigest: response.action_gate_digest,
      actionContextVersion: response.action_context_version,
      gates,
      readyForReviewTotal: response.ready_for_review_total,
      blockedTotal: response.blocked_total,
      notApplicableTotal: response.not_applicable_total,
      availableActionTotal: response.available_action_total,
      mutationEndpointsAvailable: response.mutation_endpoints_available,
      durableActionAuditAvailable: response.durable_action_audit_available,
      actionMutationExecuted: response.action_mutation_executed,
    };
  }

  const expectedAvailabilityBlockers = [
    "mutation_endpoint_unavailable",
    "durable_action_audit_unavailable",
  ] as const;
  const gates: WorkflowRunActionGateEvidence[] = response.gates.map((gate) => {
    const preconditionBlockers = [...gate.precondition_blocker_codes];
    const availabilityBlockers = [...gate.availability_blocker_codes];
    const evidenceRefs = [...gate.evidence_refs];
    if (
      gate.action_available ||
      new Set(preconditionBlockers).size !== preconditionBlockers.length ||
      availabilityBlockers.join("|") !==
        expectedAvailabilityBlockers.join("|") ||
      evidenceRefs.length === 0 ||
      new Set(evidenceRefs).size !== evidenceRefs.length ||
      (gate.precondition_status === "ready_for_review"
        ? preconditionBlockers.length !== 0
        : preconditionBlockers.length === 0)
    ) {
      throw new Error("workflow_run_action_gate_boundary_invalid");
    }
    return {
      action: gate.action,
      preconditionStatus: gate.precondition_status,
      actionAvailable: gate.action_available,
      preconditionBlockerCodes: preconditionBlockers,
      availabilityBlockerCodes: availabilityBlockers,
      nextActionCode: gate.next_action_code,
      evidenceRefs,
    };
  });
  const boundaryInvalid =
    response.available_action_total !== 0 ||
    response.mutation_endpoints_available ||
    response.durable_action_audit_available ||
    response.action_mutation_executed;
  const totalsInvalid =
    gates.map((item) => item.action).join("|") !== expectedActions.join("|") ||
    response.ready_for_review_total !==
      gates.filter((item) => item.preconditionStatus === "ready_for_review")
        .length ||
    response.blocked_total !==
      gates.filter((item) => item.preconditionStatus === "blocked").length ||
    response.not_applicable_total !==
      gates.filter((item) => item.preconditionStatus === "not_applicable")
        .length;
  if (boundaryInvalid || totalsInvalid) {
    throw new Error("workflow_run_action_gates_boundary_invalid");
  }
  return {
    ...boundary,
    schemaVersion: response.schema_version,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    workflowPlanId: response.workflow_plan_id,
    workflowVersionId: response.workflow_version_id,
    workflowRunId: response.workflow_run_id,
    runStatus: response.run_status,
    gates,
    readyForReviewTotal: response.ready_for_review_total,
    blockedTotal: response.blocked_total,
    notApplicableTotal: response.not_applicable_total,
    availableActionTotal: response.available_action_total,
    mutationEndpointsAvailable: response.mutation_endpoints_available,
    durableActionAuditAvailable: response.durable_action_audit_available,
    actionMutationExecuted: response.action_mutation_executed,
  };
}

export function mapWorkflowActionApprovalReceipt(
  response: WorkflowActionApprovalReceiptDto,
  projectId: string,
  runId: string,
): WorkflowActionApprovalReceipt {
  if (
    response.schema_version !== "workflow_action_approval_receipt.v1" ||
    response.project_id !== projectId ||
    response.workflow_run_id !== runId ||
    response.provider_call ||
    response.credential_read_attempted ||
    response.execution_started ||
    response.production_write_allowed ||
    response.database_write === response.idempotent_replay ||
    !/^sha256:[0-9a-f]{64}$/.test(response.proposal_digest) ||
    !/^sha256:[0-9a-f]{64}$/.test(response.action_gate_digest) ||
    response.evidence_digests.length === 0 ||
    new Set(response.evidence_digests).size !==
      response.evidence_digests.length ||
    Number.isNaN(Date.parse(response.issued_at)) ||
    Number.isNaN(Date.parse(response.expires_at)) ||
    Date.parse(response.issued_at) >= Date.parse(response.expires_at)
  ) {
    throw new Error("workflow_action_approval_receipt_boundary_invalid");
  }
  return {
    id: response.id,
    action: response.action,
    approvalKind: response.approval_kind,
    proposalDigest: response.proposal_digest,
    actionGateDigest: response.action_gate_digest,
    evidenceDigests: [...response.evidence_digests],
    expectedActionContextVersion: response.expected_action_context_version,
    expectedRunStatus: response.expected_run_status,
    reasonCode: response.reason_code,
    reason: response.reason,
    issuedAt: response.issued_at,
    expiresAt: response.expires_at,
    databaseWrite: response.database_write,
    idempotentReplay: response.idempotent_replay,
  };
}

export function mapWorkflowActionReceipt(
  response: WorkflowActionReceiptDto,
  projectId: string,
  runId: string,
): WorkflowActionReceipt {
  if (
    response.schema_version !== "workflow_action_receipt.v1" ||
    response.project_id !== projectId ||
    response.workflow_run_id !== runId ||
    response.provider_call ||
    response.credential_read_attempted ||
    response.execution_started ||
    response.production_write_allowed ||
    response.database_write === response.idempotent_replay ||
    response.after_action_context_version !==
      response.before_action_context_version + 1 ||
    (response.outcome === "accepted_pending_executor_ack" &&
      response.action !== "cancel") ||
    !/^sha256:[0-9a-f]{64}$/.test(response.receipt_digest) ||
    Number.isNaN(Date.parse(response.created_at))
  ) {
    throw new Error("workflow_action_receipt_boundary_invalid");
  }
  return {
    id: response.id,
    requestId: response.request_id,
    action: response.action,
    outcome: response.outcome,
    beforeActionContextVersion: response.before_action_context_version,
    afterActionContextVersion: response.after_action_context_version,
    beforeRunStatus: response.before_run_status,
    afterRunStatus: response.after_run_status,
    stateChanged: response.state_changed,
    databaseWrite: response.database_write,
    idempotentReplay: response.idempotent_replay,
    nextActionCode: response.next_action_code,
    receiptDigest: response.receipt_digest,
    createdAt: response.created_at,
  };
}

export function mapWorkflowLineagePreview(
  response: WorkflowRunLineagePreviewDto,
): WorkflowRunLineagePreview {
  const boundary = mapReadBoundary(response);
  if (
    response.schema_version !== "workflow_lineage_preview.v2" ||
    response.provider_call ||
    response.database_write ||
    response.raw_record_write ||
    response.dataset_write ||
    response.provider_call_attempted ||
    response.credential_read_attempted ||
    response.actor_run ||
    response.browser_run ||
    response.llm_call ||
    response.production_write_allowed
  ) {
    throw new Error("workflow_lineage_preview_boundary_invalid");
  }
  const providerStepIds = response.provider_evidence.map(
    (item) => item.step_run_id,
  );
  if (
    providerStepIds.length === 0 ||
    new Set(providerStepIds).size !== providerStepIds.length ||
    providerStepIds.join("|") !==
      response.raw_record.source_step_run_ids.join("|") ||
    providerStepIds.join("|") !== response.dataset.source_step_run_ids.join("|")
  ) {
    throw new Error("workflow_lineage_preview_source_invalid");
  }
  return {
    ...boundary,
    schemaVersion: response.schema_version,
    workflowRunId: response.workflow_run_id,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    lineageDigest: response.lineage_digest,
    materializationEligible: response.materialization_eligible,
    providerEvidence: response.provider_evidence.map((item) => ({
      stepRunId: item.step_run_id,
      implementationId: item.implementation_id,
      platform: item.platform,
      resourceType: item.resource_type,
      operation: item.operation,
      fixtureCaseId: item.fixture_case_id,
      fixtureContentHash: item.fixture_content_hash,
      outputDigest: item.output_digest,
      recordsCount: item.records_count,
      evidenceRefs: [...item.evidence_refs],
    })),
    rawRecord: {
      sourceTaskRunId: response.raw_record.source_task_run_id,
      sourceStepRunIds: [...response.raw_record.source_step_run_ids],
      materializedRawRecordIds: [
        ...response.raw_record.materialized_raw_record_ids,
      ],
      expectedRecordCount: response.raw_record.expected_record_count,
      rawRecordWrite: response.raw_record.raw_record_write,
      materialized: response.raw_record.materialized,
      blockedReasons: [...response.raw_record.blocked_reasons],
    },
    dataset: {
      datasetId: response.dataset.dataset_id,
      datasetVersionId: response.dataset.dataset_version_id,
      sourceStepRunIds: [...response.dataset.source_step_run_ids],
      sourceRawRecordIds: [...response.dataset.source_raw_record_ids],
      expectedRecordCount: response.dataset.expected_record_count,
      datasetWrite: response.dataset.dataset_write,
      materialized: response.dataset.materialized,
      blockedReasons: [...response.dataset.blocked_reasons],
    },
    blockedReasons: [...response.blocked_reasons],
  };
}

function mapWorkflowShadowComparison(
  response: WorkflowShadowComparisonDto,
): WorkflowShadowComparison {
  const evidence = response.difference_evidence;
  return {
    ...mapReadBoundary(response),
    id: response.id,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    workflowRunId: response.workflow_run_id,
    stepRunId: response.step_run_id,
    requirementRef: response.requirement_ref,
    contractVersion: response.contract_version,
    comparisonDigest: response.comparison_digest,
    primaryImplementationId: response.primary_implementation_id,
    shadowImplementationId: response.shadow_implementation_id,
    fixtureProfileId: response.fixture_profile_id,
    fixtureProfileHash: response.fixture_profile_hash,
    primaryFixtureCaseId: response.primary_fixture_case_id,
    primaryFixtureContentHash: response.primary_fixture_content_hash,
    shadowFixtureCaseId: response.shadow_fixture_case_id,
    shadowFixtureContentHash: response.shadow_fixture_content_hash,
    sampleRate: response.sample_rate,
    maxItems: response.max_items,
    sampledItems: response.sampled_items,
    matchedItems: response.matched_items,
    mismatchedItems: response.mismatched_items,
    primaryOnlyItems: response.primary_only_items,
    shadowOnlyItems: response.shadow_only_items,
    equivalenceStatus: response.equivalence_status,
    differenceEvidence: {
      sampledRecordKeys: [...evidence.sampled_record_keys],
      matchedRecordKeys: [...evidence.matched_record_keys],
      mismatchedRecordKeys: [...evidence.mismatched_record_keys],
      primaryOnlyRecordKeys: [...evidence.primary_only_record_keys],
      shadowOnlyRecordKeys: [...evidence.shadow_only_record_keys],
      missingRequiredFields: [...evidence.missing_required_fields],
      primaryOnlyFields: [...evidence.primary_only_fields],
      shadowOnlyFields: [...evidence.shadow_only_fields],
    },
    routingRecommendation: response.routing_recommendation,
    evidenceRefs: [...response.evidence_refs],
    catalogMutationApplied: response.catalog_mutation_applied,
    routeRankingMutationApplied: response.route_ranking_mutation_applied,
    createdAt: response.created_at,
  };
}

export function mapWorkflowShadowComparisonList(
  response: WorkflowShadowComparisonListResponseDto,
): WorkflowShadowComparisonListResult {
  const boundary = mapReadBoundary(response);
  const items = response.items.map(mapWorkflowShadowComparison);
  const boundaryInvalid =
    boundary.executionMode !== "fixture" ||
    boundary.liveExecutionAuthorized ||
    boundary.providerCall ||
    boundary.providerCallAttempted ||
    boundary.credentialReadAttempted ||
    boundary.actorRun ||
    boundary.browserRun ||
    boundary.llmCall ||
    boundary.rawRecordWrite ||
    boundary.datasetWrite ||
    boundary.productionWriteAllowed ||
    boundary.databaseWrite;
  const evidenceInvalid = items.some((item) => {
    const partitionCount =
      item.matchedItems +
      item.mismatchedItems +
      item.primaryOnlyItems +
      item.shadowOnlyItems;
    const partitionKeys = [
      ...item.differenceEvidence.matchedRecordKeys,
      ...item.differenceEvidence.mismatchedRecordKeys,
      ...item.differenceEvidence.primaryOnlyRecordKeys,
      ...item.differenceEvidence.shadowOnlyRecordKeys,
    ];
    return (
      item.contractVersion !== "workflow_shadow_comparison.v1" ||
      item.catalogMutationApplied ||
      item.routeRankingMutationApplied ||
      item.executionMode !== "fixture" ||
      item.liveExecutionAuthorized ||
      item.providerCall ||
      item.providerCallAttempted ||
      item.credentialReadAttempted ||
      item.actorRun ||
      item.browserRun ||
      item.llmCall ||
      item.rawRecordWrite ||
      item.datasetWrite ||
      item.productionWriteAllowed ||
      item.databaseWrite ||
      item.sampledItems !== partitionCount ||
      item.sampledItems !== item.differenceEvidence.sampledRecordKeys.length ||
      item.matchedItems !== item.differenceEvidence.matchedRecordKeys.length ||
      item.mismatchedItems !==
        item.differenceEvidence.mismatchedRecordKeys.length ||
      item.primaryOnlyItems !==
        item.differenceEvidence.primaryOnlyRecordKeys.length ||
      item.shadowOnlyItems !==
        item.differenceEvidence.shadowOnlyRecordKeys.length ||
      partitionKeys.length !== new Set(partitionKeys).size ||
      [...partitionKeys].sort().join("|") !==
        [...item.differenceEvidence.sampledRecordKeys].sort().join("|") ||
      (item.equivalenceStatus === "equivalent") !==
        (item.sampledItems === item.matchedItems) ||
      item.routingRecommendation !==
        (item.equivalenceStatus === "equivalent"
          ? "eligible_for_governance_review"
          : "keep_primary_investigate_shadow")
    );
  });
  if (boundaryInvalid || response.total !== items.length || evidenceInvalid) {
    throw new Error("workflow_shadow_comparison_boundary_invalid");
  }
  return { ...boundary, items, total: response.total };
}

function buildListQuery(options: WorkflowRunListOptions): string {
  const params = new URLSearchParams();
  if (options.workflowPlanId) {
    params.set("workflow_plan_id", options.workflowPlanId);
  }
  if (options.workflowVersionId) {
    params.set("workflow_version_id", options.workflowVersionId);
  }
  params.set("limit", String(options.limit ?? 50));
  params.set("offset", String(options.offset ?? 0));
  return params.toString();
}

export async function listWorkflowRuns(
  projectId: string,
  options: WorkflowRunListOptions = {},
): Promise<WorkflowRunListResult> {
  if (mockApiEnabled) {
    return mapWorkflowRunList(buildMockWorkflowRunListDto(projectId, options));
  }

  const response = await apiFetch<WorkflowRunListResponseDto>(
    `/api/projects/${encodeURIComponent(projectId)}/workflow-runs?${buildListQuery(options)}`,
    { signal: options.signal },
  );
  return mapWorkflowRunList(response);
}

export async function getWorkflowRun(
  projectId: string,
  runId: string,
  options: { signal?: AbortSignal } = {},
): Promise<WorkflowRunDetail> {
  if (mockApiEnabled) {
    return mapWorkflowRunDetail(
      buildMockWorkflowRunDetailDto(projectId, runId),
    );
  }

  const response = await apiFetch<WorkflowRunDetailResponseDto>(
    `/api/projects/${encodeURIComponent(projectId)}/workflow-runs/${encodeURIComponent(runId)}`,
    { signal: options.signal },
  );
  return mapWorkflowRunDetail(response);
}

export async function getWorkflowRunAttemptFallbackEvidence(
  projectId: string,
  runId: string,
  options: { signal?: AbortSignal } = {},
): Promise<WorkflowAttemptFallbackEvidence> {
  if (mockApiEnabled) {
    return mapWorkflowAttemptFallbackEvidence(
      buildMockWorkflowAttemptFallbackEvidenceDto(projectId, runId),
    );
  }

  const response = await apiFetch<WorkflowAttemptFallbackEvidenceResponseDto>(
    `/api/projects/${encodeURIComponent(projectId)}/workflow-runs/${encodeURIComponent(runId)}/attempt-fallback-evidence`,
    { signal: options.signal },
  );
  return mapWorkflowAttemptFallbackEvidence(response);
}

export async function getWorkflowRunCheckpointBudgetEvidence(
  projectId: string,
  runId: string,
  options: { signal?: AbortSignal } = {},
): Promise<WorkflowCheckpointBudgetEvidence> {
  if (mockApiEnabled) {
    return mapWorkflowCheckpointBudgetEvidence(
      buildMockWorkflowCheckpointBudgetEvidenceDto(projectId, runId),
    );
  }

  const response = await apiFetch<WorkflowCheckpointBudgetEvidenceResponseDto>(
    `/api/projects/${encodeURIComponent(projectId)}/workflow-runs/${encodeURIComponent(runId)}/checkpoint-budget-evidence`,
    { signal: options.signal },
  );
  return mapWorkflowCheckpointBudgetEvidence(response);
}

export async function getWorkflowRunProviderHealthEvidence(
  projectId: string,
  runId: string,
  options: { signal?: AbortSignal } = {},
): Promise<WorkflowProviderHealthEvidence> {
  if (mockApiEnabled) {
    return mapWorkflowProviderHealthEvidence(
      buildMockWorkflowProviderHealthEvidenceDto(projectId, runId),
    );
  }

  const response = await apiFetch<WorkflowProviderHealthEvidenceResponseDto>(
    `/api/projects/${encodeURIComponent(projectId)}/workflow-runs/${encodeURIComponent(runId)}/provider-health-evidence`,
    { signal: options.signal },
  );
  return mapWorkflowProviderHealthEvidence(response);
}

export async function getWorkflowRunExecutorEvidence(
  projectId: string,
  runId: string,
  options: { signal?: AbortSignal } = {},
): Promise<WorkflowExecutorEvidence> {
  if (mockApiEnabled) {
    return mapWorkflowExecutorEvidence(
      buildMockWorkflowExecutorEvidenceDto(projectId, runId),
    );
  }

  const response = await apiFetch<WorkflowExecutorEvidenceResponseDto>(
    `/api/projects/${encodeURIComponent(projectId)}/workflow-runs/${encodeURIComponent(runId)}/executor-evidence`,
    { signal: options.signal },
  );
  return mapWorkflowExecutorEvidence(response);
}

export async function getWorkflowRunActionGates(
  projectId: string,
  runId: string,
  options: { signal?: AbortSignal } = {},
): Promise<WorkflowRunActionGates> {
  if (mockApiEnabled) {
    return mapWorkflowRunActionGates(
      buildMockWorkflowRunActionGatesDto(projectId, runId),
    );
  }

  const response = await apiFetch<WorkflowRunActionGatesResponseDto>(
    `/api/projects/${encodeURIComponent(projectId)}/workflow-runs/${encodeURIComponent(runId)}/action-gates`,
    { signal: options.signal },
  );
  return mapWorkflowRunActionGates(response);
}

export async function createWorkflowRunActionApproval(
  projectId: string,
  runId: string,
  payload: WorkflowActionApprovalRequestDto,
  idempotencyKey: string,
  options: { signal?: AbortSignal } = {},
): Promise<WorkflowActionApprovalReceipt> {
  if (mockApiEnabled) {
    throw new ApiRequestError(
      409,
      "workflow_action_mutation_mock_unavailable",
    );
  }
  const response = await apiFetch<WorkflowActionApprovalReceiptDto>(
    `/api/projects/${encodeURIComponent(projectId)}/workflow-runs/${encodeURIComponent(runId)}/action-approval-receipts`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(payload),
      signal: options.signal,
    },
  );
  return mapWorkflowActionApprovalReceipt(response, projectId, runId);
}

export async function createWorkflowRunAction(
  projectId: string,
  runId: string,
  payload: WorkflowRunActionRequestDto,
  idempotencyKey: string,
  options: { signal?: AbortSignal } = {},
): Promise<WorkflowActionReceipt> {
  if (mockApiEnabled) {
    throw new ApiRequestError(
      409,
      "workflow_action_mutation_mock_unavailable",
    );
  }
  const response = await apiFetch<WorkflowActionReceiptDto>(
    `/api/projects/${encodeURIComponent(projectId)}/workflow-runs/${encodeURIComponent(runId)}/actions`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(payload),
      signal: options.signal,
    },
  );
  return mapWorkflowActionReceipt(response, projectId, runId);
}

export async function getWorkflowRunLineagePreview(
  projectId: string,
  runId: string,
  options: { signal?: AbortSignal } = {},
): Promise<WorkflowRunLineagePreview> {
  if (mockApiEnabled) {
    return mapWorkflowLineagePreview(
      buildMockWorkflowRunLineagePreviewDto(projectId, runId),
    );
  }

  const response = await apiFetch<WorkflowRunLineagePreviewDto>(
    `/api/projects/${encodeURIComponent(projectId)}/workflow-runs/${encodeURIComponent(runId)}/lineage-preview`,
    { signal: options.signal },
  );
  return mapWorkflowLineagePreview(response);
}

export async function getWorkflowRunShadowComparisons(
  projectId: string,
  runId: string,
  options: { signal?: AbortSignal } = {},
): Promise<WorkflowShadowComparisonListResult> {
  if (mockApiEnabled) {
    return mapWorkflowShadowComparisonList(
      buildMockWorkflowShadowComparisonListDto(projectId, runId),
    );
  }

  const response = await apiFetch<WorkflowShadowComparisonListResponseDto>(
    `/api/projects/${encodeURIComponent(projectId)}/workflow-runs/${encodeURIComponent(runId)}/shadow-comparisons`,
    { signal: options.signal },
  );
  return mapWorkflowShadowComparisonList(response);
}

export async function getWorkflowFixtureRunGate(
  projectId: string,
  planId: string,
  versionId: string,
  options: { signal?: AbortSignal } = {},
): Promise<WorkflowFixtureRunGate> {
  const response = mockApiEnabled
    ? await buildMockWorkflowFixtureRunGateDto(projectId, planId, versionId)
    : await apiFetch<WorkflowFixtureRunGateDto>(
        `/api/projects/${encodeURIComponent(projectId)}/workflow-plans/${encodeURIComponent(planId)}/versions/${encodeURIComponent(versionId)}/fixture-run-gate`,
        { signal: options.signal },
      );
  const boundary = mapReadBoundary(response);
  if (
    response.workflow_plan_id !== planId ||
    response.workflow_version_id !== versionId ||
    response.is_current_version !==
      (response.current_version_id === response.workflow_version_id) ||
    response.runnable !== (response.blocker_codes.length === 0) ||
    (response.runnable &&
      (response.next_action_codes.length !== 1 ||
        response.next_action_codes[0] !== "create_fixture_run")) ||
    (!response.runnable &&
      response.next_action_codes.includes("create_fixture_run"))
  ) {
    throw new Error("workflow_fixture_run_gate_context_invalid");
  }
  return {
    ...boundary,
    gateContractVersion: response.gate_contract_version,
    projectStatus: response.project_status,
    workflowPlanId: response.workflow_plan_id,
    workflowVersionId: response.workflow_version_id,
    currentVersionId: response.current_version_id,
    planStatus: response.plan_status,
    planningStatus: response.planning_status,
    isCurrentVersion: response.is_current_version,
    runnable: response.runnable,
    blockerCodes: [...response.blocker_codes],
    nextActionCodes: [...response.next_action_codes],
    evidenceRefs: [...response.evidence_refs],
  };
}

export async function createWorkflowFixtureRun(
  projectId: string,
  planId: string,
  versionId: string,
  input: WorkflowFixtureRunCreateInput,
  options: { signal?: AbortSignal } = {},
): Promise<WorkflowFixtureRunCreateResult> {
  let response: WorkflowFixtureRunCreateResponseDto;
  if (mockApiEnabled) {
    const gate = await buildMockWorkflowFixtureRunGateDto(
      projectId,
      planId,
      versionId,
    );
    if (!gate.runnable) {
      throw new ApiRequestError(409, "workflow_version_not_fixture_runnable");
    }
    response = buildMockWorkflowFixtureRunCreateDto({
      projectId,
      planId,
      versionId,
      previewFingerprint: input.expectedPreviewFingerprint,
      fixtureProfileId: input.fixtureProfileId,
    });
  } else {
    const body: WorkflowFixtureRunCreateRequestDto = {
      expected_preview_fingerprint: input.expectedPreviewFingerprint,
      fixture_profile_id: input.fixtureProfileId,
    };
    response = await apiFetch<WorkflowFixtureRunCreateResponseDto>(
      `/api/projects/${encodeURIComponent(projectId)}/workflow-plans/${encodeURIComponent(planId)}/versions/${encodeURIComponent(versionId)}/fixture-runs`,
      {
        method: "POST",
        headers: { "Idempotency-Key": input.idempotencyKey },
        body: JSON.stringify(body),
        signal: options.signal,
      },
    );
  }
  const run = mapWorkflowRun(response.run);
  const steps = response.steps.map(mapWorkflowStepRun);
  if (
    run.projectId !== projectId ||
    run.workflowPlanId !== planId ||
    run.workflowVersionId !== versionId ||
    run.previewFingerprint !== input.expectedPreviewFingerprint ||
    run.fixtureProfileId !== input.fixtureProfileId ||
    steps.some((step) => step.workflowRunId !== run.id) ||
    response.database_write === response.idempotent_replay
  ) {
    throw new Error("workflow_fixture_run_create_context_invalid");
  }
  return {
    executionMode: response.execution_mode,
    liveExecutionAuthorized: response.live_execution_authorized,
    providerCall: response.provider_call,
    providerCallAttempted: response.provider_call_attempted,
    credentialReadAttempted: response.credential_read_attempted,
    actorRun: response.actor_run,
    browserRun: response.browser_run,
    llmCall: response.llm_call,
    rawRecordWrite: response.raw_record_write,
    datasetWrite: response.dataset_write,
    productionWriteAllowed: response.production_write_allowed,
    databaseWrite: response.database_write,
    idempotentReplay: response.idempotent_replay,
    run,
    steps,
  };
}

export const workflowRunTransport: WorkflowRunTransport = {
  listRuns: listWorkflowRuns,
  getRun: getWorkflowRun,
  getAttemptFallbackEvidence: getWorkflowRunAttemptFallbackEvidence,
  getCheckpointBudgetEvidence: getWorkflowRunCheckpointBudgetEvidence,
  getProviderHealthEvidence: getWorkflowRunProviderHealthEvidence,
  getExecutorEvidence: getWorkflowRunExecutorEvidence,
  getActionGates: getWorkflowRunActionGates,
  createActionApproval: createWorkflowRunActionApproval,
  createAction: createWorkflowRunAction,
  getLineagePreview: getWorkflowRunLineagePreview,
  getShadowComparisons: getWorkflowRunShadowComparisons,
};
