import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import {
  getMockEmailChannelStatus,
  getMockNotifications,
  testMockEmailChannel,
} from "@/lib/api/mock";
import type {
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
};

export async function listNotifications(isRead?: boolean): Promise<NotificationItem[]> {
  if (mockApiEnabled) {
    return getMockNotifications().filter((item) => isRead === undefined || item.isRead === isRead);
  }
  const query = new URLSearchParams();
  if (isRead !== undefined) {
    query.set("is_read", String(isRead));
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  const response = await apiFetch<NotificationResponse[]>(`/api/notifications${suffix}`);
  return response.map(mapNotification);
}

export async function markNotificationRead(notificationId: string): Promise<NotificationItem> {
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
  const response = await apiFetch<{ updated_count: number }>("/api/notifications/read-all", {
    method: "POST",
  });
  return response.updated_count;
}

export async function getEmailChannelStatus(): Promise<EmailChannelStatus> {
  if (mockApiEnabled) {
    return getMockEmailChannelStatus();
  }
  const response = await apiFetch<EmailChannelStatusResponse>("/api/notifications/email-channel");
  return mapEmailChannelStatus(response);
}

export async function testEmailChannel(): Promise<EmailChannelTestResult> {
  if (mockApiEnabled) {
    return testMockEmailChannel();
  }
  const response = await apiFetch<EmailChannelTestResponse>(
    "/api/notifications/email-channel/test",
    { method: "POST" },
  );
  return mapEmailChannelTestResult(response);
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

function mapEmailChannelStatus(response: EmailChannelStatusResponse): EmailChannelStatus {
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

function mapEmailChannelTestResult(response: EmailChannelTestResponse): EmailChannelTestResult {
  return {
    delivered: response.delivered,
    recipientEmail: response.recipient_email,
    status: mapEmailChannelStatus(response.status),
    reason: response.reason,
    testedAt: response.tested_at,
  };
}
