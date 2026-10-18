"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { fetchRunById, fetchRunRecords } from "@/lib/api/runs";
import type { TaskRun } from "@/lib/api/runs";
import { isSuccessfulRunStatus } from "@/lib/run-status";
import { AlertCircle, CheckCircle, Clock, FileText, Loader2 } from "lucide-react";

type Props = { params: Promise<{ runId: string }> };

const STATUS_LABELS: Record<string, string> = {
  completed: "已完成",
  success: "成功",
  failed: "失败",
  running: "运行中",
  pending: "等待中",
};

function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("zh-CN", { hour12: false });
}

function formatDuration(run: TaskRun): string {
  const start = run.started_at ?? run.created_at;
  if (!run.finished_at) return "—";
  const ms = new Date(run.finished_at).getTime() - new Date(start).getTime();
  if (Number.isNaN(ms) || ms < 0) return "—";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m${Math.floor((ms % 60_000) / 1000)}s`;
}

function errorReason(run: TaskRun): string {
  return run.error_message?.trim() || "未提供错误信息";
}

function statusCardStyle(run: TaskRun | null | undefined): string {
  if (run?.status === "failed") {
    return "border-[var(--state-danger)] bg-[var(--danger-soft)]";
  }
  if (run && isSuccessfulRunStatus(run.status)) {
    return "border-[var(--state-success)] bg-[var(--success-soft)]";
  }
  return "border-[var(--border-subtle)] bg-[var(--surface-primary)]";
}

function RunStatusIcon({
  run,
  loading,
}: {
  run: TaskRun | null | undefined;
  loading: boolean;
}) {
  if (loading) {
    return <Loader2 size={20} className="mt-0.5 shrink-0 animate-spin text-[var(--text-tertiary)]" />;
  }
  if (run?.status === "failed") {
    return <AlertCircle size={20} className="mt-0.5 shrink-0 text-[var(--state-danger)]" />;
  }
  if (run && isSuccessfulRunStatus(run.status)) {
    return <CheckCircle size={20} className="mt-0.5 shrink-0 text-[var(--state-success)]" />;
  }
  if (run?.status === "running") {
    return <Loader2 size={20} className="mt-0.5 shrink-0 animate-spin text-[var(--state-info)]" />;
  }
  return <Clock size={20} className="mt-0.5 shrink-0 text-[var(--text-tertiary)]" />;
}

export default function CollectResultPage({ params }: Props) {
  const { runId } = use(params);

  const {
    data: run,
    isLoading: runLoading,
    error: runError,
  } = useQuery({
    queryKey: ["run", runId],
    queryFn: () => fetchRunById(runId),
    enabled: !!runId,
  });

  const { data: records, isLoading: recordsLoading } = useQuery({
    queryKey: ["run-records", runId],
    queryFn: () => fetchRunRecords(runId),
    enabled: !!runId,
  });

  const isFailed = run?.status === "failed";
  const isSuccess = run ? isSuccessfulRunStatus(run.status) : false;
  const isRunning = run?.status === "running" || run?.status === "pending";
  const hasRecords = !!records && records.length > 0;

  return (
    <AppShell
      title="采集结果"
      description="查看本次采集的原始数据"
      breadcrumbs={[
        { label: "运行记录", href: "/runs" },
        { label: `结果 ${runId.slice(0, 8)}…` },
      ]}
    >
      {/* 运行状态 */}
      <div className={`rounded-[var(--radius-3)] border p-4 ${statusCardStyle(run)}`}>
        <div className="flex items-start gap-3">
          <RunStatusIcon run={run} loading={runLoading} />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-bold text-[var(--text-primary)]">
              {runLoading ? "加载运行信息..." : run ? statusLabel(run.status) : "运行状态未知"}
            </p>

            {runLoading && (
              <p className="mt-0.5 text-sm text-[var(--text-secondary)]">
                正在读取本次运行的状态
              </p>
            )}

            {!runLoading && run && (
              <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-xs text-[var(--text-secondary)]">
                <div className="flex gap-1.5">
                  <dt className="text-[var(--text-tertiary)]">开始时间</dt>
                  <dd className="tabular-nums">
                    {formatDateTime(run.started_at ?? run.created_at)}
                  </dd>
                </div>
                <div className="flex gap-1.5">
                  <dt className="text-[var(--text-tertiary)]">耗时</dt>
                  <dd className="tabular-nums">{formatDuration(run)}</dd>
                </div>
                <div className="flex gap-1.5">
                  <dt className="text-[var(--text-tertiary)]">记录数</dt>
                  <dd className="tabular-nums">{run.records_count}</dd>
                </div>
              </dl>
            )}

            {!runLoading && !run && (
              <p className="mt-0.5 text-sm text-[var(--text-secondary)]">
                本次运行较早，状态信息已不可用。原始记录仍可查看。
              </p>
            )}

            {runError && (
              <p className="mt-2 text-sm text-[var(--state-danger)]">
                运行信息加载失败：{(runError as Error).message}
              </p>
            )}

            {!runLoading && isFailed && run && (
              <div className="mt-2 rounded-[var(--radius-2)] border border-[var(--state-danger)] bg-[var(--surface-primary)] px-3 py-2 text-sm text-[var(--state-danger)]">
                失败原因：{errorReason(run)}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Records */}
      {hasRecords && (
        <div className="grid gap-3">
          {records.map((rec) => (
            <div
              key={rec.id}
              className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-4"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText size={14} className="text-[var(--text-tertiary)]" />
                  <span className="text-xs font-semibold text-[var(--text-primary)]">
                    {rec.record_type}
                  </span>
                </div>
                <span className="text-xs text-[var(--text-tertiary)]">
                  {new Date(rec.created_at).toLocaleTimeString("zh-CN")}
                </span>
              </div>

              {rec.source_url ? (
                <p className="mt-2 truncate text-xs text-[var(--text-tertiary)]">
                  {rec.source_url}
                </p>
              ) : null}

              <div className="mt-3 grid gap-1.5">
                {Object.entries(rec.content ?? {})
                  .filter(([k]) => k !== "raw")
                  .slice(0, 6)
                  .map(([k, v]) => (
                    <div key={k} className="flex gap-3 text-xs">
                      <span className="w-28 shrink-0 font-mono text-[var(--text-tertiary)] truncate">
                        {k}
                      </span>
                      <span className="truncate text-[var(--text-secondary)]">
                        {typeof v === "object"
                          ? JSON.stringify(v).slice(0, 80)
                          : String(v ?? "").slice(0, 120)}
                      </span>
                    </div>
                  ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {recordsLoading && (
        <div className="flex justify-center py-12">
          <Loader2 size={28} className="animate-spin text-[var(--text-tertiary)]" />
        </div>
      )}

      {!recordsLoading && !hasRecords && !runLoading && (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-8 text-center">
          {isFailed && run ? (
            <>
              <AlertCircle size={32} className="mx-auto text-[var(--state-danger)]" />
              <p className="mt-3 text-sm font-medium text-[var(--state-danger)]">
                本次运行失败，未产生原始记录
              </p>
              <p className="mt-1 text-xs text-[var(--text-secondary)]">
                详见上方状态区。
              </p>
            </>
          ) : isRunning ? (
            <>
              <Loader2 size={32} className="mx-auto animate-spin text-[var(--text-tertiary)]" />
              <p className="mt-3 text-sm text-[var(--text-secondary)]">
                采集仍在进行，暂无原始记录
              </p>
              <p className="mt-1 text-xs text-[var(--text-tertiary)]">
                运行结束后，原始记录会显示在这里
              </p>
            </>
          ) : isSuccess ? (
            <>
              <FileText size={32} className="mx-auto text-[var(--text-tertiary)]" />
              <p className="mt-3 text-sm text-[var(--text-secondary)]">
                本次运行已完成，未产生原始记录
              </p>
            </>
          ) : (
            <>
              <FileText size={32} className="mx-auto text-[var(--text-tertiary)]" />
              <p className="mt-3 text-sm text-[var(--text-secondary)]">暂无数据</p>
              <p className="mt-1 text-xs text-[var(--text-tertiary)]">
                本次采集未产生原始记录
              </p>
            </>
          )}
        </div>
      )}

      <div className="text-xs text-[var(--text-tertiary)]">
        运行 ID: <code className="font-mono">{runId}</code>
      </div>
    </AppShell>
  );
}
