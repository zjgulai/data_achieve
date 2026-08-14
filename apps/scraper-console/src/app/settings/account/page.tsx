import { AppShell } from "@/components/layout/app-shell";

export default function AccountPage() {
  return (
    <AppShell
      title="账户设置"
      description="管理账户信息"
    >
      <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-8 text-center">
        <p className="text-sm text-[var(--text-tertiary)]">账户设置建设中...</p>
      </div>
    </AppShell>
  );
}
