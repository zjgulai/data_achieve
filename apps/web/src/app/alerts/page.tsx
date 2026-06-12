import { AlertsWorkspace } from "@/components/alerts/alerts-workspace";
import { AppShell } from "@/components/layout/app-shell";

export default function AlertsPage() {
  return (
    <AppShell title="预警中心" description="规则配置、预警事件、通知渠道">
      <AlertsWorkspace />
    </AppShell>
  );
}
