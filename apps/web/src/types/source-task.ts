import type { ProjectDomain } from "@/types/project";

export type CollectorType = "github_repo" | "github_topic" | "generic_web" | "manual_json";

export type Collector = {
  id: string;
  type: CollectorType;
  name: string;
  description: string;
  configSchema: Record<string, unknown>;
  enabled: boolean;
};

export type Source = {
  id: string;
  projectId: string;
  name: string;
  type: CollectorType;
  url: string | null;
  config: Record<string, unknown>;
  scheduleCron: string | null;
  enabled: boolean;
};

export type SourceCreateInput = {
  projectId: string;
  name: string;
  type: CollectorType;
  url?: string;
  config: Record<string, unknown>;
  scheduleCron?: string;
};

export type SourceUpdateInput = {
  name?: string;
  url?: string | null;
  config?: Record<string, unknown>;
  scheduleCron?: string | null;
};

export type SourceTestResult = {
  status: "config_valid";
  collectorType: CollectorType;
  message: string;
};

export type CollectionTaskStatus = "draft" | "enabled" | "running" | "paused" | "disabled";

export type CollectionTask = {
  id: string;
  projectId: string;
  sourceId: string;
  collectorType: CollectorType;
  name: string;
  scheduleCron: string | null;
  status: CollectionTaskStatus;
  successCount: number;
  failureCount: number;
  lastRunAt: string | null;
  latestRunStatus?: string | null;
  latestRunErrorMessage?: string | null;
  latestRunRecordsCount?: number | null;
  latestRunEntitiesCount?: number | null;
  latestRunFinishedAt?: string | null;
};

export type TaskRun = {
  id: string;
  taskId: string;
  status: string;
  startedAt: string | null;
  finishedAt: string | null;
  recordsCount: number;
  entitiesCount: number;
  errorMessage: string | null;
  logs: Array<{ step: string; message: string; timestamp?: string }>;
};

export const sourceDomainDefaults: Record<CollectorType, ProjectDomain> = {
  github_repo: "osint",
  github_topic: "osint",
  generic_web: "competitor",
  manual_json: "mixed",
};
