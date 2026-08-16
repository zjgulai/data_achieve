import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import { getMockRawRecords } from "@/lib/api/mock";
import type { RawRecord } from "@/types/raw-record";

type RawRecordResponse = {
  id: string;
  workspace_id: string;
  project_id: string;
  source_id: string | null;
  task_run_id: string | null;
  workflow_run_id: string | null;
  workflow_step_run_id: string | null;
  workflow_lineage_contract_version: string | null;
  record_type: string;
  source_url: string | null;
  content: Record<string, unknown> | unknown[];
  content_hash: string;
  screenshot_url: string | null;
  collected_at: string;
  created_at: string;
};

export async function listRawRecords(): Promise<RawRecord[]> {
  if (mockApiEnabled) {
    return getMockRawRecords();
  }
  const response = await apiFetch<RawRecordResponse[]>("/api/raw-records");
  return response.map(mapRawRecord);
}

export async function getRawRecord(rawRecordId: string): Promise<RawRecord> {
  if (mockApiEnabled) {
    const rawRecord = getMockRawRecords().find((item) => item.id === rawRecordId);
    return rawRecord ?? getMockRawRecords()[0];
  }
  const response = await apiFetch<RawRecordResponse>(`/api/raw-records/${rawRecordId}`);
  return mapRawRecord(response);
}

export function mapRawRecord(response: RawRecordResponse): RawRecord {
  return {
    id: response.id,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    sourceId: response.source_id,
    taskRunId: response.task_run_id,
    workflowRunId: response.workflow_run_id,
    workflowStepRunId: response.workflow_step_run_id,
    workflowLineageContractVersion: response.workflow_lineage_contract_version,
    recordType: response.record_type,
    sourceUrl: response.source_url,
    content: response.content,
    contentHash: response.content_hash,
    screenshotUrl: response.screenshot_url,
    collectedAt: response.collected_at,
    createdAt: response.created_at,
  };
}
