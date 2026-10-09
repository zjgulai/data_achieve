"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { StatTile } from "@/components/ui/stat-tile";
import { fetchDashboardOverview } from "@/lib/api/dashboard";

function formatNumber(value: number): string {
  return value.toLocaleString("zh-CN");
}

function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("zh-CN", { hour12: false });
}

export default function DashboardPage() {
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["dashboard-overview"],
    queryFn: fetchDashboardOverview,
  });

  return (
    <AppShell
      title="工作台"
      description="采集控制台总览"
      brief="采集健康度、失败任务与最新情报"
    >
      <div className="grid gap-6">
        <div className="flex items-center justify-between">
          <p className="text-xs text-[var(--text-tertiary)]">
            {data ? `数据生成于 ${formatTimestamp(data.freshness.generated_at)}` : " "}
          </p>
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
        ) : error || !data ? (
          <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--danger-soft)] p-6 text-sm text-[var(--state-danger)]">
            概览加载失败：{error instanceof Error ? error.message : "未知错误"}
          </div>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatTile
                label="任务成功率"
                value={formatPercent(data.task_success_rate)}
                hint={`近 ${formatNumber(data.recent_runs)} 次运行`}
              />
              <StatTile
                label="字段完整度"
                value={formatPercent(data.field_completeness)}
                hint={`${formatNumber(data.source_count)} 个数据源`}
              />
              <StatTile
                label="失败任务"
                value={formatNumber(data.failed_tasks)}
                hint={`共 ${formatNumber(data.task_health.total_tasks)} 个任务`}
              />
              <StatTile
                label="活跃告警"
                value={formatNumber(data.active_alerts)}
                hint={`最新采集 ${formatTimestamp(data.freshness.latest_collection_at)}`}
              />
            </div>

            <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6">
              <h2 className="text-base font-bold text-[var(--text-primary)]">最近失败运行</h2>
              {data.task_health.recent_failures.length === 0 ? (
                <p className="mt-3 text-sm text-[var(--text-tertiary)]">
                  暂无失败运行
                </p>
              ) : (
                <ul className="mt-4 grid gap-2">
                  {data.task_health.recent_failures.map(failure => (
                    <li
                      key={`${failure.task_id}-${failure.started_at ?? ""}`}
                      className="flex items-start gap-3 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-2"
                    >
                      <AlertTriangle
                        size={14}
                        className="mt-0.5 shrink-0 text-[var(--state-warning)]"
                      />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-[var(--text-primary)]">
                          {failure.task_name}
                        </p>
                        <p className="mt-0.5 truncate text-xs text-[var(--text-tertiary)]">
                          {failure.error_message ?? failure.status} ·{" "}
                          {formatTimestamp(failure.started_at)}
                        </p>
                      </div>
                      <Link
                        href={`/tasks`}
                        className="shrink-0 text-xs text-[var(--action-primary)] underline"
                      >
                        查看任务
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <div className="grid gap-6 lg:grid-cols-2">
              <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6">
                <h2 className="text-base font-bold text-[var(--text-primary)]">情报类型分布</h2>
                {data.type_breakdown.length === 0 ? (
                  <p className="mt-3 text-sm text-[var(--text-tertiary)]">暂无情报</p>
                ) : (
                  <ul className="mt-4 grid gap-3">
                    {data.type_breakdown.map(item => (
                      <li key={item.type}>
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-medium text-[var(--text-secondary)]">
                            {item.type}
                          </span>
                          <span className="tabular-nums text-[var(--text-tertiary)]">
                            {formatNumber(item.count)} · {formatPercent(item.percent)}
                          </span>
                        </div>
                        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-[var(--surface-muted)]">
                          <div
                            className="h-full rounded-full bg-[var(--action-primary)]"
                            style={{ width: `${Math.min(100, Math.max(0, item.percent))}%` }}
                          />
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6">
                <h2 className="text-base font-bold text-[var(--text-primary)]">业务域覆盖</h2>
                {data.domain_breakdown.length === 0 ? (
                  <p className="mt-3 text-sm text-[var(--text-tertiary)]">暂无数据</p>
                ) : (
                  <table className="mt-4 w-full text-sm">
                    <thead>
                      <tr className="text-xs text-[var(--text-tertiary)]">
                        <th className="pb-2 text-left font-medium">业务域</th>
                        <th className="pb-2 text-right font-medium">情报</th>
                        <th className="pb-2 text-right font-medium">信号</th>
                        <th className="pb-2 text-right font-medium">项目</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.domain_breakdown.map(item => (
                        <tr
                          key={item.domain}
                          className="border-t border-[var(--border-subtle)]"
                        >
                          <td className="py-2 text-[var(--text-secondary)]">{item.domain}</td>
                          <td className="py-2 text-right tabular-nums text-[var(--text-secondary)]">
                            {formatNumber(item.intelligence_count)}
                          </td>
                          <td className="py-2 text-right tabular-nums text-[var(--text-secondary)]">
                            {formatNumber(item.signal_count)}
                          </td>
                          <td className="py-2 text-right tabular-nums text-[var(--text-secondary)]">
                            {formatNumber(item.project_count)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </section>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
