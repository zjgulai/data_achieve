import { AppShell } from "@/components/layout/app-shell";
import { WorkflowPlannerWorkspace } from "@/components/workflow-planner/workflow-planner-workspace";
import { parseWorkflowPlannerRouteQuery } from "@/lib/workflow-planner";

type WorkflowPlannerPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function WorkflowPlannerPage({
  searchParams,
}: WorkflowPlannerPageProps) {
  const resolved = await searchParams;
  const route = parseWorkflowPlannerRouteQuery(resolved);
  return (
    <AppShell
      brief="Preview 可显式保存为 WorkflowPlan Version；保存不会激活、运行或调用 Provider。"
      description="从 MonitoringScope 生成、审阅并显式保存可解释的采集计划"
      signals={["双模式规划", "Candidate 不可执行", "production unchanged"]}
      title="Workflow Planner"
    >
      <WorkflowPlannerWorkspace
        initialMode={route.mode}
        initialPlanId={route.planId}
        initialProjectId={route.projectId}
        initialSourceVersionId={route.sourceVersionId}
        key={[
          route.mode,
          route.projectId ?? "new-project",
          route.planId ?? "new-plan",
          route.sourceVersionId ?? "current-version",
        ].join(":")}
        routeError={route.error}
      />
    </AppShell>
  );
}
