import { AppShell } from "@/components/layout/app-shell";
import { SavedWorkflowPlansWorkspace } from "@/components/workflow-planner/saved-workflow-plans-workspace";

export default function SavedWorkflowPlansPage() {
  return (
    <AppShell
      brief="按当前 Project 读取已保存的 WorkflowPlan 与当前 Version 摘要。"
      description="审阅 Project 范围内的计划、版本与更新时间"
      signals={["Project scoped", "read-only", "database_write=false"]}
      title="已保存计划"
    >
      <SavedWorkflowPlansWorkspace />
    </AppShell>
  );
}
