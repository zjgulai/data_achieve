import { IntelligenceWorkspace } from "@/components/intelligence/intelligence-workspace";
import { AppShell } from "@/components/layout/app-shell";

export default function IntelligencePage() {
  return (
    <AppShell
      title="情报中心"
      description="全局情报列表、筛选、状态管理"
      brief="情报中心把信号转化为可阅读的判断结论，并保留证据数量、业务域、状态和可追溯来源。"
      signals={["判断结论", "证据数量", "状态流转"]}
    >
      <IntelligenceWorkspace />
    </AppShell>
  );
}
