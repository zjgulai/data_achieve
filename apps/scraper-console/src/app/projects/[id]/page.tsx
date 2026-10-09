"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { fetchProject, DOMAIN_LABELS, DOMAIN_COLORS } from "@/lib/api/projects";
import { fetchTasks } from "@/lib/api/tasks";
import { Loader2, FolderKanban, PlayCircle, Database, Calendar } from "lucide-react";
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
            <div className="mt-6 text-center py-8 text-sm text-[var(--text-tertiary)]">
              暂无运行记录
            </div>
          </div>
        </div>

        {/* 右侧数据集 */}
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6">
          <h2 className="flex items-center gap-2 text-base font-bold text-[var(--text-primary)]">
            <Database size={18} />
            数据集
          </h2>
          <div className="mt-6 text-center py-8 text-sm text-[var(--text-tertiary)]">
            暂无数据集
          </div>
        </div>
      </div>
    </AppShell>
  );
}
