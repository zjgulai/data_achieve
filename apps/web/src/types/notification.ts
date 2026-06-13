export type NotificationItem = {
  id: string;
  userId: string;
  title: string;
  body: string;
  notificationType: "report_ready" | "alert" | "task_failed" | string;
  referenceType: "report" | "alert_event" | "task_run" | string;
  referenceId: string;
  isRead: boolean;
  createdAt: string;
};

export type EmailChannelStatus = {
  status: "misconfigured" | "not_configured" | "ready" | string;
  configured: boolean;
  missingSettings: string[];
  hostConfigured: boolean;
  port: number;
  senderConfigured: boolean;
  authConfigured: boolean;
  tlsMode: "ssl" | "starttls" | string;
  reason: string | null;
};

export type EmailChannelTestResult = {
  delivered: boolean;
  recipientEmail: string;
  status: EmailChannelStatus;
  reason: string | null;
  testedAt: string;
};
