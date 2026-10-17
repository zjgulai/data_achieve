"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { fetchProviderStatus } from "@/lib/api/platform-packages";
import type { EndpointAvailability } from "@/lib/api/platform-packages";
import { BlockerList } from "@/components/ui/reachability-badge";
import { resolveReachability } from "@/lib/reachability";
import { Loader2, RefreshCw } from "lucide-react";

/** 服务端的可用性枚举。顺序即展示顺序。 */
type Availability = EndpointAvailability["availability"];

const AVAILABILITY_ORDER: readonly Availability[] = [
  "verified",
  "degraded",
  "empty",
  "untested",
  "config-gated",
  "disabled",
];

/** 每个可用性的界面文案、颜色与释义。
 *
 * 本页是状态页，必须原样呈现服务端的六态，不再派生。
 * 早先版本把 degraded 与 empty 压成「可用」，与事实不符。
 */
const AVAILABILITY_META: Record<
  Availability,
  { label: string; color: string; hint: string }
> = {
  verified: {
    label: "已验证",
    color: "var(--state-success)",
    hint: "最近一次实测成功，且有记录。",
  },
  degraded: {
    label: "实测未通过",
    color: "var(--state-danger)",
    hint: "最近一次实测失败，或部分成功。",
  },
  empty: {
    label: "成功但无记录",
    color: "var(--state-warning)",
    hint: "最近一次实测成功，但返回 0 条。",
  },
  untested: {
    label: "未实测",
    color: "var(--text-tertiary)",
    hint: "没有实测记录。",
  },
  "config-gated": {
    label: "缺配置或受策略限制",
    color: "var(--state-warning)",
    hint: "缺必需配置，或被外访策略阻断。",
  },
  disabled: {
    label: "已停用",
    color: "var(--text-tertiary)",
    hint: "目录标记为 disabled。",
  },
};

/** 判定输入。结构化字段优先，策略原因兜底。
 *
 * 已停用的端点不再传策略原因：两个原因同时显示会互相矛盾。
 */
function toInput(row: EndpointAvailability) {
  const disabled = row.availability === "disabled";
  return {
    catalogStatus: disabled ? "disabled" : null,
    policyBlockReason: disabled ? null : (row.policy_block_reason ?? null),
    missingConfiguration: row.missing_configuration,
    availability: row.availability,
  };
}

function formatTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("zh-CN", { hour12: false });
}

export default function ProvidersPage() {
  const [filter, setFilter] = useState<Availability | "all">("all");

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["provider-status"],
    queryFn: fetchProviderStatus,
  });

  const rows = useMemo(() => {
    return (data?.endpoints ?? []).map(row => ({
      row,
      input: toInput(row),
      reachability: resolveReachability(toInput(row)),
    }));
  }, [data]);

  // 按服务端的可用性直接计数。不派生。
  const counts = useMemo(() => {
    const tally = new Map<Availability, number>();
    for (const { row } of rows) {
      tally.set(row.availability, (tally.get(row.availability) ?? 0) + 1);
    }
    return tally;
  }, [rows]);

  const visible = filter === "all"
    ? rows
    : rows.filter(item => item.row.availability === filter);

  return (
    <AppShell
      title="提供方状态"
      description="按端点显示服务端给出的可用性与阻断原因"
      breadcrumbs={[{ label: "设置" }, { label: "提供方状态" }]}
    >
      {isLoading ? (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-8 text-center">
          <Loader2 size={24} className="mx-auto animate-spin text-[var(--text-tertiary)]" />
          <p className="mt-2 text-sm text-[var(--text-tertiary)]">加载中...</p>
        </div>
      ) : error ? (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--danger-soft)] p-8 text-center">
          <p className="text-sm text-[var(--state-danger)]">
            加载失败：{(error as Error).message}
          </p>
          <button
            type="button"
            onClick={() => refetch()}
            className="mt-4 inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
          >
            <RefreshCw size={14} />
            重试
          </button>
        </div>
      ) : (
        <div className="grid gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-1.5">
              <FilterChip
                active={filter === "all"}
                onClick={() => setFilter("all")}
                label="全部"
                count={rows.length}
                color="var(--text-secondary)"
              />
              {AVAILABILITY_ORDER.map(state => {
                const count = counts.get(state) ?? 0;
                // 计数归零时隐藏。但当前选中的那一项必须保留，
                // 否则筛选状态还在、芯片却消失，页面无法退出该筛选。
                if (count === 0 && filter !== state) return null;
                const meta = AVAILABILITY_META[state];
                return (
                  <FilterChip
                    key={state}
                    active={filter === state}
                    onClick={() => setFilter(state)}
                    label={meta.label}
                    count={count}
                    color={meta.color}
                  />
                );
              })}
            </div>
            <button
              type="button"
              onClick={() => refetch()}
              disabled={isFetching}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] disabled:opacity-40"
            >
              <RefreshCw size={14} className={isFetching ? "animate-spin" : undefined} />
              刷新
            </button>
          </div>

          <p className="text-xs text-[var(--text-tertiary)]">
            可用性来自服务端最近一次实测记录与当前进程配置。
            目录摘要 {data?.catalog_digest?.slice(0, 12) ?? "—"}。
          </p>

          {visible.length === 0 ? (
            <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-8 text-center">
              <p className="text-sm text-[var(--text-tertiary)]">该筛选下没有端点</p>
            </div>
          ) : (
            <ul className="grid gap-2">
              {visible.map(({ row, reachability }) => {
                const meta = AVAILABILITY_META[row.availability];
                return (
                  <li
                    key={row.endpoint_type}
                    className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate font-mono text-sm font-medium text-[var(--text-primary)]">
                          {row.endpoint_type}
                        </p>
                        <p className="mt-1 text-xs text-[var(--text-tertiary)]">
                          最近实测 {formatTime(row.last_test_at)}
                          {" · "}
                          {row.last_records_count === null
                            ? "无记录数"
                            : `${row.last_records_count} 条`}
                          {row.last_test_status ? ` · ${row.last_test_status}` : ""}
                        </p>
                      </div>
                      <span
                        className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium"
                        title={meta.hint}
                      >
                        <span
                          aria-hidden
                          className="inline-block h-1.5 w-1.5 rounded-full"
                          style={{ backgroundColor: meta.color }}
                        />
                        {meta.label}
                      </span>
                    </div>

                    {row.last_error_message && (
                      <p className="mt-2 break-words text-xs text-[var(--state-danger)]">
                        {row.last_error_message}
                      </p>
                    )}

                    {reachability.blockers.length > 0 && (
                      <div className="mt-3">
                        <BlockerList reachability={reachability} />
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </AppShell>
  );
}

function FilterChip({
  active,
  onClick,
  label,
  count,
  color,
}: {
  readonly active: boolean;
  readonly onClick: () => void;
  readonly label: string;
  readonly count: number;
  readonly color: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={[
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors",
        active
          ? "border-[var(--text-primary)] bg-[var(--surface-muted)] text-[var(--text-primary)]"
          : "border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]",
      ].join(" ")}
    >
      <span
        aria-hidden
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: color }}
      />
      {label}
      <span className="tabular-nums text-[var(--text-tertiary)]">{count}</span>
    </button>
  );
}
