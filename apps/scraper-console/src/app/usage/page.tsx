"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import {
  fetchUsageRuns,
  fetchUsageSummary,
  type CostSource,
  type UsageRunItem,
} from "@/lib/api/usage";
import { Loader2 } from "lucide-react";

function money(value: string): string {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return value;
  return `$${amount.toFixed(4)}`;
}

/** 成本来源的展示文案。unknown 必须显式写出来，不能显示成 $0。 */
function costCell(item: UsageRunItem): string {
  if (item.cost_source === "unknown") return "未知";
  return money(item.cost_usd);
}

const COST_SOURCE_LABEL: Record<CostSource, string> = {
  actual: "实测",
  estimated: "估算",
  unknown: "未知",
};

/** 时间只显示到分钟，账本要的是先后而不是精确时刻。 */
function shortTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function UsagePage() {
  const [days, setDays] = useState(30);
  const { data, isLoading, error } = useQuery({
    queryKey: ["usage", days],
    queryFn: () => fetchUsageSummary(days),
  });
  // 账本与汇总并行取。账本回答「每次值不值」，汇总回答「一共多少」。
  const ledger = useQuery({
    queryKey: ["usage-runs", days],
    queryFn: () => fetchUsageRuns(days, { limit: 200 }),
  });

  return (
    <AppShell
      title="用量与成本"
      description="按工作区汇总运行次数、记录数与估算成本"
      breadcrumbs={[{ label: "设置" }, { label: "用量与成本" }]}
    >
      <div className="mb-4 flex items-center gap-3">
        <label className="text-xs text-[var(--text-secondary)]" htmlFor="usage-days">
          时间范围
        </label>
        <select
          id="usage-days"
          value={days}
          onChange={(event) => setDays(Number(event.target.value))}
          className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-1.5 text-xs"
        >
          <option value={7}>最近 7 天</option>
          <option value={30}>最近 30 天</option>
          <option value={90}>最近 90 天</option>
        </select>
        {data && (
          <span className="text-xs text-[var(--text-tertiary)]">
            自 {data.since} · 成本为实际值或按价格簿估算
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 size={28} className="animate-spin text-[var(--text-tertiary)]" />
        </div>
      ) : error ? (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--danger-soft)] p-6 text-sm text-[var(--state-danger)]">
          加载失败：{(error as Error).message}
        </div>
      ) : !data ? (
        <p className="text-sm text-[var(--text-tertiary)]">没有用量数据</p>
      ) : (
        <div className="grid gap-6">
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="运行次数" value={String(data.totals.runs)} />
            <Stat label="记录数" value={String(data.totals.records)} />
            <Stat label="已知成本" value={money(data.totals.cost_usd)} />
          </div>

          <section
            className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5"
            data-testid="usage-run-ledger"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-sm font-semibold text-[var(--text-primary)]">
                逐次运行（最近 200 次）
              </h2>
              {ledger.data && ledger.data.totals.unknown_cost_runs > 0 && (
                <span
                  className="text-xs text-[var(--state-warning)]"
                  data-testid="usage-unknown-cost-notice"
                >
                  {ledger.data.totals.unknown_cost_runs} 次运行成本未知（价格簿无该端点），未计入总额
                </span>
              )}
            </div>
            {ledger.isLoading ? (
              <p className="mt-3 text-xs text-[var(--text-tertiary)]">加载中…</p>
            ) : ledger.error ? (
              <p className="mt-3 text-xs text-[var(--state-danger)]">
                账本加载失败：{(ledger.error as Error).message}
              </p>
            ) : !ledger.data || ledger.data.items.length === 0 ? (
              <p className="mt-3 text-xs text-[var(--text-tertiary)]">该时间范围内没有运行</p>
            ) : (
              <Table
                headers={["时间", "提供方", "端点", "状态", "记录", "耗时", "成本", "来源"]}
                rows={ledger.data.items.map((item) => [
                  shortTime(item.created_at),
                  item.provider ?? "—",
                  item.endpoint_type ?? "—",
                  item.status,
                  String(item.records_count),
                  item.duration_ms === null ? "—" : `${item.duration_ms} ms`,
                  costCell(item),
                  COST_SOURCE_LABEL[item.cost_source],
                ])}
              />
            )}
          </section>

          <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">按提供方</h2>
            {data.by_provider.length === 0 ? (
              <p className="mt-3 text-xs text-[var(--text-tertiary)]">暂无数据</p>
            ) : (
              <Table
                headers={["提供方", "运行", "记录", "成本"]}
                rows={data.by_provider.map((row) => [
                  row.provider,
                  String(row.runs),
                  String(row.records),
                  money(row.cost_usd),
                ])}
              />
            )}
          </section>

          <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">按端点（成本前 50）</h2>
            {data.by_endpoint.length === 0 ? (
              <p className="mt-3 text-xs text-[var(--text-tertiary)]">暂无数据</p>
            ) : (
              <Table
                headers={["端点", "运行", "记录", "成本"]}
                rows={data.by_endpoint.map((row) => [
                  row.endpoint_type,
                  String(row.runs),
                  String(row.records),
                  money(row.cost_usd),
                ])}
              />
            )}
          </section>

          <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">按天</h2>
            {data.by_day.length === 0 ? (
              <p className="mt-3 text-xs text-[var(--text-tertiary)]">暂无数据</p>
            ) : (
              <Table
                headers={["日期", "运行", "记录", "成本"]}
                rows={data.by_day.map((row) => [
                  row.date,
                  String(row.runs),
                  String(row.records),
                  money(row.cost_usd),
                ])}
              />
            )}
          </section>
        </div>
      )}
    </AppShell>
  );
}

function Stat({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
      <p className="text-xs text-[var(--text-tertiary)]">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-[var(--text-primary)]">{value}</p>
    </div>
  );
}

function Table({
  headers,
  rows,
}: {
  readonly headers: string[];
  readonly rows: string[][];
}) {
  return (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--border-subtle)] text-xs text-[var(--text-tertiary)]">
            {headers.map((header) => (
              <th key={header} className="py-2 pr-4 font-medium">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row[0]} className="border-b border-[var(--border-subtle)] last:border-0">
              {row.map((cell, index) => (
                <td
                  key={index}
                  className={`py-2 pr-4 ${index === row.length - 1 ? "tabular-nums" : ""} text-[var(--text-secondary)]`}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
