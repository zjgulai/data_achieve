import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...actual, mockApiEnabled: false };
});

import {
  createWorkflowRunAction,
  createWorkflowRunActionApproval,
  mapWorkflowActionApprovalReceipt,
  mapWorkflowActionReceipt,
  mapWorkflowRunActionGates,
} from "@/lib/api/workflow-runs";

const DIGEST = `sha256:${"a".repeat(64)}`;
const PROJECT_ID = "10000000-0000-4000-8000-000000000002";
const RUN_ID = "10000000-0000-4000-8000-000000000005";

afterEach(() => {
  vi.unstubAllGlobals();
});

function v2ActionGates() {
  const actions = [
    "retry",
    "resume",
    "cancel",
    "budget_override",
    "route_switch",
  ] as const;
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
    schema_version: "workflow_run_action_gates.v2",
    workspace_id: "10000000-0000-4000-8000-000000000001",
    project_id: PROJECT_ID,
    workflow_plan_id: "10000000-0000-4000-8000-000000000003",
    workflow_version_id: "10000000-0000-4000-8000-000000000004",
    workflow_run_id: RUN_ID,
    run_status: "held",
    action_gate_digest: DIGEST,
    action_context_version: 2,
    gates: actions.map((action) => ({
      action,
      precondition_status:
        action === "cancel" ? "ready_for_review" : "blocked",
      precondition_blocker_codes:
        action === "cancel"
          ? []
          : action === "retry"
            ? ["retry_policy_snapshot_unavailable"]
            : action === "resume"
              ? ["budget_limit_exceeded"]
              : action === "budget_override"
                ? ["owner_approval_receipt_unavailable"]
                : ["fallback_gate_blocked"],
      submission_available: action === "cancel",
      availability_blocker_codes: [],
      approval_kind:
        action === "budget_override"
          ? "owner_policy_override"
          : action === "route_switch"
            ? "owner_route_override"
            : "owner_confirmation",
      approval_receipt_required: true,
      evidence_refs: [`workflow-run:10000000-0000-4000-8000-000000000005:${action}`],
      expires_at: "2026-07-27T13:15:00Z",
    })),
    ready_for_review_total: 1,
    blocked_total: 4,
    not_applicable_total: 0,
    available_action_total: 1,
    mutation_endpoints_available: true,
    durable_action_audit_available: true,
    action_mutation_executed: false,
  };
}

describe("workflow action mutation surface", () => {
  it("maps the strict v2 discriminator without weakening the v1 contract", () => {
    const result = mapWorkflowRunActionGates(v2ActionGates() as never);

    expect(result.schemaVersion).toBe("workflow_run_action_gates.v2");
    if (result.schemaVersion !== "workflow_run_action_gates.v2") {
      throw new Error("expected_workflow_run_action_gates_v2");
    }
    expect(result.actionGateDigest).toBe(DIGEST);
    expect(result.actionContextVersion).toBe(2);
    expect(result.availableActionTotal).toBe(1);
    expect(result.gates.find((gate) => gate.action === "cancel")).toMatchObject({
      submissionAvailable: true,
      approvalKind: "owner_confirmation",
      approvalReceiptRequired: true,
    });
  });

  it("maps server receipts and rejects contradictory mutation evidence", () => {
    const approval = mapWorkflowActionApprovalReceipt(
      {
        schema_version: "workflow_action_approval_receipt.v1",
        id: "20000000-0000-4000-8000-000000000001",
        workspace_id: "10000000-0000-4000-8000-000000000001",
        project_id: PROJECT_ID,
        workflow_run_id: RUN_ID,
        approver_user_id: "30000000-0000-4000-8000-000000000001",
        action: "cancel",
        approval_kind: "owner_confirmation",
        proposal_digest: DIGEST,
        expected_action_context_version: 1,
        expected_run_status: "held",
        action_gate_digest: DIGEST,
        evidence_digests: [DIGEST],
        reason_code: "cancel_operator_request",
        reason: "Cancel after Owner review.",
        issued_at: "2026-07-27T13:00:00Z",
        expires_at: "2026-07-27T13:15:00Z",
        database_write: true,
        idempotent_replay: false,
        provider_call: false,
        credential_read_attempted: false,
        execution_started: false,
        production_write_allowed: false,
      },
      PROJECT_ID,
      RUN_ID,
    );
    expect(approval).toMatchObject({
      action: "cancel",
      databaseWrite: true,
      idempotentReplay: false,
    });

    const receiptDto = {
      schema_version: "workflow_action_receipt.v1" as const,
      id: "40000000-0000-4000-8000-000000000001",
      request_id: "50000000-0000-4000-8000-000000000001",
      workspace_id: "10000000-0000-4000-8000-000000000001",
      project_id: PROJECT_ID,
      workflow_run_id: RUN_ID,
      action: "cancel" as const,
      outcome: "accepted" as const,
      before_action_context_version: 1,
      after_action_context_version: 2,
      before_run_status: "held" as const,
      after_run_status: "cancelled" as const,
      state_changed: true,
      database_write: true,
      idempotent_replay: false,
      provider_call: false as const,
      credential_read_attempted: false as const,
      execution_started: false as const,
      production_write_allowed: false as const,
      next_action_code: "workflow_run_cancelled" as const,
      receipt_digest: DIGEST,
      created_at: "2026-07-27T13:01:00Z",
    };
    expect(mapWorkflowActionReceipt(receiptDto, PROJECT_ID, RUN_ID)).toMatchObject(
      {
        afterActionContextVersion: 2,
        afterRunStatus: "cancelled",
        databaseWrite: true,
      },
    );
    expect(() =>
      mapWorkflowActionReceipt(
        {
          ...receiptDto,
          after_action_context_version: 1,
        },
        PROJECT_ID,
        RUN_ID,
      ),
    ).toThrow("workflow_action_receipt_boundary_invalid");
    expect(() =>
      mapWorkflowActionReceipt(
        {
          ...receiptDto,
          database_write: false,
        },
        PROJECT_ID,
        RUN_ID,
      ),
    ).toThrow("workflow_action_receipt_boundary_invalid");
  });

  it("posts approval and action to the fixed Run paths with caller idempotency", async () => {
    const approvalId = "20000000-0000-4000-8000-000000000001";
    const approvalPayload = {
      schema_version: "workflow_action_approval_request.v1",
      action: "cancel",
      approval_kind: "owner_confirmation",
      expected_action_context_version: 1,
      expected_run_status: "held",
      action_gate_digest: DIGEST,
      reason_code: "cancel_operator_request",
      reason: "Cancel after Owner review.",
      parameters: { action: "cancel", cancel_scope: "held_run" },
    } as const;
    const actionPayload = {
      schema_version: "workflow_run_action_request.v1",
      action: "cancel",
      expected_action_context_version: 1,
      expected_run_status: "held",
      action_gate_digest: DIGEST,
      approval_receipt_id: approvalId,
      reason_code: "cancel_operator_request",
      reason: "Cancel after Owner review.",
      parameters: { action: "cancel", cancel_scope: "held_run" },
    } as const;
    const responses = [
      {
        schema_version: "workflow_action_approval_receipt.v1",
        id: approvalId,
        workspace_id: "10000000-0000-4000-8000-000000000001",
        project_id: PROJECT_ID,
        workflow_run_id: RUN_ID,
        approver_user_id: "30000000-0000-4000-8000-000000000001",
        action: "cancel",
        approval_kind: "owner_confirmation",
        proposal_digest: DIGEST,
        expected_action_context_version: 1,
        expected_run_status: "held",
        action_gate_digest: DIGEST,
        evidence_digests: [DIGEST],
        reason_code: "cancel_operator_request",
        reason: "Cancel after Owner review.",
        issued_at: "2026-07-27T13:00:00Z",
        expires_at: "2026-07-27T13:15:00Z",
        database_write: true,
        idempotent_replay: false,
        provider_call: false,
        credential_read_attempted: false,
        execution_started: false,
        production_write_allowed: false,
      },
      {
        schema_version: "workflow_action_receipt.v1",
        id: "40000000-0000-4000-8000-000000000001",
        request_id: "50000000-0000-4000-8000-000000000001",
        workspace_id: "10000000-0000-4000-8000-000000000001",
        project_id: PROJECT_ID,
        workflow_run_id: RUN_ID,
        action: "cancel",
        outcome: "accepted",
        before_action_context_version: 1,
        after_action_context_version: 2,
        before_run_status: "held",
        after_run_status: "cancelled",
        state_changed: true,
        database_write: true,
        idempotent_replay: false,
        provider_call: false,
        credential_read_attempted: false,
        execution_started: false,
        production_write_allowed: false,
        next_action_code: "workflow_run_cancelled",
        receipt_digest: DIGEST,
        created_at: "2026-07-27T13:01:00Z",
      },
    ];
    const fetchMock = vi.fn<
      (request: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    >(async () => {
      const body = responses.shift();
      return new Response(JSON.stringify(body), {
        status: 201,
        headers: { "content-type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const approval = await createWorkflowRunActionApproval(
      PROJECT_ID,
      RUN_ID,
      approvalPayload,
      "workflow-approval-key-0001",
    );
    const receipt = await createWorkflowRunAction(
      PROJECT_ID,
      RUN_ID,
      actionPayload,
      "workflow-action-key-0001",
    );

    const [approvalUrl, approvalInit] = fetchMock.mock.calls[0] ?? [];
    expect(String(approvalUrl)).toBe(
      `http://localhost:8000/api/projects/${PROJECT_ID}/workflow-runs/${RUN_ID}/action-approval-receipts`,
    );
    expect(approvalInit).toMatchObject({
      method: "POST",
      credentials: "include",
    });
    expect(
      new Headers(approvalInit?.headers).get("Idempotency-Key"),
    ).toBe("workflow-approval-key-0001");
    expect(JSON.parse(String(approvalInit?.body))).toEqual(approvalPayload);

    const [actionUrl, actionInit] = fetchMock.mock.calls[1] ?? [];
    expect(String(actionUrl)).toBe(
      `http://localhost:8000/api/projects/${PROJECT_ID}/workflow-runs/${RUN_ID}/actions`,
    );
    expect(actionInit).toMatchObject({
      method: "POST",
      credentials: "include",
    });
    expect(new Headers(actionInit?.headers).get("Idempotency-Key")).toBe(
      "workflow-action-key-0001",
    );
    expect(JSON.parse(String(actionInit?.body))).toEqual(actionPayload);
    expect(approval).toMatchObject({
      id: approvalId,
      databaseWrite: true,
      idempotentReplay: false,
    });
    expect(receipt).toMatchObject({
      afterRunStatus: "cancelled",
      afterActionContextVersion: 2,
      databaseWrite: true,
      idempotentReplay: false,
    });
  });
});
