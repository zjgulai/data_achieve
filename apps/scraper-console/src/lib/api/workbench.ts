/**
 * 工作台页面的后端调用。
 *
 * 只有已挂载的端点才发请求：
 *   GET /api/projects
 *   GET /api/tasks
 *   GET /api/tasks/runs
 *   GET /api/reports
 *
 * 未挂载的端点集中在本文件末尾。每个函数先抛出明确的错误。
 * 不得猜测路径，也不得返回假数据。
 */

import { apiFetch } from "./client";
import { fetchProjects } from "./projects";
import type { Project } from "./projects";
import { fetchTasks } from "./tasks";
import type { CollectionTask } from "./tasks";
import { fetchAllRuns, MAX_RUNS_LIMIT } from "./runs";
import type { TaskRun } from "./runs";

/** 报告列表项。`GET /api/reports` 的响应满足本类型。 */
export type WorkbenchReport = {
  id: string;
  project_id: string | null;
  report_type: string;
  title: string;
  status: string;
  period_start: string;
  period_end: string;
  created_at: string;
};

/** 工作台首屏快照。四个请求并行发出。 */
export type WorkbenchSnapshot = {
  projects: Project[];
  tasks: CollectionTask[];
  runs: TaskRun[];
  reports: WorkbenchReport[];
};

/**
 * 读取报告列表。
 *
 * 后端按 `created_at` 倒序返回。项目 ID 为空时读取当前工作区的全部报告。
 */
export async function fetchWorkbenchReports(
  projectId?: string
): Promise<WorkbenchReport[]> {
  const params = new URLSearchParams();
  if (projectId) params.set("project_id", projectId);
  const query = params.toString();
  return apiFetch<WorkbenchReport[]>(`/api/reports${query ? `?${query}` : ""}`);
}

/**
 * 读取工作台首屏快照。
 *
 * 四个请求并行发出。任一请求失败时整体失败，页面显示错误态。
 * 运行列表取最近 200 条。上限由后端 `GET /api/tasks/runs` 决定。
 */
export async function fetchWorkbenchSnapshot(
  projectId?: string
): Promise<WorkbenchSnapshot> {
  const [projects, tasks, runs, reports] = await Promise.all([
    fetchProjects(),
    fetchTasks(projectId ? { project_id: projectId } : undefined),
    fetchAllRuns({ limit: MAX_RUNS_LIMIT, project_id: projectId }),
    fetchWorkbenchReports(projectId),
  ]);
  return { projects, tasks, runs, reports };
}

/** 计划草稿。字段名与契约冻结 v1 的七槽位一致。 */
export type WorkbenchPlanDraft = {
  project_id: string | null;
  decision_question: string;
  brand: string;
  category: string;
  markets: string[];
};

/**
 * 生成计划预览。
 *
 * TODO(B5-后端): `POST /api/workbench/plans/preview` 尚未挂载。
 * 契约见《模块设计》§3.11。请求体还要由七槽位适配为 `PlanningInput`。
 * 适配器同样未实现。后端补齐前本函数必须抛出。
 */
export async function previewWorkbenchPlan(
  draft: WorkbenchPlanDraft
): Promise<never> {
  void draft;
  throw new Error("workbench_plans_preview_not_implemented");
}

/**
 * 创建任务单。
 *
 * TODO(B5-后端): `POST /api/workbench/tasks` 尚未挂载。
 * 契约见《模块设计》§3.11。缺槽位时后端应返回 422。
 */
export async function createWorkbenchTask(
  draft: WorkbenchPlanDraft
): Promise<never> {
  void draft;
  throw new Error("workbench_tasks_not_implemented");
}

/**
 * 读取任务单。
 *
 * TODO(B5-后端): `GET /api/workbench/tasks/{task_id}` 尚未挂载。
 * 响应应含 `task`、`plan`、`gates[]`、`runs[]`。
 */
export async function fetchWorkbenchTask(taskId: string): Promise<never> {
  void taskId;
  throw new Error("workbench_tasks_get_not_implemented");
}

/**
 * 批准计划。
 *
 * TODO(B5-后端): `POST /api/workbench/plans/{plan_id}/approve` 尚未挂载。
 * 没有 `authorization_id` 不得执行。契约见《模块设计》§3.11。
 */
export async function approveWorkbenchPlan(planId: string): Promise<never> {
  void planId;
  throw new Error("workbench_plans_approve_not_implemented");
}

/**
 * 读取任务门禁。
 *
 * TODO(B5-后端): `GET /api/workbench/tasks/{task_id}/gates` 尚未挂载。
 * 契约见《模块设计》§3.11。
 */
export async function fetchWorkbenchGates(taskId: string): Promise<never> {
  void taskId;
  throw new Error("workbench_gates_not_implemented");
}
