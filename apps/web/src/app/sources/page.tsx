import { AppShell } from "@/components/layout/app-shell";
import { SourcesWorkspace } from "@/components/sources/sources-workspace";

export default function SourcesPage() {
  return (
    <AppShell title="数据源" description="Collector 配置、接入测试、调度启用">
      <SourcesWorkspace />
    </AppShell>
  );
}
