import { Suspense } from "react";

import { GlobalSearch } from "@/components/layout/global-search";
import { MobileNavigation } from "@/components/layout/mobile-navigation";
import { ProjectSelector } from "@/components/layout/project-selector";

type TopBarProps = {
  title: string;
  description: string;
};

export function TopBar({ title, description }: TopBarProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-[var(--border-subtle)] bg-[var(--surface-primary)]/95 backdrop-blur-sm">
      <div className="mx-auto flex w-full max-w-[var(--content-max)] flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
        <div className="flex min-w-0 items-start gap-3">
          <Suspense fallback={null}>
            <MobileNavigation />
          </Suspense>
          <div className="min-w-0">
            <h1 className="break-words text-xl font-semibold tracking-tight text-[var(--text-primary)]">
              {title}
            </h1>
            <p className="mt-1 break-words text-sm text-[var(--text-tertiary)]">
              {description}
            </p>
          </div>
        </div>
        <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-center">
          <ProjectSelector />
          <GlobalSearch />
        </div>
      </div>
    </header>
  );
}
