"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { fetchTasks, runTask } from "@/lib/api/tasks";
import type { CollectionTask } from "@/lib/api/tasks";
import { Play, RefreshCw, CheckCircle, AlertCircle, Clock, Loader2 } from "lucide-react";

/* ── Status badge ── */
const STATUS_CONFIG: Record<string, { label: string; style: string }> = {
  enabled:  { label: "已启用", style: "bg-[var(--success-soft)] text-[var(--state-success)]" },
  running:  { label: "运行中", style: "bg-[var(--accent-2-soft)] text-[var(--state-info)]" },
  paused:   { label: "已暂停", style: "bg-[var(--warning-soft)] text-[var(--state-warning)]" },
  disabled: { label: "已禁用", style: "bg-[var(--surface-muted)] text-[var(--text-tertiary)]" },
  draft:    { label: "草稿",   style: "bg-[var(--surface-muted)] text-[var(--text-tertiary)]" },
};

const RUN_STATUS_ICON: Record<string, React.ReactNode> = {
  completed: <CheckCircle size={14} className="text-[var(--state-success)]" />,
  success:   <CheckCircle size={14} className="text-[var(--state-success)]" />,
  failed:    <AlertCircle size={14} className="text-[var(--state-danger)]" />,
  running:   <Loader2   size={14} className="animate-spin text-[var(--state-info)]" />,
  pending:   <Clock     size={14} className="text-[var(--text-tertiary)]" />,
};

function StatusPill({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? { label: status, style: "bg-[var(--surface-muted)] text-[var(--text-tertiary)]" };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cfg.style}`}>
      {cfg.label}
    </span>
  );
}

function TaskRow({ task }: { task: CollectionTask }) {
  const qc = useQueryClient();
  const run = useMutation({
    mutationFn: () => runTask(task.id, `console-manual-${task.id}-${Date.now()}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });

  const lastRunAt = task.latest_run_started_at
    ? new Date(task.latest_run_started_at).toLocaleString("zh-CN", { dateStyle: "short", timeStyle: "short" })
    : task.last_run_at
      ? new Date(task.last_run_at).toLocaleString("zh-CN", { dateStyle: "short", timeStyle: "short" })
      : "—";

  return (
    <tr className="border-b border-[var(--border-subtle)] transition-colors hover:bg-[var(--surface-muted)]">
      <td className="px-4 py-3">
        <div>
          <p className="text-sm font-medium text-[var(--text-primary)]">{task.name}</p>
          <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
            {task.collector_type}
            {task.source_name ? ` · ${task.source_name}` : ""}
          </p>
        </div>
      </td>
      <td className="px-4 py-3">
        <StatusPill status={task.status} />
      </td>
      <td className="px-4 py-3">
        {task.latest_run_status ? (
          <div className="flex items-center gap-1.5">
            {RUN_STATUS_ICON[task.latest_run_status] ?? null}
            <span className="text-xs text-[var(--text-secondary)]">
              {task.latest_run_status}
            </span>
          </div>
        ) : (
          <span className="text-xs text-[var(--text-tertiary)]">—</span>
        )}
      </td>
      <td className="px-4 py-3 text-sm tabular-nums text-[var(--text-secondary)]">
        {task.latest_run_records_count != null ? task.latest_run_records_count : "—"}
      </td>
      <td
        className="px-4 py-3 text-sm tabular-nums"
        title={`成功 ${task.success_count} 次，失败 ${task.failure_count} 次`}
      >
        <span className="text-[var(--state-success)]">{task.success_count}</span>
        <span className="text-[var(--text-tertiary)]"> / </span>
        <span className="text-[var(--state-danger)]">{task.failure_count}</span>
      </td>
      <td className="px-4 py-3 text-xs">
        {task.schedule_cron ? (
          <span className="font-mono text-[var(--text-secondary)]">{task.schedule_cron}</span>
        ) : (
          <span className="text-[var(--text-tertiary)]">手动</span>
        )}
      </td>
      <td className="px-4 py-3 text-xs text-[var(--text-tertiary)]">{lastRunAt}</td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            title="立即运行"
            disabled={run.isPending || task.status === "running"}
            onClick={() => run.mutate()}
            className="rounded-[var(--radius-1)] border border-[var(--border-subtle)] p-1.5 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--surface-muted)] hover:text-[var(--action-primary)] disabled:opacity-40"
          >
            {run.isPending
              ? <Loader2 size={14} className="animate-spin" />
              : <Play size={14} />}
          </button>
        </div>
      </td>
    </tr>
  );
}

export default function TasksPage() {
  const [statusFilter, setStatusFilter] = useState<string>("");
  const qc = useQueryClient();

  const { data: allTasks, isLoading, error } = useQuery({
    queryKey: ["tasks", "all"],
    queryFn: () => fetchTasks(),
    refetchInterval: 10_000,
  });

  const tasks = statusFilter
    ? (allTasks ?? []).filter((task) => task.status === statusFilter)
    : allTasks;
  const totalCount = allTasks?.length ?? 0;
  const filteredCount = tasks?.length ?? 0;

  return (
    <AppShell
      title="采集任务"
      description="管理所有数据采集任务"
    >
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          {(["", "enabled", "running", "paused", "disabled"] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setStatusFilter(s)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                statusFilter === s
                  ? "bg-[var(--action-primary)] text-[var(--text-inverse)]"
                  : "border border-[var(--border-subtle)] bg-[var(--surface-primary)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
              }`}
            >
              {s === "" ? "全部" : STATUS_CONFIG[s]?.label ?? s}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => qc.invalidateQueries({ queryKey: ["tasks"] })}
          className="flex items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
        >
          <RefreshCw size={12} />
          刷新
        </button>
      </div>

      <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)]">
        {isLoading ? (
          <div className="p-8 text-center">
            <Loader2 size={24} className="mx-auto animate-spin text-[var(--text-tertiary)]" />
            <p className="mt-2 text-sm text-[var(--text-tertiary)]">加载中...</p>
          </div>
        ) : error ? (
          <div className="p-8 text-center">
            <p className="text-sm text-[var(--state-danger)]">加载失败：{(error as Error).message}</p>
          </div>
        ) : !tasks || tasks.length === 0 ? (
          <div className="p-8 text-center">
            {totalCount === 0 ? (
              <>
                <p className="text-sm text-[var(--text-tertiary)]">暂无采集任务</p>
                <p className="mt-1 text-xs text-[var(--text-tertiary)]">
                  在「平台能力中心」点击「快速采集」可以自动创建任务
                </p>
              </>
            ) : (
              <>
                <p className="text-sm text-[var(--text-tertiary)]">当前筛选下没有任务</p>
                <p className="mt-1 text-xs text-[var(--text-tertiary)]">
                  全部 {totalCount} 个任务中，没有「{STATUS_CONFIG[statusFilter]?.label ?? statusFilter}」状态的任务
                </p>
                <button
                  type="button"
                  onClick={() => setStatusFilter("")}
                  className="mt-3 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
                >
                  查看全部任务
                </button>
              </>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[840px] border-collapse text-left">
              <thead>
                <tr className="border-b border-[var(--border-subtle)]">
                  {["任务名称", "状态", "最近运行", "记录数", "成功/失败", "定时", "最近执行", "操作"].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <TaskRow key={task.id} task={task} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <p className="text-xs text-[var(--text-tertiary)]">
        {statusFilter
          ? `筛选 ${filteredCount} / 全部 ${totalCount} 个任务，每 10 秒自动刷新`
          : `共 ${totalCount} 个任务，每 10 秒自动刷新`}
      </p>
    </AppShell>
  );
}
