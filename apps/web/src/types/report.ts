import type { Evidence, IntelligenceItem } from "@/types/intelligence";

export type Report = {
  id: string;
  workspaceId: string;
  projectId: string | null;
  reportType: "daily" | string;
  title: string;
  content: string;
  status: "draft" | "generated" | "sent" | string;
  periodStart: string;
  periodEnd: string;
  createdAt: string;
};

export type ReportGenerateInput = {
  periodEnd?: string;
  periodStart?: string;
  projectId?: string;
  reportType?: "daily";
};

export type ReportEvidenceReference = {
  intelligence: IntelligenceItem;
  evidences: Evidence[];
};
