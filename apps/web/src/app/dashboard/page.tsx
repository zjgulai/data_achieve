import { AppShell } from "@/components/layout/app-shell";
import { DashboardOverview } from "@/components/dashboard/dashboard-overview";

export default function DashboardPage() {
  return (
    <AppShell
      title="全局仪表盘"
      description="跨域情报、任务健康度、数据质量"
    >
      <DashboardOverview />
    </AppShell>
  );
}
