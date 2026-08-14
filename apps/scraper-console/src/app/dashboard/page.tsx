import { AppShell } from "@/components/layout/app-shell";

export default function DashboardPage() {
  return (
    <AppShell
      title="工作台"
      description="采集控制台总览"
      brief="查看采集任务状态、运行记录和平台健康"
    >
      <div className="grid gap-6">
        <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            运行中任务
          </h2>
          <p className="mt-2 text-sm text-[var(--text-tertiary)]">
            暂无运行中的任务
          </p>
        </section>

        <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            今日采集量
          </h2>
          <p className="mt-2 text-4xl font-bold text-[var(--action-primary)]">
            0
          </p>
        </section>
      </div>
    </AppShell>
  );
}
