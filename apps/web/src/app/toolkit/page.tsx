import { AppShell } from "@/components/layout/app-shell";
import { ToolkitWorkspace } from "@/components/toolkit/toolkit-workspace";

export default function ToolkitPage() {
  return (
    <AppShell
      title="采集工具库"
      description="汇聚高质量数据采集工具、平台方法和安装 SOP"
      brief="采集工具库面向培训场景，集中展示 AI 采集工具、Agent 浏览器、爬虫框架、平台采集方法和合规边界，让学员能直接看到工具价值、安装步骤、适用场景和风险限制。"
      signals={["工具雷达", "安装 SOP", "平台方法", "风险边界"]}
    >
      <ToolkitWorkspace />
    </AppShell>
  );
}
