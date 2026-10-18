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
  /**
   * 运行日志。后端 `TaskRunResponse.logs` 返回。
   * 每条含 step / message / level / timestamp。失败日志另有 failure_reason 等键。
   */
  logs: Array<{ step: string; message: string; level: string; timestamp: string }>;
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
  /** 后端允许对象或数组。见 `schemas/raw_record.py`。 */
  content: Record<string, unknown> | unknown[];
  content_hash: string;
  screenshot_url: string | null;
  collected_at: string;
  created_at: string;
};

/** 把 content 统一成键值对。数组用下标作键。 */
export function rawRecordEntries(
  content: RawRecord["content"],
): Array<[string, unknown]> {
  if (Array.isArray(content)) {
    return content.map((value, index): [string, unknown] => [String(index), value]);
  }
  if (content !== null && typeof content === "object") {
    return Object.entries(content);
  }
  return [];
}

/** 后端 GET /api/tasks/runs 列表端点的 limit 上限。 */
export const MAX_RUNS_LIMIT = 200;

export async function fetchAllRuns(params?: {
  limit?: number;
  status?: string;
  /** 按项目过滤。后端 GET /api/tasks/runs 支持。 */
  project_id?: string;
}): Promise<TaskRun[]> {
  const qs = new URLSearchParams();
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.status) qs.set("status", params.status);
  // 空串会让后端返回 422。只用真值。
  if (params?.project_id) qs.set("project_id", params.project_id);
  const query = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<TaskRun[]>(`/api/tasks/runs${query}`);
}

/**
 * 按 ID 读取一次运行。
 *
 * 使用专用端点 `GET /api/tasks/runs/{runId}`，不再拉取运行列表再匹配，
 * 因此不受列表 limit 上限影响。
 * 运行不存在或不属于当前 workspace 时后端返回 404，`apiFetch` 抛出 `ApiError`。
 */
export async function fetchRunById(runId: string): Promise<TaskRun> {
  return apiFetch<TaskRun>(`/api/tasks/runs/${encodeURIComponent(runId)}`);
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
