import { apiFetch } from "@/lib/api/client";

/**
 * Console view of `GET /api/dashboard/overview`.
 *
 * The endpoint predates the console: it was built for the insight app, which
 * is no longer deployed. The shape here mirrors the fields the console uses.
 */
export type DashboardTypeBreakdown = {
  type: string;
  count: number;
  percent: number;
};

export type DashboardDomainBreakdown = {
  domain: string;
  intelligence_count: number;
  signal_count: number;
  project_count: number;
};

export type DashboardTopIntelligence = {
  id: string;
  title: string;
  summary: string;
  domain: string;
  type: string;
  evidence_count: number;
  final_score: number;
  status: string;
  created_at: string;
  updated_at: string;
};

export type DashboardRecentFailure = {
  task_id: string;
  task_name: string;
  source_name: string | null;
  project_name: string | null;
  status: string;
  records_count: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
};

export type DashboardOverview = {
  intelligence_count: number;
  task_success_rate: number;
  field_completeness: number;
  active_alerts: number;
  failed_tasks: number;
  recent_runs: number;
  source_count: number;
  type_breakdown: DashboardTypeBreakdown[];
  domain_breakdown: DashboardDomainBreakdown[];
  top_intelligence: DashboardTopIntelligence[];
  task_health: {
    total_tasks: number;
    enabled_tasks: number;
    failed_tasks: number;
    recent_runs: number;
    recent_failures: DashboardRecentFailure[];
  };
  freshness: {
    generated_at: string;
    latest_collection_at: string | null;
    stale_enabled_tasks: number;
    stale_tasks: unknown[];
  };
};

export async function fetchDashboardOverview(): Promise<DashboardOverview> {
  return apiFetch<DashboardOverview>("/api/dashboard/overview");
}
