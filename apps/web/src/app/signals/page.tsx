import { AppShell } from "@/components/layout/app-shell";
import { SignalsWorkspace } from "@/components/signals/signals-workspace";

export default function SignalsPage() {
  return (
    <AppShell
      title="信号中心"
      description="检测规则、严重度、快照绑定"
      brief="信号中心展示由快照变化、指标阈值和规则匹配触发的事件，用于筛选值得进入情报层的变化。"
      signals={["变化检测", "严重度", "快照绑定"]}
    >
      <SignalsWorkspace />
    </AppShell>
  );
}
