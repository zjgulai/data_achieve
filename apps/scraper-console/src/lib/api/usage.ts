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