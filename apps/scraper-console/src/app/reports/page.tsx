"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { FileText, Loader2, RefreshCw } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { fetchReports } from "@/lib/api/reports";
import {
  LIST_CONTRACT_PENDING_LABEL,
  formatPeriod,
  formatTimestamp,
  resolveReportListState,
} from "@/lib/reports-view";

/*
 * 列表接口不返回合同字段。结论句、最低等级与签收三列必须显示
 * 「待合同接口」，不得写成「未生成合同」。后者会让用户以为数据没生成。
 */
const NO_CONTRACT = LIST_CONTRACT_PENDING_LABEL;

/** 报告状态的中文标签。 */
const REPORT_STATUS_LABELS: Record<string, string> = {
  generated: "已生成",
  sent: "已发送",
  draft: "草稿",
};

/** 加载骨架。固定 8 行，行高 72px。 */
function TableSkeleton() {
  return (
    <div
      className="overflow-hidden rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)]"
      aria-label="报告列表加载中"
    >
      <div className="h-11 border-b border-[var(--border-subtle)] bg-[var(--surface-muted)]" />
      {Array.from({ length: 8 }, (_, index) => (
        <div
          key={index}
          className="flex h-[72px] items-center gap-4 border-b border-[var(--border-subtle)] px-5 last:border-b-0"
        >
          <div className="h-4 w-1/4 animate-pulse rounded bg-[var(--surface-muted)]" />
          <div className="h-4 w-1/4 animate-pulse rounded bg-[var(--surface-muted)]" />
          <div className="h-4 w-16 animate-pulse rounded bg-[var(--surface-muted)]" />
          <div className="h-4 w-24 animate-pulse rounded bg-[var(--surface-muted)]" />
          <div className="h-4 w-16 animate-pulse rounded bg-[var(--surface-muted)]" />
        </div>
      ))}
    </div>
  );
}

/** 列表的三种非就绪状态。三种文案不同。 */
function StateBlock({
  title,
  hint,
  action,
}: {
  title: string;
  hint: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-6 py-16 text-center">
      <FileText size={28} className="text-[var(--text-tertiary)]" aria-hidden="true" />
      <p className="mt-3 text-sm font-semibold text-[var(--text-primary)]">{title}</p>
      <p className="mt-1 max-w-md text-sm leading-relaxed text-[var(--text-tertiary)]">
        {hint}
      </p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export default function ReportsPage() {
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["reports"],
    queryFn: () => fetchReports(),
  });

  const state = resolveReportListState({
    isLoading,
    error,
    count: data?.length,
  });

  return (
    <AppShell
      title="报告中心"
      description="每份报告首屏显示最低证据等级、门禁状态与三个哈希。"
      breadcrumbs={[{ label: "报告中心" }]}
    >
      <div className="flex items-center justify-between">
        <p className="text-sm text-[var(--text-tertiary)]">
          {state === "ready" ? `${data?.length ?? 0} 份报告` : "报告列表"}
        </p>
        <button
          type="button"
          onClick={() => void refetch()}
          disabled={isFetching}
          className="flex items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] disabled:opacity-50"
        >
          {isFetching ? (
            <Loader2 size={14} className="animate-spin" aria-hidden="true" />
          ) : (
            <RefreshCw size={14} aria-hidden="true" />
          )}
          刷新
        </button>
      </div>

      {state === "loading" ? <TableSkeleton /> : null}

      {state === "forbidden" ? (
        <StateBlock
          title="没有查看报告的权限"
          hint="当前账号不能读取这个工作区的报告。请登录有权限的账号。"
        />
      ) : null}

      {state === "error" ? (
        <StateBlock
          title="报告列表加载失败"
          hint={error instanceof Error ? error.message : "请检查 API 连接后重试。"}
          action={
            <button
              type="button"
              onClick={() => void refetch()}
              className="rounded-[var(--radius-2)] bg-[var(--action-primary)] px-4 py-2 text-sm font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)]"
            >
              重试
            </button>
          }
        />
      ) : null}

      {state === "empty" ? (
        <StateBlock
          title="还没有报告"
          hint="运行一次任务并生成报告后，报告会出现在这里。"
        />
      ) : null}

      {state === "ready" ? (
        <div className="overflow-x-auto rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)]">
          <table className="w-full min-w-[960px] border-collapse text-left">
            <caption className="sr-only">报告列表</caption>
            <thead>
              <tr className="border-b border-[var(--border-subtle)] bg-[var(--surface-muted)] text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
                <th scope="col" className="w-[28%] px-5 py-3">标题</th>
                <th scope="col" className="w-[26%] px-5 py-3">结论句</th>
                <th scope="col" className="w-[12%] px-5 py-3">最低证据等级</th>
                <th scope="col" className="w-[14%] px-5 py-3">生成时间</th>
                <th scope="col" className="w-[10%] px-5 py-3">签收</th>
                <th scope="col" className="w-[10%] px-5 py-3">操作</th>
              </tr>
            </thead>
            <tbody>
              {data?.map(report => (
                <tr
                  key={report.id}
                  className="h-[72px] border-b border-[var(--border-subtle)] text-sm last:border-b-0 hover:bg-[var(--surface-muted)]"
                >
                  <td className="px-5 py-3">
                    <Link
                      href={`/reports/${report.id}`}
                      className="line-clamp-2 font-semibold text-[var(--text-primary)] hover:text-[var(--action-primary)]"
                    >
                      {report.title}
                    </Link>
                    <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                      {REPORT_STATUS_LABELS[report.status] ?? report.status}
                      <span className="mx-1.5" aria-hidden="true">·</span>
                      {formatPeriod(report.period_start, report.period_end)}
                    </p>
                  </td>
                  <td className="px-5 py-3">
                    <span className="text-[var(--text-tertiary)]">{NO_CONTRACT}</span>
                  </td>
                  <td className="px-5 py-3">
                    <span className="text-[var(--text-tertiary)]">{NO_CONTRACT}</span>
                  </td>
                  <td className="px-5 py-3 tabular-nums text-[var(--text-secondary)]">
                    {formatTimestamp(report.created_at)}
                  </td>
                  <td className="px-5 py-3">
                    <span className="text-[var(--text-tertiary)]">{NO_CONTRACT}</span>
                  </td>
                  <td className="px-5 py-3">
                    <Link
                      href={`/reports/${report.id}`}
                      className="font-medium text-[var(--action-primary)] hover:underline"
                    >
                      打开
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </AppShell>
  );
}
