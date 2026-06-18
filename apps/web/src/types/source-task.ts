import type { ProjectDomain } from "@/types/project";

export type CollectorType =
  | "ecommerce_product_discovery"
  | "ecommerce_product_page"
  | "generic_web"
  | "github_repo"
  | "github_topic"
  | "manual_json";

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

export type CollectionTaskFreshnessStatus =
  | "disabled"
  | "failed"
  | "fresh"
  | "never_run"
  | "paused"
  | "running"
  | "stale"
  | "unknown";

export type CollectionTask = {
  id: string;
  projectId: string;
  sourceId: string;
  collectorType: CollectorType;
  name: string;
  scheduleCron: string | null;
  status: CollectionTaskStatus;
  projectName?: string | null;
  projectDomain?: string | null;
  sourceName?: string | null;
  sourceUrl?: string | null;
  schedulePolicy: "auto_freshness" | "manual_refresh_only" | string;
  freshnessTargetHours: number;
  freshnessStatus: CollectionTaskFreshnessStatus;
  staleHours: number | null;
  nextRunAt: string | null;
  retryAfterAt: string | null;
  retryDelayMinutes: number;
  successCount: number;
  failureCount: number;
  lastRunAt: string | null;
  latestRunStatus?: string | null;
  latestRunErrorMessage?: string | null;
  latestRunRecordsCount?: number | null;
  latestRunEntitiesCount?: number | null;
  latestRunStartedAt?: string | null;
  latestRunFinishedAt?: string | null;
  latestRunCreatedAt?: string | null;
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
  createdAt: string;
};

export type SchedulerTick = {
  id: string;
  leaseName: string;
  ownerId: string;
  status: string;
  lockAcquired: boolean;
  startedAt: string;
  finishedAt: string;
  scanned: number;
  due: number;
  started: number;
  skippedRunning: number;
  skippedInvalidSchedule: number;
  taskErrors: number;
  reportSubscriptionsScanned: number;
  reportSubscriptionsDue: number;
  reportSubscriptionsStarted: number;
  reportSubscriptionsSkippedRunning: number;
  reportSubscriptionErrors: number;
  errorMessage: string | null;
};

export type SchedulerOverview = {
  enabled: boolean;
  latestTick: SchedulerTick | null;
};

export const sourceDomainDefaults: Record<CollectorType, ProjectDomain> = {
  ecommerce_product_discovery: "ecommerce",
  ecommerce_product_page: "ecommerce",
  github_repo: "osint",
  github_topic: "osint",
  generic_web: "competitor",
  manual_json: "mixed",
};
