import { describe, expect, it } from "vitest";

import { mapRawRecord } from "@/lib/api/raw-records";

describe("raw-record transport", () => {
  it("preserves nullable collector provenance and workflow lineage", () => {
    const record = mapRawRecord({
      id: "record-a",
      workspace_id: "workspace-a",
      project_id: "project-a",
      source_id: null,
      task_run_id: null,
      workflow_run_id: "workflow-run-a",
      workflow_step_run_id: "workflow-step-a",
      workflow_lineage_contract_version: "workflow_raw_record.v1",
      record_type: "social_raw.v1",
      source_url: null,
      content: { provider_record_id: "provider-a" },
      content_hash: "a".repeat(64),
      screenshot_url: null,
      collected_at: "2026-07-18T00:00:00.000Z",
      created_at: "2026-07-18T00:00:00.000Z",
    });

    expect(record).toMatchObject({
      sourceId: null,
      taskRunId: null,
      workflowRunId: "workflow-run-a",
      workflowStepRunId: "workflow-step-a",
      workflowLineageContractVersion: "workflow_raw_record.v1",
    });
  });
});
