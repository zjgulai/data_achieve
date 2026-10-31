import Link from "next/link";

import { AppShell } from "@/components/layout/app-shell";

const PRIMARY_LINK_CLASS =
  "inline-flex items-center rounded-[var(--radius-2)] bg-[var(--action-primary)] px-4 py-2 text-sm font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)]";

const SECONDARY_LINK_CLASS =
  "inline-flex items-center rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]";

export default function NotFound() {
  return (
    <AppShell
      title="页面不存在"
      description="链接可能已失效，或页面已被移除。"
    >
      <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6">
        <div className="flex flex-wrap items-center gap-3">
          <Link href="/dashboard" className={PRIMARY_LINK_CLASS}>
            回工作台
          </Link>
          <Link href="/" className={SECONDARY_LINK_CLASS}>
            回首页
          </Link>
        </div>
      </section>
    </AppShell>
  );
}
