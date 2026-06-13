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
  getMockReportAuditEvents,
  getMockReportEvidenceReferences,
  getMockReports,
  upsertMockReportSubscription,
} from "@/lib/api/mock";
import type {
  Report,
  ReportAuditEvent,
  ReportEvidenceReference,
  ReportGenerateInput,
  ReportSubscription,
  ReportSubscriptionInput,
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
  created_at: string;
  updated_at: string;
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

export async function sendReport(reportId: string): Promise<Report> {
  if (mockApiEnabled) {
    const report = getMockReports().find((item) => item.id === reportId) ?? getMockReports()[0];
    createMockReportAuditEvent(reportId, "sent", { channel: "in_app" });
    return { ...report, status: "sent" };
  }
  const response = await apiFetch<ReportResponse>(`/api/reports/${reportId}/send`, {
    method: "POST",
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
    createdAt: response.created_at,
    updatedAt: response.updated_at,
  };
}
