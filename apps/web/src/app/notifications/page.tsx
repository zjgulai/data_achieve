import { AppShell } from "@/components/layout/app-shell";
import { NotificationsWorkspace } from "@/components/notifications/notifications-workspace";

export default function NotificationsPage() {
  return (
    <AppShell title="站内通知" description="交付收件箱、已读状态、关联跳转">
      <NotificationsWorkspace />
    </AppShell>
  );
}
