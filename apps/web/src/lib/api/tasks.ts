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
  success_count: number;
  failure_count: number;
  last_run_at: string | null;
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
    successCount: response.success_count,
    failureCount: response.failure_count,
    lastRunAt: response.last_run_at,
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
  };
}
