"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { X, Loader2, Download, Table2, ListTree, History, AlertTriangle } from "lucide-react";
import { PlatformLogo } from "@/components/platforms/platform-logo";
import { getPlatformLabel } from "@/lib/platforms/catalog";
import {
  downloadExport,
  createExport,
  fetchDatasetVersions,
  fetchVersionPreview,
  type DatasetExportFormat,
  type DatasetVersion,
  type DatasetPreviewRow,
} from "@/lib/api/datasets";

const FORMATS: DatasetExportFormat[] = ["csv", "xlsx", "json", "jsonl"];

const FORMAT_LABELS: Record<DatasetExportFormat, string> = {
  csv: "CSV",
  xlsx: "Excel",
  json: "JSON",
  jsonl: "JSONL",
};

type Tab = "rows" | "schema" | "lineage";

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function inferType(rows: DatasetPreviewRow[], field: string): string {
  for (const row of rows) {
    const v = row.values[field];
    if (v === null || v === undefined) continue;
    if (Array.isArray(v)) return "数组";
    const t = typeof v;
    if (t === "number") return "数值";
    if (t === "boolean") return "布尔";
    if (t === "object") return "对象";
    return "文本";
  }
  return "空";
}

function ExportControl({
  datasetId,
  versionId,
  compact = false,
}: {
  datasetId: string;
  versionId: string;
  compact?: boolean;
}) {
  const [format, setFormat] = useState<DatasetExportFormat>("csv");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setPending(true);
    setError(null);
    try {
      const job = await createExport(datasetId, versionId, format);
      await downloadExport(job);
    } catch (err) {
      setError(err instanceof Error ? err.message : "导出失败");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex items-center gap-1.5">
      <select
        value={format}
        onChange={e => setFormat(e.target.value as DatasetExportFormat)}
        aria-label="导出格式"
        className="h-8 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-2 text-xs text-[var(--text-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
      >
        {FORMATS.map(f => (
          <option key={f} value={f}>
            {FORMAT_LABELS[f]}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={run}
        disabled={pending}
        className="flex items-center gap-1 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-inverse)] transition-colors hover:bg-[var(--action-primary-hover)] disabled:opacity-50"
      >
        {pending ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
        {compact ? "导出" : `导出 ${FORMAT_LABELS[format]}`}
      </button>
      {error ? (
        <span className="flex items-center gap-1 text-xs text-[var(--state-danger)]">
          <AlertTriangle size={12} />
          {error}
        </span>
      ) : null}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 py-2">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">{label}</p>
      <p className="mt-0.5 text-sm font-semibold tabular-nums text-[var(--text-primary)]">{value}</p>
    </div>
  );
}

export function DataPreviewDrawer({
  open,
  onClose,
  datasetId,
  datasetName,
  platforms,
  initialVersion,
}: {
  open: boolean;
  onClose: () => void;
  datasetId: string;
  datasetName: string;
  platforms: string[];
  initialVersion: DatasetVersion | null;
}) {
  // `tab` / `versionId` are initialised from props; the parent remounts this
  // drawer (via `key`) when a different dataset is opened, so no reset effect
  // is needed.
  const [tab, setTab] = useState<Tab>("rows");
  const [versionId, setVersionId] = useState<string | null>(initialVersion?.id ?? null);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const versionsQuery = useQuery({
    queryKey: ["dataset-versions", datasetId],
    queryFn: () => fetchDatasetVersions(datasetId),
    enabled: open && !!datasetId,
  });

  const versions = useMemo<DatasetVersion[]>(() => {
    const list = versionsQuery.data?.versions ?? [];
    if (list.length > 0) return list;
    return initialVersion ? [initialVersion] : [];
  }, [versionsQuery.data, initialVersion]);

  const activeVersion = useMemo(
    () => versions.find(v => v.id === versionId) ?? versions[0] ?? null,
    [versions, versionId],
  );

  const previewQuery = useQuery({
    queryKey: ["dataset-preview", datasetId, activeVersion?.id],
    queryFn: () => fetchVersionPreview(datasetId, activeVersion!.id, 50),
    enabled: open && !!datasetId && !!activeVersion,
  });

  if (!open) return null;

  const preview = previewQuery.data;
  const rows = preview?.rows ?? [];
  const fields = preview?.fields ?? activeVersion?.selected_fields ?? [];
  const leadPlatform = platforms[0] ?? "";

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-[var(--overlay-scrim)]"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`数据集预览：${datasetName}`}
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col border-l border-[var(--border-subtle)] bg-[var(--surface-primary)] shadow-[var(--shadow-overlay)]"
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4 border-b border-[var(--border-subtle)] px-6 py-4">
          <div className="flex min-w-0 items-start gap-3">
            <PlatformLogo platform={leadPlatform || "web"} size={36} />
            <div className="min-w-0">
              <h2 className="truncate text-sm font-semibold text-[var(--text-primary)]">{datasetName}</h2>
              <p className="mt-0.5 truncate text-xs text-[var(--text-tertiary)]">
                {platforms.length > 0
                  ? platforms.map(getPlatformLabel).join(" · ")
                  : "平台待识别"}
                {activeVersion ? ` · v${activeVersion.version_number}` : ""}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭"
            className="rounded-[var(--radius-2)] p-1.5 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
          >
            <X size={18} />
          </button>
        </div>

        {/* Version + export toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border-subtle)] px-6 py-3">
          <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
            版本
            <select
              value={activeVersion?.id ?? ""}
              onChange={e => setVersionId(e.target.value)}
              disabled={versions.length <= 1}
              className="h-8 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-2 text-xs text-[var(--text-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)] disabled:opacity-60"
            >
              {versions.map(v => (
                <option key={v.id} value={v.id}>
                  v{v.version_number}（{v.row_count.toLocaleString()} 条）
                </option>
              ))}
            </select>
          </label>
          {activeVersion ? (
            <ExportControl datasetId={datasetId} versionId={activeVersion.id} />
          ) : null}
        </div>

        {/* Stats */}
        {activeVersion ? (
          <div className="grid grid-cols-3 gap-3 px-6 py-3">
            <Stat label="记录数" value={preview ? preview.total_rows.toLocaleString() : activeVersion.row_count.toLocaleString()} />
            <Stat label="平均完整度" value={`${activeVersion.average_completeness_percent}%`} />
            <Stat label="生成时间" value={formatDateTime(activeVersion.created_at)} />
          </div>
        ) : null}

        {/* Tabs */}
        <div className="flex items-center gap-1 border-b border-[var(--border-subtle)] px-6">
          {(
            [
              { key: "rows", label: "数据预览", icon: <Table2 size={13} /> },
              { key: "schema", label: "字段结构", icon: <ListTree size={13} /> },
              { key: "lineage", label: "采集溯源", icon: <History size={13} /> },
            ] as { key: Tab; label: string; icon: React.ReactNode }[]
          ).map(t => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={`-mb-px flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs font-medium transition-colors ${
                tab === t.key
                  ? "border-[var(--action-primary)] text-[var(--action-primary)]"
                  : "border-transparent text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]"
              }`}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {previewQuery.isLoading ? (
            <div className="flex justify-center py-16">
              <Loader2 size={22} className="animate-spin text-[var(--text-tertiary)]" />
            </div>
          ) : previewQuery.error ? (
            <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--danger-soft)] p-4 text-sm text-[var(--state-danger)]">
              加载失败：{(previewQuery.error as Error).message}
            </div>
          ) : !activeVersion ? (
            <p className="py-12 text-center text-sm text-[var(--text-tertiary)]">该数据集暂无版本</p>
          ) : tab === "rows" ? (
            rows.length === 0 ? (
              <p className="py-12 text-center text-sm text-[var(--text-tertiary)]">该版本没有可预览的记录</p>
            ) : (
              <>
                <p className="mb-2 text-xs text-[var(--text-tertiary)]">
                  展示前 {rows.length} 条，共 {preview?.total_rows.toLocaleString() ?? activeVersion.row_count} 条
                </p>
                <div className="overflow-x-auto rounded-[var(--radius-2)] border border-[var(--border-subtle)]">
                  <table className="w-full border-collapse text-left text-xs">
                    <thead>
                      <tr className="border-b border-[var(--border-subtle)] bg-[var(--surface-secondary)]">
                        {fields.map(f => (
                          <th
                            key={f}
                            className="whitespace-nowrap px-3 py-2 font-semibold uppercase tracking-wide text-[var(--text-tertiary)]"
                          >
                            {f}
                          </th>
                        ))}
                        <th className="whitespace-nowrap px-3 py-2 font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
                          完整度
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row, i) => (
                        <tr key={row.row_id || i} className="border-b border-[var(--border-subtle)] last:border-0">
                          {fields.map(f => (
                            <td
                              key={f}
                              className="max-w-[280px] truncate px-3 py-2 text-[var(--text-secondary)]"
                              title={formatCell(row.values[f])}
                            >
                              {formatCell(row.values[f])}
                            </td>
                          ))}
                          <td className="whitespace-nowrap px-3 py-2 tabular-nums text-[var(--text-secondary)]">
                            {row.completeness_percent}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )
          ) : tab === "schema" ? (
            <div className="overflow-hidden rounded-[var(--radius-2)] border border-[var(--border-subtle)]">
              <table className="w-full border-collapse text-left text-xs">
                <thead>
                  <tr className="border-b border-[var(--border-subtle)] bg-[var(--surface-secondary)]">
                    {["字段", "类型", "空值数"].map(h => (
                      <th key={h} className="px-3 py-2 font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {fields.map(f => (
                    <tr key={f} className="border-b border-[var(--border-subtle)] last:border-0">
                      <td className="px-3 py-2 font-medium text-[var(--text-primary)]">{f}</td>
                      <td className="px-3 py-2 text-[var(--text-secondary)]">{inferType(rows, f)}</td>
                      <td className="px-3 py-2 tabular-nums text-[var(--text-secondary)]">
                        {rows.filter(r => r.values[f] === null || r.values[f] === undefined).length}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="space-y-4">
              <section>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">来源任务</h3>
                <ul className="mt-2 space-y-1">
                  {activeVersion.source_task_run_ids.length === 0 ? (
                    <li className="text-xs text-[var(--text-tertiary)]">—</li>
                  ) : (
                    activeVersion.source_task_run_ids.map(id => (
                      <li key={id} className="font-mono text-xs text-[var(--text-secondary)]">{id}</li>
                    ))
                  )}
                </ul>
              </section>
              <section>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">清洗规则</h3>
                <ul className="mt-2 space-y-1">
                  {activeVersion.cleaning_script.length === 0 ? (
                    <li className="text-xs text-[var(--text-tertiary)]">—</li>
                  ) : (
                    activeVersion.cleaning_script.map((rule, i) => (
                      <li key={i} className="text-xs text-[var(--text-secondary)]">{rule}</li>
                    ))
                  )}
                </ul>
              </section>
              <section>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">版本历史</h3>
                <ul className="mt-2 divide-y divide-[var(--border-subtle)] rounded-[var(--radius-2)] border border-[var(--border-subtle)]">
                  {versions.map(v => (
                    <li key={v.id} className="flex items-center justify-between px-3 py-2 text-xs">
                      <span className="font-medium text-[var(--text-primary)]">v{v.version_number}</span>
                      <span className="tabular-nums text-[var(--text-tertiary)]">
                        {v.row_count.toLocaleString()} 条 · {formatDateTime(v.created_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
