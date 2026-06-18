import { AutomationWorkbench } from "@/components/automation/automation-workbench";
import { AppShell } from "@/components/layout/app-shell";

export default function AutomationPage() {
  return (
    <AppShell
      title="自动采集工作台"
      description="从目标 URL 解析网页结构、字段候选、工具选择和清洗计划"
      brief="自动采集工作台把工具情报转化为采集执行路径：先识别网站结构，再选择字段和工具，最后形成可保存、可调度、可追溯的数据源草稿。"
      signals={["结构解析", "字段筛选", "清洗计划", "工具路由"]}
    >
      <AutomationWorkbench />
    </AppShell>
  );
}
