import { AppShell } from "@/components/layout/app-shell";
import { NotificationsWorkspace } from "@/components/notifications/notifications-workspace";

export default function NotificationsPage() {
  return (
    <AppShell title="站内通知" description="报告、预警、任务异常通知">
      <NotificationsWorkspace />
    </AppShell>
  );
}
