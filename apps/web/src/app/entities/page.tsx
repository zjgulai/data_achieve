import { EntitiesWorkspace } from "@/components/entities/entities-workspace";
import { AppShell } from "@/components/layout/app-shell";

export default function EntitiesPage() {
  return (
    <AppShell title="实体库" description="标准化实体、快照历史、指标趋势">
      <EntitiesWorkspace />
    </AppShell>
  );
}
