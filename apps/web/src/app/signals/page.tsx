import { AppShell } from "@/components/layout/app-shell";
import { SignalsWorkspace } from "@/components/signals/signals-workspace";

export default function SignalsPage() {
  return (
    <AppShell title="信号中心" description="确定性变化信号、严重度、快照证据">
      <SignalsWorkspace />
    </AppShell>
  );
}
