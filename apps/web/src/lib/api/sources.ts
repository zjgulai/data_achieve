import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import { getMockCollectors, getMockSources } from "@/lib/api/mock";
import type {
  Collector,
  CollectionTask,
  CollectorType,
  Source,
  SourceCreateInput,
  SourceTestResult,
  SourceUpdateInput,
} from "@/types/source-task";

type CollectorResponse = {
  id: string;
  type: CollectorType;
  name: string;
  description: string;
  config_schema: Record<string, unknown>;
  enabled: boolean;
};

type SourceResponse = {
  id: string;
  project_id: string;
  name: string;
  type: CollectorType;
  url: string | null;
  config: Record<string, unknown>;
  schedule_cron: string | null;
  enabled: boolean;
};

type SourceTestResponse = {
  status: "config_valid";
  collector_type: CollectorType;
  message: string;
};

type CollectionTaskResponse = {
  id: string;
  project_id: string;
  source_id: string;
  collector_type: CollectorType;
  name: string;
  schedule_cron: string | null;
  status: CollectionTask["status"];
  project_name?: string | null;
  project_domain?: string | null;
  source_name?: string | null;
  source_url?: string | null;
  schedule_policy?: CollectionTask["schedulePolicy"];
  freshness_target_hours?: number;
  freshness_status?: CollectionTask["freshnessStatus"];
  stale_hours?: number | null;
  next_run_at?: string | null;
  retry_after_at?: string | null;
  retry_delay_minutes?: number;
  success_count: number;
  failure_count: number;
  last_run_at: string | null;
  latest_run_status?: string | null;
  latest_run_error_message?: string | null;
  latest_run_records_count?: number | null;
  latest_run_entities_count?: number | null;
  latest_run_started_at?: string | null;
  latest_run_finished_at?: string | null;
  latest_run_created_at?: string | null;
};

export async function listCollectors(): Promise<Collector[]> {
  if (mockApiEnabled) {
    return getMockCollectors();
  }
  const response = await apiFetch<CollectorResponse[]>("/api/collectors");
  return response.map(mapCollector);
}

export async function listSources(): Promise<Source[]> {
  if (mockApiEnabled) {
    return getMockSources();
  }
  const response = await apiFetch<SourceResponse[]>("/api/sources");
  return response.map(mapSource);
}

export async function createSource(payload: SourceCreateInput): Promise<Source> {
  if (mockApiEnabled) {
    return {
      id: `source_${payload.type}_${Date.now()}`,
      projectId: payload.projectId,
      name: payload.name,
      type: payload.type,
      url: payload.url ?? null,
      config: payload.config,
      scheduleCron: payload.scheduleCron ?? null,
      enabled: false,
    };
  }
  const response = await apiFetch<SourceResponse>("/api/sources", {
    method: "POST",
    body: JSON.stringify({
      project_id: payload.projectId,
      name: payload.name,
      type: payload.type,
      url: payload.url,
      config: payload.config,
      schedule_cron: payload.scheduleCron,
    }),
  });
  return mapSource(response);
}

export async function updateSource(sourceId: string, payload: SourceUpdateInput): Promise<Source> {
  if (mockApiEnabled) {
    const source =
      getMockSources().find((item) => item.id === sourceId) ??
      ({
        id: sourceId,
        projectId: "project_demo",
        name: "Draft Source",
        type: "manual_json",
        url: null,
        config: {},
        scheduleCron: null,
        enabled: false,
      } satisfies Source);
    return {
      ...source,
      name: payload.name ?? source.name,
      url: payload.url === undefined ? source.url : payload.url,
      config: payload.config ?? source.config,
      scheduleCron: payload.scheduleCron === undefined ? source.scheduleCron : payload.scheduleCron,
    };
  }
  const response = await apiFetch<SourceResponse>(`/api/sources/${sourceId}`, {
    method: "PATCH",
    body: JSON.stringify({
      name: payload.name,
      url: payload.url,
      config: payload.config,
      schedule_cron: payload.scheduleCron,
    }),
  });
  return mapSource(response);
}

export async function testSource(sourceId: string): Promise<SourceTestResult> {
  if (mockApiEnabled) {
    return {
      status: "config_valid",
      collectorType: "github_repo",
      message: "Config is valid. Manual task run can collect raw records.",
    };
  }
  const response = await apiFetch<SourceTestResponse>(`/api/sources/${sourceId}/test`, {
    method: "POST",
  });
  return {
    status: response.status,
    collectorType: response.collector_type,
    message: response.message,
  };
}

export async function enableSource(sourceId: string): Promise<CollectionTask> {
  if (mockApiEnabled) {
    const task = getMockSources().find((source) => source.id === sourceId);
    const inferredType = inferCollectorTypeFromSourceId(sourceId);
    return {
      id: `task_${sourceId}`,
      projectId: task?.projectId ?? "project_demo",
      sourceId,
      collectorType: task?.type ?? inferredType,
      name: task?.name ?? "Demo Task",
      scheduleCron: task?.scheduleCron ?? null,
      status: "enabled",
      projectName: null,
      projectDomain: null,
      sourceName: task?.name ?? null,
      sourceUrl: null,
      schedulePolicy: "manual_refresh_only",
      freshnessTargetHours: 24,
      freshnessStatus: "never_run",
      staleHours: null,
      nextRunAt: task?.scheduleCron ? new Date().toISOString() : null,
      retryAfterAt: null,
      retryDelayMinutes: 15,
      successCount: 0,
      failureCount: 0,
      lastRunAt: null,
      latestRunStatus: null,
      latestRunErrorMessage: null,
      latestRunRecordsCount: null,
      latestRunEntitiesCount: null,
      latestRunStartedAt: null,
      latestRunFinishedAt: null,
      latestRunCreatedAt: null,
    };
  }
  const response = await apiFetch<CollectionTaskResponse>(`/api/sources/${sourceId}/enable`, {
    method: "POST",
  });
  return mapTask(response);
}

function inferCollectorTypeFromSourceId(sourceId: string): CollectorType {
  if (sourceId.includes("github_topic")) {
    return "github_topic";
  }
  if (sourceId.includes("ecommerce_product_discovery")) {
    return "ecommerce_product_discovery";
  }
  if (sourceId.includes("ecommerce_product_page")) {
    return "ecommerce_product_page";
  }
  if (sourceId.includes("generic_web")) {
    return "generic_web";
  }
  if (sourceId.includes("public_feed")) {
    return "public_feed";
  }
  if (sourceId.includes("manual_json")) {
    return "manual_json";
  }
  return "github_repo";
}

export async function disableSource(sourceId: string): Promise<Source> {
  if (mockApiEnabled) {
    const source =
      getMockSources().find((item) => item.id === sourceId) ??
      ({
        id: sourceId,
        projectId: "project_demo",
        name: "Draft Source",
        type: "manual_json",
        url: null,
        config: {},
        scheduleCron: null,
        enabled: true,
      } satisfies Source);
    return { ...source, enabled: false };
  }
  const response = await apiFetch<SourceResponse>(`/api/sources/${sourceId}/disable`, {
    method: "POST",
  });
  return mapSource(response);
}

function mapCollector(response: CollectorResponse): Collector {
  return {
    id: response.id,
    type: response.type,
    name: response.name,
    description: response.description,
    configSchema: response.config_schema,
    enabled: response.enabled,
  };
}

function mapSource(response: SourceResponse): Source {
  return {
    id: response.id,
    projectId: response.project_id,
    name: response.name,
    type: response.type,
    url: response.url,
    config: response.config,
    scheduleCron: response.schedule_cron,
    enabled: response.enabled,
  };
}

function mapTask(response: CollectionTaskResponse): CollectionTask {
  return {
    id: response.id,
    projectId: response.project_id,
    sourceId: response.source_id,
    collectorType: response.collector_type,
    name: response.name,
    scheduleCron: response.schedule_cron,
    status: response.status,
    projectName: response.project_name ?? null,
    projectDomain: response.project_domain ?? null,
    sourceName: response.source_name ?? null,
    sourceUrl: response.source_url ?? null,
    schedulePolicy: response.schedule_policy ?? "manual_refresh_only",
    freshnessTargetHours: response.freshness_target_hours ?? 24,
    freshnessStatus: response.freshness_status ?? "unknown",
    staleHours: response.stale_hours ?? null,
    nextRunAt: response.next_run_at ?? null,
    retryAfterAt: response.retry_after_at ?? null,
    retryDelayMinutes: response.retry_delay_minutes ?? 15,
    successCount: response.success_count,
    failureCount: response.failure_count,
    lastRunAt: response.last_run_at,
    latestRunStatus: response.latest_run_status ?? null,
    latestRunErrorMessage: response.latest_run_error_message ?? null,
    latestRunRecordsCount: response.latest_run_records_count ?? null,
    latestRunEntitiesCount: response.latest_run_entities_count ?? null,
    latestRunStartedAt: response.latest_run_started_at ?? null,
    latestRunFinishedAt: response.latest_run_finished_at ?? null,
    latestRunCreatedAt: response.latest_run_created_at ?? null,
  };
}
