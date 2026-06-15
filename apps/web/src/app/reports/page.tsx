import { AppShell } from "@/components/layout/app-shell";
import { ReportsWorkspace } from "@/components/reports/reports-workspace";

export default function ReportsPage() {
  return (
    <AppShell
      title="报告中心"
      description="日报生成、报告阅读、发送状态"
      brief="报告中心把情报、证据引用和派发状态整理成可培训、可分发、可审计的日报和周报。"
      signals={["报告正文", "证据引用", "分发审计"]}
    >
      <ReportsWorkspace />
    </AppShell>
  );
}
