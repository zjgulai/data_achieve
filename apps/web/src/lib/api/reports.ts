import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import { getMockReports } from "@/lib/api/mock";
import type { Report, ReportGenerateInput } from "@/types/report";

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

export async function generateReport(input: ReportGenerateInput = {}): Promise<Report> {
  if (mockApiEnabled) {
    return getMockReports()[0];
  }
  const response = await apiFetch<ReportResponse>("/api/reports/generate", {
    method: "POST",
    body: JSON.stringify({
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
