import { ProjectWorkspace } from "@/components/projects/project-workspace";
import { AppShell } from "@/components/layout/app-shell";

export default function ProjectsPage() {
  return (
    <AppShell title="项目" description="按业务域组织监控主题、数据源和情报">
      <ProjectWorkspace />
    </AppShell>
  );
}
