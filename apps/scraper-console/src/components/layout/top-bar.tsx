import { ExternalLink } from "lucide-react";

import { MobileNavigation } from "@/components/layout/mobile-navigation";
import { INSIGHT_URL } from "@/lib/app-links";

type TopBarProps = {
  title: string;
  description?: string;
};

export function TopBar({ title, description }: TopBarProps) {
  // A "命令搜索 ⌘K" button used to sit here with no click handler. It was
  // removed rather than left as a dead affordance; a real command palette is a
  // separate piece of work.
  return (
    <header className="border-b border-[var(--border-subtle)] bg-[var(--surface-primary)] px-4 py-4 sm:px-6 lg:px-8">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <MobileNavigation />
          <div className="min-w-0">
            <h1 className="text-xl font-bold text-[var(--text-primary)]">
              {title}
            </h1>
            {description && (
              <p className="mt-1 text-sm text-[var(--text-tertiary)]">
                {description}
              </p>
            )}
          </div>
        </div>
        {/* 跨应用入口。跨应用切换不走客户端路由，所以用裸 <a>。 */}
        <a
          className="inline-flex shrink-0 items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors duration-[var(--duration-base)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
          href={INSIGHT_URL}
        >
          洞察工作台
          <ExternalLink aria-hidden="true" size={14} />
        </a>
      </div>
    </header>
  );
}
