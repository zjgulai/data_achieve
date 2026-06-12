import { AppShell } from "@/components/layout/app-shell";
import { TasksWorkspace } from "@/components/tasks/tasks-workspace";

export default function TasksPage() {
  return (
    <AppShell title="采集任务" description="任务列表、运行记录、结构化日志">
      <TasksWorkspace />
    </AppShell>
  );
}
