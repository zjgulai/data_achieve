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

export type ReportAuditEvent = {
  id: string;
  workspaceId: string;
  reportId: string;
  actorId: string | null;
  eventType: "generated" | "sent" | "share_link_copied" | "share_sheet_opened" | string;
  fromStatus: string | null;
  toStatus: string | null;
  metadata: Record<string, string>;
  createdAt: string;
};

export type ReportDeliveryChannel = "in_app" | "email";

export type ReportSubscription = {
  id: string;
  workspaceId: string;
  userId: string;
  projectId: string | null;
  reportType: "daily" | string;
  scheduleTime: string;
  timezone: string;
  channels: ReportDeliveryChannel[];
  enabled: boolean;
  nextRunAt: string | null;
  lastSentAt: string | null;
  createdAt: string;
  updatedAt: string;
};

export type ReportSubscriptionInput = {
  channels: ReportDeliveryChannel[];
  enabled: boolean;
  projectId?: string;
  reportType?: "daily";
  scheduleTime: string;
  timezone: string;
};
