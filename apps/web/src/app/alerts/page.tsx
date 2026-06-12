import { AlertsWorkspace } from "@/components/alerts/alerts-workspace";
import { AppShell } from "@/components/layout/app-shell";

export default function AlertsPage() {
  return (
    <AppShell title="预警中心" description="规则命中、事件交付、通知通道">
      <AlertsWorkspace />
    </AppShell>
  );
}
