"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { fetchProject, DOMAIN_LABELS, DOMAIN_COLORS } from "@/lib/api/projects";
import { fetchTasks } from "@/lib/api/tasks";
import { fetchAllRuns } from "@/lib/api/runs";
import { fetchDatasets } from "@/lib/api/datasets";
import { isSuccessfulRunStatus } from "@/lib/run-status";
import { Loader2, PlayCircle, Database, Calendar } from "lucide-react";
import Link from "next/link";

const TASK_STATUS_LABELS: Record<string, string> = {
  enabled: "已启用",
  running: "运行中",
  paused: "已暂停",
  disabled: "已禁用",
};

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("zh-CN", { hour12: false });
}

type Props = {
  params: Promise<{ id: string }>;
};

export default function ProjectDetailPage({ params }: Props) {
  const { id } = use(params);
  
  const { data: project, isLoading, error } = useQuery({
    queryKey: ["project", id],
    queryFn: () => fetchProject(id),
  });

  const { data: tasks, isLoading: tasksLoading } = useQuery({
    queryKey: ["project-tasks", id],
    queryFn: () => fetchTasks({ project_id: id }),
  });

  // 最近运行。后端按 project_id 过滤。单次请求。
  const {
    data: recentRuns,
    isLoading: runsLoading,
    error: runsError,
  } = useQuery({
    queryKey: ["project-runs", id],
    queryFn: () => fetchAllRuns({ project_id: id, limit: 10 }),
  });

  // 本项目数据集。
  const { data: datasetsData, isLoading: datasetsLoading } = useQuery({
    queryKey: ["project-datasets", id],
    queryFn: () => fetchDatasets({ project_id: id, limit: 10 }),
  });
  const datasets = datasetsData?.items ?? [];
  const taskNames = new Map((tasks ?? []).map(task => [task.id, task.name]));

  if (isLoading) {
    return (
      <AppShell title="加载中..." description="">
        <div className="flex justify-center py-16">
          <Loader2 size={32} className="animate-spin text-[var(--text-tertiary)]" />
        </div>
      </AppShell>
    );
  }

  if (error || !project) {
    return (
      <AppShell title="加载失败" description="">
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--danger-soft)] p-6 text-sm text-[var(--state-danger)]">
          {(error as Error)?.message || "项目不存在"}
        </div>
      </AppShell>
    );
  }

  const domain = project.domain as keyof typeof DOMAIN_LABELS;

  return (
    <AppShell
      title={project.name}
      description={project.description || undefined}
      breadcrumbs={[
        { label: "我的项目", href: "/projects" },
        { label: project.name },
      ]}
    >
      <div className="mb-6 flex items-center gap-3">
        <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${DOMAIN_COLORS[domain]}`}>
          {DOMAIN_LABELS[domain]}
        </span>
        {project.status === "archived" && (
          <span className="rounded-full bg-[var(--surface-muted)] px-3 py-1 text-xs font-medium text-[var(--text-tertiary)]">
            已归档
          </span>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* 任务列表 */}
        <div className="lg:col-span-2">
          <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6">
            <div className="flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-base font-bold text-[var(--text-primary)]">
                <PlayCircle size={18} />
                采集任务
              </h2>
              <Link
                href="/tasks"
                className="rounded-[var(--radius-2)] bg-[var(--action-primary)] px-3 py-1.5 text-xs font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)]"
              >
                全部任务
              </Link>
            </div>
            {tasksLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 size={20} className="animate-spin text-[var(--text-tertiary)]" />
              </div>
            ) : (tasks?.length ?? 0) === 0 ? (
              <div className="mt-6 py-8 text-center text-sm text-[var(--text-tertiary)]">
                暂无任务。在「采集平台」选择能力即可启动采集。
              </div>
            ) : (
              <ul className="mt-4 grid gap-2">
                {tasks!.map(task => (
                  <li
                    key={task.id}
                    className="flex items-center justify-between gap-3 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-2"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-[var(--text-primary)]">
                        {task.name}
                      </p>
                      <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                        {task.collector_type} · 最近运行 {formatTimestamp(task.last_run_at)}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-3 text-xs">
                      <span className="text-[var(--text-secondary)]">
                        {TASK_STATUS_LABELS[task.status] ?? task.status}
                      </span>
                      <span className="tabular-nums text-[var(--text-tertiary)]">
                        {task.latest_run_records_count ?? 0} 条
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* 运行记录 */}
          <div className="mt-6 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6">
            <h2 className="flex items-center gap-2 text-base font-bold text-[var(--text-primary)]">
              <Calendar size={18} />
              最近运行
            </h2>
            {runsLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 size={20} className="animate-spin text-[var(--text-tertiary)]" />
              </div>
            ) : runsError ? (
              <div className="mt-6 text-center py-8 text-sm text-[var(--state-danger)]">
                运行记录加载失败。{(runsError as Error).message}
              </div>
            ) : (recentRuns?.length ?? 0) === 0 ? (
              <div className="mt-6 text-center py-8 text-sm text-[var(--text-tertiary)]">
                暂无运行记录。在「采集任务」中运行任务后，记录会出现在这里。
              </div>
            ) : (
              <ul className="mt-4 grid gap-2">
                {recentRuns!.map(run => (
                  <li
                    key={run.id}
                    className="flex items-center justify-between gap-3 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-2"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-[var(--text-primary)]">
                        {taskNames.get(run.task_id) ?? run.task_id.slice(0, 8)}
                      </p>
                      <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                        {formatTimestamp(run.started_at ?? run.created_at)}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-3 text-xs">
                      <span
                        className={
                          isSuccessfulRunStatus(run.status)
                            ? "text-[var(--state-success)]"
                            : run.status === "failed"
                              ? "text-[var(--state-danger)]"
                              : "text-[var(--text-secondary)]"
                        }
                      >
                        {run.status}
                      </span>
                      <span className="tabular-nums text-[var(--text-tertiary)]">
                        {run.records_count} 条
                      </span>
                      {run.records_count > 0 && (
                        <Link
                          href={`/runs/${run.id}`}
                          className="text-[var(--action-primary)] underline"
                        >
                          查看结果
                        </Link>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* 右侧数据集 */}
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-base font-bold text-[var(--text-primary)]">
              <Database size={18} />
              数据集
            </h2>
            {datasetsData && datasetsData.total > datasets.length && (
              <Link href="/assets" className="text-xs text-[var(--action-primary)] underline">
                全部 {datasetsData.total} 个
              </Link>
            )}
          </div>
          {datasetsLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 size={20} className="animate-spin text-[var(--text-tertiary)]" />
            </div>
          ) : datasets.length === 0 ? (
            <div className="mt-6 text-center py-8 text-sm text-[var(--text-tertiary)]">
              暂无数据集。完成采集并保存后，数据集会出现在这里。
            </div>
          ) : (
            <ul className="mt-4 grid gap-2">
              {datasets.map(item => (
                <li key={item.dataset.id} className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-2">
                  <Link
                    href="/assets"
                    className="block truncate text-sm font-medium text-[var(--text-primary)] hover:text-[var(--action-primary)]"
                  >
                    {item.dataset.name}
                  </Link>
                  <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                    {item.latest_version
                      ? `v${item.latest_version.version_number} · ${item.latest_version.row_count} 条`
                      : "无版本"}
                    {" · 更新 "}
                    {formatTimestamp(item.dataset.updated_at)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </AppShell>
  );
}
