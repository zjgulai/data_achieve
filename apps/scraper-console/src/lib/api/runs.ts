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
  // 后端没有全局 runs 端点，需从 tasks 聚合
  const tasks = await apiFetch<Array<{ id: string }>>("/api/tasks");
  const allRuns: TaskRun[] = [];
  
  for (const task of tasks.slice(0, 20)) {
    try {
      const runs = await apiFetch<TaskRun[]>(`/api/tasks/${task.id}/runs`);
      allRuns.push(...runs);
    } catch {
      // 跳过失败的任务
    }
  }
  
  allRuns.sort((a, b) => 
    new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );
  
  return params?.limit ? allRuns.slice(0, params.limit) : allRuns;
}

export async function fetchRunRecords(runId: string): Promise<RawRecord[]> {
  return apiFetch<RawRecord[]>(`/api/raw-records?task_run_id=${runId}&limit=100`);
}
