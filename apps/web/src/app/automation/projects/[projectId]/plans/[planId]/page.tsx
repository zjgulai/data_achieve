import { AppShell } from "@/components/layout/app-shell";
import { WorkflowPlanDetailWorkspace } from "@/components/workflow-planner/workflow-plan-detail-workspace";

export default async function WorkflowPlanDetailPage({
  params,
}: {
  params: Promise<{ projectId: string; planId: string }>;
}) {
  const { projectId, planId } = await params;

  return (
    <AppShell
      brief="按 URL 中的 Project 与 Plan 边界读取当前 Preview、Version History 和结构化 Compare。"
      description="审阅已保存计划的当前事实与不可变版本历史"
      signals={["Project scoped", "read-only", "database_write=false"]}
      title="WorkflowPlan 详情"
    >
      <WorkflowPlanDetailWorkspace planId={planId} projectId={projectId} />
    </AppShell>
  );
}
