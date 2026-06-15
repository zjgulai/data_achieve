import { ProjectWorkspace } from "@/components/projects/project-workspace";
import { AppShell } from "@/components/layout/app-shell";

export default function ProjectsPage() {
  return (
    <AppShell
      title="项目"
      description="项目组合、状态筛选、创建弹窗"
      brief="项目定义了要长期跟踪的采集主题和业务域，是数据源、任务、信号和情报的组织边界。"
      signals={["业务域", "采集主题", "情报归属"]}
    >
      <ProjectWorkspace />
    </AppShell>
  );
}
