import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import {
  mapEvidence,
  mapIntelligence,
  type EvidenceResponse,
  type IntelligenceResponse,
} from "@/lib/api/intelligence";
import {
  createMockGeneratedReport,
  createMockReportAuditEvent,
  getMockReportSubscriptions,
  getMockReportSubscriptionRuns,
  getMockReportAuditEvents,
  getMockReportEvidenceReferences,
  getMockReports,
  retryMockReportSubscriptionRun,
  runMockReportSubscription,
  upsertMockReportSubscription,
} from "@/lib/api/mock";
import type {
  Report,
  ReportAuditEvent,
  ReportEvidenceReference,
  ReportGenerateInput,
  ReportSendInput,
  ReportSubscription,
  ReportSubscriptionInput,
  ReportSubscriptionRetryInput,
  ReportSubscriptionRun,
  ReportSubscriptionRunInput,
} from "@/types/report";

type ReportResponse = {
  id: string;
  workspace_id: string;
  project_id: string | null;
  report_type: string;
  title: string;
  content: string;
  status: string;
  period_start: string;
  period_end: string;
  created_at: string;
  delivered_channels?: Array<"in_app" | "email">;
  skipped_channels?: Record<string, string>;
  idempotency_replayed?: boolean;
  idempotency_scope?: string | null;
  idempotency_key_hash?: string | null;
};

type ReportEvidenceReferenceResponse = {
  intelligence: IntelligenceResponse;
  evidences: EvidenceResponse[];
};

type ReportAuditEventResponse = {
  id: string;
  workspace_id: string;
  report_id: string;
  actor_id: string | null;
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  metadata: Record<string, string>;
  created_at: string;
};

type ReportSubscriptionResponse = {
  id: string;
  workspace_id: string;
  user_id: string;
  project_id: string | null;
  report_type: string;
  schedule_time: string;
  timezone: string;
  channels: Array<"in_app" | "email">;
  enabled: boolean;
  next_run_at: string | null;
  last_sent_at: string | null;
  latest_run: ReportSubscriptionRunResponse | null;
  created_at: string;
  updated_at: string;
};

type ReportSubscriptionRunResponse = {
  id: string;
  workspace_id: string;
  subscription_id: string;
  report_id: string | null;
  trigger_type: string;
  status: string;
  delivered_channels: Array<"in_app" | "email">;
  skipped_channels: Record<string, string>;
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
  idempotency_replayed?: boolean;
  idempotency_scope?: string | null;
  idempotency_key_hash?: string | null;
};

export async function listReports(projectId?: string): Promise<Report[]> {
  if (mockApiEnabled) {
    return getMockReports().filter((report) => !projectId || report.projectId === projectId);
  }
  const query = new URLSearchParams();
  if (projectId) {
    query.set("project_id", projectId);
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  const response = await apiFetch<ReportResponse[]>(`/api/reports${suffix}`);
  return response.map(mapReport);
}

export async function getReport(reportId: string): Promise<Report> {
  if (mockApiEnabled) {
    const report = getMockReports().find((item) => item.id === reportId);
    if (!report) {
      throw new Error("Report not found");
    }
    return report;
  }
  const response = await apiFetch<ReportResponse>(`/api/reports/${reportId}`);
  return mapReport(response);
}

export async function generateReport(input: ReportGenerateInput = {}): Promise<Report> {
  if (mockApiEnabled) {
    return createMockGeneratedReport(input);
  }
  const response = await apiFetch<ReportResponse>("/api/reports/generate", {
    method: "POST",
    body: JSON.stringify({
      period_end: input.periodEnd ?? null,
      period_start: input.periodStart ?? null,
      project_id: input.projectId ?? null,
      report_type: input.reportType ?? "daily",
    }),
  });
  return mapReport(response);
}

export async function sendReport(
  reportId: string,
  input: ReportSendInput = {
    authorized: true,
    confirmSend: true,
    channels: ["in_app"],
  },
): Promise<Report> {
  const idempotencyKey = input.idempotencyKey ?? `report-send-${reportId}`;
  if (mockApiEnabled) {
    const report = getMockReports().find((item) => item.id === reportId) ?? getMockReports()[0];
    createMockReportAuditEvent(reportId, "sent", { channel: "in_app" });
    return {
      ...report,
      status: "sent",
      deliveredChannels: input.channels ?? ["in_app"],
      skippedChannels: {},
      idempotencyReplayed: false,
      idempotencyScope: "report_send",
      idempotencyKeyHash: "mock-report-send-key-hash",
    };
  }
  const headers: Record<string, string> = {};
  headers["Idempotency-Key"] = idempotencyKey;
  const response = await apiFetch<ReportResponse>(`/api/reports/${reportId}/send`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      authorized: input.authorized,
      channels: input.channels ?? ["in_app"],
      confirm_send: input.confirmSend,
    }),
  });
  return mapReport(response);
}

export async function listReportEvidenceReferences(
  reportId: string,
): Promise<ReportEvidenceReference[]> {
  if (mockApiEnabled) {
    return getMockReportEvidenceReferences(reportId);
  }
  const response = await apiFetch<ReportEvidenceReferenceResponse[]>(
    `/api/reports/${reportId}/evidence-references`,
  );
  return response.map((item) => ({
    intelligence: mapIntelligence(item.intelligence),
    evidences: item.evidences.map(mapEvidence),
  }));
}

export async function listReportAuditEvents(reportId: string): Promise<ReportAuditEvent[]> {
  if (mockApiEnabled) {
    return getMockReportAuditEvents(reportId);
  }
  const response = await apiFetch<ReportAuditEventResponse[]>(
    `/api/reports/${reportId}/audit-events`,
  );
  return response.map(mapReportAuditEvent);
}

export async function createReportAuditEvent(
  reportId: string,
  eventType: "share_link_copied" | "share_sheet_opened",
  metadata: Record<string, string> = {},
): Promise<ReportAuditEvent> {
  if (mockApiEnabled) {
    return createMockReportAuditEvent(reportId, eventType, metadata);
  }
  const response = await apiFetch<ReportAuditEventResponse>(
    `/api/reports/${reportId}/audit-events`,
    {
      method: "POST",
      body: JSON.stringify({ event_type: eventType, metadata }),
    },
  );
  return mapReportAuditEvent(response);
}

export async function listReportSubscriptions(): Promise<ReportSubscription[]> {
  if (mockApiEnabled) {
    return getMockReportSubscriptions();
  }
  const response = await apiFetch<ReportSubscriptionResponse[]>("/api/reports/subscriptions");
  return response.map(mapReportSubscription);
}

export async function upsertReportSubscription(
  input: ReportSubscriptionInput,
): Promise<ReportSubscription> {
  if (mockApiEnabled) {
    return upsertMockReportSubscription(input);
  }
  const response = await apiFetch<ReportSubscriptionResponse>("/api/reports/subscriptions", {
    method: "PUT",
    body: JSON.stringify({
      channels: input.channels,
      enabled: input.enabled,
      project_id: input.projectId ?? null,
      report_type: input.reportType ?? "daily",
      schedule_time: input.scheduleTime,
      timezone: input.timezone,
    }),
  });
  return mapReportSubscription(response);
}

export async function runReportSubscription(
  subscriptionId: string,
  input: ReportSubscriptionRunInput = {},
): Promise<ReportSubscription> {
  if (mockApiEnabled) {
    return runMockReportSubscription(subscriptionId);
  }
  const idempotencyKey =
    input.idempotencyKey ?? createClientIdempotencyKey("report-subscription-run", subscriptionId);
  const response = await apiFetch<ReportSubscriptionResponse>(
    `/api/reports/subscriptions/${subscriptionId}/run`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({
        authorized: input.authorized ?? true,
        confirm_run: input.confirmRun ?? true,
      }),
    },
  );
  return mapReportSubscription(response);
}

export async function listReportSubscriptionRuns(
  subscriptionId: string,
): Promise<ReportSubscriptionRun[]> {
  if (mockApiEnabled) {
    return getMockReportSubscriptionRuns(subscriptionId);
  }
  const response = await apiFetch<ReportSubscriptionRunResponse[]>(
    `/api/reports/subscriptions/${subscriptionId}/runs`,
  );
  return response.map(mapReportSubscriptionRun);
}

export async function retryReportSubscriptionRun(
  subscriptionId: string,
  runId: string,
  input: ReportSubscriptionRetryInput = {},
): Promise<ReportSubscription> {
  if (mockApiEnabled) {
    return retryMockReportSubscriptionRun(subscriptionId, runId);
  }
  const idempotencyKey =
    input.idempotencyKey ??
    createClientIdempotencyKey("report-subscription-retry", `${subscriptionId}:${runId}`);
  const response = await apiFetch<ReportSubscriptionResponse>(
    `/api/reports/subscriptions/${subscriptionId}/runs/${runId}/retry`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({
        authorized: input.authorized ?? true,
        confirm_retry: input.confirmRetry ?? true,
      }),
    },
  );
  return mapReportSubscription(response);
}

function mapReport(response: ReportResponse): Report {
  return {
    id: response.id,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    reportType: response.report_type,
    title: response.title,
    content: response.content,
    status: response.status,
    periodStart: response.period_start,
    periodEnd: response.period_end,
    createdAt: response.created_at,
    deliveredChannels: response.delivered_channels ?? [],
    skippedChannels: response.skipped_channels ?? {},
    idempotencyReplayed: response.idempotency_replayed ?? false,
    idempotencyScope: response.idempotency_scope ?? null,
    idempotencyKeyHash: response.idempotency_key_hash ?? null,
  };
}

function mapReportAuditEvent(response: ReportAuditEventResponse): ReportAuditEvent {
  return {
    id: response.id,
    workspaceId: response.workspace_id,
    reportId: response.report_id,
    actorId: response.actor_id,
    eventType: response.event_type,
    fromStatus: response.from_status,
    toStatus: response.to_status,
    metadata: response.metadata,
    createdAt: response.created_at,
  };
}

function mapReportSubscription(response: ReportSubscriptionResponse): ReportSubscription {
  return {
    id: response.id,
    workspaceId: response.workspace_id,
    userId: response.user_id,
    projectId: response.project_id,
    reportType: response.report_type,
    scheduleTime: response.schedule_time,
    timezone: response.timezone,
    channels: response.channels,
    enabled: response.enabled,
    nextRunAt: response.next_run_at,
    lastSentAt: response.last_sent_at,
    latestRun: response.latest_run ? mapReportSubscriptionRun(response.latest_run) : null,
    createdAt: response.created_at,
    updatedAt: response.updated_at,
  };
}

function mapReportSubscriptionRun(response: ReportSubscriptionRunResponse): ReportSubscriptionRun {
  return {
    id: response.id,
    workspaceId: response.workspace_id,
    subscriptionId: response.subscription_id,
    reportId: response.report_id,
    triggerType: response.trigger_type,
    status: response.status,
    deliveredChannels: response.delivered_channels,
    skippedChannels: response.skipped_channels,
    errorMessage: response.error_message,
    startedAt: response.started_at,
    finishedAt: response.finished_at,
    idempotencyReplayed: response.idempotency_replayed ?? false,
    idempotencyScope: response.idempotency_scope ?? null,
    idempotencyKeyHash: response.idempotency_key_hash ?? null,
  };
}

function createClientIdempotencyKey(scope: string, identifier: string): string {
  return [scope, identifier, Date.now(), Math.random().toString(36).slice(2)].join(":");
}
