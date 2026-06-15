import { AlertsWorkspace } from "@/components/alerts/alerts-workspace";
import { AppShell } from "@/components/layout/app-shell";

export default function AlertsPage() {
  return (
    <AppShell
      title="预警中心"
      description="规则命中、事件交付、通知通道"
      brief="预警中心展示信号规则、触发事件和交付状态，用于追踪哪些变化需要被主动提醒。"
      signals={["规则条件", "触发事件", "交付状态"]}
    >
      <AlertsWorkspace />
    </AppShell>
  );
}
