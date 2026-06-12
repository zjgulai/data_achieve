import { IntelligenceWorkspace } from "@/components/intelligence/intelligence-workspace";
import { AppShell } from "@/components/layout/app-shell";

export default function IntelligencePage() {
  return (
    <AppShell title="情报中心" description="全局情报列表、筛选、状态管理">
      <IntelligenceWorkspace />
    </AppShell>
  );
}
