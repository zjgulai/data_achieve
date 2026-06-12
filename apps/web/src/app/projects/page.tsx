import { ProjectWorkspace } from "@/components/projects/project-workspace";
import { AppShell } from "@/components/layout/app-shell";

export default function ProjectsPage() {
  return (
    <AppShell title="项目" description="项目组合、状态筛选、创建弹窗">
      <ProjectWorkspace />
    </AppShell>
  );
}
