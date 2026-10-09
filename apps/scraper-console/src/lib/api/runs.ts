import { apiFetch } from "./client";

export type TaskRun = {
  id: string;
  task_id: string;
  status: string;
  records_count: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

/**
 * Shape of `GET /api/raw-records`.
 *
 * The payload field is `content`; an earlier version of this type called it
 * `data`, which made the collect page render every record as empty.
 */
export type RawRecord = {
  id: string;
  workspace_id: string;
  project_id: string;
  source_id: string | null;
  task_run_id: string | null;
  workflow_run_id: string | null;
  workflow_step_run_id: string | null;
  record_type: string;
  source_url: string | null;
  content: Record<string, unknown>;
  content_hash: string;
  screenshot_url: string | null;
  collected_at: string;
  created_at: string;
};

export async function fetchAllRuns(params?: {
  limit?: number;
  status?: string;
}): Promise<TaskRun[]> {
  const qs = new URLSearchParams();
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.status) qs.set("status", params.status);
  const query = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<TaskRun[]>(`/api/tasks/runs${query}`);
}

export async function fetchRawRecords(params?: {
  task_run_id?: string;
  source_id?: string;
  record_type?: string;
  limit?: number;
  offset?: number;
}): Promise<RawRecord[]> {
  const qs = new URLSearchParams();
  if (params?.task_run_id) qs.set("task_run_id", params.task_run_id);
  if (params?.source_id) qs.set("source_id", params.source_id);
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.offset) qs.set("offset", String(params.offset));
  const query = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<RawRecord[]>(`/api/raw-records${query}`);
}

export async function fetchRunRecords(runId: string): Promise<RawRecord[]> {
  return apiFetch<RawRecord[]>(`/api/raw-records?task_run_id=${runId}&limit=100`);
}
