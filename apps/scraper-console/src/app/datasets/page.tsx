"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { fetchDatasets, createExport } from "@/lib/api/datasets";
import { Database, Download, RefreshCw, Loader2, Package } from "lucide-react";

function formatDate(s: string) {
  return new Date(s).toLocaleDateString("zh-CN", { month: "short", day: "numeric", year: "numeric" });
}

function ExportButton({ datasetId, versionId }: { datasetId: string; versionId: string }) {
  const [fmt, setFmt] = useState<"csv" | "json" | "jsonl">("csv");

  const exp = useMutation({
    mutationFn: () => createExport(datasetId, versionId, fmt),
    onSuccess: (data) => {
      alert(`导出已创建，任务 ID：${data.export_job_id}`);
    },
  });

  return (
    <div className="flex items-center gap-1.5">
      <select
        value={fmt}
        onChange={e => setFmt(e.target.value as "csv" | "json" | "jsonl")}
        className="h-8 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-2 text-xs text-[var(--text-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
      >
        <option value="csv">CSV</option>
        <option value="json">JSON</option>
        <option value="jsonl">JSONL</option>
      </select>
      <button
        type="button"
        disabled={exp.isPending}
        onClick={() => exp.mutate()}
        className="flex items-center gap-1 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--accent-1-soft)] hover:text-[var(--action-primary)] disabled:opacity-50"
      >
        {exp.isPending ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
        导出
      </button>
    </div>
  );
}

export default function DatasetsPage() {
  const [projectFilter] = useState<string>("");

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["datasets", projectFilter],
    queryFn: () => fetchDatasets({ project_id: projectFilter || undefined }),
  });

  const items = data?.items ?? [];

  return (
    <AppShell title="数据集" description="查看和导出所有采集数据集">
      <div className="flex items-center justify-between">
        <p className="text-sm text-[var(--text-tertiary)]">
          共 {data?.total ?? 0} 个数据集
        </p>
        <button
          type="button"
          onClick={() => refetch()}
          className="flex items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
        >
          <RefreshCw size={12} />
          刷新
        </button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 size={24} className="animate-spin text-[var(--text-tertiary)]" />
        </div>
      ) : error ? (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--danger-soft)] p-6 text-sm text-[var(--state-danger)]">
          加载失败：{(error as Error).message}
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-[var(--radius-3)] border-2 border-dashed border-[var(--border-subtle)] py-16 text-center">
          <Package size={36} className="mx-auto text-[var(--text-tertiary)]" />
          <p className="mt-3 text-base font-semibold text-[var(--text-primary)]">暂无数据集</p>
          <p className="mt-1 text-sm text-[var(--text-tertiary)]">在「采集平台」完成采集后，数据集会出现在这里</p>
        </div>
      ) : (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)]">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] border-collapse text-left">
              <thead>
                <tr className="border-b border-[var(--border-subtle)]">
                  {["数据集", "最新版本", "记录数", "更新时间", "导出"].map(h => (
                    <th key={h} className="px-5 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map(({ dataset, latest_version, version_count }) => (
                  <tr key={dataset.id} className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--surface-muted)]">
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2.5">
                        <Database size={15} className="shrink-0 text-[var(--text-tertiary)]" />
                        <div>
                          <p className="text-sm font-semibold text-[var(--text-primary)]">{dataset.name}</p>
                          <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">{dataset.source_type}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-sm text-[var(--text-secondary)]">
                        {latest_version ? `v${latest_version.version_number}` : "—"}
                        {version_count > 1 && (
                          <span className="ml-1.5 text-xs text-[var(--text-tertiary)]">（{version_count} 个版本）</span>
                        )}
                      </span>
                    </td>
                    <td className="px-5 py-4 tabular-nums text-sm text-[var(--text-secondary)]">
                      {latest_version?.row_count != null
                        ? latest_version.row_count.toLocaleString()
                        : "—"}
                    </td>
                    <td className="px-5 py-4 text-xs text-[var(--text-tertiary)]">
                      {formatDate(dataset.updated_at)}
                    </td>
                    <td className="px-5 py-4">
                      {latest_version ? (
                        <ExportButton datasetId={dataset.id} versionId={latest_version.id} />
                      ) : (
                        <span className="text-xs text-[var(--text-tertiary)]">无版本</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </AppShell>
  );
}
