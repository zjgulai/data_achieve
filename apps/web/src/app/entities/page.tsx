import { EntitiesWorkspace } from "@/components/entities/entities-workspace";
import { AppShell } from "@/components/layout/app-shell";

export default function EntitiesPage() {
  return (
    <AppShell title="实体库" description="实体画像、快照演进、信号关联">
      <EntitiesWorkspace />
    </AppShell>
  );
}
