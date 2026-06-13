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
  eventType:
    | "generated"
    | "send_skipped"
    | "sent"
    | "share_link_copied"
    | "share_sheet_opened"
    | "subscription_executed"
    | string;
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
  latestRun: ReportSubscriptionRun | null;
  createdAt: string;
  updatedAt: string;
};

export type ReportSubscriptionRun = {
  id: string;
  workspaceId: string;
  subscriptionId: string;
  reportId: string | null;
  triggerType: "manual" | "scheduled" | string;
  status: "running" | "success" | "partial_success" | "failed" | string;
  deliveredChannels: ReportDeliveryChannel[];
  skippedChannels: Record<string, string>;
  errorMessage: string | null;
  startedAt: string;
  finishedAt: string | null;
};

export type ReportSubscriptionInput = {
  channels: ReportDeliveryChannel[];
  enabled: boolean;
  projectId?: string;
  reportType?: "daily";
  scheduleTime: string;
  timezone: string;
};
