import { apiFetch } from "./client";

export type CollectionTask = {
  id: string;
  name: string;
  collector_type: string;
  status: string;
  source_name: string | null;
  schedule_cron: string | null;
  success_count: number;
  failure_count: number;
  last_run_at: string | null;
  latest_run_status: string | null;
  latest_run_records_count: number | null;
  latest_run_started_at: string | null;
  latest_run_finished_at: string | null;
  created_at: string;
};

export type TaskRun = {
  id: string;
  task_id: string;
  status: string;
  records_count: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  logs: Array<{ step: string; message: string; level: string; timestamp: string }>;
};

export async function fetchTasks(params?: {
  project_id?: string;
  status?: string;
}): Promise<CollectionTask[]> {
  const qs = new URLSearchParams();
  if (params?.project_id) qs.set("project_id", params.project_id);
  if (params?.status) qs.set("status", params.status);
  const q = qs.toString();
  return apiFetch<CollectionTask[]>(`/api/tasks${q ? `?${q}` : ""}`);
}

export async function fetchTaskRuns(taskId: string): Promise<TaskRun[]> {
  return apiFetch<TaskRun[]>(`/api/tasks/${taskId}/runs`);
}

export async function runTask(
  taskId: string,
  idempotencyKey?: string
): Promise<TaskRun> {
  return apiFetch<TaskRun>(`/api/tasks/${taskId}/run`, {
    method: "POST",
    headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {},
  });
}
