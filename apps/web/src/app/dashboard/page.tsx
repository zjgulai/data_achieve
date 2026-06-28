import { AppShell } from "@/components/layout/app-shell";
import { DashboardOverview } from "@/components/dashboard/dashboard-overview";

export default function DashboardPage() {
  return (
    <AppShell
      title="全局仪表盘"
      description="跨域情报、任务健康度、数据质量"
      brief="这里汇总当前数据采集工作台的采集覆盖、任务运行、信号触发和情报产出，用于判断整套数据链路是否稳定闭环。"
      signals={["采集健康", "情报产出", "数据新鲜度"]}
    >
      <DashboardOverview />
    </AppShell>
  );
}
