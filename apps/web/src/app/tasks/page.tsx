import { AppShell } from "@/components/layout/app-shell";
import { TasksWorkspace } from "@/components/tasks/tasks-workspace";

export default function TasksPage() {
  return (
    <AppShell title="采集运行控制台" description="监控采集任务运行状态，保障数据稳定入库">
      <TasksWorkspace />
    </AppShell>
  );
}
