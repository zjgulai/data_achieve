import { getWorkflowPlanMock } from "@/lib/workflow-plan-persistence-mock";
import type {
  WorkflowAttemptFallbackEvidenceResponseDto,
  WorkflowCheckpointBudgetEvidenceResponseDto,
  WorkflowExecutorEvidenceResponseDto,
  WorkflowFixtureRunCreateResponseDto,
  WorkflowFixtureRunGateActionCode,
  WorkflowFixtureRunGateBlockerCode,
  WorkflowFixtureRunGateDto,
  WorkflowRunDetailResponseDto,
  WorkflowRunActionGatesResponseDto,
  WorkflowRunLineagePreviewDto,
  WorkflowRunDto,
  WorkflowRunListResponseDto,
  WorkflowProviderHealthEvidenceResponseDto,
  WorkflowShadowComparisonListResponseDto,
  WorkflowStepAttemptEvidenceDto,
  WorkflowStepRunDto,
} from "@/types/workflow-run";

const WORKSPACE_ID = "00000000-0000-4000-8000-000000000001";
const PLAN_ID = "30000000-0000-4000-8000-000000000301";
const VERSION_ID = "40000000-0000-4000-8000-000000000401";
const TEMPLATE_ID = "50000000-0000-4000-8000-000000000501";
const REVISION_ID = "60000000-0000-4000-8000-000000000601";
const CREATOR_ID = "70000000-0000-4000-8000-000000000701";
const RUN_ID = "20000000-0000-4000-8000-000000000201";
const SECOND_RUN_ID = "20000000-0000-4000-8000-000000000202";
const CREATED_RUN_ID = "20000000-0000-4000-8000-000000000203";

const hash = (character: string): string => `sha256:${character.repeat(64)}`;

export function buildMockWorkflowExecutorEvidenceDto(
  projectId: string,
  runId: string,
): WorkflowExecutorEvidenceResponseDto {
  return {
    execution_mode: "fixture",
    live_execution_authorized: false,
    provider_call: false,
    provider_call_attempted: false,
    credential_read_attempted: false,
    actor_run: false,
    browser_run: false,
    llm_call: false,
    raw_record_write: false,
    dataset_write: false,
    production_write_allowed: false,
    database_write: false,
    schema_version: "workflow_executor_evidence.v1",
    workspace_id: WORKSPACE_ID,
    project_id: projectId,
    workflow_run_id: runId,
    evidence_grade: "L2_fixture_local",
    environment: "local",
    evaluated_at: "2026-07-28T02:00:10.000Z",
    dispatches: [
      {
        id: "81000000-0000-4000-8000-000000000001",
        workflow_step_run_id: "80000000-0000-4000-8000-000000000802",
        attempt_generation: 1,
        source_action_request_id: "82000000-0000-4000-8000-000000000001",
        source_action_receipt_id: "83000000-0000-4000-8000-000000000001",
        state: "claimable",
        created_at: "2026-07-28T02:00:00.000Z",
        lease: {
          id: "84000000-0000-4000-8000-000000000001",
          state: "active",
          fencing_token: 2,
          version: 3,
          heartbeat_at: "2026-07-28T02:00:05.000Z",
          expires_at: "2026-07-28T02:00:30.000Z",
          fresh: true,
        },
        last_event: {
          id: "85000000-0000-4000-8000-000000000001",
          sequence: 3,
          event_type: "preflight_eligible",
          event_digest: hash("e"),
          occurred_at: "2026-07-28T02:00:06.000Z",
        },
        preflight_state: "eligible",
        preflight_blocker_codes: [],
        next_required_authority: "exact_live_provider_call_authorization",
        credential_permit_ids: [],
        provider_permit_ids: [],
        audits: [
          {
            id: "86000000-0000-4000-8000-000000000001",
            attempt_ordinal: 1,
            provider_id: "youtube.fixture",
            operation_id: "search",
            preflight_id: hash("f"),
            transport_state: "not_attempted",
            outcome_code: null,
            environment: "local",
            started_at: null,
            finished_at: null,
          },
        ],
        audit_total: 1,
        budget_reservation_state: "not_recorded",
        cancellation: {
          requested: true,
          acknowledged: false,
          request_id: "87000000-0000-4000-8000-000000000001",
          reason_code: "owner_cancelled",
          requested_at: "2026-07-28T02:00:07.000Z",
          acknowledgement_id: null,
          safe_point: null,
          outcome: null,
          acknowledged_at: null,
        },
      },
    ],
    dispatch_total: 1,
    business_cause_code: "executor_waiting_exact_live_authority",
    business_impact_code: "workflow_execution_waiting",
    next_action_code: "request_exact_live_provider_authorization",
    client_construction: false,
    network_call: false,
    live_provider_proof: false,
  };
}

function buildMockWorkflowRun(
  projectId: string,
  id: string,
  createdAt: string,
  lineage: boolean,
): WorkflowRunDto {
  const held = id === RUN_ID;
  return {
    id,
    workspace_id: WORKSPACE_ID,
    project_id: projectId,
    workflow_plan_id: PLAN_ID,
    workflow_version_id: VERSION_ID,
    workflow_template_id: lineage ? TEMPLATE_ID : null,
    workflow_template_revision_id: lineage ? REVISION_ID : null,
    created_by_user_id: CREATOR_ID,
    execution_contract_version: "workflow_execution_fixture.v1",
    execution_mode: "fixture",
    status: held ? "held" : "completed",
    planner_contract_version: "planner.v2",
    preview_fingerprint: hash("a"),
    catalog_snapshot_id: "catalog:fixture:20260716",
    policy_version: "policy.fixture.v1",
    mode_template_version: "mode.batch_research.v2",
    query_versions: { reddit: "reddit.query.v1" },
    fixture_profile_id: "reddit-search-fixture-v1",
    fixture_profile_hash: hash("b"),
    total_steps: 2,
    completed_steps: held ? 1 : 2,
    records_count: held ? 2 : 4,
    status_reason_code: held ? "fallback_blocked" : null,
    impact_code: held ? "step_not_completed_following_steps_not_started" : null,
    missing_fields: held ? ["author_profile.country"] : [],
    recovery_action_codes: held
      ? ["inspect_fallback_gate_evidence", "resolve_primary_failure"]
      : [],
    provider_call_attempted: false,
    credential_read_attempted: false,
    actor_run: false,
    browser_run: false,
    llm_call: false,
    production_write_allowed: false,
    started_at: "2026-07-16T08:00:00.000Z",
    finished_at: held ? null : "2026-07-16T08:00:03.000Z",
    created_at: createdAt,
  };
}

function buildMockWorkflowSteps(
  projectId: string,
  runId: string,
): WorkflowStepRunDto[] {
  const held = runId === RUN_ID;
  const base = {
    workspace_id: WORKSPACE_ID,
    project_id: projectId,
    workflow_run_id: runId,
    platform: "reddit",
    resource_type: "post",
    operation: "search",
    route_plan_snapshot: {
      requirement_ref: "requirement.reddit.posts",
      route_plan_ref: "route.reddit.search.recent",
      selected_implementation_id: "fixture.reddit.search.v1",
    },
    evidence_refs: ["fixture://reddit/search/recent/001"],
    fixture_content_hash: hash("c"),
    input_digest: hash("d"),
    output_digest: hash("e"),
    idempotency_scope: `workflow-run:${runId}`,
    idempotency_key_hash: hash("f"),
    status: "completed" as const,
    records_count: 2,
    provider_call_attempted: false as const,
    credential_read_attempted: false as const,
    actor_run: false as const,
    browser_run: false as const,
    llm_call: false as const,
    production_write_allowed: false as const,
    started_at: "2026-07-16T08:00:00.000Z",
    finished_at: "2026-07-16T08:00:01.000Z",
    created_at: "2026-07-16T08:00:00.000Z",
  };

  return [
    {
      ...base,
      id: "80000000-0000-4000-8000-000000000801",
      step_ref: "step.reddit.search",
      requirement_ref: "requirement.reddit.posts",
      sequence: 1,
      assertion_id: "assertion.reddit.search.primary",
      implementation_id: "fixture.reddit.search.v1",
      fixture_case_id: "fixture_case_reddit_search_primary",
    },
    {
      ...base,
      id: "80000000-0000-4000-8000-000000000802",
      step_ref: "step.reddit.normalize",
      requirement_ref: "requirement.reddit.posts",
      sequence: 2,
      assertion_id: "assertion.reddit.normalize.contract",
      implementation_id: "fixture.reddit.normalize.v1",
      fixture_content_hash: held ? null : base.fixture_content_hash,
      output_digest: held ? null : base.output_digest,
      fixture_case_id: held ? null : "fixture_case_reddit_normalize_contract",
      status: held ? "failed" : "completed",
      records_count: held ? 0 : 2,
      finished_at: "2026-07-16T08:00:01.000Z",
    },
  ];
}

export function buildMockWorkflowRunListDto(
  projectId: string,
  options: { limit?: number; offset?: number } = {},
): WorkflowRunListResponseDto {
  const limit = options.limit ?? 50;
  const offset = options.offset ?? 0;
  const all: WorkflowRunDto[] = [
    buildMockWorkflowRun(projectId, RUN_ID, "2026-07-16T08:00:00.000Z", true),
    buildMockWorkflowRun(
      projectId,
      SECOND_RUN_ID,
      "2026-07-15T08:00:00.000Z",
      false,
    ),
  ];

  return {
    execution_mode: "fixture",
    live_execution_authorized: false,
    provider_call: false,
    provider_call_attempted: false,
    credential_read_attempted: false,
    actor_run: false,
    browser_run: false,
    llm_call: false,
    raw_record_write: false,
    dataset_write: false,
    production_write_allowed: false,
    database_write: false,
    project_status: "active",
    items: all.slice(offset, offset + limit),
    total: all.length,
    limit,
    offset,
  };
}

export function buildMockWorkflowRunDetailDto(
  projectId: string,
  runId: string,
): WorkflowRunDetailResponseDto {
  const run = buildMockWorkflowRun(
    projectId,
    runId,
    "2026-07-16T08:00:00.000Z",
    runId === RUN_ID,
  );
  return {
    execution_mode: "fixture",
    live_execution_authorized: false,
    provider_call: false,
    provider_call_attempted: false,
    credential_read_attempted: false,
    actor_run: false,
    browser_run: false,
    llm_call: false,
    raw_record_write: false,
    dataset_write: false,
    production_write_allowed: false,
    database_write: false,
    project_status: "active",
    run,
    steps: buildMockWorkflowSteps(projectId, run.id),
  };
}

export function buildMockWorkflowAttemptFallbackEvidenceDto(
  projectId: string,
  runId: string,
): WorkflowAttemptFallbackEvidenceResponseDto {
  const steps = buildMockWorkflowSteps(projectId, runId);
  const held = runId === RUN_ID;
  const attempts: WorkflowStepAttemptEvidenceDto[] = [];
  steps.forEach((step, stepIndex) => {
    const base = {
      workspace_id: WORKSPACE_ID,
      project_id: projectId,
      workflow_run_id: runId,
      step_run_id: step.id,
      provider_call_attempted: false as const,
      credential_read_attempted: false as const,
      actor_run: false as const,
      browser_run: false as const,
      llm_call: false as const,
      production_write_allowed: false as const,
      started_at: `2026-07-16T08:00:0${stepIndex}.000Z`,
      finished_at: `2026-07-16T08:00:0${stepIndex}.500Z`,
      created_at: `2026-07-16T08:00:0${stepIndex}.500Z`,
    };
    if (held && step.status === "failed") {
      attempts.push(
        {
          ...base,
          id: "90000000-0000-4000-8000-000000000902",
          attempt_number: 1,
          attempt_key_hash: hash("1"),
          status: "retryable_error" as const,
          error_code: "step_rate_limited",
          backoff_ms: 500,
        },
        {
          ...base,
          id: "90000000-0000-4000-8000-000000000903",
          attempt_number: 2,
          attempt_key_hash: hash("2"),
          status: "terminal_error" as const,
          error_code: "step_contract_invalid",
          backoff_ms: 0,
          started_at: "2026-07-16T08:00:02.000Z",
          finished_at: "2026-07-16T08:00:02.400Z",
          created_at: "2026-07-16T08:00:02.400Z",
        },
      );
      return;
    }
    attempts.push({
      ...base,
      id:
        stepIndex === 0
          ? "90000000-0000-4000-8000-000000000901"
          : "90000000-0000-4000-8000-000000000904",
      attempt_number: 1,
      attempt_key_hash: hash(stepIndex === 0 ? "3" : "4"),
      status: "succeeded" as const,
      error_code: null,
      backoff_ms: 0,
    });
  });
  const failedStep = steps.find((step) => step.status === "failed");
  const fallbackDecisions =
    held && failedStep
      ? [
          {
            id: "91000000-0000-4000-8000-000000000911",
            workspace_id: WORKSPACE_ID,
            project_id: projectId,
            workflow_plan_id: PLAN_ID,
            workflow_version_id: VERSION_ID,
            workflow_run_id: runId,
            step_run_id: failedStep.id,
            created_by_user_id: CREATOR_ID,
            step_ref: failedStep.step_ref,
            requirement_ref: failedStep.requirement_ref,
            contract_version: "workflow_fallback_gate_replay.v1" as const,
            decision_digest: hash("5"),
            primary_failure_code: "step_rate_limited",
            primary_assertion_id: failedStep.assertion_id,
            primary_implementation_id: failedStep.implementation_id,
            fallback_assertion_id: "assertion.reddit.normalize.fallback",
            fallback_implementation_id: "fixture.reddit.normalize.fallback.v1",
            outcome: "blocked" as const,
            gates: [
              ["trigger", "passed", "fallback_trigger_retryable_failure"],
              ["policy", "passed", "fallback_policy_passed"],
              ["credential", "passed", "fallback_credential_passed"],
              ["budget", "passed", "fallback_budget_within_ceiling"],
              ["fields", "blocked", "fallback_required_fields_missing"],
              ["evidence", "passed", "fallback_evidence_present"],
              ["approval", "blocked", "fallback_approval_pending"],
            ].map(([gate, status, code]) => ({
              gate: gate as
                | "trigger"
                | "policy"
                | "credential"
                | "budget"
                | "fields"
                | "evidence"
                | "approval",
              status: status as "passed" | "blocked",
              code,
              evidence_refs: [],
            })),
            field_difference: {
              evidence_status: "verified" as const,
              required_fields: ["post.id", "author_profile.country"],
              missing_required_fields: ["author_profile.country"],
              primary_missing_optional_fields: [],
              fallback_missing_optional_fields: ["author_profile.language"],
            },
            cost_snapshot: {
              evidence_status: "verified" as const,
              currency: "USD" as const,
              unit_cost_usd: "0.01",
              ceiling_usd: "0.02",
              within_ceiling: true,
            },
            evidence_refs: ["fixture://reddit/normalize/fallback/001"],
            approval_required: true,
            approval_status: "pending" as const,
            switch_executed: false as const,
            provider_call_attempted: false as const,
            credential_read_attempted: false as const,
            actor_run: false as const,
            browser_run: false as const,
            llm_call: false as const,
            production_write_allowed: false as const,
            created_at: "2026-07-16T08:00:02.500Z",
          },
        ]
      : [];

  return {
    execution_mode: "fixture",
    live_execution_authorized: false,
    provider_call: false,
    provider_call_attempted: false,
    credential_read_attempted: false,
    actor_run: false,
    browser_run: false,
    llm_call: false,
    raw_record_write: false,
    dataset_write: false,
    production_write_allowed: false,
    database_write: false,
    schema_version: "workflow_attempt_fallback_evidence.v1",
    workspace_id: WORKSPACE_ID,
    project_id: projectId,
    workflow_run_id: runId,
    attempts,
    fallback_decisions: fallbackDecisions,
    attempt_total: attempts.length,
    fallback_decision_total: fallbackDecisions.length,
  };
}

export async function buildMockWorkflowFixtureRunGateDto(
  projectId: string,
  planId: string,
  versionId: string,
): Promise<WorkflowFixtureRunGateDto> {
  const detail = await getWorkflowPlanMock(projectId, planId);
  const isCurrentVersion = detail.plan.currentVersionId === versionId;
  const contractRunnable =
    detail.currentVersion.preview.planningStatus === "resolved" &&
    detail.currentVersion.preview.routePlans.length > 0 &&
    detail.currentVersion.preview.routePlans.every(
      (route) =>
        route.status === "resolved" && route.primaryImplementation !== null,
    );
  const blockerCodes: WorkflowFixtureRunGateBlockerCode[] = [];
  const nextActionCodes: WorkflowFixtureRunGateActionCode[] = [];
  if (detail.projectStatus !== "active") {
    blockerCodes.push("project_not_active");
    nextActionCodes.push("activate_project");
  }
  if (detail.plan.status !== "active") {
    blockerCodes.push("workflow_plan_not_active");
    nextActionCodes.push("approve_and_activate_plan");
  }
  if (!isCurrentVersion) {
    blockerCodes.push("workflow_version_not_current");
    nextActionCodes.push("select_current_version");
  }
  if (!contractRunnable) {
    blockerCodes.push("workflow_version_contract_not_runnable");
    nextActionCodes.push("resolve_version_contract");
  }
  if (blockerCodes.length === 0) {
    nextActionCodes.push("create_fixture_run");
  }
  return {
    execution_mode: "fixture",
    live_execution_authorized: false,
    provider_call: false,
    provider_call_attempted: false,
    credential_read_attempted: false,
    actor_run: false,
    browser_run: false,
    llm_call: false,
    raw_record_write: false,
    dataset_write: false,
    production_write_allowed: false,
    database_write: false,
    gate_contract_version: "workflow_fixture_run_gate.v1",
    project_status: detail.projectStatus,
    workflow_plan_id: detail.plan.id,
    workflow_version_id: versionId,
    current_version_id: detail.plan.currentVersionId,
    plan_status: detail.plan.status,
    planning_status: detail.currentVersion.preview.planningStatus,
    is_current_version: isCurrentVersion,
    runnable: blockerCodes.length === 0,
    blocker_codes: blockerCodes,
    next_action_codes: nextActionCodes,
    evidence_refs: [
      `project:${projectId}`,
      `workflow_plan:${planId}`,
      `workflow_version:${versionId}`,
    ],
  };
}

export function buildMockWorkflowFixtureRunCreateDto(input: {
  projectId: string;
  planId: string;
  versionId: string;
  previewFingerprint: string;
  fixtureProfileId: string;
  idempotentReplay?: boolean;
}): WorkflowFixtureRunCreateResponseDto {
  const detail = buildMockWorkflowRunDetailDto(input.projectId, CREATED_RUN_ID);
  const replay = input.idempotentReplay ?? false;
  return {
    execution_mode: "fixture",
    live_execution_authorized: false,
    provider_call: false,
    provider_call_attempted: false,
    credential_read_attempted: false,
    actor_run: false,
    browser_run: false,
    llm_call: false,
    raw_record_write: false,
    dataset_write: false,
    production_write_allowed: false,
    database_write: !replay,
    idempotent_replay: replay,
    run: {
      ...detail.run,
      workflow_plan_id: input.planId,
      workflow_version_id: input.versionId,
      preview_fingerprint: input.previewFingerprint,
      fixture_profile_id: input.fixtureProfileId,
    },
    steps: detail.steps,
  };
}

export function buildMockWorkflowRunLineagePreviewDto(
  projectId: string,
  runId: string,
): WorkflowRunLineagePreviewDto {
  const detail = buildMockWorkflowRunDetailDto(projectId, runId);
  const providerEvidence = detail.steps.flatMap((step) => {
    if (
      step.fixture_case_id === null ||
      step.fixture_content_hash === null ||
      step.output_digest === null
    ) {
      return [];
    }
    return [
      {
        step_run_id: step.id,
        implementation_id: step.implementation_id,
        platform: step.platform,
        resource_type: step.resource_type,
        operation: step.operation,
        fixture_case_id: step.fixture_case_id,
        fixture_content_hash: step.fixture_content_hash,
        output_digest: step.output_digest,
        records_count: step.records_count,
        evidence_refs: [...step.evidence_refs],
      },
    ];
  });
  const sourceStepRunIds = providerEvidence.map((item) => item.step_run_id);
  const expectedRecordCount = providerEvidence.reduce(
    (total, item) => total + item.records_count,
    0,
  );
  return {
    execution_mode: "fixture",
    live_execution_authorized: false,
    provider_call: false,
    provider_call_attempted: false,
    credential_read_attempted: false,
    actor_run: false,
    browser_run: false,
    llm_call: false,
    raw_record_write: false,
    dataset_write: false,
    production_write_allowed: false,
    database_write: false,
    schema_version: "workflow_lineage_preview.v2",
    workflow_run_id: detail.run.id,
    workspace_id: detail.run.workspace_id,
    project_id: detail.run.project_id,
    lineage_digest: `sha256:${"9".repeat(64)}`,
    materialization_eligible: false,
    provider_evidence: providerEvidence,
    raw_record: {
      source_task_run_id: null,
      source_step_run_ids: sourceStepRunIds,
      materialized_raw_record_ids: [],
      expected_record_count: expectedRecordCount,
      raw_record_write: false,
      materialized: false,
      blocked_reasons: ["workflow_payload_unbound"],
    },
    dataset: {
      dataset_id: null,
      dataset_version_id: null,
      source_step_run_ids: sourceStepRunIds,
      source_raw_record_ids: [],
      expected_record_count: expectedRecordCount,
      dataset_write: false,
      materialized: false,
      blocked_reasons: ["workflow_payload_unbound"],
    },
    blocked_reasons: ["workflow_payload_unbound"],
  };
}

export function buildMockWorkflowShadowComparisonListDto(
  projectId: string,
  runId: string,
): WorkflowShadowComparisonListResponseDto {
  const boundary = {
    execution_mode: "fixture" as const,
    live_execution_authorized: false as const,
    provider_call: false as const,
    provider_call_attempted: false as const,
    credential_read_attempted: false as const,
    actor_run: false as const,
    browser_run: false as const,
    llm_call: false as const,
    raw_record_write: false as const,
    dataset_write: false as const,
    production_write_allowed: false as const,
    database_write: false as const,
  };
  if (runId !== RUN_ID) {
    return { ...boundary, items: [], total: 0 };
  }

  return {
    ...boundary,
    items: [
      {
        ...boundary,
        id: "90000000-0000-4000-8000-000000000901",
        workspace_id: WORKSPACE_ID,
        project_id: projectId,
        workflow_run_id: runId,
        step_run_id: "80000000-0000-4000-8000-000000000801",
        requirement_ref: "requirement.reddit.posts",
        contract_version: "workflow_shadow_comparison.v1",
        comparison_digest: hash("7"),
        primary_implementation_id: "fixture.reddit.search.v1",
        shadow_implementation_id: "fixture.reddit.search.shadow.v2",
        fixture_profile_id: "reddit-search-fixture-v1",
        fixture_profile_hash: hash("b"),
        primary_fixture_case_id: "fixture_case_reddit_search_primary",
        primary_fixture_content_hash: hash("c"),
        shadow_fixture_case_id: "fixture_case_reddit_search_shadow",
        shadow_fixture_content_hash: hash("8"),
        sample_rate: 1,
        max_items: 10,
        sampled_items: 2,
        matched_items: 1,
        mismatched_items: 1,
        primary_only_items: 0,
        shadow_only_items: 0,
        equivalence_status: "different",
        difference_evidence: {
          sampled_record_keys: ["post:primary:001", "post:primary:002"],
          matched_record_keys: ["post:primary:001"],
          mismatched_record_keys: ["post:primary:002"],
          primary_only_record_keys: [],
          shadow_only_record_keys: [],
          missing_required_fields: ["author_profile.country"],
          primary_only_fields: ["primary_rank"],
          shadow_only_fields: ["shadow_confidence"],
        },
        routing_recommendation: "keep_primary_investigate_shadow",
        evidence_refs: [
          "fixture://reddit/search/recent/001",
          "fixture://reddit/search/shadow/001",
        ],
        catalog_mutation_applied: false,
        route_ranking_mutation_applied: false,
        created_at: "2026-07-16T08:00:02.000Z",
      },
    ],
    total: 1,
  };
}

export function buildMockWorkflowCheckpointBudgetEvidenceDto(
  projectId: string,
  runId: string,
): WorkflowCheckpointBudgetEvidenceResponseDto {
  const boundary = {
    execution_mode: "fixture" as const,
    live_execution_authorized: false as const,
    provider_call: false as const,
    provider_call_attempted: false as const,
    credential_read_attempted: false as const,
    actor_run: false as const,
    browser_run: false as const,
    llm_call: false as const,
    raw_record_write: false as const,
    dataset_write: false as const,
    production_write_allowed: false as const,
    database_write: false as const,
  };
  const empty = {
    ...boundary,
    schema_version: "workflow_checkpoint_budget_evidence.v1" as const,
    workspace_id: WORKSPACE_ID,
    project_id: projectId,
    workflow_plan_id: PLAN_ID,
    workflow_version_id: VERSION_ID,
    workflow_run_id: runId,
    execution_session_id: runId,
    checkpoint_steps: [],
    checkpoint_step_total: 0,
    checkpoint_page_total: 0,
    budget_status: "not_configured" as const,
    budget_account: null,
    budget_entries: [],
    budget_entry_total: 0,
    usage: null,
    held_reason_code: null,
    resume_action_available: false as const,
    budget_override_available: false as const,
  };
  if (runId !== RUN_ID) {
    return empty;
  }

  const accountId = "92000000-0000-4000-8000-000000000921";
  const policyDigest = hash("a");
  const sideEffectKeyHash = hash("3");
  const firstLedgerDigest = hash("4");
  const checkpoint = {
    id: "93000000-0000-4000-8000-000000000931",
    execution_session_id: runId,
    workspace_id: WORKSPACE_ID,
    project_id: projectId,
    workflow_plan_id: PLAN_ID,
    workflow_version_id: VERSION_ID,
    step_ref: "step.reddit.search",
    requirement_ref: "requirement.reddit.posts",
    implementation_id: "fixture.reddit.search.v1",
    contract_version: "workflow_step_checkpoint.v1" as const,
    fixture_profile_id: "reddit-search-fixture-v1",
    fixture_profile_hash: hash("b"),
    step_input_digest: hash("d"),
    page_number: 1,
    cursor_before: null,
    cursor_before_digest: hash("0"),
    cursor_after: "fixture-cursor-page-2",
    cursor_after_digest: hash("1"),
    side_effect_key_hash: sideEffectKeyHash,
    page_output_digest: hash("e"),
    checkpoint_digest: hash("2"),
    records_count: 2,
    terminal: false,
    evidence_refs: ["fixture://reddit/search/page-1"],
    provider_call_attempted: false as const,
    credential_read_attempted: false as const,
    actor_run: false as const,
    browser_run: false as const,
    llm_call: false as const,
    raw_record_write: false as const,
    dataset_write: false as const,
    production_write_allowed: false as const,
    confirmed_at: "2026-07-16T08:00:01.000Z",
    created_at: "2026-07-16T08:00:01.000Z",
  };
  const accountBoundary = {
    provider_call_attempted: false as const,
    credential_read_attempted: false as const,
    actor_run: false as const,
    browser_run: false as const,
    llm_call: false as const,
    raw_record_write: false as const,
    dataset_write: false as const,
    production_write_allowed: false as const,
  };
  const entryBase = {
    ...accountBoundary,
    budget_account_id: accountId,
    execution_session_id: runId,
    workspace_id: WORKSPACE_ID,
    project_id: projectId,
    contract_version: "workflow_budget_ledger.v1" as const,
    policy_digest: policyDigest,
    step_ref: "step.reddit.search",
    request_count: 1,
    item_count: 2,
    quota_units: { "fixture.read": 2 },
    estimated_cost_usd: "0.10000000",
    reserved_time_ms: 100,
    cumulative_request_count: 1,
    cumulative_item_count: 2,
    cumulative_quota_units: { "fixture.read": 2 },
    cumulative_cost_usd: "0.10000000",
    cumulative_time_ms: 100,
  };

  return {
    ...empty,
    checkpoint_steps: [
      {
        step_run_id: "80000000-0000-4000-8000-000000000801",
        execution_session_id: runId,
        step_ref: checkpoint.step_ref,
        requirement_ref: checkpoint.requirement_ref,
        implementation_id: checkpoint.implementation_id,
        checkpoints: [checkpoint],
        confirmed_pages: 1,
        confirmed_records: 2,
        terminal: false,
        next_page_number: 2,
        next_cursor: checkpoint.cursor_after,
        resume_action_available: false,
      },
    ],
    checkpoint_step_total: 1,
    checkpoint_page_total: 1,
    budget_status: "held",
    budget_account: {
      ...accountBoundary,
      id: accountId,
      execution_session_id: runId,
      workspace_id: WORKSPACE_ID,
      project_id: projectId,
      workflow_plan_id: PLAN_ID,
      workflow_version_id: VERSION_ID,
      contract_version: "workflow_budget_account.v1",
      policy_digest: policyDigest,
      max_requests: 1,
      max_items: 10,
      quota_ceilings: { "fixture.read": 5 },
      max_cost_usd: "1.00000000",
      max_time_ms: 1000,
      evidence_refs: ["fixture://budget/policy-v1"],
    },
    budget_entries: [
      {
        ...entryBase,
        id: "94000000-0000-4000-8000-000000000941",
        entry_number: 1,
        page_number: 1,
        side_effect_key_hash: sideEffectKeyHash,
        status: "reserved",
        blocker_code: null,
        previous_ledger_digest: null,
        ledger_digest: firstLedgerDigest,
      },
      {
        ...entryBase,
        id: "94000000-0000-4000-8000-000000000942",
        entry_number: 2,
        page_number: 2,
        side_effect_key_hash: hash("5"),
        status: "blocked",
        blocker_code: "workflow_request_budget_exceeded",
        previous_ledger_digest: firstLedgerDigest,
        ledger_digest: hash("6"),
      },
    ],
    budget_entry_total: 2,
    usage: {
      request_count: 1,
      request_limit: 1,
      item_count: 2,
      item_limit: 10,
      quota_units: { "fixture.read": 2 },
      quota_ceilings: { "fixture.read": 5 },
      cost_usd: "0.10000000",
      cost_limit_usd: "1.00000000",
      time_ms: 100,
      time_limit_ms: 1000,
    },
    held_reason_code: "workflow_request_budget_exceeded",
  };
}

export function buildMockWorkflowProviderHealthEvidenceDto(
  projectId: string,
  runId: string,
): WorkflowProviderHealthEvidenceResponseDto {
  const boundary = {
    execution_mode: "fixture" as const,
    live_execution_authorized: false as const,
    provider_call: false as const,
    provider_call_attempted: false as const,
    credential_read_attempted: false as const,
    actor_run: false as const,
    browser_run: false as const,
    llm_call: false as const,
    raw_record_write: false as const,
    dataset_write: false as const,
    production_write_allowed: false as const,
    database_write: false as const,
  };
  const emptySteps = buildMockWorkflowSteps(projectId, runId).map((step) => ({
    step_run_id: step.id,
    step_ref: step.step_ref,
    requirement_ref: step.requirement_ref,
    platform_id: step.platform,
    resource_type: step.resource_type,
    operation: step.operation,
    selected_implementation_id: step.implementation_id,
    candidates: [
      {
        implementation_id: step.implementation_id,
        selected_for_run: true,
        health_status: "not_observed" as const,
        routing_state: "not_observed" as const,
        snapshot: null,
      },
    ],
    route_feedback: null,
    route_feedback_match: "not_available" as const,
    route_decision_applied_to_run: false as const,
  }));
  const empty = {
    ...boundary,
    schema_version: "workflow_provider_health_evidence.v1" as const,
    workspace_id: WORKSPACE_ID,
    project_id: projectId,
    workflow_run_id: runId,
    read_at: "2026-07-24T08:00:00.000Z",
    steps: emptySteps,
    step_total: emptySteps.length,
    observed_candidate_total: 0,
    routing_active_candidate_total: 0,
    attention_candidate_total: 0,
    route_feedback_total: 0,
    health_probe_attempted: false as const,
    catalog_mutation_applied: false as const,
    automatic_route_switch_executed: false as const,
    route_switch_action_available: false as const,
  };
  if (runId !== RUN_ID) {
    return empty;
  }

  const selectedId = "fixture.reddit.search.v1";
  const fallbackId = "fixture.reddit.search.fallback.v1";
  const providerBoundary = {
    execution_mode: "fixture" as const,
    live_execution_authorized: false as const,
    provider_call: false as const,
    provider_call_attempted: false as const,
    credential_read_attempted: false as const,
    actor_run: false as const,
    browser_run: false as const,
    llm_call: false as const,
    raw_record_write: false as const,
    dataset_write: false as const,
    production_write_allowed: false as const,
  };
  const snapshotBase = {
    ...providerBoundary,
    workspace_id: WORKSPACE_ID,
    project_id: projectId,
    contract_version: "provider_health_snapshot.v1" as const,
    snapshot_version: 1,
    platform_id: "reddit",
    resource_type: "post",
    operation: "search",
    window_started_at: "2026-07-24T05:00:00.000Z",
    window_ended_at: "2026-07-24T06:00:00.000Z",
    evaluated_at: "2026-07-24T06:30:00.000Z",
    sample_count: 3,
    policy_snapshot: {
      min_sample_size: 3,
      routing_ttl_hours: 24,
      evidence_retention_days: 90,
    },
    observation_manifest: [
      { observation_digest: hash("1") },
      { observation_digest: hash("2") },
      { observation_digest: hash("3") },
    ],
    previous_snapshot_digest: null,
    health_probe_attempted: false as const,
  };
  const primarySnapshot = {
    ...snapshotBase,
    id: "95000000-0000-4000-8000-000000000951",
    scope_key: hash("4"),
    aggregation_key: hash("5"),
    implementation_id: selectedId,
    status: "unhealthy" as const,
    success_count: 1,
    timeout_count: 1,
    rate_limited_count: 1,
    transient_error_count: 0,
    terminal_error_count: 0,
    success_rate_bps: 3333,
    p95_latency_ms: 6100,
    reason_codes: ["provider_health_success_rate_unhealthy"],
    evidence_refs: ["fixture://health/reddit/primary/window"],
    snapshot_digest: hash("6"),
    routing_valid_until: "2026-07-25T06:30:00.000Z",
    evidence_retain_until: "2026-10-22T06:30:00.000Z",
  };
  const fallbackSnapshot = {
    ...snapshotBase,
    id: "95000000-0000-4000-8000-000000000952",
    scope_key: hash("7"),
    aggregation_key: hash("8"),
    implementation_id: fallbackId,
    status: "healthy" as const,
    success_count: 3,
    timeout_count: 0,
    rate_limited_count: 0,
    transient_error_count: 0,
    terminal_error_count: 0,
    success_rate_bps: 10000,
    p95_latency_ms: 480,
    reason_codes: ["provider_health_healthy"],
    evidence_refs: ["fixture://health/reddit/fallback/window"],
    snapshot_digest: hash("9"),
    routing_valid_until: "2026-07-24T07:00:00.000Z",
    evidence_retain_until: "2026-10-21T06:30:00.000Z",
  };
  const feedback = {
    ...providerBoundary,
    id: "96000000-0000-4000-8000-000000000961",
    workspace_id: WORKSPACE_ID,
    project_id: projectId,
    contract_version: "provider_health_route_feedback.v1" as const,
    route_key: "route://reddit/post/search",
    feedback_key: hash("a"),
    feedback_version: 1,
    platform_id: "reddit",
    resource_type: "post",
    operation: "search",
    original_candidate_order: [selectedId, fallbackId],
    adjusted_candidate_order: [fallbackId, selectedId],
    candidate_score_manifest: [
      { implementation_id: selectedId, adjusted_score_bps: 4000 },
      { implementation_id: fallbackId, adjusted_score_bps: 8500 },
    ],
    source_snapshot_manifest: [
      { implementation_id: selectedId, snapshot_digest: hash("6") },
      { implementation_id: fallbackId, snapshot_digest: hash("9") },
    ],
    ranking_changed: true,
    reason_codes: ["provider_health_ranking_reordered"],
    evidence_refs: ["fixture://health/reddit/route-feedback"],
    previous_feedback_digest: null,
    feedback_digest: hash("b"),
    evaluated_at: "2026-07-24T06:45:00.000Z",
    evidence_retain_until: "2027-01-20T06:45:00.000Z",
    health_probe_attempted: false as const,
    catalog_mutation_applied: false as const,
    automatic_route_switch_executed: false as const,
  };

  return {
    ...empty,
    steps: [
      {
        ...emptySteps[0]!,
        candidates: [
          {
            implementation_id: selectedId,
            selected_for_run: true,
            health_status: "unhealthy",
            routing_state: "routing_active",
            snapshot: primarySnapshot,
          },
          {
            implementation_id: fallbackId,
            selected_for_run: false,
            health_status: "healthy",
            routing_state: "routing_expired",
            snapshot: fallbackSnapshot,
          },
        ],
        route_feedback: feedback,
        route_feedback_match: "ordered_candidate_match",
      },
      emptySteps[1]!,
    ],
    observed_candidate_total: 2,
    routing_active_candidate_total: 1,
    attention_candidate_total: 1,
    route_feedback_total: 1,
  };
}

export function buildMockWorkflowRunActionGatesDto(
  projectId: string,
  runId: string,
): WorkflowRunActionGatesResponseDto {
  const boundary = {
    execution_mode: "fixture" as const,
    live_execution_authorized: false as const,
    provider_call: false as const,
    provider_call_attempted: false as const,
    credential_read_attempted: false as const,
    actor_run: false as const,
    browser_run: false as const,
    llm_call: false as const,
    raw_record_write: false as const,
    dataset_write: false as const,
    production_write_allowed: false as const,
    database_write: false as const,
  };
  const availability = [
    "mutation_endpoint_unavailable",
    "durable_action_audit_unavailable",
  ] as const;
  const evidence = (name: string) => [
    `workflow-run:${runId}:state`,
    `workflow-run:${runId}:${name}`,
  ];
  const held = runId === RUN_ID;
  const gates: WorkflowRunActionGatesResponseDto["gates"] = held
    ? [
        {
          action: "retry",
          precondition_status: "blocked",
          action_available: false,
          precondition_blocker_codes: ["terminal_failure_not_retryable"],
          availability_blocker_codes: [...availability],
          next_action_code: "inspect_retry_evidence",
          evidence_refs: evidence("attempt-fallback-evidence"),
        },
        {
          action: "resume",
          precondition_status: "blocked",
          action_available: false,
          precondition_blocker_codes: ["budget_limit_exceeded"],
          availability_blocker_codes: [...availability],
          next_action_code: "restore_checkpoint_budget",
          evidence_refs: evidence("checkpoint-budget-evidence"),
        },
        {
          action: "cancel",
          precondition_status: "ready_for_review",
          action_available: false,
          precondition_blocker_codes: [],
          availability_blocker_codes: [...availability],
          next_action_code: "review_cancel_request",
          evidence_refs: [`workflow-run:${runId}:state`],
        },
        {
          action: "budget_override",
          precondition_status: "blocked",
          action_available: false,
          precondition_blocker_codes: ["owner_approval_receipt_unavailable"],
          availability_blocker_codes: [...availability],
          next_action_code: "request_budget_override_approval",
          evidence_refs: evidence("checkpoint-budget-evidence"),
        },
        {
          action: "route_switch",
          precondition_status: "blocked",
          action_available: false,
          precondition_blocker_codes: ["fallback_gate_blocked"],
          availability_blocker_codes: [...availability],
          next_action_code: "resolve_fallback_gates",
          evidence_refs: [
            ...evidence("attempt-fallback-evidence"),
            `workflow-run:${runId}:provider-health-evidence`,
          ],
        },
      ]
    : [
        {
          action: "retry",
          precondition_status: "not_applicable",
          action_available: false,
          precondition_blocker_codes: ["run_state_not_retryable"],
          availability_blocker_codes: [...availability],
          next_action_code: "no_action_required",
          evidence_refs: evidence("attempt-fallback-evidence"),
        },
        {
          action: "resume",
          precondition_status: "not_applicable",
          action_available: false,
          precondition_blocker_codes: ["run_state_not_resumable"],
          availability_blocker_codes: [...availability],
          next_action_code: "no_action_required",
          evidence_refs: evidence("checkpoint-budget-evidence"),
        },
        {
          action: "cancel",
          precondition_status: "not_applicable",
          action_available: false,
          precondition_blocker_codes: ["run_state_not_cancellable"],
          availability_blocker_codes: [...availability],
          next_action_code: "no_action_required",
          evidence_refs: [`workflow-run:${runId}:state`],
        },
        {
          action: "budget_override",
          precondition_status: "not_applicable",
          action_available: false,
          precondition_blocker_codes: ["budget_not_held"],
          availability_blocker_codes: [...availability],
          next_action_code: "no_action_required",
          evidence_refs: evidence("checkpoint-budget-evidence"),
        },
        {
          action: "route_switch",
          precondition_status: "not_applicable",
          action_available: false,
          precondition_blocker_codes: ["run_state_not_switchable"],
          availability_blocker_codes: [...availability],
          next_action_code: "no_action_required",
          evidence_refs: [
            ...evidence("attempt-fallback-evidence"),
            `workflow-run:${runId}:provider-health-evidence`,
          ],
        },
      ];

  return {
    ...boundary,
    schema_version: "workflow_run_action_gates.v1",
    workspace_id: WORKSPACE_ID,
    project_id: projectId,
    workflow_plan_id: PLAN_ID,
    workflow_version_id: VERSION_ID,
    workflow_run_id: runId,
    run_status: held ? "held" : "completed",
    gates,
    ready_for_review_total: held ? 1 : 0,
    blocked_total: held ? 4 : 0,
    not_applicable_total: held ? 0 : 5,
    available_action_total: 0,
    mutation_endpoints_available: false,
    durable_action_audit_available: false,
    action_mutation_executed: false,
  };
}
