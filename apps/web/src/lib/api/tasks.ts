import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import { getMockTaskRun, getMockTasks } from "@/lib/api/mock";
import type { CollectionTask, CollectorType, TaskRun } from "@/types/source-task";

type CollectionTaskResponse = {
  id: string;
  project_id: string;
  source_id: string;
  collector_type: CollectorType;
  name: string;
  schedule_cron: string | null;
  status: CollectionTask["status"];
  project_name?: string | null;
  project_domain?: string | null;
  source_name?: string | null;
  source_url?: string | null;
  freshness_target_hours?: number;
  freshness_status?: CollectionTask["freshnessStatus"];
  stale_hours?: number | null;
  success_count: number;
  failure_count: number;
  last_run_at: string | null;
  latest_run_status?: string | null;
  latest_run_error_message?: string | null;
  latest_run_records_count?: number | null;
  latest_run_entities_count?: number | null;
  latest_run_started_at?: string | null;
  latest_run_finished_at?: string | null;
  latest_run_created_at?: string | null;
};

type TaskRunResponse = {
  id: string;
  task_id: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  records_count: number;
  entities_count: number;
  error_message: string | null;
  logs: TaskRun["logs"];
  created_at: string;
};

export async function listTasks(): Promise<CollectionTask[]> {
  if (mockApiEnabled) {
    return getMockTasks();
  }
  const response = await apiFetch<CollectionTaskResponse[]>("/api/tasks");
  return response.map(mapTask);
}

export async function runTask(taskId: string): Promise<TaskRun> {
  if (mockApiEnabled) {
    return getMockTaskRun(taskId);
  }
  const response = await apiFetch<TaskRunResponse>(`/api/tasks/${taskId}/run`, {
    method: "POST",
  });
  return mapTaskRun(response);
}

export async function listTaskRuns(taskId: string): Promise<TaskRun[]> {
  if (mockApiEnabled) {
    return [
      getMockTaskRun(taskId),
      {
        ...getMockTaskRun(taskId),
        id: `run_previous_${taskId}`,
        startedAt: "2026-06-11T16:10:00.000Z",
        finishedAt: "2026-06-11T16:10:06.000Z",
      },
    ];
  }
  const response = await apiFetch<TaskRunResponse[]>(`/api/tasks/${taskId}/runs`);
  return response.map(mapTaskRun);
}

export async function pauseTask(taskId: string): Promise<CollectionTask> {
  if (mockApiEnabled) {
    const task = getMockTasks().find((item) => item.id === taskId) ?? getMockTasks()[0];
    return { ...task, status: "paused" };
  }
  const response = await apiFetch<CollectionTaskResponse>(`/api/tasks/${taskId}/pause`, {
    method: "POST",
  });
  return mapTask(response);
}

export async function resumeTask(taskId: string): Promise<CollectionTask> {
  if (mockApiEnabled) {
    const task = getMockTasks().find((item) => item.id === taskId) ?? getMockTasks()[0];
    return { ...task, status: "enabled" };
  }
  const response = await apiFetch<CollectionTaskResponse>(`/api/tasks/${taskId}/resume`, {
    method: "POST",
  });
  return mapTask(response);
}

function mapTask(response: CollectionTaskResponse): CollectionTask {
  return {
    id: response.id,
    projectId: response.project_id,
    sourceId: response.source_id,
    collectorType: response.collector_type,
    name: response.name,
    scheduleCron: response.schedule_cron,
    status: response.status,
    projectName: response.project_name ?? null,
    projectDomain: response.project_domain ?? null,
    sourceName: response.source_name ?? null,
    sourceUrl: response.source_url ?? null,
    freshnessTargetHours: response.freshness_target_hours ?? 24,
    freshnessStatus: response.freshness_status ?? "unknown",
    staleHours: response.stale_hours ?? null,
    successCount: response.success_count,
    failureCount: response.failure_count,
    lastRunAt: response.last_run_at,
    latestRunStatus: response.latest_run_status ?? null,
    latestRunErrorMessage: response.latest_run_error_message ?? null,
    latestRunRecordsCount: response.latest_run_records_count ?? null,
    latestRunEntitiesCount: response.latest_run_entities_count ?? null,
    latestRunStartedAt: response.latest_run_started_at ?? null,
    latestRunFinishedAt: response.latest_run_finished_at ?? null,
    latestRunCreatedAt: response.latest_run_created_at ?? null,
  };
}

function mapTaskRun(response: TaskRunResponse): TaskRun {
  return {
    id: response.id,
    taskId: response.task_id,
    status: response.status,
    startedAt: response.started_at,
    finishedAt: response.finished_at,
    recordsCount: response.records_count,
    entitiesCount: response.entities_count,
    errorMessage: response.error_message,
    logs: response.logs,
    createdAt: response.created_at,
  };
}
