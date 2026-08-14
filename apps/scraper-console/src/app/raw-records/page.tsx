import { AppShell } from "@/components/layout/app-shell";

export default function RawRecordsPage() {
  return (
    <AppShell
      title="原始数据"
      description="浏览所有原始采集记录"
    >
      <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-8 text-center">
        <p className="text-sm text-[var(--text-tertiary)]">原始数据浏览建设中...</p>
      </div>
    </AppShell>
  );
}
