"use client";

import { use, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { fetchRunById, fetchRunRecords, rawRecordEntries } from "@/lib/api/runs";
import type { RawRecord, TaskRun } from "@/lib/api/runs";
import {
  RUN_STATUS_CARD_CLASS,
  RUN_STATUS_TEXT_CLASS,
  isCompletedRunStatus,
  runStatusMeta,
} from "@/lib/run-status";
import type { RunStatusIconName } from "@/lib/run-status";
import {
  AlertCircle, CheckCircle, Clock, FileText, Inbox, Loader2,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

type Props = { params: Promise<{ runId: string }> };

const RUN_STATUS_ICONS: Record<RunStatusIconName, LucideIcon> = {
  check: CheckCircle,
  alert: AlertCircle,
  loader: Loader2,
  clock: Clock,
  inbox: Inbox,
};

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
  if (!run) return RUN_STATUS_CARD_CLASS.neutral;
  return RUN_STATUS_CARD_CLASS[runStatusMeta(run.status).tone];
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
  if (!run) {
    return <Clock size={20} className="mt-0.5 shrink-0 text-[var(--text-tertiary)]" />;
  }

  const meta = runStatusMeta(run.status);
  const Icon = RUN_STATUS_ICONS[meta.icon];
  const className = `mt-0.5 shrink-0 ${RUN_STATUS_TEXT_CLASS[meta.tone]}${
    meta.icon === "loader" ? " animate-spin" : ""
  }`;
  return <Icon size={20} className={className} />;
}

/** 标量值直接显示，保持原值。 */
function formatScalar(value: unknown): string {
  if (value === null) return "null";
  if (value === undefined) return "—";
  return String(value);
}

function isScalar(value: unknown): boolean {
  return value === null || typeof value !== "object";
}

function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2) ?? formatScalar(value);
  } catch {
    return formatScalar(value);
  }
}

function sizeHint(value: unknown): string {
  if (Array.isArray(value)) return `数组 · ${value.length} 项`;
  if (value !== null && typeof value === "object") {
    return `对象 · ${Object.keys(value).length} 个键`;
  }
  return "";
}

/**
 * 显示一条记录的全部字段。
 * 标量直接显示；对象、数组和 raw 键默认折叠。
 */
function RecordContent({ content }: { content: RawRecord["content"] }) {
  const entries = rawRecordEntries(content);
  const collapsibleKeys = entries
    .filter(([key, value]) => key === "raw" || !isScalar(value))
    .map(([key]) => key);
  const [openKeys, setOpenKeys] = useState<Set<string>>(
    () =>
      new Set(
        entries
          .filter(([key, value]) => key !== "raw" && isScalar(value))
          .map(([key]) => key),
      ),
  );

  if (entries.length === 0) {
    return <p className="mt-3 text-xs text-[var(--text-tertiary)]">该记录内容为空</p>;
  }

  const allOpen =
    collapsibleKeys.length > 0 &&
    collapsibleKeys.every(key => openKeys.has(key));

  function toggleAll() {
    setOpenKeys(
      allOpen ? new Set() : new Set(entries.map(([key]) => key)),
    );
  }

  return (
    <div className="mt-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-[var(--text-tertiary)]">
          {Array.isArray(content)
            ? `共 ${entries.length} 项`
            : `共 ${entries.length} 个字段`}
        </span>
        {collapsibleKeys.length > 0 ? (
          <button
            type="button"
            onClick={toggleAll}
            className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
          >
            {allOpen ? "收起全部" : "展开全部"}
          </button>
        ) : null}
      </div>

      <dl className="grid gap-1.5">
        {entries.map(([key, value]) => {
          const collapsible = key === "raw" || !isScalar(value);

          if (!collapsible) {
            return (
              <div key={key} className="flex gap-3 text-xs">
                <dt className="w-28 shrink-0 break-all font-mono text-[var(--text-tertiary)]">
                  {key}
                </dt>
                <dd className="min-w-0 flex-1 whitespace-pre-wrap break-all text-[var(--text-secondary)]">
                  {formatScalar(value)}
                </dd>
              </div>
            );
          }

          const isOpen = openKeys.has(key);
          return (
            <details
              key={key}
              open={isOpen}
              onToggle={event => {
                const nextOpen = event.currentTarget.open;
                setOpenKeys(current => {
                  const next = new Set(current);
                  if (nextOpen) next.add(key);
                  else next.delete(key);
                  return next;
                });
              }}
              className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 py-2"
            >
              <summary className="cursor-pointer break-all font-mono text-xs text-[var(--text-tertiary)]">
                {key}
                <span className="ml-2 font-sans">{sizeHint(value)}</span>
              </summary>
              {isOpen ? (
                <div className="mt-2 max-h-96 overflow-auto">
                  {isScalar(value) ? (
                    <p className="whitespace-pre-wrap break-all text-xs text-[var(--text-secondary)]">
                      {formatScalar(value)}
                    </p>
                  ) : (
                    <pre className="whitespace-pre-wrap break-all font-mono text-xs text-[var(--text-secondary)]">
                      {formatJson(value)}
                    </pre>
                  )}
                </div>
              ) : null}
            </details>
          );
        })}
      </dl>
    </div>
  );
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

  const meta = run ? runStatusMeta(run.status) : null;
  const isFailed = run?.status === "failed";
  const isEmpty = run?.status === "empty";
  const isCompleted = run ? isCompletedRunStatus(run.status) : false;
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
              {runLoading ? "加载运行信息..." : meta ? meta.label : "运行状态未知"}
            </p>

            {!runLoading && meta?.description ? (
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                {meta.description}
              </p>
            ) : null}

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

              <RecordContent content={rec.content} />
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
          ) : isEmpty ? (
            <>
              <Inbox size={32} className="mx-auto text-[var(--state-warning)]" />
              <p className="mt-3 text-sm font-medium text-[var(--text-primary)]">
                运行完成，但没有取到数据
              </p>
              <p className="mt-1 text-xs text-[var(--text-secondary)]">
                本次运行没有错误，采集器返回 0 条记录。
              </p>
            </>
          ) : isCompleted ? (
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
