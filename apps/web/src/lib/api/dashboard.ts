import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import { getMockDashboard } from "@/lib/api/mock";
import type {
  DashboardFilters,
  DashboardFreshness,
  DashboardSummary,
  DomainBreakdownItem,
  IntelligenceSummaryItem,
  RecentFailureItem,
  DashboardStaleTaskItem,
  TypeBreakdownItem,
} from "@/types/dashboard";

type DashboardResponse = {
  intelligence_count: number;
  task_success_rate: number;
  field_completeness: number;
  active_alerts: number;
  failed_tasks: number;
  recent_runs: number;
  source_count: number;
  type_breakdown: TypeBreakdownResponse[];
  domain_breakdown: DomainBreakdownResponse[];
  top_intelligence: TopIntelligenceResponse[];
  task_health: TaskHealthResponse;
  freshness: DashboardFreshnessResponse;
};

type TypeBreakdownResponse = {
  type: string;
  count: number;
  percent: number;
};

type DomainBreakdownResponse = {
  domain: string;
  intelligence_count: number;
  signal_count: number;
  project_count: number;
};

type TopIntelligenceResponse = {
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

type TaskHealthResponse = {
  total_tasks: number;
  enabled_tasks: number;
  failed_tasks: number;
  recent_runs: number;
  recent_failures: RecentFailureResponse[];
};

type RecentFailureResponse = {
  task_id: string;
  task_name: string;
  status: string;
  error_message: string | null;
  created_at: string;
};

type DashboardFreshnessResponse = {
  generated_at: string;
  latest_collection_at: string | null;
  stale_enabled_tasks: number;
  stale_tasks: DashboardStaleTaskResponse[];
};

type DashboardStaleTaskResponse = {
  task_id: string;
  task_name: string;
  collector_type: string;
  status: string;
  last_run_at: string | null;
  freshness_target_hours: number;
  stale_hours: number | null;
};

export async function getDashboardOverview(
  filters: DashboardFilters = {},
): Promise<DashboardSummary> {
  if (mockApiEnabled) {
    return getMockDashboard(filters.domain, filters.projectId);
  }
  const query = new URLSearchParams();
  if (filters.projectId) {
    query.set("project_id", filters.projectId);
  }
  if (filters.domain) {
    query.set("domain", filters.domain);
  }
  if (filters.from) {
    query.set("from", filters.from);
  }
  if (filters.to) {
    query.set("to", filters.to);
  }
  if (filters.limit) {
    query.set("limit", String(filters.limit));
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  const response = await apiFetch<DashboardResponse>(`/api/dashboard/overview${suffix}`);
  return mapDashboard(response);
}

function mapDashboard(response: DashboardResponse): DashboardSummary {
  return {
    intelligenceCount: response.intelligence_count,
    taskSuccessRate: response.task_success_rate,
    fieldCompleteness: response.field_completeness,
    activeAlerts: response.active_alerts,
    failedTasks: response.failed_tasks,
    recentRuns: response.recent_runs,
    sourceCount: response.source_count,
    typeBreakdown: response.type_breakdown.map(mapTypeBreakdown),
    domainBreakdown: response.domain_breakdown.map(mapDomainBreakdown),
    topIntelligence: response.top_intelligence.map(mapTopIntelligence),
    taskHealth: {
      totalTasks: response.task_health.total_tasks,
      enabledTasks: response.task_health.enabled_tasks,
      failedTasks: response.task_health.failed_tasks,
      recentRuns: response.task_health.recent_runs,
      recentFailures: response.task_health.recent_failures.map(mapRecentFailure),
    },
    freshness: mapFreshness(response.freshness),
  };
}

function mapTypeBreakdown(response: TypeBreakdownResponse): TypeBreakdownItem {
  return {
    type: response.type,
    count: response.count,
    percent: response.percent,
  };
}

function mapDomainBreakdown(response: DomainBreakdownResponse): DomainBreakdownItem {
  return {
    domain: response.domain,
    intelligenceCount: response.intelligence_count,
    signalCount: response.signal_count,
    projectCount: response.project_count,
  };
}

function mapTopIntelligence(response: TopIntelligenceResponse): IntelligenceSummaryItem {
  return {
    id: response.id,
    title: response.title,
    summary: response.summary,
    domain: response.domain,
    type: response.type,
    evidenceCount: response.evidence_count,
    finalScore: response.final_score,
    status: response.status,
    createdAt: response.created_at,
    updatedAt: response.updated_at,
  };
}

function mapRecentFailure(response: RecentFailureResponse): RecentFailureItem {
  return {
    taskId: response.task_id,
    taskName: response.task_name,
    status: response.status,
    errorMessage: response.error_message,
    createdAt: response.created_at,
  };
}

function mapFreshness(response: DashboardFreshnessResponse): DashboardFreshness {
  return {
    generatedAt: response.generated_at,
    latestCollectionAt: response.latest_collection_at,
    staleEnabledTasks: response.stale_enabled_tasks,
    staleTasks: response.stale_tasks.map(mapStaleTask),
  };
}

function mapStaleTask(response: DashboardStaleTaskResponse): DashboardStaleTaskItem {
  return {
    taskId: response.task_id,
    taskName: response.task_name,
    collectorType: response.collector_type,
    status: response.status,
    lastRunAt: response.last_run_at,
    freshnessTargetHours: response.freshness_target_hours,
    staleHours: response.stale_hours,
  };
}
