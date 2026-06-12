import { AppShell } from "@/components/layout/app-shell";
import { ReportsWorkspace } from "@/components/reports/reports-workspace";

export default function ReportsPage() {
  return (
    <AppShell title="报告中心" description="日报生成、报告阅读、发送状态">
      <ReportsWorkspace />
    </AppShell>
  );
}
