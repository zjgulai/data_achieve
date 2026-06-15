import { AppShell } from "@/components/layout/app-shell";
import { NotificationsWorkspace } from "@/components/notifications/notifications-workspace";

export default function NotificationsPage() {
  return (
    <AppShell
      title="站内通知"
      description="交付收件箱、已读状态、关联跳转"
      brief="站内通知收敛报告派发、预警触达和训练工作台状态，帮助确认系统消息是否送达。"
      signals={["消息收件箱", "已读状态", "关联对象"]}
    >
      <NotificationsWorkspace />
    </AppShell>
  );
}
