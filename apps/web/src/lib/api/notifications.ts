import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import {
  getMockEmailProviderLiveSendReadiness,
  getMockEmailChannelStatus,
  getMockNotifications,
  executeMockEmailProviderLiveSendGate,
  prepareMockEmailProviderLiveGate,
  testMockEmailChannel,
} from "@/lib/api/mock";
import type {
  EmailProviderLiveGateInput,
  EmailProviderLiveGateResult,
  EmailProviderLiveSendInput,
  EmailProviderLiveSendReadiness,
  EmailProviderLiveSendResult,
  EmailChannelTestInput,
  EmailChannelStatus,
  EmailChannelTestResult,
  NotificationItem,
} from "@/types/notification";

type NotificationResponse = {
  id: string;
  user_id: string;
  title: string;
  body: string;
  notification_type: string;
  reference_type: string;
  reference_id: string;
  is_read: boolean;
  created_at: string;
};

type EmailChannelStatusResponse = {
  status: string;
  configured: boolean;
  missing_settings: string[];
  host_configured: boolean;
  port: number;
  sender_configured: boolean;
  auth_configured: boolean;
  tls_mode: string;
  reason: string | null;
};

type EmailChannelTestResponse = {
  delivered: boolean;
  recipient_email: string;
  status: EmailChannelStatusResponse;
  reason: string | null;
  tested_at: string;
  provider_call_attempted?: boolean;
  idempotency_replayed?: boolean;
  idempotency_scope?: string | null;
  idempotency_key_hash?: string | null;
};

type EmailProviderLiveGateResponse = {
  id: string;
  operation: string;
  status: string;
  recipient_email: string;
  channel_status: EmailChannelStatusResponse;
  blocked_reasons: string[];
  provider_call_allowed: boolean;
  email_send_allowed: boolean;
  production_write_allowed: boolean;
  provider_call_attempted: boolean;
  max_provider_calls: number;
  audit_fields: string[];
  next_required_authorization: string;
  prepared_at: string;
  expires_at: string | null;
  idempotency_replayed?: boolean;
  idempotency_scope?: string | null;
  idempotency_key_hash?: string | null;
};

type EmailProviderLiveSendResponse = {
  id: string;
  gate_run_id: string;
  approval_id: string;
  operation: string;
  status: string;
  delivered: boolean;
  recipient_email: string;
  channel_status: EmailChannelStatusResponse;
  blocked_reasons: string[];
  reason: string | null;
  send_enabled: boolean;
  live_approval_required: boolean;
  recipient_allowlisted: boolean;
  provider_call_allowed: boolean;
  email_send_allowed: boolean;
  production_write_allowed: boolean;
  provider_call_attempted: boolean;
  audit_fields: string[];
  next_required_authorization: string;
  sent_at: string;
  idempotency_replayed?: boolean;
  idempotency_scope?: string | null;
  idempotency_key_hash?: string | null;
};

type EmailProviderLiveSendReadinessResponse = {
  status: string;
  channel_status: EmailChannelStatusResponse;
  blocked_reasons: string[];
  send_enabled: boolean;
  live_approval_required: boolean;
  recipient_allowlist_configured: boolean;
  recipient_allowlist_count: number;
  provider_call_allowed: boolean;
  email_send_allowed: boolean;
  production_write_allowed: boolean;
  provider_call_attempted: boolean;
  required_authorization: string;
  required_request_fields: string[];
  checked_at: string;
};

export async function listNotifications(
  isRead?: boolean,
): Promise<NotificationItem[]> {
  if (mockApiEnabled) {
    return getMockNotifications().filter(
      (item) => isRead === undefined || item.isRead === isRead,
    );
  }
  const query = new URLSearchParams();
  if (isRead !== undefined) {
    query.set("is_read", String(isRead));
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  const response = await apiFetch<NotificationResponse[]>(
    `/api/notifications${suffix}`,
  );
  return response.map(mapNotification);
}

export async function markNotificationRead(
  notificationId: string,
): Promise<NotificationItem> {
  if (mockApiEnabled) {
    const notification =
      getMockNotifications().find((item) => item.id === notificationId) ??
      getMockNotifications()[0];
    return { ...notification, isRead: true };
  }
  const response = await apiFetch<NotificationResponse>(
    `/api/notifications/${notificationId}/read`,
    { method: "PATCH" },
  );
  return mapNotification(response);
}

export async function markAllNotificationsRead(): Promise<number> {
  if (mockApiEnabled) {
    return getMockNotifications().filter((item) => !item.isRead).length;
  }
  const response = await apiFetch<{ updated_count: number }>(
    "/api/notifications/read-all",
    {
      method: "POST",
    },
  );
  return response.updated_count;
}

export async function markNotificationsRead(
  notificationIds: string[],
): Promise<number> {
  if (mockApiEnabled) {
    const idSet = new Set(notificationIds);
    return getMockNotifications().filter(
      (item) => idSet.has(item.id) && !item.isRead,
    ).length;
  }
  const response = await apiFetch<{ updated_count: number }>(
    "/api/notifications/read-bulk",
    {
      method: "POST",
      body: JSON.stringify({ notification_ids: notificationIds }),
    },
  );
  return response.updated_count;
}

export async function getEmailChannelStatus(): Promise<EmailChannelStatus> {
  if (mockApiEnabled) {
    return getMockEmailChannelStatus();
  }
  const response = await apiFetch<EmailChannelStatusResponse>(
    "/api/notifications/email-channel",
  );
  return mapEmailChannelStatus(response);
}

export async function testEmailChannel(
  input: EmailChannelTestInput = {},
): Promise<EmailChannelTestResult> {
  if (mockApiEnabled) {
    return testMockEmailChannel();
  }
  const idempotencyKey =
    input.idempotencyKey ??
    [
      "email-channel-test",
      Date.now(),
      Math.random().toString(36).slice(2),
    ].join(":");
  const response = await apiFetch<EmailChannelTestResponse>(
    "/api/notifications/email-channel/test",
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({
        authorized: input.authorized ?? true,
        confirm_send: input.confirmSend ?? true,
      }),
    },
  );
  return mapEmailChannelTestResult(response);
}

export async function prepareEmailProviderLiveGate(
  input: EmailProviderLiveGateInput = {},
): Promise<EmailProviderLiveGateResult> {
  if (mockApiEnabled) {
    return prepareMockEmailProviderLiveGate(input);
  }
  const idempotencyKey =
    input.idempotencyKey ??
    [
      "email-provider-live-gate",
      Date.now(),
      Math.random().toString(36).slice(2),
    ].join(":");
  const body: Record<string, unknown> = {
    authorized: input.authorized ?? true,
    confirm_prepare: input.confirmPrepare ?? true,
    operation: input.operation ?? "email_channel_test",
    max_provider_calls: input.maxProviderCalls ?? 1,
  };
  if (input.recipientEmail) {
    body.recipient_email = input.recipientEmail;
  }
  if (input.expiresAt !== undefined) {
    body.expires_at = input.expiresAt;
  }
  if (input.note) {
    body.note = input.note;
  }
  const response = await apiFetch<EmailProviderLiveGateResponse>(
    "/api/notifications/email-channel/provider-live-gate",
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(body),
    },
  );
  return mapEmailProviderLiveGateResult(response);
}

export async function getEmailProviderLiveSendReadiness(): Promise<EmailProviderLiveSendReadiness> {
  if (mockApiEnabled) {
    return getMockEmailProviderLiveSendReadiness();
  }
  const response = await apiFetch<EmailProviderLiveSendReadinessResponse>(
    "/api/notifications/email-channel/live-send-readiness",
  );
  return mapEmailProviderLiveSendReadiness(response);
}

export async function executeEmailProviderLiveSendGate(
  input: EmailProviderLiveSendInput,
): Promise<EmailProviderLiveSendResult> {
  if (mockApiEnabled) {
    return executeMockEmailProviderLiveSendGate(input);
  }
  const idempotencyKey =
    input.idempotencyKey ??
    [
      "email-provider-live-send",
      input.gateRunId,
      Date.now(),
      Math.random().toString(36).slice(2),
    ].join(":");
  const body: Record<string, unknown> = {
    authorized: input.authorized ?? true,
    confirm_send: input.confirmSend ?? true,
    gate_run_id: input.gateRunId,
    approval_id: input.approvalId,
    operation: input.operation ?? "email_channel_test",
  };
  if (input.recipientEmail) {
    body.recipient_email = input.recipientEmail;
  }
  const response = await apiFetch<EmailProviderLiveSendResponse>(
    "/api/notifications/email-channel/live-send",
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(body),
    },
  );
  return mapEmailProviderLiveSendResult(response);
}

function mapNotification(response: NotificationResponse): NotificationItem {
  return {
    id: response.id,
    userId: response.user_id,
    title: response.title,
    body: response.body,
    notificationType: response.notification_type,
    referenceType: response.reference_type,
    referenceId: response.reference_id,
    isRead: response.is_read,
    createdAt: response.created_at,
  };
}

function mapEmailChannelStatus(
  response: EmailChannelStatusResponse,
): EmailChannelStatus {
  return {
    status: response.status,
    configured: response.configured,
    missingSettings: response.missing_settings,
    hostConfigured: response.host_configured,
    port: response.port,
    senderConfigured: response.sender_configured,
    authConfigured: response.auth_configured,
    tlsMode: response.tls_mode,
    reason: response.reason,
  };
}

function mapEmailChannelTestResult(
  response: EmailChannelTestResponse,
): EmailChannelTestResult {
  return {
    delivered: response.delivered,
    recipientEmail: response.recipient_email,
    status: mapEmailChannelStatus(response.status),
    reason: response.reason,
    testedAt: response.tested_at,
    providerCallAttempted: response.provider_call_attempted ?? false,
    idempotencyReplayed: response.idempotency_replayed ?? false,
    idempotencyScope: response.idempotency_scope ?? null,
    idempotencyKeyHash: response.idempotency_key_hash ?? null,
  };
}

function mapEmailProviderLiveGateResult(
  response: EmailProviderLiveGateResponse,
): EmailProviderLiveGateResult {
  return {
    id: response.id,
    operation: response.operation,
    status: response.status,
    recipientEmail: response.recipient_email,
    channelStatus: mapEmailChannelStatus(response.channel_status),
    blockedReasons: response.blocked_reasons,
    providerCallAllowed: response.provider_call_allowed,
    emailSendAllowed: response.email_send_allowed,
    productionWriteAllowed: response.production_write_allowed,
    providerCallAttempted: response.provider_call_attempted,
    maxProviderCalls: response.max_provider_calls,
    auditFields: response.audit_fields,
    nextRequiredAuthorization: response.next_required_authorization,
    preparedAt: response.prepared_at,
    expiresAt: response.expires_at,
    idempotencyReplayed: response.idempotency_replayed ?? false,
    idempotencyScope: response.idempotency_scope ?? null,
    idempotencyKeyHash: response.idempotency_key_hash ?? null,
  };
}

function mapEmailProviderLiveSendReadiness(
  response: EmailProviderLiveSendReadinessResponse,
): EmailProviderLiveSendReadiness {
  return {
    status: response.status,
    channelStatus: mapEmailChannelStatus(response.channel_status),
    blockedReasons: response.blocked_reasons,
    sendEnabled: response.send_enabled,
    liveApprovalRequired: response.live_approval_required,
    recipientAllowlistConfigured: response.recipient_allowlist_configured,
    recipientAllowlistCount: response.recipient_allowlist_count,
    providerCallAllowed: response.provider_call_allowed,
    emailSendAllowed: response.email_send_allowed,
    productionWriteAllowed: response.production_write_allowed,
    providerCallAttempted: response.provider_call_attempted,
    requiredAuthorization: response.required_authorization,
    requiredRequestFields: response.required_request_fields,
    checkedAt: response.checked_at,
  };
}

function mapEmailProviderLiveSendResult(
  response: EmailProviderLiveSendResponse,
): EmailProviderLiveSendResult {
  return {
    id: response.id,
    gateRunId: response.gate_run_id,
    approvalId: response.approval_id,
    operation: response.operation,
    status: response.status,
    delivered: response.delivered,
    recipientEmail: response.recipient_email,
    channelStatus: mapEmailChannelStatus(response.channel_status),
    blockedReasons: response.blocked_reasons,
    reason: response.reason,
    sendEnabled: response.send_enabled,
    liveApprovalRequired: response.live_approval_required,
    recipientAllowlisted: response.recipient_allowlisted,
    providerCallAllowed: response.provider_call_allowed,
    emailSendAllowed: response.email_send_allowed,
    productionWriteAllowed: response.production_write_allowed,
    providerCallAttempted: response.provider_call_attempted,
    auditFields: response.audit_fields,
    nextRequiredAuthorization: response.next_required_authorization,
    sentAt: response.sent_at,
    idempotencyReplayed: response.idempotency_replayed ?? false,
    idempotencyScope: response.idempotency_scope ?? null,
    idempotencyKeyHash: response.idempotency_key_hash ?? null,
  };
}
