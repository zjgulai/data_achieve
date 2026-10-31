import { InsightNewWorkspace } from "@/components/insight/insight-new-workspace";
import { AppShell } from "@/components/layout/app-shell";

export default function InsightNewPage() {
  return (
    <AppShell
      brief="查看已生成的分析报告，确认数据范围与结论。当前版本不执行新分析。"
      description="选题分析与归档报告"
      signals={["分析类型", "归档报告", "数据范围"]}
      title="新建洞察"
    >
      <InsightNewWorkspace />
    </AppShell>
  );
}
