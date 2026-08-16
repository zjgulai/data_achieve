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

export type RawRecord = {
  id: string;
  source_id: string;
  task_run_id: string;
  record_type: string;
  data: Record<string, unknown>;
  metadata: Record<string, unknown>;
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

export async function fetchRunRecords(runId: string): Promise<RawRecord[]> {
  return apiFetch<RawRecord[]>(`/api/raw-records?task_run_id=${runId}&limit=100`);
}
