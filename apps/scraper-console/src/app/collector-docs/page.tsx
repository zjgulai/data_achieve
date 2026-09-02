"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BookOpen, Search, ChevronDown, ChevronRight, CheckCircle2,
  XCircle, Clock, AlertCircle, Loader2, RefreshCw, ExternalLink,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { fetchCollectorDocs } from "@/lib/api/collector-docs";
import type { CollectorDocsEndpoint, CollectorDocsEntry } from "@/lib/api/collector-docs";

// ──────────────────────────────────────────────────────────────
//  Method badge colors
// ──────────────────────────────────────────────────────────────
const METHOD_COLORS: Record<string, string> = {
  tikhub:     "bg-[#010101] text-white",
  apify:      "bg-[#00A37A] text-white",
  github_api: "bg-[#24292F] text-white",
  rss:        "bg-[#F26522] text-white",
  web_crawl:  "bg-[#4A5568] text-white",
  browser:    "bg-[#805AD5] text-white",
  jina:       "bg-[#0085FF] text-white",
  anysearch:  "bg-[#0084FF] text-white",
  sherlock:   "bg-[#E53E3E] text-white",
  maigret:    "bg-[#DD6B20] text-white",
  twscrape:   "bg-[#1DA1F2] text-white",
  spiderfoot: "bg-[#2D3748] text-white",
  firecrawl:  "bg-[#FF4F00] text-white",
  bestblogs:  "bg-[#38B2AC] text-white",
  blackbird:  "bg-[#553C9A] text-white",
};

function MethodBadge({ method }: { method: string }) {
  const cls = METHOD_COLORS[method] ?? "bg-[var(--surface-muted)] text-[var(--text-tertiary)]";
  return (
    <span className={`inline-block rounded-[var(--radius-1)] px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${cls}`}>
      {method}
    </span>
  );
}

// ──────────────────────────────────────────────────────────────
//  Status badge
// ──────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  if (status === "verified") return (
    <span className="inline-flex items-center gap-1 rounded-full border border-[var(--state-success)] bg-[var(--success-soft)] px-2 py-0.5 text-[11px] font-medium text-[var(--state-success)]">
      <CheckCircle2 size={10} />已验证
    </span>
  );
  if (status === "disabled") return (
    <span className="inline-flex items-center gap-1 rounded-full border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-tertiary)]">
      <XCircle size={10} />已停用
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-[var(--state-warning)] bg-[var(--warning-soft)] px-2 py-0.5 text-[11px] font-medium text-[var(--state-warning)]">
      <Clock size={10} />待验证
    </span>
  );
}

// ──────────────────────────────────────────────────────────────
//  Test result icon
// ──────────────────────────────────────────────────────────────
function TestResultIcon({ result }: { result: CollectorDocsEndpoint["test_result"] }) {
  if (!result) return (
    <span title="未测试" className="text-[var(--text-tertiary)]">
      <AlertCircle size={14} />
    </span>
  );
  if (result.last_run_status === "success") return (
    <span title={`成功 · ${result.last_records_count ?? 0} 条 · ${result.last_run_at ?? ""}`} className="text-[var(--state-success)]">
      <CheckCircle2 size={14} />
    </span>
  );
  return (
    <span title={result.last_error_message ?? "失败"} className="text-[var(--state-danger)]">
      <XCircle size={14} />
    </span>
  );
}

// ──────────────────────────────────────────────────────────────
//  Param chip
// ──────────────────────────────────────────────────────────────
function ParamChip({ name, required }: { name: string; required: boolean }) {
  return (
    <span className={`inline-block rounded-[var(--radius-1)] border px-1.5 py-0.5 font-mono text-[11px] ${
      required
        ? "border-[var(--action-primary)]/30 bg-[var(--accent-1-soft)] text-[var(--action-primary)]"
        : "border-[var(--border-subtle)] bg-[var(--surface-muted)] text-[var(--text-tertiary)]"
    }`}>
      {name}{required && <span className="ml-0.5 text-[var(--state-danger)]">*</span>}
    </span>
  );
}

// ──────────────────────────────────────────────────────────────
//  Endpoint row (expandable)
// ──────────────────────────────────────────────────────────────
function EndpointRow({ ep }: { ep: CollectorDocsEndpoint }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-b border-[var(--border-subtle)] last:border-0">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="flex w-full items-start gap-3 px-5 py-3.5 text-left hover:bg-[var(--surface-muted)] transition-colors"
      >
        <span className="mt-0.5 shrink-0 text-[var(--text-tertiary)]">
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>

        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm font-semibold text-[var(--text-primary)]">
              {ep.endpoint_type}
            </span>
            <span className="text-xs text-[var(--text-tertiary)]">·</span>
            <span className="text-sm text-[var(--text-secondary)]">{ep.label}</span>
          </span>
          <span className="text-xs text-[var(--text-tertiary)] line-clamp-1">{ep.description}</span>
        </span>

        <span className="ml-auto flex shrink-0 items-center gap-2">
          <MethodBadge method={ep.method} />
          <StatusBadge status={ep.status} />
          <TestResultIcon result={ep.test_result} />
        </span>
      </button>

      {open && (
        <div className="border-t border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-5 py-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {/* 描述 */}
            <div className="lg:col-span-3">
              <p className="text-sm text-[var(--text-secondary)]">{ep.description}</p>
            </div>

            {/* 必填参数 */}
            {ep.required_params.length > 0 && (
              <div>
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
                  必填参数
                </p>
                <div className="flex flex-wrap gap-1">
                  {ep.required_params.map(p => <ParamChip key={p} name={p} required />)}
                </div>
              </div>
            )}

            {/* 可选参数 */}
            {ep.optional_params.length > 0 && (
              <div>
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
                  可选参数
                </p>
                <div className="flex flex-wrap gap-1">
                  {ep.optional_params.map(p => <ParamChip key={p} name={p} required={false} />)}
                </div>
              </div>
            )}

            {/* 元信息 */}
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
                提供商 / 费用
              </p>
              <p className="text-sm text-[var(--text-secondary)]">{ep.provider}</p>
              {ep.cost_hint && (
                <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">{ep.cost_hint}</p>
              )}
            </div>

            {/* 数据类型 */}
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
                数据类型
              </p>
              <p className="text-sm text-[var(--text-secondary)]">{ep.content_type}</p>
            </div>

            {/* 最近测试结果 */}
            {ep.test_result && (
              <div>
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
                  最近测试
                </p>
                <div className="flex items-center gap-1.5 text-sm">
                  {ep.test_result.last_run_status === "success" ? (
                    <CheckCircle2 size={12} className="text-[var(--state-success)]" />
                  ) : (
                    <XCircle size={12} className="text-[var(--state-danger)]" />
                  )}
                  <span className={ep.test_result.last_run_status === "success"
                    ? "text-[var(--state-success)]" : "text-[var(--state-danger)]"}>
                    {ep.test_result.last_run_status === "success" ? "成功" : "失败"}
                  </span>
                  {ep.test_result.last_records_count != null && (
                    <span className="text-[var(--text-tertiary)]">
                      · {ep.test_result.last_records_count} 条记录
                    </span>
                  )}
                </div>
                {ep.test_result.last_error_message && (
                  <p className="mt-1 text-xs text-[var(--state-danger)] line-clamp-2">
                    {ep.test_result.last_error_message}
                  </p>
                )}
                {ep.test_result.last_run_at && (
                  <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                    {new Date(ep.test_result.last_run_at).toLocaleString("zh-CN")}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
//  Group section
// ──────────────────────────────────────────────────────────────
function GroupSection({ entry }: { entry: CollectorDocsEntry }) {
  const [open, setOpen] = useState(true);
  const verified = entry.endpoints.filter(e => e.status === "verified").length;
  const tested   = entry.endpoints.filter(e => e.test_result).length;

  return (
    <div className="overflow-hidden rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)]">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="flex w-full items-center gap-3 px-5 py-4 text-left hover:bg-[var(--surface-muted)] transition-colors"
      >
        <span className="text-[var(--text-tertiary)]">
          {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </span>
        <span className="flex-1 font-semibold text-[var(--text-primary)]">{entry.label}</span>
        <span className="flex items-center gap-3 text-xs text-[var(--text-tertiary)]">
          <span>{entry.endpoints.length} 个端点</span>
          <span className="text-[var(--state-success)]">{verified} 已验证</span>
          <span>{tested} 已测试</span>
        </span>
      </button>

      {open && (
        <div className="border-t border-[var(--border-subtle)]">
          {entry.endpoints.map(ep => (
            <EndpointRow key={ep.endpoint_type} ep={ep} />
          ))}
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
//  Main page
// ──────────────────────────────────────────────────────────────
export default function CollectorDocsPage() {
  const [search, setSearch] = useState("");
  const [filterMethod, setFilterMethod] = useState("");
  const [filterStatus, setFilterStatus] = useState("");

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["collector-docs"],
    queryFn: fetchCollectorDocs,
    staleTime: 60_000,
  });

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = search.toLowerCase();
    return data.groups
      .map(g => ({
        ...g,
        endpoints: g.endpoints.filter(ep => {
          if (filterStatus && ep.status !== filterStatus) return false;
          if (filterMethod && ep.method !== filterMethod) return false;
          if (!q) return true;
          return (
            ep.endpoint_type.toLowerCase().includes(q) ||
            ep.label.toLowerCase().includes(q) ||
            ep.description.toLowerCase().includes(q) ||
            ep.platform.toLowerCase().includes(q) ||
            ep.provider.toLowerCase().includes(q)
          );
        }),
      }))
      .filter(g => g.endpoints.length > 0);
  }, [data, search, filterMethod, filterStatus]);

  const methods = useMemo(() => {
    if (!data) return [];
    const set = new Set<string>();
    data.groups.forEach(g => g.endpoints.forEach(e => set.add(e.method)));
    return Array.from(set).sort();
  }, [data]);

  const totalShown = filtered.reduce((s, g) => s + g.endpoints.length, 0);

  return (
    <AppShell
      title="采集文档"
      description="所有采集端点的参数说明、数据类型、费用估算和最近测试结果"
    >
      {/* ── Stats bar ── */}
      {data && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: "总端点", value: data.total_endpoints, color: "text-[var(--text-primary)]" },
            { label: "已测试", value: data.tested_endpoints, color: "text-[var(--action-primary)]" },
            { label: "测试通过", value: data.success_endpoints, color: "text-[var(--state-success)]" },
            { label: "失败/未测", value: data.total_endpoints - data.success_endpoints, color: "text-[var(--state-danger)]" },
          ].map(s => (
            <div key={s.label} className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-4 py-3">
              <p className="text-xs text-[var(--text-tertiary)]">{s.label}</p>
              <p className={`mt-0.5 text-2xl font-bold tabular-nums ${s.color}`}>{s.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* ── Toolbar ── */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[200px] flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="搜索端点、平台、提供商..."
            className="h-9 w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] pl-8 pr-3 text-sm text-[var(--text-primary)] placeholder-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--focus-1)]"
          />
        </div>

        <select
          value={filterMethod}
          onChange={e => setFilterMethod(e.target.value)}
          className="h-9 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 text-sm text-[var(--text-secondary)] focus:outline-none focus:ring-2 focus:ring-[var(--focus-1)]"
        >
          <option value="">全部方式</option>
          {methods.map(m => <option key={m} value={m}>{m}</option>)}
        </select>

        <select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          className="h-9 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 text-sm text-[var(--text-secondary)] focus:outline-none focus:ring-2 focus:ring-[var(--focus-1)]"
        >
          <option value="">全部状态</option>
          <option value="verified">已验证</option>
          <option value="pending">待验证</option>
          <option value="disabled">已停用</option>
        </select>

        <button
          type="button"
          onClick={() => refetch()}
          className="flex h-9 items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
        >
          <RefreshCw size={13} />
          刷新
        </button>

        {(search || filterMethod || filterStatus) && (
          <span className="text-xs text-[var(--text-tertiary)]">
            显示 {totalShown} 个端点
          </span>
        )}
      </div>

      {/* ── Content ── */}
      {isLoading ? (
        <div className="flex justify-center py-20">
          <Loader2 size={24} className="animate-spin text-[var(--text-tertiary)]" />
        </div>
      ) : error ? (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--danger-soft)] p-6 text-sm text-[var(--state-danger)]">
          加载失败：{(error as Error).message}
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-[var(--radius-3)] border-2 border-dashed border-[var(--border-subtle)] py-16 text-center">
          <BookOpen size={36} className="mx-auto text-[var(--text-tertiary)]" />
          <p className="mt-3 text-base font-semibold text-[var(--text-primary)]">
            {search ? "未找到匹配端点" : "暂无数据"}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {filtered.map(entry => (
            <GroupSection key={entry.collector_type} entry={entry} />
          ))}
        </div>
      )}
    </AppShell>
  );
}
