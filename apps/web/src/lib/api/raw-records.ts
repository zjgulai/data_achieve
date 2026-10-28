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

/** 列表筛选。全部可选，不传时行为与之前一致（全域混合列表）。 */
export type RawRecordFilter = {
  domain?: string;
  projectId?: string;
  taskRunId?: string;
  limit?: number;
};

export async function listRawRecords(
  filter?: RawRecordFilter,
): Promise<RawRecord[]> {
  if (mockApiEnabled) {
    const items = getMockRawRecords();
    // mock 数据没有域字段，按 projectId 过滤是能做到的最接近的近似。
    return filter?.projectId
      ? items.filter((item) => item.projectId === filter.projectId)
      : items;
  }
  const params = new URLSearchParams();
  if (filter?.domain) params.set("domain", filter.domain);
  if (filter?.projectId) params.set("project_id", filter.projectId);
  if (filter?.taskRunId) params.set("task_run_id", filter.taskRunId);
  if (filter?.limit) params.set("limit", String(filter.limit));
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  const response = await apiFetch<RawRecordResponse[]>(`/api/raw-records${suffix}`);
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
