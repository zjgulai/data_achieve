import { AppShell } from "@/components/layout/app-shell";
import { TasksWorkspace } from "@/components/tasks/tasks-workspace";

export default function TasksPage() {
  return (
    <AppShell
      title="采集运行控制台"
      description="监控采集任务运行状态，保障数据稳定入库"
      brief="采集任务展示每个数据源的调度状态、最近运行、失败原因和新鲜度，是判断数据能否持续入库的运行面。"
      signals={["调度状态", "运行历史", "失败诊断"]}
    >
      <TasksWorkspace />
    </AppShell>
  );
}
