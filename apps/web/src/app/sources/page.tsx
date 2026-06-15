import { AppShell } from "@/components/layout/app-shell";
import { SourcesWorkspace } from "@/components/sources/sources-workspace";

export default function SourcesPage() {
  return (
    <AppShell
      title="数据源"
      description="Collector 配置、接入测试、调度启用"
      brief="数据源记录不同平台和采集方法的接入配置，覆盖 GitHub、网页、手工 JSON 和平台型训练样本。"
      signals={["平台入口", "Collector 配置", "采集授权"]}
    >
      <SourcesWorkspace />
    </AppShell>
  );
}
