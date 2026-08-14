"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { fetchRunRecords } from "@/lib/api/runs";
import { CheckCircle, AlertCircle, Loader2, FileText } from "lucide-react";

type Props = { params: Promise<{ run_id: string }> };

export default function CollectResultPage({ params }: Props) {
  const { run_id } = use(params);

  const { data: records, isLoading: recordsLoading } = useQuery({
    queryKey: ["run-records", run_id],
    queryFn: () => fetchRunRecords(run_id),
    enabled: !!run_id,
  });

  const isOk = records && records.length > 0;

  return (
    <AppShell
      title="采集结果"
      description="查看本次采集的原始数据"
      breadcrumbs={[
        { label: "运行记录", href: "/runs" },
        { label: `结果 ${run_id.slice(0, 8)}…` },
      ]}
    >
      {/* Status bar */}
      <div className={`flex items-center gap-3 rounded-[var(--radius-3)] border p-4 ${
        isOk
          ? "border-[var(--state-success)] bg-[var(--success-soft)]"
          : recordsLoading
            ? "border-[var(--border-subtle)] bg-[var(--surface-primary)]"
            : "border-[var(--state-danger)] bg-[var(--danger-soft)]"
      }`}>
        {recordsLoading ? (
          <Loader2 size={20} className="animate-spin text-[var(--text-tertiary)]" />
        ) : isOk ? (
          <CheckCircle size={20} className="text-[var(--state-success)]" />
        ) : (
          <AlertCircle size={20} className="text-[var(--state-danger)]" />
        )}
        <div>
          <p className="text-sm font-bold text-[var(--text-primary)]">
            {recordsLoading ? "加载中..." : isOk ? "采集完成" : "暂无数据"}
          </p>
          {!recordsLoading && (
            <p className="mt-0.5 text-sm text-[var(--text-secondary)]">
              {isOk
                ? `写入 ${records.length} 条原始记录`
                : "本次采集未产生原始记录"}
            </p>
          )}
        </div>
      </div>

      {/* Records */}
      {records && records.length > 0 && (
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

              <div className="mt-3 grid gap-1.5">
                {Object.entries(rec.data ?? {})
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

      <div className="text-xs text-[var(--text-tertiary)]">
        运行 ID: <code className="font-mono">{run_id}</code>
      </div>
    </AppShell>
  );
}
