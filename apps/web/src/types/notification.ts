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
