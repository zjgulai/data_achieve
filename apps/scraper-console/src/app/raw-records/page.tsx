"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ChevronLeft, ChevronRight, Loader2, RefreshCw, Search } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { fetchRawRecords, type RawRecord } from "@/lib/api/runs";

const PAGE_SIZE = 25;

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("zh-CN", { hour12: false });
}

function summarize(content: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [key, value] of Object.entries(content)) {
    if (key === "raw" || key === "html_content") continue;
    if (value === null || value === undefined || value === "") continue;
    const text = typeof value === "object" ? JSON.stringify(value) : String(value);
    parts.push(`${key}: ${text.slice(0, 60)}`);
    if (parts.length >= 3) break;
  }
  return parts.join(" · ") || "—";
}

export default function RawRecordsPage() {
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["raw-records", offset],
    queryFn: () => fetchRawRecords({ limit: PAGE_SIZE, offset }),
  });

  const records = useMemo<RawRecord[]>(() => data ?? [], [data]);

  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return records;
    return records.filter(record => {
      const hay = `${record.record_type} ${record.source_url ?? ""}`.toLowerCase();
      return hay.includes(query);
    });
  }, [records, search]);

  return (
    <AppShell
      title="原始数据"
      description="浏览所有原始采集记录"
      brief={`每页 ${PAGE_SIZE} 条，按采集时间倒序`}
    >
      <div className="grid gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[220px]">
            <Search
              size={14}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]"
            />
            <input
              value={search}
              onChange={event => setSearch(event.target.value)}
              placeholder="在本页内搜索记录类型或来源 URL"
              aria-label="搜索原始记录"
              className="h-9 w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] pl-9 pr-3 text-xs text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
            />
          </div>
          <button
            type="button"
            onClick={() => refetch()}
            className="flex items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-2 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
          >
            {isFetching ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <RefreshCw size={12} />
            )}
            刷新
          </button>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-16">
            <Loader2 size={24} className="animate-spin text-[var(--text-tertiary)]" />
          </div>
        ) : error ? (
          <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--danger-soft)] p-6 text-sm text-[var(--state-danger)]">
            加载失败：{error instanceof Error ? error.message : "未知错误"}
          </div>
        ) : visible.length === 0 ? (
          <div className="rounded-[var(--radius-3)] border border-dashed border-[var(--border-subtle)] bg-[var(--surface-primary)] p-10 text-center text-sm text-[var(--text-tertiary)]">
            {records.length === 0 ? "暂无原始记录" : "本页没有匹配的记录"}
          </div>
        ) : (
          <div className="grid gap-2">
            {visible.map(record => (
              <div
                key={record.id}
                className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-4 py-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="rounded-[var(--radius-pill)] bg-[var(--surface-muted)] px-2 py-0.5 text-xs font-medium text-[var(--text-secondary)]">
                      {record.record_type}
                    </span>
                    {record.task_run_id ? (
                      <Link
                        href={`/collect/${record.task_run_id}`}
                        className="text-xs text-[var(--action-primary)] underline"
                      >
                        查看该次运行
                      </Link>
                    ) : null}
                  </div>
                  <span className="text-xs text-[var(--text-tertiary)]">
                    {formatTimestamp(record.collected_at)}
                  </span>
                </div>
                {record.source_url ? (
                  <p className="mt-1.5 truncate text-xs text-[var(--text-tertiary)]">
                    {record.source_url}
                  </p>
                ) : null}
                <p className="mt-1.5 truncate font-mono text-xs text-[var(--text-secondary)]">
                  {summarize(record.content)}
                </p>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between">
          <p className="text-xs text-[var(--text-tertiary)]">
            第 {offset + 1}–{offset + records.length} 条
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={offset === 0}
              onClick={() => setOffset(previous => Math.max(0, previous - PAGE_SIZE))}
              className="flex items-center gap-1 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] disabled:opacity-40"
            >
              <ChevronLeft size={12} />
              上一页
            </button>
            <button
              type="button"
              disabled={records.length < PAGE_SIZE}
              onClick={() => setOffset(previous => previous + PAGE_SIZE)}
              className="flex items-center gap-1 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] disabled:opacity-40"
            >
              下一页
              <ChevronRight size={12} />
            </button>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
