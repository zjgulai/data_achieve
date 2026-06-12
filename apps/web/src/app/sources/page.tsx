import { AppShell } from "@/components/layout/app-shell";
import { SourcesWorkspace } from "@/components/sources/sources-workspace";

export default function SourcesPage() {
  return (
    <AppShell title="数据源" description="Source 管理、Collector 配置、测试采集">
      <SourcesWorkspace />
    </AppShell>
  );
}
