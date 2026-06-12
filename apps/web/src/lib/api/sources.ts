import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import { getMockCollectors, getMockSources } from "@/lib/api/mock";
import type {
  Collector,
  CollectorType,
  Source,
  SourceCreateInput,
  SourceTestResult,
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
      id: `source_${Date.now()}`,
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

export async function enableSource(sourceId: string): Promise<void> {
  if (mockApiEnabled) {
    return;
  }
  await apiFetch(`/api/sources/${sourceId}/enable`, { method: "POST" });
}

export async function disableSource(sourceId: string): Promise<Source> {
  if (mockApiEnabled) {
    const source = getMockSources().find((item) => item.id === sourceId);
    return { ...(source ?? getMockSources()[0]), enabled: false };
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
