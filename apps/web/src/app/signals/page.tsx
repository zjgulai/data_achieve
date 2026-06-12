import { AppShell } from "@/components/layout/app-shell";
import { SignalsWorkspace } from "@/components/signals/signals-workspace";

export default function SignalsPage() {
  return (
    <AppShell title="信号中心" description="检测规则、严重度、快照绑定">
      <SignalsWorkspace />
    </AppShell>
  );
}
