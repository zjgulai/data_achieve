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
  providerCallAttempted: boolean;
  idempotencyReplayed: boolean;
  idempotencyScope: string | null;
  idempotencyKeyHash: string | null;
};

export type EmailChannelTestInput = {
  authorized?: boolean;
  confirmSend?: boolean;
  idempotencyKey?: string;
};

export type EmailProviderLiveGateOperation =
  | "email_channel_test"
  | "report_send"
  | "drift_alert_email";

export type EmailProviderLiveGateResult = {
  id: string;
  operation: string;
  status: "blocked" | "ready_pending_live_authorization" | string;
  recipientEmail: string;
  channelStatus: EmailChannelStatus;
  blockedReasons: string[];
  providerCallAllowed: boolean;
  emailSendAllowed: boolean;
  productionWriteAllowed: boolean;
  providerCallAttempted: boolean;
  maxProviderCalls: number;
  auditFields: string[];
  nextRequiredAuthorization: string;
  preparedAt: string;
  expiresAt: string | null;
  idempotencyReplayed: boolean;
  idempotencyScope: string | null;
  idempotencyKeyHash: string | null;
};

export type EmailProviderLiveGateInput = {
  authorized?: boolean;
  confirmPrepare?: boolean;
  operation?: EmailProviderLiveGateOperation;
  recipientEmail?: string;
  maxProviderCalls?: number;
  expiresAt?: string | null;
  note?: string;
  idempotencyKey?: string;
};

export type EmailProviderLiveSendResult = {
  id: string;
  gateRunId: string;
  approvalId: string;
  operation: string;
  status: "blocked" | "sent" | "delivery_failed" | string;
  delivered: boolean;
  recipientEmail: string;
  channelStatus: EmailChannelStatus;
  blockedReasons: string[];
  reason: string | null;
  sendEnabled: boolean;
  liveApprovalRequired: boolean;
  recipientAllowlisted: boolean;
  providerCallAllowed: boolean;
  emailSendAllowed: boolean;
  productionWriteAllowed: boolean;
  providerCallAttempted: boolean;
  auditFields: string[];
  nextRequiredAuthorization: string;
  sentAt: string;
  idempotencyReplayed: boolean;
  idempotencyScope: string | null;
  idempotencyKeyHash: string | null;
};

export type EmailProviderLiveSendInput = {
  authorized?: boolean;
  confirmSend?: boolean;
  gateRunId: string;
  approvalId: string;
  operation?: EmailProviderLiveGateOperation;
  recipientEmail?: string;
  idempotencyKey?: string;
};

export type EmailProviderLiveSendReadiness = {
  status: "blocked" | "ready_pending_l4_authorization" | string;
  channelStatus: EmailChannelStatus;
  blockedReasons: string[];
  sendEnabled: boolean;
  liveApprovalRequired: boolean;
  recipientAllowlistConfigured: boolean;
  recipientAllowlistCount: number;
  providerCallAllowed: boolean;
  emailSendAllowed: boolean;
  productionWriteAllowed: boolean;
  providerCallAttempted: boolean;
  requiredAuthorization: string;
  requiredRequestFields: string[];
  checkedAt: string;
};

export type NotificationDeliveryPreference = {
  inApp: boolean;
  email: boolean;
};

export type NotificationPreferenceState = {
  delivery: Record<string, NotificationDeliveryPreference>;
  quietHoursEnabled: boolean;
  digestTime: string;
  updatedAt: string | null;
};
