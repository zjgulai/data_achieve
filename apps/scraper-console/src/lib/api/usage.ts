import { apiFetch } from "./client";

export type UsageBucket = Readonly<{
  runs: number;
  records: number;
  cost_usd: string;
}>;

export type UsageSummary = Readonly<{
  since: string;
  days: number;
  project_id: string | null;
  totals: UsageBucket;
  by_provider: ReadonlyArray<UsageBucket & { provider: string }>;
  by_endpoint: ReadonlyArray<UsageBucket & { endpoint_type: string }>;
  by_day: ReadonlyArray<UsageBucket & { date: string }>;
}>;

export function fetchUsageSummary(days = 30, projectId?: string): Promise<UsageSummary> {
  const params = new URLSearchParams({ days: String(days) });
  if (projectId) params.set("project_id", projectId);
  return apiFetch<UsageSummary>(`/api/usage/summary?${params.toString()}`);
}

/** 成本来源。`unknown` 表示价格簿无此端点，不是「免费」。 */
export type CostSource = "actual" | "estimated" | "unknown";

/** 逐次运行账本的一行。 */
export type UsageRunItem = Readonly<{
  task_run_id: string;
  task_id: string;
  provider: string | null;
  endpoint_type: string | null;
  status: string;
  records_count: number;
  /** 已按 cost_source 解释过：unknown 时该值为 "0.000000"，不代表免费。 */
  cost_usd: string;
  cost_source: CostSource;
  unit: string | null;
  quantity: string | null;
  unit_price: string | null;
  duration_ms: number | null;
  created_at: string | null;
}>;

export type UsageRunLedger = Readonly<{
  since: string;
  days: number;
  limit: number;
  project_id: string | null;
  items: ReadonlyArray<UsageRunItem>;
  totals: Readonly<{
    runs: number;
    records: number;
    /** 只含已知金额。unknown 的金额不计入。 */
    cost_usd: string;
    unknown_cost_runs: number;
  }>;
}>;

/**
 * 读取逐次运行账本。回答「每次运行值不值」。
 *
 * 与 `fetchUsageSummary` 共用同一套成本口径：逐行已知金额之和
 * 等于 summary 的总量，所以两个页面不会互相矛盾。
 */
export function fetchUsageRuns(
  days = 7,
  options?: { limit?: number; projectId?: string; taskRunId?: string },
): Promise<UsageRunLedger> {
  const params = new URLSearchParams({
    days: String(days),
    limit: String(options?.limit ?? 200),
  });
  if (options?.projectId) params.set("project_id", options.projectId);
  if (options?.taskRunId) params.set("task_run_id", options.taskRunId);
  return apiFetch<UsageRunLedger>(`/api/usage/runs?${params.toString()}`);
}
