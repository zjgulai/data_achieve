import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import { getMockNotifications } from "@/lib/api/mock";
import type { NotificationItem } from "@/types/notification";

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
