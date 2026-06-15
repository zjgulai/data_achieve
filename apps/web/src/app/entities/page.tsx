import { EntitiesWorkspace } from "@/components/entities/entities-workspace";
import { AppShell } from "@/components/layout/app-shell";

export default function EntitiesPage() {
  return (
    <AppShell
      title="实体库"
      description="实体画像、快照演进、信号关联"
      brief="实体库把原始记录归并为可跟踪对象，展示对象快照、字段变化和关联信号。"
      signals={["监控对象", "快照演进", "信号关联"]}
    >
      <EntitiesWorkspace />
    </AppShell>
  );
}
