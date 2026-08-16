import { AppShell } from "@/components/layout/app-shell";
import { WorkflowRunHistoryWorkspace } from "@/components/workflow-execution/workflow-run-history-workspace";

export default function WorkflowRunHistoryPage() {
  return (
    <AppShell
      brief="按当前 Project 读取 fixture WorkflowRun 历史、不可变 Version lineage 与 StepRun 证据。"
      description="只读审阅运行收据与冻结步骤"
      signals={["Project scoped", "fixture-only", "database_write=false"]}
      title="运行记录"
    >
      <WorkflowRunHistoryWorkspace />
    </AppShell>
  );
}

