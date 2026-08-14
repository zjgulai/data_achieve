"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { fetchAllRuns, fetchRunRecords } from "@/lib/api/runs";
import type { TaskRun, RawRecord } from "@/lib/api/runs";
import {
  CheckCircle, AlertCircle, Clock, Loader2,
  ChevronDown, ChevronRight, FileText,
} from "lucide-react";

/* ── Status helpers ── */
function RunStatusIcon({ status }: { status: string }) {
  if (status === "completed") return <CheckCircle size={16} className="text-[var(--state-success)]" />;
  if (status === "failed")    return <AlertCircle size={16} className="text-[var(--state-danger)]" />;
  if (status === "running")   return <Loader2    size={16} className="animate-spin text-[var(--state-info)]" />;
  return <Clock size={16} className="text-[var(--text-tertiary)]" />;
}

function RunStatusLabel({ status }: { status: string }) {
  const map: Record<string, { label: string; style: string }> = {
    completed: { label: "已完成", style: "text-[var(--state-success)]" },
    failed:    { label: "失败",   style: "text-[var(--state-danger)]" },
    running:   { label: "运行中", style: "text-[var(--state-info)]" },
    pending:   { label: "等待中", style: "text-[var(--text-tertiary)]" },
  };
  const cfg = map[status] ?? { label: status, style: "text-[var(--text-secondary)]" };
  return <span className={`text-sm font-medium ${cfg.style}`}>{cfg.label}</span>;
}

function dur(a: string | null, b: string | null) {
  if (!a || !b) return "—";
  const ms = new Date(b).getTime() - new Date(a).getTime();
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m${Math.floor((ms % 60_000) / 1000)}s`;
}

/* ── Raw record preview ── */
function RecordPreview({ runId }: { runId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["run-records", runId],
    queryFn: () => fetchRunRecords(runId),
  });

  if (isLoading) return (
    <div className="py-4 text-center text-sm text-[var(--text-tertiary)]">
      加载记录中...
    </div>
  );

  if (!data || data.length === 0) return (
    <p className="py-4 text-center text-sm text-[var(--text-tertiary)]">暂无原始记录</p>
  );

  return (
    <div className="mt-2 grid gap-2">
      {data.slice(0, 5).map((rec) => (
        <div
          key={rec.id}
          className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-3 py-2"
        >
          <div className="flex items-center gap-2">
            <FileText size={12} className="text-[var(--text-tertiary)]" />
            <span className="text-xs font-medium text-[var(--text-primary)]">
              {rec.record_type}
            </span>
            <span className="ml-auto text-xs text-[var(--text-tertiary)]">
              {new Date(rec.created_at).toLocaleTimeString("zh-CN")}
            </span>
          </div>
          {/* Show first 3 data keys */}
          <div className="mt-1.5 grid gap-0.5">
            {Object.entries(rec.data ?? {}).slice(0, 3).map(([k, v]) => (
              <div key={k} className="flex gap-2 text-xs">
                <span className="shrink-0 font-mono text-[var(--text-tertiary)]">{k}:</span>
                <span className="truncate text-[var(--text-secondary)]">
                  {typeof v === "object" ? JSON.stringify(v).slice(0, 60) : String(v ?? "").slice(0, 80)}
                </span>
              </div>
            ))}
          </div>
        </div>
      ))}
      {data.length > 5 && (
        <p className="text-center text-xs text-[var(--text-tertiary)]">
          显示前 5 条，共 {data.length} 条
        </p>
      )}
    </div>
  );
}

/* ── Run row with expandable detail ── */
function RunRow({ run }: { run: TaskRun }) {
  const [expanded, setExpanded] = useState(false);

  const startedAt = run.started_at
    ? new Date(run.started_at).toLocaleString("zh-CN", { dateStyle: "short", timeStyle: "short" })
    : new Date(run.created_at).toLocaleString("zh-CN", { dateStyle: "short", timeStyle: "short" });

  return (
    <>
      <tr
        className="cursor-pointer border-b border-[var(--border-subtle)] transition-colors hover:bg-[var(--surface-muted)]"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            {expanded
              ? <ChevronDown size={14} className="text-[var(--text-tertiary)]" />
              : <ChevronRight size={14} className="text-[var(--text-tertiary)]" />}
            <RunStatusIcon status={run.status} />
            <RunStatusLabel status={run.status} />
          </div>
        </td>
        <td className="px-4 py-3 text-sm tabular-nums text-[var(--text-secondary)]">
          {run.records_count}
        </td>
        <td className="px-4 py-3 text-xs text-[var(--text-tertiary)]">{startedAt}</td>
        <td className="px-4 py-3 text-xs tabular-nums text-[var(--text-tertiary)]">
          {dur(run.started_at, run.finished_at)}
        </td>
        <td className="px-4 py-3 text-xs font-mono text-[var(--text-tertiary)]">
          {run.id.slice(0, 8)}…
        </td>
      </tr>

      {expanded && (
        <tr className="border-b border-[var(--border-subtle)] bg-[var(--surface-secondary)]">
          <td colSpan={5} className="px-6 pb-4 pt-2">
            {run.error_message && (
              <div className="mb-3 rounded-[var(--radius-2)] border border-[var(--state-danger)] bg-[var(--danger-soft)] px-3 py-2 text-sm text-[var(--state-danger)]">
                {run.error_message}
              </div>
            )}
            <p className="mb-2 text-xs font-semibold uppercase text-[var(--text-tertiary)]">
              原始记录预览
            </p>
            <RecordPreview runId={run.id} />
          </td>
        </tr>
      )}
    </>
  );
}

/* ── Page ── */
export default function RunsPage() {
  const { data: runs, isLoading, error } = useQuery({
    queryKey: ["all-runs"],
    queryFn: () => fetchAllRuns({ limit: 50 }),
    refetchInterval: 15_000,
  });

  return (
    <AppShell
      title="运行记录"
      description="所有采集任务的执行历史"
    >
      <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)]">
        {isLoading ? (
          <div className="p-8 text-center">
            <Loader2 size={24} className="mx-auto animate-spin text-[var(--text-tertiary)]" />
            <p className="mt-2 text-sm text-[var(--text-tertiary)]">加载运行记录中...</p>
          </div>
        ) : error ? (
          <div className="p-8 text-center">
            <p className="text-sm text-[var(--state-danger)]">
              加载失败：{(error as Error).message}
            </p>
          </div>
        ) : !runs || runs.length === 0 ? (
          <div className="p-8 text-center">
            <Clock size={32} className="mx-auto text-[var(--text-tertiary)]" />
            <p className="mt-3 text-sm text-[var(--text-tertiary)]">暂无运行记录</p>
            <p className="mt-1 text-xs text-[var(--text-tertiary)]">
              在「平台能力中心」执行快速采集后，记录会出现在这里
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] border-collapse text-left">
              <thead>
                <tr className="border-b border-[var(--border-subtle)]">
                  {["状态", "记录数", "开始时间", "耗时", "运行 ID"].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <RunRow key={run.id} run={run} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <p className="text-xs text-[var(--text-tertiary)]">
        点击行可展开原始记录预览，共 {runs?.length ?? 0} 条记录，每 15 秒自动刷新
      </p>
    </AppShell>
  );
}
