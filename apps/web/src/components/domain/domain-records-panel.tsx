"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { Route } from "next";
import { AlertCircle, Database, Loader2 } from "lucide-react";

import { listRawRecords } from "@/lib/api/raw-records";
import type { RawRecord } from "@/types/raw-record";

/**
 * 业务域页的「最近采集」面板。
 *
 * 域仪表盘此前只有聚合计数，看不到该域实际采到了什么，
 * 「选业务域 → 看到真实采集的数据」这条链在这环是断的。
 *
 * 数据来自 `GET /api/raw-records?domain=<domain>`：记录经
 * `project_id -> projects.domain` 关联到业务域，由后端过滤。
 * 不按顶部选中的项目过滤——域是跨项目的分类，叠加项目会把结果
 * 收窄到空集，这正是审计发现的「选到别域项目时计数清零」问题。
 */

const PREVIEW_LIMIT = 5;

/** 一条记录的单行摘要。内容可能是对象或数组，统一压成短文本。 */
function summarize(record: RawRecord): string {
  const content = record.content;
  if (Array.isArray(content)) {
    return `[${content.length} 项]`;
  }
  if (!content || typeof content !== "object") {
    return "—";
  }
  const preferred = ["title", "name", "text", "query", "url"];
  for (const key of preferred) {
    const value = content[key];
    if (typeof value === "string" && value.trim()) {
      const single = value.replace(/\s+/g, " ").trim();
      return single.length > 80 ? `${single.slice(0, 80)}…` : single;
    }
  }
  const keys = Object.keys(content);
  return keys.length > 0 ? `{${keys.slice(0, 4).join(", ")}}` : "—";
}

function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function DomainRecordsPanel({ domain }: { domain: string }) {
  const [records, setRecords] = useState<RawRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    listRawRecords({ domain, limit: PREVIEW_LIMIT })
      .then((items) => {
        if (mounted) {
          setRecords(items);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "采集记录暂不可用");
        }
      })
      .finally(() => {
        if (mounted) {
          setLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, [domain]);

  const listHref = `/raw-records?domain=${encodeURIComponent(domain)}` as Route;

  return (
    <section
      className="rounded-2xl border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-4"
      data-testid="domain-records-panel"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex items-center gap-2">
          <Database size={16} className="text-[var(--text-tertiary)]" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">最近采集</h2>
        </div>
        <Link className="text-xs font-semibold text-[var(--action-primary)]" href={listHref}>
          查看全部原始数据
        </Link>
      </div>

      {loading ? (
        <div className="mt-3 flex items-center gap-2 text-xs text-[var(--text-tertiary)]">
          <Loader2 size={14} className="animate-spin" aria-hidden="true" />
          加载中…
        </div>
      ) : error ? (
        <p className="mt-3 flex items-center gap-1.5 text-xs text-[var(--state-danger)]">
          <AlertCircle size={14} aria-hidden="true" />
          {error}
        </p>
      ) : records.length === 0 ? (
        <p className="mt-3 text-xs text-[var(--text-tertiary)]">
          该域还没有采集到的原始记录。先在「采集任务」里跑一次，或在 /tools 里执行一次快速采集。
        </p>
      ) : (
        <ul className="mt-3 grid gap-1.5" data-testid="domain-records-list">
          {records.map((record) => (
            <li key={record.id}>
              <Link
                className="grid gap-0.5 rounded-[var(--radius-1)] px-2 py-1.5 hover:bg-[var(--surface-muted)]"
                href={`/raw-records?record=${encodeURIComponent(record.id)}` as Route}
              >
                <span className="truncate text-xs font-medium text-[var(--text-primary)]">
                  {summarize(record)}
                </span>
                <span className="flex flex-wrap gap-x-3 text-[11px] text-[var(--text-tertiary)]">
                  <span>{record.recordType}</span>
                  {record.sourceUrl ? (
                    <span className="truncate">{record.sourceUrl}</span>
                  ) : null}
                  <span className="tabular-nums">{formatTime(record.collectedAt)}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
