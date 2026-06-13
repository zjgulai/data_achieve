import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import {
  mapEvidence,
  mapIntelligence,
  type EvidenceResponse,
  type IntelligenceResponse,
} from "@/lib/api/intelligence";
import {
  createMockGeneratedReport,
  getMockReportEvidenceReferences,
  getMockReports,
} from "@/lib/api/mock";
import type { Report, ReportEvidenceReference, ReportGenerateInput } from "@/types/report";

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
